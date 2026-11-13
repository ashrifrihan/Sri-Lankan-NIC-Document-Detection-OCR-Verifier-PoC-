from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class NICFormat(str, Enum):
    OLD_9_DIGIT = "old_9_digit"
    NEW_12_DIGIT = "new_12_digit"
    INVALID = "invalid"

class Gender(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    UNKNOWN = "Unknown"

class VoterStatus(str, Enum):
    ELIGIBLE = "Eligible"
    INELIGIBLE = "Ineligible"
    NOT_APPLICABLE = "Not Applicable (New 12-Digit Format)"

class DocumentCategory(str, Enum):
    OLD_LAMINATED = "old_laminated"
    PRINTED_LAMINATED = "printed_laminated"
    NEWER_PLASTIC_CARD = "newer_plastic_card"
    UNCERTAIN = "uncertain"

class DocumentClassificationType(str, Enum):
    SRI_LANKAN_NIC = "sri_lankan_nic"
    NOT_NIC = "not_nic"
    UNCERTAIN = "uncertain"

class MatchStatus(str, Enum):
    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    MISMATCH = "mismatch"
    UNCERTAIN = "uncertain"
    UNAVAILABLE = "unavailable"

class NICValidationResult(BaseModel):
    is_valid: bool
    nic_number: str
    format: NICFormat
    birth_year: Optional[int] = None
    day_of_year: Optional[int] = None
    decoded_dob: Optional[str] = None  # YYYY-MM-DD
    gender: Gender = Gender.UNKNOWN
    voter_status: VoterStatus = VoterStatus.NOT_APPLICABLE
    serial_number: Optional[str] = None
    check_digit: Optional[str] = None
    equivalent_alternate_format: Optional[str] = None
    errors: List[str] = []
    warnings: List[str] = []

class ImageQualityAssessment(BaseModel):
    is_acceptable: bool
    blur_score: float
    is_blurry: bool
    brightness_score: float
    is_dark: bool
    is_glare: bool
    aspect_ratio: float
    is_cropped_suspected: bool
    width: int
    height: int
    recommendations: List[str] = []

class DocumentClassification(BaseModel):
    classification: DocumentClassificationType
    visual_category: DocumentCategory
    confidence: float
    is_provisional: bool = True  # Heuristic classification, not certified ML model
    visual_signals: Dict[str, Any] = {}
    ocr_evidence: List[str] = []
    notes: List[str] = []

class FieldMatchResult(BaseModel):
    status: MatchStatus
    form_value: Optional[str] = None
    extracted_value: Optional[str] = None
    confidence: float = 0.0
    reason: str

class VerificationResponse(BaseModel):
    request_id: str
    can_train: bool = False
    dob_source: Optional[str] = None
    field_warnings: Dict[str, str] = {}
    alternate_nic_reads: List[str] = []
    review_status: Optional[str] = None
    processed_at: str
    front_quality: ImageQualityAssessment
    back_quality: Optional[ImageQualityAssessment] = None
    front_classification: DocumentClassification
    extracted_nic: Optional[str] = None
    nic_validation: Optional[NICValidationResult] = None
    extracted_name: Optional[str] = None
    extracted_dob: Optional[str] = None
    matches: Dict[str, FieldMatchResult]
    overall_assessment: str
    user_guidance: List[str]
    disclaimer: str
    requires_manual_review: bool = True

class ValidateNICRequest(BaseModel):
    nic_number: str


class BookingPartnerReview(BaseModel):
    request_id: str
    review_status: str
    requires_manual_review: bool
    dob_source: Optional[str] = None
    field_warnings: Dict[str, str]
    match_statuses: Dict[str, MatchStatus]


class TrainingFeedback(BaseModel):
    nic_number: Optional[str] = None
    full_name: Optional[str] = None
