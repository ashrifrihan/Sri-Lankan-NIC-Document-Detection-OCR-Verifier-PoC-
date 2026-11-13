import os
import re
import sys
import cv2
import tempfile
import subprocess
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from ..utils.privacy import get_sanitized_logger
from .card_geometry import straighten_card
from .nic_parser import parse_sri_lankan_nic

logger = get_sanitized_logger("ocr_engine")

# Unicode block ranges
SINHALA_RANGE = re.compile(r"[\u0D80-\u0DFF]")
TAMIL_RANGE = re.compile(r"[\u0B80-\u0BFF]")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WIN_OCR_PS1 = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "run_win_ocr.ps1"))

class OCREngine:
    def __init__(self, lang: str = "en"):
        self.lang = lang
        self.is_win_ocr_available = sys.platform == "win32" and os.path.exists(WIN_OCR_PS1)

    def detect_scripts(self, text: str) -> Dict[str, bool]:
        """Detects presence of Latin, Sinhala, or Tamil characters in extracted text."""
        return {
            "has_sinhala": bool(SINHALA_RANGE.search(text)),
            "has_tamil": bool(TAMIL_RANGE.search(text)),
            "has_latin": bool(re.search(r"[A-Za-z]", text))
        }

    def _run_win_ocr_on_file(self, file_path: str) -> List[str]:
        """Invokes built-in Windows Media OCR via PowerShell script."""
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", WIN_OCR_PS1,
                file_path
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if proc.returncode == 0:
                lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
                return lines
            else:
                logger.warning(f"Windows OCR returned error: {proc.stderr}")
                return []
        except Exception as e:
            logger.error(f"Failed to execute Windows Native OCR: {str(e)}")
            return []

    def run_ocr(self, image_bytes: bytes, *, compare_profiles=False, prefer_enhanced=False, prefer_enhanced_name=False) -> Tuple[List[str], float, Dict[str, Any]]:
        """Read the original image and retry with conservative enhancement if needed."""
        if not image_bytes:
            return [], 0.0, {"engine": "none", "error": "Decode failed"}
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return [], 0.0, {"engine": "none", "error": "Decode failed"}

        original = self._read_image(img)
        original_nic = self.extract_nic_candidate(original[0])
        if original_nic and not (compare_profiles or prefer_enhanced or prefer_enhanced_name) and self.extract_name_candidate(original[0]):
            return original
        if not self.is_win_ocr_available:
            return original

        # Work only on an OCR copy. Keep the original for quality assessment.
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if 0 < min(gray.shape) < 500:
            scale = min(2.0, 500 / min(gray.shape))
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        contrast = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        softened = cv2.GaussianBlur(contrast, (0, 0), 0.8)
        sharpened = cv2.addWeighted(contrast, 1.35, softened, -0.35, 0)
        enhanced = self._read_image(cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR))
        enhanced_nic = self.extract_nic_candidate(enhanced[0])
        use_enhanced = (enhanced_nic and (prefer_enhanced or not original_nic)) or (not original[0] and enhanced[0])
        lines, confidence, metadata = enhanced if use_enhanced else original
        if compare_profiles:
            metadata["profile_candidates"] = (original_nic, enhanced_nic)
        original_name = self.extract_name_candidate(original[0])
        enhanced_name = self.extract_name_candidate(enhanced[0])
        if compare_profiles:
            metadata["name_candidates"] = (original_name, enhanced_name)
        name = (enhanced_name or original_name) if prefer_enhanced_name else (original_name or enhanced_name)
        nic = self.extract_nic_candidate(lines)
        if not nic or (nic.isdigit() and not name):
            straight = straighten_card(img)
            if straight is not img:
                scale = min(3.0, max(1.0, 650 / min(straight.shape[:2])))
                prepared = cv2.resize(straight, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                straight_lines, _, _ = self._read_image(prepared)
                if not nic:
                    nic = self.extract_nic_candidate(straight_lines)
                    if nic:
                        lines = straight_lines
                name = name or self.extract_name_candidate(straight_lines)
            if not nic and straight.shape[1] > straight.shape[0]:
                h, w = straight.shape[:2]
                number_region = straight[round(.15*h):round(.30*h), round(.36*w):round(.96*w)]
                if number_region.size:
                    prepared = cv2.resize(number_region, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                    number_lines, _, _ = self._read_image(prepared)
                    candidate = self.extract_nic_candidate(number_lines)
                    if candidate and candidate.isdigit() and parse_sri_lankan_nic(candidate).is_valid:
                        nic = candidate
                        lines = [*lines, candidate]
            if nic and nic.isdigit() and not name:
                name = self._read_modern_name_region(straight)
                if name is None and straight is not img:
                    name = self._read_modern_name_region(img)
            if not nic and img.shape[0] > img.shape[1]:
                h, w = img.shape[:2]
                old_number = img[round(.22*h):round(.40*h), round(.17*w):round(.86*w)]
                if old_number.size:
                    old_lines, _, _ = self._read_image(old_number)
                    candidate = self.extract_nic_candidate(old_lines)
                    if candidate and candidate.endswith(("V", "X")) and parse_sri_lankan_nic(candidate).is_valid:
                        lines = [*lines, candidate]
        metadata["recovered_name"] = name
        metadata["labeled_dob"] = self.extract_labeled_dob(lines) or self.extract_labeled_dob(
            original[0] if use_enhanced else enhanced[0]
        )
        disagreements = {}
        for field, pair in {
            "nic": (original_nic, enhanced_nic),
            "name": (original_name, enhanced_name),
            "dob": (self.extract_labeled_dob(original[0]), self.extract_labeled_dob(enhanced[0])),
        }.items():
            if all(pair) and pair[0].casefold() != pair[1].casefold():
                disagreements[field] = "OCR passes returned different values. Check this field against the card."
        metadata["field_warnings"] = disagreements
        if "nic" in disagreements:
            metadata["alternate_nic_reads"] = [original_nic, enhanced_nic]
        return lines, confidence, metadata

    def _read_modern_name_region(self, img: np.ndarray) -> Optional[str]:
        """Retry the English name area on a straightened landscape card image."""
        h, w = img.shape[:2]
        if not 1.35 <= w / h <= 2.1:
            return None
        region = img[round(h * .62):round(h * .70), round(w * .42):round(w * .94)]
        if region.size == 0:
            return None
        scale = max(1.0, min(3.0, 1150 / region.shape[1]))
        region = cv2.resize(region, None, fx=scale, fy=scale,
                            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        gray = cv2.copyMakeBorder(gray, 25, 25, 25, 25, cv2.BORDER_CONSTANT, value=255)
        lines, _, _ = self._read_image(gray)
        # OCR can read a damaged capital S as a dollar sign inside a word.
        lines = [re.sub(r"(?<=[A-Z])\$(?=[A-Z])", "S", line) for line in lines]
        return self.extract_name_candidate(lines)

    def _read_image(self, img: np.ndarray) -> Tuple[List[str], float, Dict[str, Any]]:
        """
        Executes OCR on raw image bytes.
        Supports multi-angle auto-rotation (0, 90, 270 degrees) to ensure rotated photos are correctly read.
        """
        lines: List[str] = []
        confidences: List[float] = []
        active_engine = "Fallback"

        h, w = img.shape[:2]

        if self.is_win_ocr_available:
            # Check orientations to test:
            # If portrait (height > width), standard ID cards are landscape, so rotate 90 and 270 degrees
            orientations = [0, 180]
            if h > w:
                orientations = [270, 90, 0]  # Try 90 deg clockwise first

            best_lines = []
            best_score = -1

            for rot_angle in orientations:
                temp_img = img
                if rot_angle == 90:
                    temp_img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                elif rot_angle == 180:
                    temp_img = cv2.rotate(img, cv2.ROTATE_180)
                elif rot_angle == 270:
                    temp_img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

                # Write to ephemeral temp file
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    temp_path = tf.name

                try:
                    if not cv2.imwrite(temp_path, temp_img):
                        continue
                    candidate_lines = self._run_win_ocr_on_file(temp_path)
                finally:
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass

                # Score this orientation based on recognized keywords & numbers
                joined = " ".join(candidate_lines).upper()
                score = 0
                if "NATIONAL IDENTITY" in joined or "IDENTITY CARD" in joined:
                    score += 50
                if "SRI LANKA" in joined:
                    score += 30
                if self.extract_nic_candidate(candidate_lines):
                    score += 40
                score += min(len(candidate_lines), 9)

                if score > best_score:
                    best_score = score
                    best_lines = candidate_lines

                if score >= 80 or (rot_angle == 0 and self.extract_nic_candidate(candidate_lines)):
                    break

            if best_lines:
                lines = best_lines
                confidences = [0.95] * len(lines)
                active_engine = "Windows-Native-OCR"

        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        joined_text = " ".join(lines)
        scripts = self.detect_scripts(joined_text)

        metadata = {
            "engine": active_engine,
            "language": self.lang,
            "detected_scripts": scripts,
            "line_count": len(lines),
            "script_support_notice": (
                "OCR engine active. Latin alphanumeric & trilingual headings supported."
            )
        }

        return lines, round(avg_conf, 2), metadata

    def extract_nic_candidate(self, lines: List[str]) -> Optional[str]:
        """
        Extracts Sri Lankan NIC number from OCR lines using strict regex patterns.
        Prioritizes:
        1. 12 consecutive digits (post-2016 format, e.g. 200285701548)
        2. 9 digits followed by V or X (pre-2016 format, e.g. 853451234V)
        """
        joined = "\n".join(lines)

        # 12-digit format pattern
        new_pattern = re.compile(r"\b([12]\d{3}[0-8]\d{2}\d{5})\b|\b([0-9]{12})\b")
        m_new = new_pattern.search(joined)
        if m_new:
            val = m_new.group(1) or m_new.group(2)
            clean = re.sub(r"\s+", "", val)
            return clean

        # Also search line by line if label precedes number (e.g. 'No.: 200285701548' or 'අංකය: 200285701548')
        for line in lines:
            m = re.search(r"(\b[12]\d{11}\b)", line)
            if m:
                return m.group(1)

        # 9-digit format pattern
        old_pattern = re.compile(r"\b([0-9]{9}\s?[vVxX])\b")
        m_old = old_pattern.search(joined)
        if m_old:
            clean = re.sub(r"\s+", "", m_old.group(1)).upper()
            return clean

        loose_pattern = re.compile(r"\b([0-9]{9})\s*([VvXx])\b")
        m_loose = loose_pattern.search(joined)
        if m_loose:
            return f"{m_loose.group(1)}{m_loose.group(2).upper()}"

        return None

    def extract_labeled_dob(self, lines: List[str]) -> Optional[str]:
        for index, line in enumerate(lines):
            label = re.search(r"\b(?:date\s+of\s+birth|birth\s+date|dob)\b", line, re.IGNORECASE)
            if label:
                value = line[label.end():].strip(" :/.-")
                if not value and index + 1 < len(lines):
                    value = lines[index + 1]
                return self.extract_dob_candidate([value])
        return None

    def extract_dob_candidate(self, lines: List[str]) -> Optional[str]:
        """
        Extracts date of birth string from document text.
        Patterns: YYYY/MM/DD, YYYY-MM-DD, YYYY.MM.DD, DD/MM/YYYY
        """
        date_pattern = re.compile(
            r"\b(19\d{2}|20\d{2})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])\b|"
            r"\b(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](19\d{2}|20\d{2})\b"
        )
        for line in lines:
            # Skip if line is the 12-digit NIC number
            if re.search(r"\b\d{12}\b|\b\d{9}[vVxX]\b", line):
                continue
            m = date_pattern.search(line)
            if m:
                # Normalize to YYYY-MM-DD
                if m.group(1):  # YYYY-MM-DD
                    y, mo, d = m.group(1), m.group(2), m.group(3)
                    return f"{y}-{mo}-{d}"
                elif m.group(4):  # DD-MM-YYYY
                    d, mo, y = m.group(4), m.group(5), m.group(6)
                    return f"{y}-{mo}-{d}"
        # Also check for date with missing secondary delimiter e.g. 1985/0804
        noisy_date_pattern = re.compile(r"\b(19\d{2}|20\d{2})[-/.](0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\b")
        for line in lines:
            if re.search(r"\b\d{12}\b|\b\d{9}[vVxX]\b", line):
                continue
            m = noisy_date_pattern.search(line)
            if m:
                return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        return None

    def extract_name_candidate(self, lines: List[str], *, require_label=False) -> Optional[str]:
        """
        Extracts candidate person name from OCR lines.
        Handles labels 'Name :', 'Name:', 'Natne', or prominent Latin uppercase names.
        """
        label_pattern = re.compile(r"\b(?:Full Name|Natne|Nalne|Names?)\b\s*[:.\-]?\s*(.*)$", re.IGNORECASE)
        name_pattern = re.compile(r"[^\W\d_]+(?:[.'’\-][^\W\d_]+)*\.?(?:\s+[^\W\d_]+(?:[.'’\-][^\W\d_]+)*\.?)+")

        for i, line in enumerate(lines):
            clean = line.strip()
            m = label_pattern.search(clean)
            if m:
                val = m.group(1).strip()
                if not val and i + 1 < len(lines):
                    val = lines[i + 1].strip()
                val = re.split(r"\s+\bSex\b", val, maxsplit=1, flags=re.IGNORECASE)[0].strip()
                if name_pattern.fullmatch(val) and not re.search(
                    r"\b(?:sex|birth|card|signature|address|male|female)\b", val, re.IGNORECASE
                ):
                    return val

        if require_label:
            return None

        # 2. Look for uppercase Sri Lankan name line
        for line in lines:
            clean = line.strip()
            # Ignore headers, country name, labels, and place names
            upper_clean = clean.upper()
            if any(h in upper_clean for h in [
                "SRI LANKA", "SHI L.ANKA", "SHI LANKA", "SRILANKA", "LANKA", "IDENTITY",
                "REPUBLIC", "DEMOCRATIC", "COLOMBO", "CARD", "HOLDER", "SIGNATURE",
                "DATE OF BIRTH", "BIRTH", "SEX", "FEMALE", "MALE", "ADDRESS"
            ]):
                continue
            tokens = clean.split()
            if 2 <= len(tokens) <= 6:
                if all(re.match(r"^[A-Z][A-Za-z.'-]*$", t) for t in tokens):
                    if not any(char.isdigit() for char in clean):
                        return clean

        return None

ocr_service = OCREngine()
