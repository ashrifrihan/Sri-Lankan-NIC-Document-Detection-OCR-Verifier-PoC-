import json

import pytest

import evaluate_ocr
from evaluate_ocr import evaluate_cases
from generate_synthetic_samples import create_synthetic_samples


def test_metrics_include_unread_in_denominator_and_group_by_type_and_quality(monkeypatch, tmp_path):
    create_synthetic_samples(tmp_path, quiet=True)
    responses = iter([
        (["853451234V", "Name: SAMPLE PERSON", "DOB: 1985/12/10"], .9, {}),
        ([], 0, {"detected_nic": "853451235V"}),
        ([], 0, {}),
    ])
    monkeypatch.setattr(evaluate_ocr.ocr_service, "run_ocr", lambda *args, **kwargs: next(responses))
    cases = [
        dict(card_group="one", split="test", front="synthetic_smart_card.png",
             nic="853451234V", name="sample person", printed_dob="1985-12-10",
             card_type="smart_card", quality=quality)
        for quality in ("clear", "blurry", "blurry")
    ]
    report = evaluate_cases(cases, tmp_path, "test", use_local_model=False)
    overall = report["overall"]["nic"]
    assert overall == dict(correct=1, wrong=1, unread=1, total=3,
                           exact_match_accuracy=1/3, unread_rate=1/3)
    assert report["by_card_type"]["smart_card"]["nic"] == overall
    assert report["by_quality"]["blurry"]["nic"]["unread_rate"] == .5
    assert report["overall"]["name"]["correct"] == report["overall"]["printed_dob"]["correct"] == 1
    assert report["nic_digit_confusions"] == [{"expected_digit": "4", "observed_digit": "5", "count": 1}]
    assert "853451234V" not in json.dumps(report)


def test_card_group_cannot_cross_splits(tmp_path):
    cases = [dict(card_group="one", split=split) for split in ("train", "test")]
    with pytest.raises(ValueError, match="one split"):
        evaluate_cases(cases, tmp_path, "test", use_local_model=False)


@pytest.mark.parametrize(("minimum", "exit_code"), [(".8", 0), (".81", 1)])
def test_ci_gate_exit_status(monkeypatch, capsys, minimum, exit_code):
    report = {"overall": {"nic": {"exact_match_accuracy": .8}}}
    monkeypatch.setattr(evaluate_ocr, "evaluate_synthetic", lambda: report)
    assert evaluate_ocr.main(["--synthetic", "--min-nic-accuracy", minimum]) == exit_code
    captured = capsys.readouterr()
    assert json.loads(captured.out) == report
    assert ("gate failed" in captured.err) == bool(exit_code)
