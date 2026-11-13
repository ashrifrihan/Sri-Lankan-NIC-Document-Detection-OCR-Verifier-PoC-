import numpy as np
import pytest

from app.core import ocr_engine
from app.core.ocr_backends import OCRLine, WindowsBackend


def test_paddle_falls_back_and_reuses_tesseract(monkeypatch):
    loaded = []

    class Paddle:
        def __init__(self):
            loaded.append("paddle")

        def read(self, _):
            raise RuntimeError("private input")

    class Tesseract:
        name = "Tesseract"

        def __init__(self, _):
            loaded.append("tesseract")

        def read(self, _):
            return [OCRLine("NATIONAL IDENTITY CARD", .91), OCRLine("853451234V", .71)]

    Paddle.name = "PaddleOCR"
    monkeypatch.setattr(ocr_engine, "PaddleBackend", Paddle)
    monkeypatch.setattr(ocr_engine, "TesseractBackend", Tesseract)
    engine = ocr_engine.OCREngine("paddle")
    pixels = np.zeros((20, 40, 3), dtype=np.uint8)

    for _ in range(2):
        lines, average, metadata = engine._read_image(pixels)
        assert lines == ["NATIONAL IDENTITY CARD", "853451234V"]
        assert average == pytest.approx(.81)
        assert metadata["line_confidences"] == [.91, .71]
        assert metadata["engine"] == "Tesseract"

    assert loaded == ["paddle", "tesseract"]


def test_windows_line_has_no_invented_score(monkeypatch):
    engine = ocr_engine.OCREngine("windows")
    monkeypatch.setattr(engine, "_recognize", lambda _: ("Windows OCR", [OCRLine("853451234V", None)]))

    lines, average, metadata = engine._read_image(np.zeros((20, 40), dtype=np.uint8))

    assert lines == ["853451234V"]
    assert average == 0.0
    assert metadata["line_confidences"] == [None]


def test_windows_backend_is_unavailable_on_linux(monkeypatch):
    monkeypatch.setattr(ocr_engine.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="requires Windows"):
        WindowsBackend()
