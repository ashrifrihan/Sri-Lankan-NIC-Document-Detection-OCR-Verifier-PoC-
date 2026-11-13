import io

import cv2
import numpy as np
import pytest
import zxingcpp
from starlette.datastructures import UploadFile

from app.core.barcode import scan_back_barcode
from app.main import ocr_service, verify_bookingpartner


def png(image):
    return cv2.imencode(".png", image)[1].tobytes()


def barcode_image(payload):
    code = zxingcpp.create_barcode(payload, zxingcpp.BarcodeFormat.PDF417)
    return np.asarray(zxingcpp.write_barcode_to_image(code, scale=4))


@pytest.mark.parametrize(("payload", "expected"), [
    ("199518001234", "match"),
    ("199518001235", "mismatch"),
    ("record:199518001234", "unavailable"),
])
def test_scan_pdf417(payload, expected):
    result = scan_back_barcode(png(np.rot90(barcode_image(payload))), "199518001234")
    assert result.model_dump() == {"status": "decoded", "format": "PDF417", "nic_match": expected}


def test_scan_blank_image():
    result = scan_back_barcode(png(np.full((300, 500), 255, dtype=np.uint8)), None)
    assert result.status == "unread"


def test_bookingpartner_barcode_mismatch_requires_review(monkeypatch):
    reads = iter([
        (["SRI LANKA NATIONAL IDENTITY CARD", "199518001234", "NAME: SAMPLE PERSON"], .9, {}),
        ([], 0, {}),
    ])
    monkeypatch.setattr(ocr_service, "run_ocr", lambda *args, **kwargs: next(reads))
    rng = np.random.default_rng(42)
    front = rng.integers(40, 230, (540, 856), dtype=np.uint8)
    back = np.full((540, 856), 230, dtype=np.uint8)
    code = barcode_image("199518001235")
    height, width = code.shape
    back[300:300 + height, 40:40 + width] = code
    headers = {"content-type": "image/png"}
    result = verify_bookingpartner(
        UploadFile(io.BytesIO(png(front)), headers=headers),
        UploadFile(io.BytesIO(png(back)), headers=headers),
        None, None, None,
    )
    assert result.back_barcode.nic_match == "mismatch"
    assert result.review_status == "manual_review"
    assert "199518001235" not in result.model_dump_json()
