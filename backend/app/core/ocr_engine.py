import re
import sys
import cv2
from threading import Lock
from statistics import mean
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from ..config import settings
from .ocr_backends import OCRBackend, OCRLine, PaddleBackend, TesseractBackend, WindowsBackend
from ..utils.privacy import get_sanitized_logger
from .card_geometry import straighten_card
from .nic_field import normalize_nic_field
from .nic_parser import parse_sri_lankan_nic
from .vision_models import vision_models

logger = get_sanitized_logger("ocr_engine")

# Unicode block ranges
SINHALA_RANGE = re.compile(r"[\u0D80-\u0DFF]")
TAMIL_RANGE = re.compile(r"[\u0B80-\u0BFF]")

class OCREngine:
    def __init__(self, backend=None, tessdata_dir=None):
        self.selection = backend or settings.OCR_BACKEND
        self.tessdata_dir = tessdata_dir
        self._backends: dict[str, OCRBackend | None] = {}
        self._lock = Lock()
        self.active_engine: OCRBackend | None = None

    def _load_backend(self, name: str) -> OCRBackend | None:
        factories = {
            "paddle": PaddleBackend,
            "tesseract": lambda: TesseractBackend(self.tessdata_dir),
            "windows": WindowsBackend,
        }
        if name not in self._backends:
            try:
                self._backends[name] = factories[name]()
            except Exception as error:
                self._backends[name] = None
                logger.warning("OCR backend %s could not initialize (%s)", name, type(error).__name__)
        return self._backends[name]

    def _recognize(self, image, *, nic_field=False):
        selection = self.selection
        if selection == "auto":
            selection = "windows" if sys.platform == "win32" else "paddle"
        order = ("paddle", "tesseract") if selection == "paddle" else (selection,)
        with self._lock:
            available = None
            for name in order:
                backend = self._load_backend(name)
                if backend is None:
                    continue
                try:
                    if nic_field and isinstance(backend, TesseractBackend):
                        lines = backend.read_nic(image)
                        if not any(normalize_nic_field(row.text) for row in lines):
                            lines = backend.read(image)
                    else:
                        lines = backend.read(image)
                except Exception as error:
                    logger.warning("OCR backend %s failed (%s)", backend.name, type(error).__name__)
                    continue
                self.active_engine = backend
                available = backend.name
                if nic_field:
                    lines = [
                        OCRLine(candidate, row.confidence)
                        for row in lines
                        if (candidate := normalize_nic_field(row.text))
                    ]
                if lines:
                    return backend.name, lines
            return available or "Unavailable", []

    def detect_scripts(self, text: str) -> Dict[str, bool]:
        """Detects presence of Latin, Sinhala, or Tamil characters in extracted text."""
        return {
            "has_sinhala": bool(SINHALA_RANGE.search(text)),
            "has_tamil": bool(TAMIL_RANGE.search(text)),
            "has_latin": bool(re.search(r"[A-Za-z]", text))
        }

    def run_ocr(self, image_bytes: bytes, *, compare_profiles=False, prefer_enhanced=False, prefer_enhanced_name=False) -> Tuple[List[str], float, Dict[str, Any]]:
        """Read the original image and retry with conservative enhancement if needed."""
        if not image_bytes:
            return [], 0.0, {"engine": "none", "error": "Decode failed"}
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return [], 0.0, {"engine": "none", "error": "Decode failed"}

        detected = vision_models.detect(img)
        document = detected.get("card", img)
        original = self._read_image(document)
        original_nic = self.extract_nic_candidate(original[0])
        if original[2]["engine"] == "Unavailable":
            return original

        # Work only on an OCR copy. Keep the original for quality assessment.
        fast_pass = original_nic and not (compare_profiles or prefer_enhanced or prefer_enhanced_name)
        fast_pass = fast_pass and self.extract_name_candidate(original[0])
        enhanced = original if fast_pass else self._read_image(self._enhance(document))
        enhanced_nic = self.extract_nic_candidate(enhanced[0])
        use_enhanced = (enhanced_nic and (prefer_enhanced or not original_nic)) or (not original[0] and enhanced[0])
        lines, _, metadata = enhanced if use_enhanced else original
        if compare_profiles:
            metadata["profile_candidates"] = (original_nic, enhanced_nic)
        original_name = self.extract_name_candidate(original[0])
        enhanced_name = self.extract_name_candidate(enhanced[0])
        if compare_profiles:
            metadata["name_candidates"] = (original_name, enhanced_name)
        name = (enhanced_name or original_name) if prefer_enhanced_name else (original_name or enhanced_name)
        nic = self.extract_nic_candidate(lines)
        field_image = document
        if not detected and (not nic or (nic.isdigit() and not name)):
            straight = straighten_card(document)
            if straight is not document:
                scale = min(3.0, max(1.0, 650 / min(straight.shape[:2])))
                prepared = cv2.resize(straight, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                straight_lines, _, straight_meta = self._read_image(prepared)
                if not nic:
                    nic = self.extract_nic_candidate(straight_lines)
                    if nic:
                        lines = straight_lines
                        metadata.update(straight_meta)
                        field_image = straight
                name = name or self.extract_name_candidate(straight_lines)
            if nic and nic.isdigit() and not name:
                name = self._read_modern_name_region(straight)
                if name is None and straight is not img:
                    name = self._read_modern_name_region(img)

        # Crop from the chosen orientation so a sideways phone photo uses
        # the same field coordinates as an upright card.
        oriented = field_image if metadata["rotation"] is None else cv2.rotate(field_image, metadata["rotation"])
        number_crop = detected.get("nic_number")
        if number_crop is not None:
            crop_reads = self._read_nic_crop(number_crop, metadata["rotation"])
        else:
            crop_reads = {} if detected else self._read_nic_region(oriented)
        full_card_nic = nic
        if detected and crop_reads:
            best = next(iter(crop_reads.values()))
            metadata["detected_nic_confidence"] = best.confidence
            if best.text != nic:
                metadata["detected_nic"] = best.text
        if not nic and crop_reads:
            best = next(iter(crop_reads.values()))
            nic = best.text
            lines = [*lines, nic]
            metadata["line_confidences"] = [*metadata["line_confidences"], best.confidence]
        card_dob = self.extract_labeled_dob(lines) or self.extract_labeled_dob(
            original[0] if use_enhanced else enhanced[0]
        )
        name_crop = detected.get("name")
        dob_crop = detected.get("dob")
        detected_name = None
        detected_dob = None
        crop_warnings = {}
        if name_crop is not None:
            rows = self._read_detected_field(name_crop, metadata["rotation"])
            detected_name = self.extract_name_candidate([row.text for row in rows])
            if detected_name and self._low_field_confidence(rows):
                crop_warnings["name"] = "OCR confidence is low or unavailable. Check the name against the card."
        if dob_crop is not None:
            rows = self._read_detected_field(dob_crop, metadata["rotation"])
            detected_dob = self.extract_dob_candidate([row.text for row in rows])
            if detected_dob and self._low_field_confidence(rows):
                crop_warnings["dob"] = "OCR confidence is low or unavailable. Check the date against the card."
        metadata["recovered_name"] = detected_name or name
        metadata["labeled_dob"] = detected_dob or card_dob
        if detected:
            metadata["visual_prediction"] = vision_models.classify(oriented)
        disagreements = crop_warnings
        for field, pair in {
            "nic": (original_nic, enhanced_nic),
            "name": (original_name, enhanced_name),
            "dob": (self.extract_labeled_dob(original[0]), self.extract_labeled_dob(enhanced[0])),
        }.items():
            if all(pair) and pair[0].casefold() != pair[1].casefold():
                disagreements[field] = "OCR passes returned different values. Check this field against the card."
        metadata["field_warnings"] = disagreements
        for field, whole, cropped in (("name", name, detected_name), ("dob", card_dob, detected_dob)):
            if whole and cropped and whole.casefold() != cropped.casefold():
                disagreements[field] = "OCR passes returned different values. Check this field against the card."
        candidates = list(dict.fromkeys(value for value in (nic, full_card_nic, original_nic, enhanced_nic, *crop_reads) if value))
        if len(candidates) > 1:
            disagreements["nic"] = "OCR passes returned different values. Check this field against the card."
            metadata["alternate_nic_reads"] = candidates
        scores = [score for score in metadata["line_confidences"] if score is not None]
        metadata["line_count"] = len(lines)
        metadata["detected_scripts"] = self.detect_scripts(" ".join(lines))
        return lines, mean(scores) if scores else 0.0, metadata

    @staticmethod
    def _enhance(image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        if min(gray.shape) < 500:
            scale = min(2.0, 500 / min(gray.shape))
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        contrast = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        softened = cv2.GaussianBlur(contrast, (0, 0), 0.8)
        return cv2.addWeighted(contrast, 1.35, softened, -0.35, 0)

    def _read_nic_region(self, image: np.ndarray) -> dict[str, OCRLine]:
        height, width = image.shape[:2]
        if width >= height:
            crop = image[round(.15 * height):round(.34 * height), round(.27 * width):round(.97 * width)]
        else:
            crop = image[round(.22 * height):round(.40 * height), round(.17 * width):round(.86 * width)]
        if not crop.size:
            return {}
        return self._read_nic_crop(crop, None)

    def _read_nic_crop(self, crop, rotation):
        if rotation is not None:
            crop = cv2.rotate(crop, rotation)
        reads = {}
        for prepared in (crop, self._enhance(crop)):
            _, rows = self._recognize(prepared, nic_field=True)
            for row in rows:
                reads.setdefault(row.text, row)
        return reads

    def _read_detected_field(self, crop, rotation):
        if rotation is not None:
            crop = cv2.rotate(crop, rotation)
        _, rows = self._recognize(self._enhance(crop))
        return rows

    @staticmethod
    def _low_field_confidence(rows):
        return any(row.confidence is None or row.confidence < settings.OCR_REVIEW_CONFIDENCE for row in rows)

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
        """Pick the strongest orientation and preserve confidence with its lines."""
        height, width = img.shape[:2]
        rotations = (None, cv2.ROTATE_180)
        if height > width:
            rotations = (cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_90_CLOCKWISE, None, cv2.ROTATE_180)

        best: list[OCRLine] = []
        best_score = -1
        engine = "Unavailable"
        selected_rotation = None
        for rotation in rotations:
            candidate_engine, rows = self._recognize(img if rotation is None else cv2.rotate(img, rotation))
            texts = [row.text for row in rows]
            joined = " ".join(texts).upper()
            has_nic = bool(self.extract_nic_candidate(texts))
            score = min(len(texts), 9)
            if "IDENTITY CARD" in joined or "NATIONAL IDENTITY" in joined:
                score += 50
            if "SRI LANKA" in joined:
                score += 30
            if has_nic:
                score += 40
            if score > best_score:
                best, best_score, engine = rows, score, candidate_engine
                selected_rotation = rotation
            if candidate_engine == "Unavailable" or score >= 80 or (rotation is None and has_nic):
                break

        lines = [row.text for row in best]
        scores = [row.confidence for row in best]
        measured = [score for score in scores if score is not None]
        return lines, mean(measured) if measured else 0.0, {
            "engine": engine,
            "rotation": selected_rotation,
            "line_confidences": scores,
            "line_count": len(lines),
            "detected_scripts": self.detect_scripts(" ".join(lines)),
        }

    def extract_nic_candidate(self, lines: List[str]) -> Optional[str]:
        """
        Extracts Sri Lankan NIC number from OCR lines using strict regex patterns.
        Prioritizes:
        1. 12 consecutive digits (post-2016 format, e.g. 200285701548)
        2. 9 digits followed by V or X (pre-2016 format, e.g. 853451234V)
        """
        joined = "\n".join(lines)
        for pattern in (r"\b[0-9]{12}\b", r"\b[0-9]{9}[ \t]*[VvXx]\b"):
            for match in re.finditer(pattern, joined):
                candidate = normalize_nic_field(match.group())
                if candidate:
                    return candidate
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

ocr_service = OCREngine(tessdata_dir=settings.TESSDATA_PREFIX)
