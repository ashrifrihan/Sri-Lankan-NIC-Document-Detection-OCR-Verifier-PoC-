import io
import pytest
from starlette.datastructures import UploadFile
from fastapi import HTTPException
from PIL import Image
from app.main import health_check, train_analysis, validate_nic_endpoint, verify_nic
from app.core.local_model import LocalAnalysisModel
from app.core.ocr_engine import ocr_service
from app.models.schemas import TrainingFeedback, ValidateNICRequest
from uuid import UUID
from pydantic import SecretStr

def create_dummy_png(color=(200, 220, 240)):
    img = Image.new("RGB", (600, 400), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def test_health_endpoint():
    data = health_check()
    assert data["status"] == "healthy"
    assert "ocr_engine" in data

def test_validate_nic_endpoint_valid():
    req = ValidateNICRequest(nic_number="853451234V")
    res = validate_nic_endpoint(req)
    assert res.is_valid is True
    assert res.birth_year == 1985
    assert res.gender == "Male"
    assert res.decoded_dob == "1985-12-10"

def test_validate_nic_endpoint_invalid():
    req = ValidateNICRequest(nic_number="123invalid")
    res = validate_nic_endpoint(req)
    assert res.is_valid is False
    assert len(res.errors) > 0

def test_verify_endpoint_unsupported_file():
    txt_file = UploadFile(filename="test.txt", file=io.BytesIO(b"plain text content"), headers={"content-type": "text/plain"})
    with pytest.raises(HTTPException) as exc_info:
        verify_nic(front_image=txt_file)
    assert exc_info.value.status_code == 400
    assert "Unsupported file format" in exc_info.value.detail

def test_verify_endpoint_full_flow():
    png_bytes = create_dummy_png()
    img_file = UploadFile(filename="front.png", file=io.BytesIO(png_bytes), headers={"content-type": "image/png"})
    
    response = verify_nic(
        front_image=img_file,
        back_image=None,
        full_name="Kamal Perera",
        nic_number="853451234V",
        dob="1985-12-10"
    )
    assert response.request_id is not None
    assert response.front_quality.width == 600
    assert response.front_quality.height == 400
    assert "matches" in response.model_dump()
    assert response.requires_manual_review is True
    assert "experimental proof of concept" in response.disclaimer.lower()


def test_verify_with_only_an_image(monkeypatch):
    monkeypatch.setattr(ocr_service, "run_ocr", lambda _, **kwargs: (["853451234V"], 0.95, {}))
    front = UploadFile(
        file=io.BytesIO(create_dummy_png()),
        headers={"content-type": "image/png"},
    )

    response = verify_nic(front, None, None, None, None)

    assert response.matches["nic"].extracted_value == "853451234V"
    assert response.matches["dob"].extracted_value == "1985-12-10"


def test_confirmed_feedback_changes_preprocessing_for_future_uploads(monkeypatch, tmp_path):
    path = tmp_path / "analysis.sqlite3"
    model = LocalAnalysisModel(path)
    monkeypatch.setattr("app.main.local_model", model)
    preferences = []

    def read_image(_, *, compare_profiles, prefer_enhanced):
        assert compare_profiles
        preferences.append(prefer_enhanced)
        candidates = ("853451235V", "853451234V")
        return [candidates[int(prefer_enhanced)]], 0.95, {"profile_candidates": candidates}

    monkeypatch.setattr(ocr_service, "run_ocr", read_image)

    def analyze():
        front = UploadFile(
            file=io.BytesIO(create_dummy_png()),
            headers={"content-type": "image/png"},
        )
        return verify_nic(front, None, None, None, None)

    first = analyze()
    assert first.can_train and first.extracted_nic == "853451235V"
    request_id = UUID(first.request_id)
    confirmed = TrainingFeedback(nic_number="853451234V")
    assert train_analysis(request_id, confirmed) == {"saved": True}
    with pytest.raises(HTTPException) as duplicate:
        train_analysis(request_id, confirmed)
    assert duplicate.value.status_code == 409

    monkeypatch.setattr("app.main.local_model", LocalAnalysisModel(path))
    assert analyze().extracted_nic == "853451234V"
    assert preferences == [False, True]


def test_bookingpartner_api_requires_key_and_disables_local_routes(monkeypatch):
    from app.main import require_bookingpartner_key, require_local_mode, settings

    key = "test" * 16
    monkeypatch.setattr(settings, "BOOKINGPARTNER_API_KEY", None)
    require_local_mode()
    with pytest.raises(HTTPException) as disabled:
        require_bookingpartner_key(key)
    assert disabled.value.status_code == 404

    monkeypatch.setattr(settings, "BOOKINGPARTNER_API_KEY", SecretStr(key))
    require_bookingpartner_key(key)

    for invalid in (None, "wrong"):
        with pytest.raises(HTTPException) as unauthorized:
            require_bookingpartner_key(invalid)
        assert unauthorized.value.status_code == 401

    with pytest.raises(HTTPException) as local_disabled:
        require_local_mode()
    assert local_disabled.value.status_code == 404


def test_name_feedback_can_prefer_a_different_preprocessing_pass(monkeypatch, tmp_path):
    model = LocalAnalysisModel(tmp_path / "model.sqlite3")
    monkeypatch.setattr("app.main.local_model", model)
    request_id = UUID("cb0da34e-416e-4807-906b-729e29c3f174")
    model.remember(str(request_id), "sample", None, None, ("Sample Nane", "Sample Name"))

    assert train_analysis(request_id, TrainingFeedback(full_name="sample name")) == {"saved": True}
    assert model.prefers_enhanced("name:sample")
    assert not model.prefers_enhanced("sample")
    assert b"Sample Name" not in model.path.read_bytes()


def test_back_issue_date_is_not_used_as_birth_date(monkeypatch):
    reads = iter([(["853451234V"], 0.95, {}), (["Date of Issue: 2016/07/13"], 0.95, {})])
    monkeypatch.setattr(ocr_service, "run_ocr", lambda _, **kwargs: next(reads))
    front, back = [
        UploadFile(file=io.BytesIO(create_dummy_png(color)), headers={"content-type": "image/png"})
        for color in [(200, 220, 240), (210, 225, 245)]
    ]

    response = verify_nic(front, back, None, None, None)

    assert response.dob_source == "nic"
    assert response.extracted_dob == "1985-12-10"


@pytest.mark.parametrize("front_bytes, has_duplicate, message", [
    (b"unreadable", False, "could not be opened"),
    (create_dummy_png(), True, "same photo"),
])
def test_bad_photos_are_rejected_before_ocr(front_bytes, has_duplicate, message, monkeypatch):
    def unexpected_ocr(*args, **kwargs):
        pytest.fail("OCR should only run after upload validation")

    monkeypatch.setattr(ocr_service, "run_ocr", unexpected_ocr)
    headers = {"content-type": "image/png"}
    front = UploadFile(file=io.BytesIO(front_bytes), headers=headers)
    back = UploadFile(file=io.BytesIO(front_bytes), headers=headers) if has_duplicate else None
    with pytest.raises(HTTPException) as error:
        verify_nic(front, back, None, None, None)
    assert error.value.status_code == 400
    assert message in error.value.detail
