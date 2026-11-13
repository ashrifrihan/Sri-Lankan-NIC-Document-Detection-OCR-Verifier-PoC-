import pytest
from app.core.nic_parser import parse_sri_lankan_nic, are_nics_equivalent
from app.models.schemas import NICFormat, Gender, VoterStatus

def test_valid_old_nic_male():
    # 853451234V -> 1985, day 345, male, eligible voter
    # In DRP 366-day convention, day 345 is 1985-12-10
    res = parse_sri_lankan_nic("853451234V")
    assert res.is_valid is True
    assert res.format == NICFormat.OLD_9_DIGIT
    assert res.birth_year == 1985
    assert res.gender == Gender.MALE
    assert res.day_of_year == 345
    assert res.voter_status == VoterStatus.ELIGIBLE
    assert res.decoded_dob == "1985-12-10"

def test_valid_old_nic_female_and_non_voter():
    # 927891234X -> 1992, day 789 (789 - 500 = 289), female, ineligible voter (X)
    res = parse_sri_lankan_nic("927891234X")
    assert res.is_valid is True
    assert res.format == NICFormat.OLD_9_DIGIT
    assert res.birth_year == 1992
    assert res.gender == Gender.FEMALE
    assert res.day_of_year == 289
    assert res.voter_status == VoterStatus.INELIGIBLE
    assert res.decoded_dob == "1992-10-15"

def test_valid_new_nic_male():
    # 199518001234 -> 1995, day 180, male
    res = parse_sri_lankan_nic("199518001234")
    assert res.is_valid is True
    assert res.format == NICFormat.NEW_12_DIGIT
    assert res.birth_year == 1995
    assert res.gender == Gender.MALE
    assert res.day_of_year == 180
    assert res.voter_status == VoterStatus.NOT_APPLICABLE
    assert res.decoded_dob == "1995-06-28"

def test_valid_new_nic_female():
    # 200268101234 -> 2002, day 681 (681 - 500 = 181), female
    res = parse_sri_lankan_nic("200268101234")
    assert res.is_valid is True
    assert res.format == NICFormat.NEW_12_DIGIT
    assert res.birth_year == 2002
    assert res.gender == Gender.FEMALE
    assert res.day_of_year == 181
    assert res.decoded_dob == "2002-06-29"

def test_invalid_days():
    # Day 000 is invalid
    res1 = parse_sri_lankan_nic("850001234V")
    assert res1.is_valid is False
    assert any("Invalid days-of-year" in e for e in res1.errors)

    # Day 367 is invalid for male (must be 1-366)
    res2 = parse_sri_lankan_nic("853671234V")
    assert res2.is_valid is False
    assert any("Invalid days-of-year" in e for e in res2.errors)

    # Day 867 is invalid for female (867 - 500 = 367)
    res3 = parse_sri_lankan_nic("858671234V")
    assert res3.is_valid is False
    assert any("Invalid days-of-year" in e for e in res3.errors)

def test_invalid_lengths_and_characters():
    assert parse_sri_lankan_nic("").is_valid is False
    assert parse_sri_lankan_nic("85345123V").is_valid is False  # 8 digits + V (9 chars instead of 10)
    assert parse_sri_lankan_nic("8534512345V").is_valid is False # 10 digits + V (11 chars)
    assert parse_sri_lankan_nic("853451234A").is_valid is False # Ends with A instead of V/X
    assert parse_sri_lankan_nic("19951800123").is_valid is False # 11 digits
    assert parse_sri_lankan_nic("1995180012345").is_valid is False # 13 digits

def test_nic_equivalence():
    # 853451234V and 198534501234 represent the same identity parameters
    assert are_nics_equivalent("853451234V", "198534501234") is True
    assert are_nics_equivalent("853451234V", "853451234v") is True
    # Different year / day
    assert are_nics_equivalent("853451234V", "198634501234") is False
    assert are_nics_equivalent("853451234V", "927891234X") is False
