import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core import ocr_engine as oe
from app.core.ocr_backends import OCRLine
from app.main import app, settings


def _png():
    image = np.full((480, 760, 3), 255, dtype=np.uint8)
    return cv2.imencode(".png", image)[1].tobytes()


def test_full_card_nic_wins_over_crop_read(monkeypatch):
    class FakeVision:
        def detect(self, img):
            return {"nic_number": img[:50, :50]}

        def classify(self, img):
            return None

    monkeypatch.setattr(oe, "vision_models", FakeVision())
    engine = oe.OCREngine()

    def fake(image, *, nic_field=False):
        if nic_field:
            return "Fake", [OCRLine("199518001235", .9)]
        return "Fake", [OCRLine("NATIONAL IDENTITY CARD", .9), OCRLine("199518001234", .9)]

    monkeypatch.setattr(engine, "_recognize", fake)
    lines, _, meta = engine.run_ocr(_png())
    assert engine.extract_nic_candidate(lines) == "199518001234"
    assert "detected_nic" not in meta
    assert set(meta["alternate_nic_reads"]) == {"199518001234", "199518001235"}
    assert "nic" in meta["field_warnings"]


def test_crop_read_used_when_full_card_has_no_nic(monkeypatch):
    class FakeVision:
        def detect(self, img):
            return {"nic_number": img[:50, :50]}

        def classify(self, img):
            return None

    monkeypatch.setattr(oe, "vision_models", FakeVision())
    engine = oe.OCREngine()
    monkeypatch.setattr(engine, "_recognize", lambda image, *, nic_field=False: (
        "Fake", [OCRLine("199518001234", .9)] if nic_field else [OCRLine("NATIONAL IDENTITY CARD", .9)]))
    lines, _, _ = engine.run_ocr(_png())
    assert engine.extract_nic_candidate(lines) == "199518001234"


@pytest.mark.parametrize("bookingpartner", [False, True])
def test_ocr_outage_returns_503_not_retake(monkeypatch, bookingpartner):
    from app.main import ocr_service
    key = "A" * 64
    monkeypatch.setattr(settings, "BOOKINGPARTNER_API_KEY", SecretStr(key) if bookingpartner else None)
    monkeypatch.setattr(ocr_service, "run_ocr", lambda *a, **k: ([], 0.0, {"engine": "Unavailable"}))
    image = _png()
    path = "/api/v1/bookingpartner/verify" if bookingpartner else "/api/verify"
    response = TestClient(app).post(path, files={"front_image": ("a.png", image, "image/png")},
                                    headers={"X-API-Key": key} if bookingpartner else {})
    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable"
