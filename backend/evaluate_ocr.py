"""Evaluate OCR on a private JSON manifest and print aggregate scores only."""

import argparse
import json
from pathlib import Path

from app.core.image_quality import assess_image_quality
from app.core.local_model import local_model
from app.core.ocr_engine import ocr_service


def normalize(value):
    return " ".join(value.casefold().split())


def evaluate(manifest, split):
    cases = json.loads(manifest.read_text(encoding="utf-8-sig"))
    groups = {}
    for case in cases:
        group = case["card_group"]
        if groups.setdefault(group, case["split"]) != case["split"]:
            raise ValueError("Every image of the same card must belong to one split.")

    counts = {}
    for case in cases:
        if case["split"] != split:
            continue
        photo = (manifest.parent / case["front"]).read_bytes()
        profile = local_model.profile(assess_image_quality(photo))
        lines, _, metadata = ocr_service.run_ocr(
            photo, compare_profiles=True,
            prefer_enhanced=local_model.prefers_enhanced(profile),
            prefer_enhanced_name=local_model.prefers_enhanced(f"name:{profile}"),
        )
        fields = {
            "nic": metadata.get("detected_nic") or ocr_service.extract_nic_candidate(lines),
            "name": metadata.get("recovered_name") or ocr_service.extract_name_candidate(lines),
            "printed_dob": metadata.get("labeled_dob") or ocr_service.extract_labeled_dob(lines),
        }
        for field, observed in fields.items():
            expected = case.get(field)
            if not expected:
                continue
            category = "unread" if not observed else "correct" if normalize(observed) == normalize(expected) else "wrong"
            for cohort in {"all", case.get("cohort", "unspecified")}:
                tally = counts.setdefault(cohort, {}).setdefault(field, dict(correct=0, wrong=0, unread=0))
                tally[category] += 1
    if not counts:
        raise ValueError("The requested split has no labeled fields.")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--split", default="test")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.manifest, args.split), indent=2))
