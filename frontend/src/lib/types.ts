export type NICFormat = 'old_9_digit' | 'new_12_digit' | 'invalid';
export type Gender = 'Male' | 'Female' | 'Unknown';
export type VoterStatus = 'Eligible' | 'Ineligible' | 'Not Applicable (New 12-Digit Format)';
export type DocumentCategory = 'old_laminated' | 'printed_laminated' | 'newer_plastic_card' | 'uncertain';
export type DocumentClassificationType = 'sri_lankan_nic' | 'not_nic' | 'uncertain';
export type MatchStatus = 'match' | 'partial_match' | 'mismatch' | 'uncertain' | 'unavailable';

export interface NICValidationResult {
  is_valid: boolean;
  nic_number: string;
  format: NICFormat;
  birth_year?: number;
  day_of_year?: number;
  decoded_dob?: string;
  gender: Gender;
  voter_status: VoterStatus;
  serial_number?: string;
  check_digit?: string;
  equivalent_alternate_format?: string;
  errors: string[];
  warnings: string[];
}

export interface ImageQualityAssessment {
  is_acceptable: boolean;
  blur_score: number;
  is_blurry: boolean;
  brightness_score: number;
  is_dark: boolean;
  is_glare: boolean;
  aspect_ratio: number;
  is_cropped_suspected: boolean;
  width: number;
  height: number;
  recommendations: string[];
}

export interface DocumentClassification {
  classification: DocumentClassificationType;
  visual_category: DocumentCategory;
  confidence: number;
  is_provisional: boolean;
  visual_signals: Record<string, any>;
  ocr_evidence: string[];
  notes: string[];
}

export interface FieldMatchResult {
  status: MatchStatus;
  form_value?: string;
  extracted_value?: string;
  confidence: number;
  reason: string;
}

export interface VerificationResponse {
  can_train: boolean;
  request_id: string;
  processed_at: string;
  front_quality: ImageQualityAssessment;
  back_quality?: ImageQualityAssessment;
  front_classification: DocumentClassification;
  extracted_nic?: string;
  nic_validation?: NICValidationResult;
  extracted_name?: string;
  extracted_dob?: string;
  dob_source?: 'card' | 'nic' | null;
  field_warnings?: Record<string, string>;
  alternate_nic_reads?: string[];
  review_status?: 'readable' | 'retake_needed' | 'manual_review';
  back_barcode?: {
    status: 'unread' | 'decoded' | 'ambiguous' | 'unavailable';
    format: 'PDF417' | null;
    nic_match: 'match' | 'mismatch' | 'unavailable';
  } | null;
  matches: {
    nic: FieldMatchResult;
    name: FieldMatchResult;
    dob: FieldMatchResult;
  };
  overall_assessment: string;
  user_guidance: string[];
  disclaimer: string;
  requires_manual_review: boolean;
}
