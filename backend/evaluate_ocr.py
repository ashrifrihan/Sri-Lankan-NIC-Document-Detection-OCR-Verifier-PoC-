"""Evaluate OCR on a private JSON manifest and print aggregate scores only."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.image_quality import assess_image_quality
from app.core.local_model import local_model
from app.core.ocr_engine import ocr_service


def normalize(value):
    return " ".join(value.casefold().split())


def nic_digit_confusions(expected, observed):
    """Count aligned digit substitutions without publishing complete identifiers."""
    expected = "".join(expected.upper().split())
    observed = "".join(observed.upper().split())
    if len(expected) != len(observed):
        return []
    return [
        (before, after) for before, after in zip(expected, observed)
        if before in "0123456789" and after in "0123456789" and before != after
    ]


def evaluate(manifest, split, *, use_local_model=True):
    cases = json.loads(manifest.read_text(encoding="utf-8-sig"))
    return evaluate_cases(cases, manifest.parent, split, use_local_model=use_local_model)


def evaluate_cases(cases, root, split, *, use_local_model):
    groups = {}
    for case in cases:
        group = case["card_group"]
        if groups.setdefault(group, case["split"]) != case["split"]:
            raise ValueError("Every image of the same card must belong to one split.")

    report = {"overall": {}, "by_card_type": {}, "by_quality": {}, "by_cohort": {}}
    confusions = Counter()
    for case in cases:
        if case["split"] != split:
            continue
        photo = (root / case["front"]).read_bytes()
        quality = assess_image_quality(photo)
        profile = local_model.profile(quality)
        lines, _, metadata = ocr_service.run_ocr(
            photo, compare_profiles=True,
            prefer_enhanced=use_local_model and local_model.prefers_enhanced(profile),
            prefer_enhanced_name=use_local_model and local_model.prefers_enhanced(f"name:{profile}"),
        )
        fields = {
            "nic": ocr_service.extract_nic_candidate(lines),
            "name": metadata.get("recovered_name") or ocr_service.extract_name_candidate(lines),
            "printed_dob": metadata.get("labeled_dob") or ocr_service.extract_labeled_dob(lines),
        }
        quality_labels = case.get("quality")
        if quality_labels is None:
            quality_labels = [
                label for label, flag in (
                    ("blurry", quality.is_blurry), ("low_light", quality.is_dark),
                    ("glare", quality.is_glare), ("framing", quality.is_cropped_suspected),
                ) if flag
            ] or ["clear"]
        elif isinstance(quality_labels, str):
            quality_labels = [quality_labels]
        cohorts = [
            report["overall"],
            report["by_card_type"].setdefault(case.get("card_type", "unspecified"), {}),
            *(report["by_quality"].setdefault(label, {}) for label in dict.fromkeys(quality_labels)),
        ]
        if case.get("cohort"):
            cohorts.append(report["by_cohort"].setdefault(case["cohort"], {}))
        for field, observed in fields.items():
            expected = case.get(field)
            if not expected:
                continue
            category = "unread" if not observed else "correct" if normalize(observed) == normalize(expected) else "wrong"
            if field == "nic" and category == "wrong":
                confusions.update(nic_digit_confusions(expected, observed))
            for cohort in cohorts:
                tally = cohort.setdefault(field, dict(correct=0, wrong=0, unread=0))
                tally[category] += 1
    if not report["overall"]:
        raise ValueError("The requested split has no labeled fields.")
    for cohort in [report["overall"], *(entry for group in ("by_card_type", "by_quality", "by_cohort")
                                         for entry in report[group].values())]:
        for tally in cohort.values():
            total = sum(tally.values())
            tally.update(total=total, exact_match_accuracy=tally["correct"] / total, unread_rate=tally["unread"] / total)
    report["nic_digit_confusions"] = [
        {"expected_digit": before, "observed_digit": after, "count": count}
        for (before, after), count in sorted(confusions.items())
    ]
    return report


def evaluate_synthetic():
    from generate_synthetic_samples import create_synthetic_samples

    cases = []
    for group, filename, card_type, quality, nic, name, dob in (
        ("old", "old_laminated", "old_laminated", "clear", "853451234V", "K. A. PERERA", "1985-12-11"),
        ("printed", "printed_laminated", "printed_laminated", "clear", "927891234X", "M. S. FERNANDO", "1992-10-15"),
        ("smart", "smart_card", "smart_card", "clear", "199518001234", "NIMAL SILVA", "1995-06-29"),
        ("smart", "blurry", "smart_card", "blurry", "199518001234", "NIMAL SILVA", "1995-06-29"),
        ("smart", "dark", "smart_card", "low_light", "199518001234", "NIMAL SILVA", "1995-06-29"),
    ):
        cases.append(dict(card_group=group, split="test", front=f"synthetic_{filename}.png",
                          card_type=card_type, quality=quality, nic=nic, name=name, printed_dob=dob))
    with TemporaryDirectory() as folder:
        create_synthetic_samples(folder, quiet=True)
        return evaluate_cases(cases, Path(folder), "test", use_local_model=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("manifest", type=Path, nargs="?")
    inputs.add_argument("--synthetic", action="store_true")
    parser.add_argument("--split", default="test")
    parser.add_argument("--min-nic-accuracy", type=float, help="Minimum exact-match accuracy on a 0 to 1 scale.")
    args = parser.parse_args(argv)
    if args.synthetic and args.split != "test":
        parser.error("The synthetic set only contains a test split.")
    minimum = args.min_nic_accuracy
    if minimum is not None and not 0 <= minimum <= 1:
        parser.error("--min-nic-accuracy must be between 0 and 1.")
    try:
        report = evaluate_synthetic() if args.synthetic else evaluate(args.manifest, args.split)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Evaluation failed ({type(error).__name__}). Check manifest labels, splits and image paths.", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    nic = report["overall"].get("nic")
    if minimum is not None and (nic is None or nic["exact_match_accuracy"] < minimum):
        print(f"NIC accuracy gate failed. Required at least {minimum:.1%} on labeled NICs.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
