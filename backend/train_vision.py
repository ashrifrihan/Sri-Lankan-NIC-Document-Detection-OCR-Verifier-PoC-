"""Train the NIC field detector or card type classifier on a private dataset."""

import argparse
from pathlib import Path

from app.core.vision_models import CARD_CLASSES, classifier_architecture, classifier_transform


def train_detector(args):
    from ultralytics import YOLO

    model = YOLO(str(args.initial_weights or "yolo11n.pt"))
    model.train(
        data=str(args.dataset.resolve()), epochs=args.epochs, device=args.device,
        imgsz=960, batch=args.batch, project=str(args.output.resolve()), name="detector",
        degrees=12, perspective=.0005, hsv_v=.25, fliplr=0, flipud=0,
        mosaic=0, plots=False,
    )
    print(f"Detector weights: {model.trainer.best}")


def train_classifier(args):
    import torch
    from torch import nn
    from torch.utils.data import DataLoader
    from torchvision import datasets, transforms

    torch.manual_seed(42)
    device = torch.device(args.device)
    preprocess = classifier_transform()
    augmented = transforms.Compose([
        transforms.RandomRotation(12),
        transforms.RandomPerspective(distortion_scale=.15, p=.3),
        transforms.ColorJitter(brightness=.3, contrast=.25),
        transforms.RandomApply([transforms.GaussianBlur(5)], p=.2),
        preprocess,
    ])
    train = datasets.ImageFolder(args.dataset / "train", transform=augmented)
    val = datasets.ImageFolder(args.dataset / "val", transform=preprocess)
    for dataset in (train, val):
        if tuple(dataset.classes) != CARD_CLASSES:
            raise ValueError(f"Expected these class folders in each split: {CARD_CLASSES}")
    train_loader = DataLoader(train, batch_size=args.batch, shuffle=True)
    val_loader = DataLoader(val, batch_size=args.batch)
    model = classifier_architecture().to(device)
    if args.initial_weights:
        model.load_state_dict(torch.load(args.initial_weights, map_location=device, weights_only=True))
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
    loss = nn.CrossEntropyLoss()
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / "classifier.pt"
    best = -1
    for epoch in range(args.epochs):
        model.train()
        for images, labels in train_loader:
            optimizer.zero_grad()
            loss(model(images.to(device)), labels.to(device)).backward()
            optimizer.step()
        model.eval()
        correct = 0
        with torch.inference_mode():
            for images, labels in val_loader:
                correct += int((model(images.to(device)).argmax(1).cpu() == labels).sum())
        print(f"Epoch {epoch + 1}: validation exact matches {correct}/{len(val)}")
        if correct > best:
            best = correct
            torch.save(model.state_dict(), output)
    print(f"Classifier weights: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=("detector", "classifier"))
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--initial-weights", type=Path)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch < 1:
        parser.error("--epochs and --batch must be positive.")
    (train_detector if args.task == "detector" else train_classifier)(args)
