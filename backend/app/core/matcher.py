import re
from difflib import SequenceMatcher
from datetime import datetime
from typing import Optional, List, Tuple
from ..models.schemas import FieldMatchResult, MatchStatus
from .nic_parser import parse_sri_lankan_nic, are_nics_equivalent

def normalize_text(text: str) -> str:
    """Removes punctuation and normalizes spacing to lower case."""
    if not text:
        return ""
    clean = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", clean).strip().lower()

def compare_nic(form_nic: Optional[str], extracted_nic: Optional[str]) -> FieldMatchResult:
    """
    Compares the user-submitted NIC with the OCR-extracted NIC number.
    Supports equivalent matching between 9-digit old format and 12-digit new format.
    """
    if not extracted_nic:
        return FieldMatchResult(
            status=MatchStatus.UNAVAILABLE,
            form_value=form_nic,
            extracted_value=None,
            confidence=0.0,
            reason="NIC number could not be clearly extracted from the uploaded document image."
        )

    clean_extracted = re.sub(r"[\s\-]", "", extracted_nic).upper()
    if not form_nic:
        return FieldMatchResult(
            status=MatchStatus.UNAVAILABLE,
            form_value=None,
            extracted_value=clean_extracted,
            confidence=0.0,
            reason=f"Extracted '{clean_extracted}' from document. Form was left blank, so comparison could not be performed."
        )

    clean_form = re.sub(r"[\s\-]", "", form_nic).upper()

    # Exact string match
    if clean_form == clean_extracted:
        return FieldMatchResult(
            status=MatchStatus.MATCH,
            form_value=clean_form,
            extracted_value=clean_extracted,
            confidence=1.0,
            reason="Exact NIC number match."
        )

    # Format-aware equivalence match (e.g. 853451234V vs 198534501234)
    if are_nics_equivalent(clean_form, clean_extracted):
        return FieldMatchResult(
            status=MatchStatus.MATCH,
            form_value=clean_form,
            extracted_value=clean_extracted,
            confidence=0.95,
            reason="NIC matched via Sri Lankan cross-generation format equivalence (old 9-digit <-> new 12-digit)."
        )

    # Check for minor OCR character confusion (e.g. 'O' vs '0', 'I' vs '1')
    sim = SequenceMatcher(None, clean_form, clean_extracted).ratio()
    if sim >= 0.85:
        return FieldMatchResult(
            status=MatchStatus.UNCERTAIN,
            form_value=clean_form,
            extracted_value=clean_extracted,
            confidence=round(sim, 2),
            reason=f"High similarity ({round(sim*100)}%), but slight character discrepancy observed. Possible OCR noise."
        )

    return FieldMatchResult(
        status=MatchStatus.MISMATCH,
        form_value=clean_form,
        extracted_value=clean_extracted,
        confidence=0.0,
        reason="NIC number extracted from document does not match the provided form value."
    )

def compare_dob(
    form_dob: Optional[str],
    extracted_dob: Optional[str],
    encoded_dob_from_nic: Optional[str]
) -> FieldMatchResult:
    """
    Compares Date of Birth across three sources:
    1. User form input (YYYY-MM-DD)
    2. OCR-extracted text date
    3. Algorithmically decoded DOB from validated NIC number
    """
    target_date = extracted_dob or encoded_dob_from_nic
    if not form_dob:
        return FieldMatchResult(
            status=MatchStatus.UNAVAILABLE,
            form_value=None,
            extracted_value=target_date,
            confidence=0.0,
            reason="Date of birth was left blank in the form."
        )

    clean_form = form_dob.strip()

    if not target_date:
        return FieldMatchResult(
            status=MatchStatus.UNAVAILABLE,
            form_value=clean_form,
            extracted_value=None,
            confidence=0.0,
            reason="Date of birth could not be extracted from document text or decoded from NIC."
        )

    # Direct match with extracted text or encoded NIC
    if clean_form == target_date:
        source_note = "extracted document text" if (extracted_dob and clean_form == extracted_dob) else "encoded NIC birth date"
        return FieldMatchResult(
            status=MatchStatus.MATCH,
            form_value=clean_form,
            extracted_value=target_date,
            confidence=1.0,
            reason=f"Exact date of birth match with {source_note}."
        )

    # Check 1-day tolerance for Sri Lankan DRP 366-day non-leap-year convention
    try:
        dt_form = datetime.strptime(clean_form, "%Y-%m-%d").date()
        dt_target = datetime.strptime(target_date, "%Y-%m-%d").date()
        diff_days = abs((dt_form - dt_target).days)
        if diff_days <= 1 and dt_form.year == dt_target.year:
            return FieldMatchResult(
                status=MatchStatus.MATCH,
                form_value=clean_form,
                extracted_value=target_date,
                confidence=0.92,
                reason="Match within Sri Lankan DRP leap-year convention tolerance (1 day offset in non-leap year)."
            )
    except Exception:
        pass

    # Compare birth year only
    if clean_form[:4] == target_date[:4]:
        return FieldMatchResult(
            status=MatchStatus.PARTIAL_MATCH,
            form_value=clean_form,
            extracted_value=target_date,
            confidence=0.6,
            reason=f"Birth year ({clean_form[:4]}) matches, but month/day differ."
        )

    return FieldMatchResult(
        status=MatchStatus.MISMATCH,
        form_value=clean_form,
        extracted_value=target_date,
        confidence=0.0,
        reason=f"Date of birth mismatch: form specifies {clean_form}, document indicates {target_date}."
    )

def compare_names(form_name: Optional[str], extracted_name: Optional[str]) -> FieldMatchResult:
    """
    Careful name matching between form and extracted text.
    Handles:
    - Initials vs Full names (e.g. 'K. A. Perera' vs 'Kamal Anuradha Perera')
    - Word ordering
    - Transliteration uncertainty: flags uncertain rather than inventing matches
    """
    if not extracted_name:
        return FieldMatchResult(
            status=MatchStatus.UNAVAILABLE,
            form_value=form_name,
            extracted_value=None,
            confidence=0.0,
            reason="Full name could not be isolated from OCR text."
        )

    if not form_name:
        return FieldMatchResult(
            status=MatchStatus.UNAVAILABLE,
            form_value=None,
            extracted_value=extracted_name,
            confidence=0.0,
            reason=f"Extracted '{extracted_name}' from document. Form was left blank."
        )

    norm_form = normalize_text(form_name)
    norm_ext = normalize_text(extracted_name)

    # 1. Exact normalized match
    if norm_form == norm_ext:
        return FieldMatchResult(
            status=MatchStatus.MATCH,
            form_value=form_name,
            extracted_value=extracted_name,
            confidence=1.0,
            reason="Exact name match."
        )

    form_tokens = norm_form.split()
    ext_tokens = norm_ext.split()

    # 2. Token set equality (order permutation, e.g. 'Perera Kamal' vs 'Kamal Perera')
    if set(form_tokens) == set(ext_tokens):
        return FieldMatchResult(
            status=MatchStatus.MATCH,
            form_value=form_name,
            extracted_value=extracted_name,
            confidence=0.98,
            reason="Exact token match with differing word ordering."
        )

    # 3. Initials matching logic
    is_initials_compatible, init_confidence = check_initials_compatibility(form_tokens, ext_tokens)
    if is_initials_compatible:
        return FieldMatchResult(
            status=MatchStatus.MATCH,
            form_value=form_name,
            extracted_value=extracted_name,
            confidence=init_confidence,
            reason="Name matches standard Sri Lankan initials-and-surname convention."
        )

    # 4. Partial subset match (e.g. middle name omitted)
    set_form = set(form_tokens)
    set_ext = set(ext_tokens)
    if set_form.issubset(set_ext) or set_ext.issubset(set_form):
        return FieldMatchResult(
            status=MatchStatus.PARTIAL_MATCH,
            form_value=form_name,
            extracted_value=extracted_name,
            confidence=0.85,
            reason="Partial name overlap detected (subset of names matches exactly)."
        )

    # 5. Fuzzy string similarity
    ratio = SequenceMatcher(None, norm_form, norm_ext).ratio()
    if ratio >= 0.82:
        return FieldMatchResult(
            status=MatchStatus.PARTIAL_MATCH,
            form_value=form_name,
            extracted_value=extracted_name,
            confidence=round(ratio, 2),
            reason=f"High textual similarity ({round(ratio*100)}%). Possible minor OCR artifact or spelling variant."
        )
    elif ratio >= 0.60:
        return FieldMatchResult(
            status=MatchStatus.UNCERTAIN,
            form_value=form_name,
            extracted_value=extracted_name,
            confidence=round(ratio, 2),
            reason="Name similarity is moderate/ambiguous. Sinhala/Tamil transliteration or spelling difference requires manual inspection."
        )

    return FieldMatchResult(
        status=MatchStatus.MISMATCH,
        form_value=form_name,
        extracted_value=extracted_name,
        confidence=round(ratio, 2),
        reason="Extracted name does not match form name."
    )

def check_initials_compatibility(tokens1: List[str], tokens2: List[str]) -> Tuple[bool, float]:
    """
    Checks if one token list is initials + surname for the other.
    E.g. ['k', 'a', 'perera'] vs ['kamal', 'anuradha', 'perera']
    """
    if len(tokens1) < 2 or len(tokens2) < 2:
        return False, 0.0

    # Determine which token list is the initials (shorter total character length)
    len1 = sum(len(t) for t in tokens1)
    len2 = sum(len(t) for t in tokens2)

    if len1 < len2:
        short_tokens, long_tokens = tokens1, tokens2
    else:
        short_tokens, long_tokens = tokens2, tokens1

    # Check if surname matches (last token or first token)
    if short_tokens[-1] == long_tokens[-1]:
        short_inits = short_tokens[:-1]
        long_names = long_tokens[:-1]
    elif short_tokens[0] == long_tokens[0]:
        short_inits = short_tokens[1:]
        long_names = long_tokens[1:]
    else:
        return False, 0.0

    if not short_inits or not long_names:
        return False, 0.0

    # Verify each short token matches the initial letter of corresponding long name
    if len(short_inits) <= len(long_names):
        all_match = True
        for i, s_tok in enumerate(short_inits):
            if len(s_tok) == 1:
                if not long_names[i].startswith(s_tok):
                    all_match = False
                    break
            elif s_tok != long_names[i]:
                all_match = False
                break
        if all_match:
            return True, 0.94

    return False, 0.0
