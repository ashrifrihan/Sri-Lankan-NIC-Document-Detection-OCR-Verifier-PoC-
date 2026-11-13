"""In-process OCR adapters. Scores are normalized to 0..1 when available."""

import sys
from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np
from PIL import Image
from .nic_field import NIC_ALPHABET


@dataclass(frozen=True)
class OCRLine:
    text: str
    confidence: float | None


class OCRBackend(Protocol):
    name: str
    languages: str

    def read(self, image: np.ndarray) -> list[OCRLine]: ...


class PaddleBackend:
    name = "PaddleOCR"
    languages = "en"

    def __init__(self):
        from paddleocr import PaddleOCR

        self.model = PaddleOCR(
            device="cpu", enable_mkldnn=False,
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="en_PP-OCRv5_mobile_rec",
            use_doc_orientation_classify=False, use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def read(self, image):
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        return [
            OCRLine(text.strip(), float(score))
            for page in self.model.predict(image)
            for text, score in zip(page["rec_texts"], page["rec_scores"], strict=True)
            if text.strip()
        ]


class TesseractBackend:
    name = "Tesseract"
    languages = "eng+sin+tam"

    def __init__(self, data_dir=None):
        from tesserocr import PSM, RIL, PyTessBaseAPI, get_languages, iterate_level

        self.level = RIL.TEXTLINE
        self.field_psm = PSM.SINGLE_BLOCK
        self.page_psm = PSM.AUTO
        self.iterate_level = iterate_level
        options = {"path": data_dir} if data_dir else {}
        path, languages = get_languages(**options)
        if not set(self.languages.split("+")).issubset(languages):
            raise RuntimeError("Tesseract requires English, Sinhala and Tamil language data.")
        self.api = PyTessBaseAPI(path=path, lang=self.languages, psm=PSM.AUTO)

    def read_nic(self, image):
        self.api.SetPageSegMode(self.field_psm)
        try:
            if not self.api.SetVariable("tessedit_char_whitelist", NIC_ALPHABET):
                raise RuntimeError("Could not set the Tesseract NIC whitelist.")
            return self.read(image)
        finally:
            self.api.SetVariable("tessedit_char_whitelist", "")
            self.api.SetPageSegMode(self.page_psm)

    def read(self, image):
        pixels = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.ndim == 3 else image
        try:
            self.api.SetImage(Image.fromarray(pixels))
            self.api.Recognize()
            if not (self.api.GetUTF8Text() or "").strip():
                return []
            iterator = self.api.GetIterator()
            if iterator is None:
                return []
            lines = []
            for row in self.iterate_level(iterator, self.level):
                text = (row.GetUTF8Text(self.level) or "").strip()
                if text:
                    lines.append(OCRLine(text, row.Confidence(self.level) / 100))
            return lines
        finally:
            self.api.Clear()
            self.api.ClearAdaptiveClassifier()


class WindowsBackend:
    name = "Windows OCR"
    languages = "Windows profile languages"

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Windows OCR requires Windows.")
        from winrt.windows.media.ocr import OcrEngine

        self.engine = OcrEngine.try_create_from_user_profile_languages()
        self.max_image_dimension = OcrEngine.max_image_dimension
        if self.engine is None:
            raise RuntimeError("No Windows OCR language is installed.")

    def read(self, image):
        from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.foundation import AsyncStatus

        scale = min(1.0, self.max_image_dimension / max(image.shape[:2]))
        if scale < 1:
            size = tuple(max(1, round(side * scale)) for side in image.shape[:2][::-1])
            image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
        pixels = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA if image.ndim == 3 else cv2.COLOR_GRAY2BGRA)
        height, width = pixels.shape[:2]
        with SoftwareBitmap.create_copy_from_buffer(
            pixels.tobytes(), BitmapPixelFormat.BGRA8, width, height, BitmapAlphaMode.IGNORE
        ) as bitmap:
            operation = self.engine.recognize_async(bitmap)
            if operation.wait(10) == AsyncStatus.STARTED:
                operation.cancel()
                raise TimeoutError("Windows OCR timed out.")
            result = operation.get_results()
        # Windows.Media.Ocr exposes text and geometry, with no recognition score.
        return [OCRLine(line.text.strip(), None) for line in result.lines if line.text.strip()]
