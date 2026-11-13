import cv2
import numpy as np

from app.core.classifier import classify_sri_lankan_nic
from app.config import settings
from app.core.ocr_backends import OCRLine
from app.core.ocr_engine import OCREngine
from app.core.vision_models import select_crops, vision_models
from app.models.schemas import DocumentCategory, DocumentClassificationType


def test_detector_crops_clip_image_and_skip_other_cards_fields():
    image = np.zeros((80, 100, 3), dtype=np.uint8)
    crops = select_crops(image, [
        ((-5, 10, 60, 90), 0, .9),
        ((71, 12, 95, 21), 1, .95),
        ((5, 20, 25, 26), 1, .8),
        ((0, 0, 20, 10), 9, .99),
    ])
    assert crops["card"].shape == (70, 60, 3)
    assert crops["nic_number"].shape == (6, 20, 3)
    assert set(crops) == {"card", "nic_number"}


def test_ocr_prefers_detected_fields_and_surfaces_conflict(monkeypatch):
    image = np.zeros((100, 160, 3), dtype=np.uint8)
    crops = {
        "card": image,
        "nic_number": np.full((12, 70, 3), 1, dtype=np.uint8),
        "name": np.full((12, 71, 3), 2, dtype=np.uint8),
        "dob": np.full((12, 72, 3), 3, dtype=np.uint8),
    }
    monkeypatch.setattr(vision_models, "detect", lambda _: crops)
    monkeypatch.setattr(vision_models, "classify", lambda _: ("printed_laminated", .93))
    engine = OCREngine("paddle")
    monkeypatch.setattr(engine, "_enhance", lambda crop: crop)

    def recognize(crop, *, nic_field=False):
        values = {1: "853451235V", 2: "SAMPLE PERSON", 3: "1985/12/10"}
        if crop.shape[0] < 100:
            return "PaddleOCR", [OCRLine(values[int(crop[0, 0, 0])], .9)]
        return "PaddleOCR", [OCRLine(text, .9) for text in (
            "SRI LANKA NATIONAL IDENTITY CARD", "853451234V", "FULL NAME: OTHER PERSON",
        )]

    monkeypatch.setattr(engine, "_recognize", recognize)
    _, encoded = cv2.imencode(".png", image)
    lines, _, metadata = engine.run_ocr(encoded.tobytes())
    assert metadata["detected_nic"] == "853451235V"
    assert set(metadata["alternate_nic_reads"]) == {"853451234V", "853451235V"}
    assert metadata["recovered_name"] == "SAMPLE PERSON"
    assert metadata["labeled_dob"] == "1985-12-10"
    assert {"nic", "name"} <= metadata["field_warnings"].keys()
    result = classify_sri_lankan_nic(encoded.tobytes(), lines, visual_prediction=metadata["visual_prediction"])
    assert result.visual_category == DocumentCategory.PRINTED_LAMINATED
    assert result.is_provisional


def test_classifier_disagreement_stays_uncertain():
    _, encoded = cv2.imencode(".png", np.zeros((30, 50, 3), dtype=np.uint8))
    result = classify_sri_lankan_nic(encoded.tobytes(), ["853451234V"], visual_prediction=("not_nic", .98))
    assert result.classification == DocumentClassificationType.UNCERTAIN


def test_missing_weights_keep_heuristic_classification(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "NIC_CLASSIFIER_WEIGHTS", str(tmp_path / "missing.pt"))
    monkeypatch.setattr(settings, "NIC_DETECTOR_WEIGHTS", str(tmp_path / "missing.pt"))
    image = np.zeros((30, 50, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", image)
    assert vision_models.detect(image) == {}
    result = classify_sri_lankan_nic(encoded.tobytes(), ["SRI LANKA NATIONAL IDENTITY CARD", "853451234V"])
    assert result.classification == DocumentClassificationType.SRI_LANKAN_NIC
    assert "yellow_ochre_ratio" in result.visual_signals
