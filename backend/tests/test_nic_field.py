import cv2
import numpy as np
import pytest

from app.core.nic_field import normalize_nic_field
from app.core.ocr_backends import OCRLine
from app.core.ocr_engine import OCREngine


@pytest.mark.parametrize(("observed", "expected"), [
    ("BS34S l234v", "853451234V"),
    ("2OO5 OI7 OO98O", "200501700980"),
    ("NIC No.: 853451234x", "853451234X"),
    ("853451234S", None),
    ("85345123XV", None),
    ("200500000980", None),
    ("20050170098X", None),
    ("NAME 853451234V", None),
    ("853451234V 1", None),
])
def test_normalize_position_aware_nic_field(observed, expected):
    assert normalize_nic_field(observed) == expected


def test_crop_rescues_nic_and_preserves_disagreement(monkeypatch):
    engine = OCREngine("paddle")
    crop_shapes = []

    class Backend:
        name = "PaddleOCR"

        def read(self, image):
            if image.shape[:2] == (200, 320):
                return [OCRLine("SRI LANKA NATIONAL IDENTITY CARD", .97)]
            crop_shapes.append(image.shape[:2])
            candidate = "BS34S l234v" if len(crop_shapes) == 1 else "853451235V"
            return [OCRLine(candidate, .72)]

    monkeypatch.setattr(engine, "_load_backend", lambda _: Backend())
    monkeypatch.setattr(engine, "_enhance", lambda image: image)
    _, image = cv2.imencode(".png", np.zeros((200, 320, 3), dtype=np.uint8))

    lines, _, metadata = engine.run_ocr(image.tobytes())

    assert engine.extract_nic_candidate(lines) == "853451234V"
    assert len(crop_shapes) == 2
    assert all(height < 200 and width < 320 for height, width in crop_shapes)
    assert metadata["alternate_nic_reads"] == ["853451234V", "853451235V"]
    assert "nic" in metadata["field_warnings"]
    assert metadata["line_confidences"][-1] == .72


def test_full_card_read_skips_invalid_number_without_repairing_other_text():
    engine = OCREngine()
    assert engine.extract_nic_candidate(["200500000980", "853451234V"]) == "853451234V"
    assert engine.extract_nic_candidate(["BS34S l234v"]) is None
