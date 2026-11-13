import uuid
from collections import deque
from secrets import compare_digest
from threading import Lock
from time import monotonic
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, FastAPI, Header, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.formparsers import MultiPartParser

from .config import settings
from .utils.privacy import get_sanitized_logger
from .models.schemas import (
    VerificationResponse,
    BookingPartnerReview,
    ValidateNICRequest,
    TrainingFeedback,
    NICValidationResult,
    DocumentClassificationType,
    FieldMatchResult,
    MatchStatus
)
from .core.image_quality import assess_image_quality
from .core.ocr_engine import ocr_service
from .core.classifier import classify_sri_lankan_nic
from .core.nic_parser import parse_sri_lankan_nic
from .core.matcher import compare_nic, compare_dob, compare_names
from .core.local_model import local_model

logger = get_sanitized_logger("main")
# SpooledTemporaryFile treats zero as disabling automatic disk rollover.
MultiPartParser.spool_max_size = 0
MultiPartParser.max_file_size = 0  # Starlette versions before the attribute rename.
booking_requests = deque()
booking_lock = Lock()
booking_in_flight: set[str] = set()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Sri Lankan NIC Document Detection and OCR Testing Proof of Concept"
)

# Restrict CORS to localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    """System health check and OCR engine status."""
    engine = ocr_service.active_engine
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ocr_engine": engine.name if engine else "Not initialized",
        "ocr_language": engine.languages if engine else None,
        "ocr_backend_config": settings.OCR_BACKEND,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/api/validate-nic", response_model=NICValidationResult)
def validate_nic_endpoint(payload: ValidateNICRequest):
    """
    Live NIC validation endpoint.
    Decodes Sri Lankan 9-digit (old) and 12-digit (new) formats,
    calculates encoded birth date, gender, voter status, and format equivalence.
    """
    logger.info("Validating NIC structure")
    return parse_sri_lankan_nic(payload.nic_number)


def require_local_mode():
    if settings.BOOKINGPARTNER_API_KEY is not None:
        raise HTTPException(404, "Route unavailable.")


def require_bookingpartner_key(x_api_key: str | None = Header(None)):
    configured_key = settings.BOOKINGPARTNER_API_KEY
    if configured_key is None:
        raise HTTPException(404, "Route unavailable.")
    keys = (configured_key, settings.BOOKINGPARTNER_PREVIOUS_API_KEY)
    if x_api_key is None or not any(compare_digest(x_api_key.encode(), key.get_secret_value().encode())
                                  for key in keys if key is not None):
        raise HTTPException(401, "Invalid API key.")


@app.middleware("http")
async def bookingpartner_upload_limits(request: Request, call_next):
    if request.method == "POST" and request.url.path.rstrip("/") == "/api/v1/bookingpartner/verify":
        try:
            require_bookingpartner_key(request.headers.get("x-api-key"))
        except HTTPException as error:
            return JSONResponse({"detail": error.detail}, status_code=error.status_code)
        length = request.headers.get("content-length")
        if length and length.isdecimal() and int(length) > 2 * settings.MAX_FILE_SIZE_BYTES + 64 * 1024:
            return JSONResponse({"detail": "Upload is too large."}, status_code=413)
        upload_id = request.headers.get("idempotency-key")
        if upload_id and (len(upload_id) > 128 or not upload_id.isascii()):
            return JSONResponse({"detail": "Invalid Idempotency-Key."}, status_code=400)
        with booking_lock:
            now = monotonic()
            while booking_requests and now - booking_requests[0] >= 60:
                booking_requests.popleft()
            if len(booking_requests) >= settings.BOOKINGPARTNER_REQUESTS_PER_MINUTE:
                return JSONResponse({"detail": "Too many uploads."}, status_code=429, headers={"Retry-After": "60"})
            if upload_id and upload_id in booking_in_flight:
                return JSONResponse({"detail": "This upload is already being processed."}, status_code=409)
            booking_requests.append(now)
            if upload_id:
                booking_in_flight.add(upload_id)
        try:
            return await call_next(request)
        finally:
            if upload_id:
                with booking_lock:
                    booking_in_flight.discard(upload_id)
    return await call_next(request)


@app.post("/api/train/{request_id}", dependencies=[Depends(require_local_mode)])
def train_analysis(request_id: uuid.UUID, payload: TrainingFeedback):
    confirmed = "".join((payload.nic_number or "").upper().split())
    name = (payload.full_name or "").strip()
    if confirmed and not parse_sri_lankan_nic(confirmed).is_valid:
        raise HTTPException(400, "Enter the valid NIC number printed on the card.")
    if not (confirmed or name) or len(name) > 180 or (name and not any(ch.isalpha() for ch in name)):
        raise HTTPException(400, "Enter a confirmed NIC number or full name from the card.")
    if not local_model.learn(str(request_id), confirmed, name):
        raise HTTPException(409, "This result is no longer available for training. Analyze the photo again.")
    return {"saved": True}

@app.post("/api/verify", response_model=VerificationResponse, dependencies=[Depends(require_local_mode)])
def verify_nic(
    front_image: UploadFile = File(..., description="Front image of the NIC document"),
    back_image: Optional[UploadFile] = File(None, description="Optional back image of the NIC document"),
    full_name: Optional[str] = Form(None, description="Owner full name from form"),
    nic_number: Optional[str] = Form(None, description="Owner NIC number from form"),
    dob: Optional[str] = Form(None, description="Owner date of birth (YYYY-MM-DD) from form")
):
    """
    Core document processing pipeline:
    1. Validation of image MIME and file size
    2. Image quality assessment (blur, lighting, cropping)
    3. Conservative document classification & visual category detection
    4. Text extraction using OCR with script awareness
    5. Sri Lankan NIC numbering validation and DOB decoding
    6. Field-by-field normalization and comparison
    7. User-friendly guidance and strict disclaimer
    """
    request_id = str(uuid.uuid4())
    logger.info("Processing verification request %s", request_id)

    # 1. Validate front image file size and MIME type
    if front_image.content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{front_image.content_type}'. Please upload JPEG, PNG, or WebP."
        )

    front_bytes = front_image.file.read(settings.MAX_FILE_SIZE_BYTES + 1)
    if len(front_bytes) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Front image exceeds maximum allowed size of {settings.MAX_FILE_SIZE_BYTES // (1024*1024)}MB."
        )

    back_bytes: Optional[bytes] = None
    if back_image:
        if back_image.content_type not in settings.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported back image format '{back_image.content_type}'."
            )
        back_bytes = back_image.file.read(settings.MAX_FILE_SIZE_BYTES + 1)
        if len(back_bytes) > settings.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Back image exceeds maximum allowed size of 10MB."
            )
        if front_bytes == back_bytes:
            raise HTTPException(400, "The front and back uploads are the same photo. Upload each side once.")

    # 2. Assess Image Quality (Front Image)
    front_quality = assess_image_quality(front_bytes)
    back_quality = assess_image_quality(back_bytes) if back_bytes else None
    if front_quality.width == 0 or (back_quality and back_quality.width == 0):
        raise HTTPException(400, "An uploaded image could not be opened. Choose a readable JPEG, PNG, or WebP photo.")

    # 3. Run OCR Text Extraction
    profile = local_model.profile(front_quality)
    ocr_lines, ocr_conf, ocr_meta = ocr_service.run_ocr(
        front_bytes,
        compare_profiles=settings.BOOKINGPARTNER_API_KEY is None,
        prefer_enhanced=local_model.prefers_enhanced(profile),
        **({"prefer_enhanced_name": True} if local_model.prefers_enhanced(f"name:{profile}") else {}),
    )
    candidates = ocr_meta.get("profile_candidates")
    can_train = candidates is not None and settings.BOOKINGPARTNER_API_KEY is None
    if can_train:
        local_model.remember(request_id, profile, *candidates, ocr_meta.get("name_candidates", (None, None)))
    extracted_name = ocr_meta.get("recovered_name") or ocr_service.extract_name_candidate(ocr_lines)
    extracted_nic = ocr_meta.get("detected_nic") or ocr_service.extract_nic_candidate(ocr_lines)
    extracted_dob = ocr_meta.get("labeled_dob") or ocr_service.extract_labeled_dob(ocr_lines)
    front_text = " ".join(ocr_lines).casefold()
    front_looks_like_back = "address" in front_text and ("date of issue" in front_text or "commissioner general" in front_text)
    back_looks_like_front = False
    if back_bytes:
        back_lines, _, _ = ocr_service.run_ocr(back_bytes)
        back_text = " ".join(back_lines).casefold()
        back_looks_like_front = "identity card" in back_text and ("holder" in back_text or "date of birth" in back_text)
        # A back-side issue date can look like a birth date. Require an explicit label.
        extracted_dob = extracted_dob or ocr_service.extract_labeled_dob(back_lines)
        if not extracted_name and extracted_nic and extracted_nic.endswith(("V", "X")):
            extracted_name = ocr_service.extract_name_candidate(back_lines, require_label=True)

    # 4. Conservative Document Classifier
    classification = classify_sri_lankan_nic(
        front_bytes, ocr_lines,
        visual_prediction=ocr_meta.get("visual_prediction"),
        selected_nic=extracted_nic,
    )

    # 5. Extract Candidates from OCR

    # 6. Validate Extracted / Form NIC with Sri Lankan Rules
    nic_validation: Optional[NICValidationResult] = None
    target_nic_for_validation = extracted_nic or nic_number
    if target_nic_for_validation:
        nic_validation = parse_sri_lankan_nic(target_nic_for_validation)

    # 7. Field-by-Field Matching
    encoded_dob = nic_validation.decoded_dob if (nic_validation and nic_validation.is_valid) else None
    field_warnings = ocr_meta.get("field_warnings", {})
    scores = ocr_meta.get("line_confidences", [])
    if "detected_nic_confidence" in ocr_meta:
        score = ocr_meta["detected_nic_confidence"]
        if score is None or score < settings.OCR_REVIEW_CONFIDENCE:
            field_warnings.setdefault("nic", "OCR confidence is low or unavailable. Check the number against the card.")
    if extracted_nic and scores and (
        any(score is None for score in scores) or ocr_conf < settings.OCR_REVIEW_CONFIDENCE
        or any(extracted_nic in "".join(line.upper().split()) and score < settings.OCR_REVIEW_CONFIDENCE
               for line, score in zip(ocr_lines, scores) if score is not None)
    ):
        field_warnings.setdefault("nic", "OCR confidence is low or unavailable. Check the number against the card.")
    if extracted_dob and extracted_nic and encoded_dob and extracted_dob != encoded_dob:
        field_warnings["dob"] = "The date read from the card differs from the date encoded in the NIC. Check both fields."

    nic_match = compare_nic(nic_number, extracted_nic)
    dob_match = compare_dob(dob, extracted_dob, encoded_dob)
    name_match = compare_names(full_name, extracted_name)

    matches = {
        "nic": nic_match,
        "name": name_match,
        "dob": dob_match
    }

    # 8. User Guidance Recommendations
    guidance = []
    if front_looks_like_back:
        guidance.append("The front upload appears to show the back. Check the side and upload the front of the card.")
    if back_looks_like_front:
        guidance.append("The back upload appears to show a front. Check that you uploaded one photo of each side.")
    if front_quality.recommendations:
        guidance.extend(front_quality.recommendations)

    if back_quality and back_quality.recommendations:
        guidance.extend([f"Back image: {r}" for r in back_quality.recommendations])

    if classification.classification == DocumentClassificationType.NOT_NIC:
        guidance.append("The uploaded image does not appear to show a valid Sri Lankan National Identity Card. Please upload an official NIC.")
    elif classification.classification == DocumentClassificationType.UNCERTAIN:
        guidance.append("Document classification is uncertain. Ensure the card is resting flat on a plain background with even lighting.")

    if not extracted_nic:
        guidance.append("Could not read NIC number clearly from the document. Please ensure the card text is sharp and free of glare.")
    if not extracted_name and extracted_nic:
        if extracted_nic.endswith(("V", "X")) and not back_bytes:
            guidance.append("Upload the back of the laminated NIC to read the full name if it is printed there.")
        else:
            guidance.append("Could not read the full name clearly. Upload a sharper photo with the name in focus.")

    # 9. Overall Assessment Summary
    has_form_input = bool(nic_number or full_name or dob)
    if not front_quality.is_acceptable:
        overall_assessment = "Low Image Quality - Image re-upload recommended before processing."
    elif classification.classification == DocumentClassificationType.NOT_NIC:
        overall_assessment = "Document Rejected - Image does not match Sri Lankan NIC characteristics."
    elif not has_form_input and (extracted_nic or extracted_name):
        overall_assessment = "Document Successfully Extracted - Data read by OCR. Enter form values to test matching."
    elif nic_match.status == MatchStatus.MATCH and (name_match.status in [MatchStatus.MATCH, MatchStatus.PARTIAL_MATCH]):
        overall_assessment = "Provisional Document Match - Document appears consistent with input data. Manual review required."
    elif nic_match.status == MatchStatus.MISMATCH:
        overall_assessment = "Data Discrepancy - Extracted NIC number does not match form entry."
    else:
        overall_assessment = "Provisional Review Required - Additional verification or clearer document required."

    disclaimer = (
        "IMPORTANT NOTICE: This is an experimental proof of concept for document detection and OCR testing. "
        "It is NOT a certified or legally binding identity verification system. Results are provisional and heuristic. "
        "Never claim an uploaded document is genuine or the owner's identity is verified solely from automated OCR. "
        "All decisions must be subject to authorized administrative and manual review."
    )

    review_status = "readable"
    if not front_quality.is_acceptable or not extracted_nic or front_looks_like_back or back_looks_like_front:
        review_status = "retake_needed"
    elif (
        field_warnings or not extracted_name or not nic_validation or not nic_validation.is_valid
        or classification.classification != DocumentClassificationType.SRI_LANKAN_NIC
        or any(match.status == MatchStatus.MISMATCH for match in matches.values())
    ):
        review_status = "manual_review"

    response = VerificationResponse(
        request_id=request_id,
        processed_at=datetime.now(timezone.utc).isoformat(),
        can_train=can_train,
        front_quality=front_quality,
        back_quality=back_quality,
        front_classification=classification,
        extracted_nic=extracted_nic,
        nic_validation=nic_validation,
        extracted_name=extracted_name,
        extracted_dob=extracted_dob or (encoded_dob if extracted_nic else None),
        dob_source="card" if extracted_dob else "nic" if extracted_nic and encoded_dob else None,
        field_warnings=field_warnings,
        alternate_nic_reads=ocr_meta.get("alternate_nic_reads", []) if settings.BOOKINGPARTNER_API_KEY is None else [],
        review_status=review_status,
        matches=matches,
        overall_assessment=overall_assessment,
        user_guidance=guidance,
        disclaimer=disclaimer,
        requires_manual_review=True
    )

    return response


@app.post("/api/v1/bookingpartner/verify", response_model=BookingPartnerReview,
          dependencies=[Depends(require_bookingpartner_key)])
def verify_bookingpartner(
    front_image: UploadFile = File(...),
    back_image: Optional[UploadFile] = File(None),
    full_name: Optional[str] = Form(None),
    nic_number: Optional[str] = Form(None),
    dob: Optional[str] = Form(None),
):
    result = verify_nic(front_image, back_image, full_name, nic_number, dob)
    return BookingPartnerReview(
        request_id=result.request_id,
        review_status=result.review_status,
        requires_manual_review=result.requires_manual_review,
        dob_source=result.dob_source,
        field_warnings=result.field_warnings,
        match_statuses={field: match.status for field, match in result.matches.items()},
    )
