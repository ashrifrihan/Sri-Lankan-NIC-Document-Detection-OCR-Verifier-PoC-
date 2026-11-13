"""Decode a back-side PDF417 locally and expose comparison results only."""

import re

import cv2
import numpy as np
from zxingcpp import BarcodeFormat, read_barcodes

from ..models.schemas import BarcodeReview, BarcodeScan
from ..utils.privacy import get_sanitized_logger
from .nic_parser import are_nics_equivalent, parse_sri_lankan_nic

logger = get_sanitized_logger("barcode")


def scan_back_barcode(image_bytes: bytes, front_nic: str | None) -> BarcodeReview:
    return _scan_pdf417(image_bytes, front_nic)


def scan_barcode_details(image_bytes: bytes) -> BarcodeScan:
    return BarcodeScan.model_validate(_scan_pdf417(image_bytes, None, include_details=True).model_dump())


def _scan_pdf417(image_bytes: bytes, front_nic: str | None, *, include_details=False) -> BarcodeReview:
    try:
        gray = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            return BarcodeReview(status="unread")
        # Search the full image for rotated cards, then retry the expected code
        # area at higher contrast for horizontally framed photos.
        height, width = gray.shape
        scale = min(1.0, 2400 / max(height, width))
        image = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else gray
        options = {"formats": BarcodeFormat.PDF417, "try_rotate": True}
        codes = read_barcodes(image, **options)
        if not codes and width > height and height >= 32:
            lower = gray[height // 2:]
            scale = min(2.0, 2400 / width)
            focused = cv2.resize(lower, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            focused = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(focused)
            codes = read_barcodes(focused, **options)
    except (RuntimeError, ValueError, cv2.error) as error:
        logger.warning("Barcode processing failed (%s)", type(error).__name__)
        return BarcodeReview(status="unavailable")

    payloads = {bytes(code.bytes) for code in codes if code.valid}
    if not payloads:
        return BarcodeReview(status="unread")
    if len(payloads) > 1:
        return BarcodeReview(status="ambiguous", format="PDF417")

    # A plain NIC value is supported. Structured or opaque data needs an
    # issuer-defined parser. Never search arbitrary bytes for digit sequences.
    payload = next(iter(payloads)).strip()
    match = "unavailable"
    parsed = None
    if re.fullmatch(rb"(?:[0-9]{12}|[0-9]{9}[VvXx])", payload):
        candidate = payload.decode("ascii").upper()
        parsed = parse_sri_lankan_nic(candidate)
        if parsed.is_valid and front_nic and parse_sri_lankan_nic(front_nic).is_valid:
            match = "match" if are_nics_equivalent(candidate, front_nic) else "mismatch"
    if include_details and parsed and parsed.is_valid:
        return BarcodeScan(status="decoded", format="PDF417", nic_number=parsed.nic_number, decoded_dob=parsed.decoded_dob)
    return BarcodeReview(status="decoded", format="PDF417", nic_match=match)
