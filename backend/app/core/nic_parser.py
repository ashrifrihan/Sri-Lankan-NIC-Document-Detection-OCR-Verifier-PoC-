import re
from datetime import date, timedelta
from typing import Tuple, Optional, List
from ..models.schemas import NICValidationResult, NICFormat, Gender, VoterStatus

# Days per month in a standard 366-day leap year system traditionally used by Sri Lanka DRP
# (Department of Registration of Persons) where February is consistently evaluated with 29 days
DAYS_IN_MONTHS_366 = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
DAYS_IN_MONTHS_365 = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def parse_day_of_year_to_date(year: int, day_of_year: int) -> Tuple[Optional[str], List[str]]:
    """
    Decodes day of year (1-366) to YYYY-MM-DD.
    Sri Lankan DRP scheme historically assumes Feb has 29 days for all years (366-day table).
    For non-leap years, if person was born after Feb 28, standard Gregorian calendar is day - 1.
    We compute the official DRP date and document any leap-year convention notes.
    """
    warnings = []
    if day_of_year < 1 or day_of_year > 366:
        return None, [f"Day of year {day_of_year} is out of valid range (1-366)."]

    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

    # Calculate month and day according to DRP 366-day standard
    remaining_days = day_of_year
    month = 1
    for m_idx, days in enumerate(DAYS_IN_MONTHS_366):
        if remaining_days <= days:
            month = m_idx + 1
            break
        remaining_days -= days
    day = remaining_days

    if month == 2 and day == 29 and not is_leap:
        warnings.append(
            f"Birth year {year} was not a leap year, but DRP encoded Feb 29 (day {day_of_year})."
        )
        day = 28

    try:
        dt = date(year, month, day)
        return dt.strftime("%Y-%m-%d"), warnings
    except ValueError as e:
        return None, [f"Could not convert year {year}, day {day_of_year} to valid date: {str(e)}"]

def parse_sri_lankan_nic(nic_input: str) -> NICValidationResult:
    """
    Validates and extracts metadata from Sri Lankan NIC numbers.
    Supports:
    - 9 digits + V/X (pre-2016 format, 10 chars total, e.g. '853451234V')
    - 12 digits (post-2016 format, e.g. '198534501234')
    """
    if not nic_input:
        return NICValidationResult(
            is_valid=False,
            nic_number="",
            format=NICFormat.INVALID,
            errors=["NIC number cannot be empty."]
        )

    clean_nic = re.sub(r"[\s\-]", "", nic_input.strip()).upper()
    errors = []
    warnings = []

    # Old format: 2 digits (YY) + 3 digits (DDD) + 4 digits (serial) + V/X = 10 chars
    old_match = re.match(r"^(\d{2})(\d{3})(\d{4})([VX])$", clean_nic)
    # New format: 4 digits (YYYY) + 3 digits (DDD) + 1 digit (check/sep) + 4 digits (serial) = 12 digits
    new_match = re.match(r"^(\d{4})(\d{3})(\d{1})(\d{4})$", clean_nic)

    if old_match:
        yy_str, days_str, serial_str, voter_char = old_match.groups()
        yy = int(yy_str)
        days = int(days_str)
        serial = serial_str
        voter_status = VoterStatus.ELIGIBLE if voter_char == "V" else VoterStatus.INELIGIBLE

        # Old format: 1900 + YY
        birth_year = 1900 + yy

        # Gender & raw day of year
        if days > 500:
            gender = Gender.FEMALE
            calc_day = days - 500
        else:
            gender = Gender.MALE
            calc_day = days

        if calc_day < 1 or calc_day > 366:
            errors.append(f"Invalid days-of-year value {days} in old NIC format (must be 1-366 for male, 501-866 for female).")
            return NICValidationResult(
                is_valid=False,
                nic_number=clean_nic,
                format=NICFormat.OLD_9_DIGIT,
                birth_year=birth_year,
                gender=gender,
                voter_status=voter_status,
                errors=errors
            )

        decoded_dob, dob_warnings = parse_day_of_year_to_date(birth_year, calc_day)
        warnings.extend(dob_warnings)

        # Equivalent 12-digit format: 19YY DDD 0 SSSS
        equivalent_12 = f"19{yy_str}{days_str}0{serial_str}"

        return NICValidationResult(
            is_valid=True,
            nic_number=clean_nic,
            format=NICFormat.OLD_9_DIGIT,
            birth_year=birth_year,
            day_of_year=calc_day,
            decoded_dob=decoded_dob,
            gender=gender,
            voter_status=voter_status,
            serial_number=serial,
            equivalent_alternate_format=equivalent_12,
            errors=[],
            warnings=warnings
        )

    elif new_match:
        yyyy_str, days_str, check_sep, serial_str = new_match.groups()
        birth_year = int(yyyy_str)
        days = int(days_str)
        serial = serial_str

        current_year = date.today().year
        if birth_year < 1900 or birth_year > current_year:
            errors.append(f"Birth year {birth_year} is out of realistic range (1900 - {current_year}).")

        if days > 500:
            gender = Gender.FEMALE
            calc_day = days - 500
        else:
            gender = Gender.MALE
            calc_day = days

        if calc_day < 1 or calc_day > 366:
            errors.append(f"Invalid days-of-year value {days} in 12-digit NIC format (must be 1-366 for male, 501-866 for female).")

        if errors:
            return NICValidationResult(
                is_valid=False,
                nic_number=clean_nic,
                format=NICFormat.NEW_12_DIGIT,
                birth_year=birth_year,
                gender=gender,
                errors=errors
            )

        decoded_dob, dob_warnings = parse_day_of_year_to_date(birth_year, calc_day)
        warnings.extend(dob_warnings)

        # Equivalent 9-digit format if born in 20th century (1900-1999)
        equivalent_9 = None
        if 1900 <= birth_year < 2000:
            yy_part = yyyy_str[2:]
            equivalent_9 = f"{yy_part}{days_str}{serial_str}V"

        return NICValidationResult(
            is_valid=True,
            nic_number=clean_nic,
            format=NICFormat.NEW_12_DIGIT,
            birth_year=birth_year,
            day_of_year=calc_day,
            decoded_dob=decoded_dob,
            gender=gender,
            voter_status=VoterStatus.NOT_APPLICABLE,
            serial_number=serial,
            check_digit=serial_str[-1],
            equivalent_alternate_format=equivalent_9,
            errors=[],
            warnings=warnings
        )

    else:
        # Invalid format
        if len(clean_nic) == 10:
            errors.append("Invalid 10-char NIC format. Expected 9 digits followed by 'V' or 'X' (e.g. 853451234V).")
        elif len(clean_nic) == 12:
            errors.append("Invalid 12-digit NIC format. Expected 12 numeric digits (e.g. 198534501234).")
        else:
            errors.append(f"Invalid NIC length ({len(clean_nic)} chars). Expected 9 digits + V/X (10 chars) or 12 digits.")

        return NICValidationResult(
            is_valid=False,
            nic_number=clean_nic,
            format=NICFormat.INVALID,
            errors=errors
        )

def are_nics_equivalent(nic1: str, nic2: str) -> bool:
    """
    Checks if two NIC numbers represent the same person
    (handling identical match or cross-format conversion between old 9-digit and new 12-digit).
    """
    c1 = re.sub(r"[\s\-]", "", nic1.strip()).upper()
    c2 = re.sub(r"[\s\-]", "", nic2.strip()).upper()

    if c1 == c2:
        return True

    res1 = parse_sri_lankan_nic(c1)
    res2 = parse_sri_lankan_nic(c2)

    if not res1.is_valid or not res2.is_valid:
        return False

    # Check if birth year, gender, and day of year match
    if res1.birth_year == res2.birth_year and res1.gender == res2.gender and res1.day_of_year == res2.day_of_year:
        if res1.serial_number and res2.serial_number:
            s1 = res1.serial_number
            s2 = res2.serial_number
            # Check if serial numbers match or overlap
            if s1 == s2 or s1 in s2 or s2 in s1:
                return True

    return False
