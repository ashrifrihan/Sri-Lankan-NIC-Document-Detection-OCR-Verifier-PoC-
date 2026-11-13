import cv2
import re
import numpy as np
from typing import List, Dict, Any, Tuple
from ..models.schemas import DocumentClassification, DocumentClassificationType, DocumentCategory
from .nic_parser import parse_sri_lankan_nic

# Sri Lanka NIC textual indicators (Latin and script keywords)
SRI_LANKA_KEYWORDS = [
    "SRI LANKA", "SRILANKA", "DEMOCRATIC SOCIALIST",
    "NATIONAL IDENTITY", "IDENTITY CARD", "DEPARTMENT OF REGISTRATION",
    "DEPT OF REGISTRATION", "PERSONS", "COLOMBO", "DATE OF BIRTH",
    "HOLDER'S SIGNATURE", "HOLDERS SIGNATURE", "SEX :", "MALE", "FEMALE",
    "PLATE OF BIRTH", "PLACE OF BIRTH", "DATE OF ISSUE", "COMMISSIONER GENERAL"
]

# Unicode keywords for Sinhala & Tamil
SINHALA_KEYWORDS = [
    "ශ්‍රී ලංකා", "ශ්‍රීලංකා", "ජාතික", "හැඳුනුම්පත", "පුද්ගලයින්",
    "ලියාපදිංචි", "උපන් දිනය", "ස්ත්‍රී", "පුරුෂ", "කොළඹ", "ලිපිනය"
]
TAMIL_KEYWORDS = [
    "இலங்கை", "தேசிய", "அடையாள", "அட்டை", "பெயர்", "பிறந்த திகதி",
    "பெண்", "ஆண்", "முகவரி"
]

def extract_color_distribution(img_bgr: np.ndarray) -> Dict[str, float]:
    """
    Computes dominant color distributions in HSV space to assess card base material.
    - Old laminated: yellow-ochre aged paper or blue-violet hue range
    - Printed laminated: light cyan / blue hue range
    - New plastic card: light green/cyan/yellow pastel security background
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    total_pixels = float(img_bgr.shape[0] * img_bgr.shape[1])

    # 1. Yellow/Ochre paper mask (Classic Old Laminated cards, e.g. 961230144v)
    # H: 16 - 45, S: 25 - 200, V: 120 - 255
    yellow_ochre_mask = cv2.inRange(hsv, np.array([16, 25, 120]), np.array([45, 200, 255]))
    yellow_ochre_ratio = float(np.sum(yellow_ochre_mask > 0)) / total_pixels

    # 2. Blue-violet mask (Blue tinted laminated cards)
    blue_mask = cv2.inRange(hsv, np.array([90, 30, 50]), np.array([140, 255, 240]))
    blue_ratio = float(np.sum(blue_mask > 0)) / total_pixels

    # 3. Gold/yellow chip mask
    gold_mask = cv2.inRange(hsv, np.array([15, 80, 100]), np.array([35, 255, 255]))
    gold_ratio = float(np.sum(gold_mask > 0)) / total_pixels

    # 4. Light neutral / pastel background ratio
    neutral_white_mask = cv2.inRange(hsv, np.array([0, 0, 170]), np.array([180, 60, 255]))
    neutral_white_ratio = float(np.sum(neutral_white_mask > 0)) / total_pixels

    # 5. Light green/cyan pastel (Modern Smart NIC cards)
    green_pastel_mask = cv2.inRange(hsv, np.array([35, 15, 160]), np.array([95, 120, 255]))
    green_pastel_ratio = float(np.sum(green_pastel_mask > 0)) / total_pixels

    return {
        "yellow_ochre_ratio": round(yellow_ochre_ratio, 3),
        "blue_ratio": round(blue_ratio, 3),
        "gold_ratio": round(gold_ratio, 4),
        "neutral_white_ratio": round(neutral_white_ratio, 3),
        "green_pastel_ratio": round(green_pastel_ratio, 3)
    }

def detect_smart_chip_candidate(img_bgr: np.ndarray) -> bool:
    """Inspects whether a gold/copper metallic contact chip pattern exists."""
    h, w = img_bgr.shape[:2]
    roi = img_bgr[int(0.25*h):int(0.75*h), int(0.08*w):int(0.42*w)]
    if roi.size == 0:
        return False

    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gold_mask = cv2.inRange(hsv_roi, np.array([12, 60, 90]), np.array([38, 255, 255]))
    contours, _ = cv2.findContours(gold_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        area = cv2.contourArea(c)
        if area > (roi.shape[0] * roi.shape[1] * 0.015):
            x, y, cw, ch = cv2.boundingRect(c)
            ratio = float(cw) / float(ch) if ch > 0 else 0
            if 0.7 <= ratio <= 1.5:
                return True
    return False

def classify_sri_lankan_nic(
    image_bytes: bytes,
    detected_texts: List[str]
) -> DocumentClassification:
    """
    Conservative, heuristic-based Sri Lankan NIC document classifier.
    Combines color analysis, card structure signals, and OCR evidence.
    Accurately recognizes both classic old laminated cards (yellow/blue) and modern smart cards.
    """
    notes: List[str] = []
    ocr_evidence: List[str] = []
    signals: Dict[str, Any] = {}

    np_arr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        return DocumentClassification(
            classification=DocumentClassificationType.NOT_NIC,
            visual_category=DocumentCategory.UNCERTAIN,
            confidence=0.0,
            is_provisional=True,
            visual_signals={"error": "Image could not be decoded."},
            ocr_evidence=[],
            notes=["Corrupt or unsupported image stream."]
        )

    # 1. OCR text keyword matching
    full_text_upper = " ".join(detected_texts).upper()
    found_keywords = []
    for kw in SRI_LANKA_KEYWORDS:
        if kw in full_text_upper:
            found_keywords.append(kw)

    raw_joined = " ".join(detected_texts)
    for sk in SINHALA_KEYWORDS:
        if sk in raw_joined:
            found_keywords.append(f"Sinhala: {sk}")
    for tk in TAMIL_KEYWORDS:
        if tk in raw_joined:
            found_keywords.append(f"Tamil: {tk}")

    # Check for valid Sri Lankan NIC numbers in detected text
    found_valid_nic = False
    nic_format_detected = None

    # Search for 12-digit NIC
    m_12 = re.search(r"\b([12]\d{11})\b", full_text_upper)
    if m_12:
        res = parse_sri_lankan_nic(m_12.group(1))
        if res.is_valid:
            found_valid_nic = True
            nic_format_detected = "12_digit"
            found_keywords.append(f"Valid 12-Digit NIC ({res.birth_year})")

    # Search for 9-digit + V/X NIC
    m_9 = re.search(r"\b([0-9]{9}\s?[vVxX])\b", full_text_upper)
    if m_9:
        clean_9 = re.sub(r"\s+", "", m_9.group(1)).upper()
        res = parse_sri_lankan_nic(clean_9)
        if res.is_valid:
            found_valid_nic = True
            nic_format_detected = "9_digit"
            found_keywords.append(f"Valid 9-Digit NIC ({res.birth_year})")

    ocr_evidence = found_keywords
    signals["keywords_detected"] = found_keywords
    signals["valid_nic_detected"] = found_valid_nic

    # 2. Color and structure distribution
    color_dist = extract_color_distribution(img_bgr)
    signals.update(color_dist)

    chip_detected = detect_smart_chip_candidate(img_bgr)
    signals["smart_chip_candidate"] = chip_detected

    # 3. Decision Heuristics
    has_nic_keywords = len(found_keywords) > 0
    has_definitive_heading = any(
        k in full_text_upper for k in ["NATIONAL IDENTITY", "IDENTITY CARD", "SRI LANKA", "REGISTRATION OF PERSONS"]
    ) or any("Sinhala: ජාතික" in k or "Sinhala: ශ්‍රී ලංකා" in k or "Tamil: தேசிய" in k for k in found_keywords)

    score = 0.0
    if has_definitive_heading:
        score += 0.50
    elif has_nic_keywords:
        score += 0.30

    if found_valid_nic:
        score += 0.45  # A valid Sri Lankan NIC number is decisive evidence

    # Material/color scoring
    if color_dist["yellow_ochre_ratio"] > 0.25:
        score += 0.20  # Classic old laminated paper signature
    elif color_dist["green_pastel_ratio"] > 0.12 or color_dist["neutral_white_ratio"] > 0.20 or color_dist["blue_ratio"] > 0.15:
        score += 0.15

    if chip_detected:
        score += 0.15

    # Determine classification
    if score >= 0.50:
        classification = DocumentClassificationType.SRI_LANKAN_NIC
    elif score >= 0.25:
        classification = DocumentClassificationType.UNCERTAIN
        notes.append("Ambiguous visual features: document exhibits some characteristics but lacks definitive Sri Lankan NIC hallmarks.")
    else:
        classification = DocumentClassificationType.NOT_NIC
        notes.append("Uploaded image does not show identifiable Sri Lankan NIC features, text headers, or layout.")

    # Determine Visual Category
    category = DocumentCategory.UNCERTAIN
    if classification in [DocumentClassificationType.SRI_LANKAN_NIC, DocumentClassificationType.UNCERTAIN]:
        if nic_format_detected == "12_digit" or chip_detected or (
            color_dist["green_pastel_ratio"] > 0.12 or color_dist["neutral_white_ratio"] > 0.30
        ):
            category = DocumentCategory.NEWER_PLASTIC_CARD
            notes.append("Visual signals match modern polycarbonate card (bilingual/trilingual headers, 12-digit numbering or pastel security pattern).")
        elif nic_format_detected == "9_digit" or color_dist["yellow_ochre_ratio"] > 0.20 or color_dist["blue_ratio"] > 0.40:
            category = DocumentCategory.OLD_LAMINATED
            notes.append("Visual signals match classic laminated paper NIC (pre-2016 9-digit format or guilloche security paper).")
        elif color_dist["blue_ratio"] > 0.25:
            category = DocumentCategory.PRINTED_LAMINATED
            notes.append("Visual signals match computer-printed laminated NIC.")
        else:
            category = DocumentCategory.UNCERTAIN
            notes.append("Document visual subtype could not be conclusively determined.")

    confidence = min(round(score, 2), 0.98)

    return DocumentClassification(
        classification=classification,
        visual_category=category,
        confidence=confidence,
        is_provisional=True,
        visual_signals=signals,
        ocr_evidence=ocr_evidence,
        notes=notes
    )
