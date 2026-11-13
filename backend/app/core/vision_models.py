"""Optional, process-local card detector and classifier."""

from math import ceil, floor, isfinite
from pathlib import Path
from threading import Lock

import cv2
from PIL import Image

from ..config import settings
from ..utils.privacy import get_sanitized_logger

DETECTION_CLASSES = ("card", "nic_number", "name", "dob", "photo", "chip")
CARD_CLASSES = ("not_nic", "old_laminated", "printed_laminated", "smart_card")
logger = get_sanitized_logger("vision_models")


def classifier_architecture():
    from torch import nn
    from torchvision.models import mobilenet_v3_small

    model = mobilenet_v3_small(weights=None)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(CARD_CLASSES))
    return model


def classifier_transform():
    from torchvision import transforms

    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize((.485, .456, .406), (.229, .224, .225)),
    ])


class VisionModels:
    def __init__(self):
        self.lock = Lock()
        self.models = {}

    def warmup(self):
        for kind, path in (("detector", settings.NIC_DETECTOR_WEIGHTS),
                           ("classifier", settings.NIC_CLASSIFIER_WEIGHTS)):
            if path:
                try:
                    self._load(kind, path)
                except Exception as error:
                    logger.warning("Vision model %s could not initialize (%s)", kind, type(error).__name__)

    def _load(self, kind, path):
        if kind not in self.models:
            if not Path(path).is_file():
                raise FileNotFoundError("Configured model weights are missing.")
            if kind == "detector":
                from ultralytics import YOLO

                model = YOLO(path, task="detect")
                if tuple(model.names[i] for i in range(len(model.names))) != DETECTION_CLASSES:
                    raise ValueError("Detector class order does not match the NIC dataset.")
                self.models[kind] = model
            else:
                import torch

                model = classifier_architecture()
                model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
                self.models[kind] = (model.eval(), classifier_transform())
        return self.models[kind]

    def detect(self, image):
        path = settings.NIC_DETECTOR_WEIGHTS
        if not path:
            return {}
        try:
            with self.lock:
                model = self._load("detector", path)
                result = model.predict(image, device="cpu", imgsz=960, conf=.4, save=False, verbose=False)[0]
                xyxy = result.boxes.xyxy.tolist()
                classes = result.boxes.cls.tolist()
                scores = result.boxes.conf.tolist()
            return select_crops(image, zip(xyxy, classes, scores))
        except Exception as error:
            logger.warning("Card detector unavailable (%s)", type(error).__name__)
            return {}

    def classify(self, image):
        path = settings.NIC_CLASSIFIER_WEIGHTS
        if not path:
            return None
        try:
            import torch

            rgb = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            with self.lock, torch.inference_mode():
                model, transform = self._load("classifier", path)
                probability, label = model(transform(rgb).unsqueeze(0)).softmax(dim=1)[0].max(dim=0)
            score = probability.item()
            return (CARD_CLASSES[label.item()], score) if isfinite(score) else None
        except Exception as error:
            logger.warning("Card classifier unavailable (%s)", type(error).__name__)
            return None


def select_crops(image, detections):
    """Clip boxes and keep the best card and fields whose centers lie inside it."""
    height, width = image.shape[:2]
    boxes = []
    for coordinates, class_id, score in detections:
        if not all(isfinite(value) for value in (*coordinates, class_id, score)):
            continue
        index = int(class_id)
        if not 0 <= index < len(DETECTION_CLASSES):
            continue
        x1, y1, x2, y2 = coordinates
        bounds = max(0, floor(x1)), max(0, floor(y1)), min(width, ceil(x2)), min(height, ceil(y2))
        if bounds[0] < bounds[2] and bounds[1] < bounds[3]:
            boxes.append((score, DETECTION_CLASSES[index], bounds))
    boxes.sort(key=lambda box: box[0], reverse=True)
    card = next((bounds for _, label, bounds in boxes if label == "card"), None)
    crops = {}
    for _, label, (x1, y1, x2, y2) in boxes:
        if card and label != "card":
            center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
            if not (card[0] <= center_x <= card[2] and card[1] <= center_y <= card[3]):
                continue
        crops.setdefault(label, image[y1:y2, x1:x2])
    return crops


vision_models = VisionModels()
