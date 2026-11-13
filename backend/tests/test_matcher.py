import pytest
from app.core.matcher import compare_nic, compare_dob, compare_names
from app.models.schemas import MatchStatus

def test_compare_nic_exact():
    res = compare_nic("853451234V", "853451234v")
    assert res.status == MatchStatus.MATCH
    assert res.confidence == 1.0

def test_compare_nic_cross_format():
    res = compare_nic("853451234V", "198534501234")
    assert res.status == MatchStatus.MATCH
    assert res.confidence >= 0.90

def test_compare_nic_mismatch():
    res = compare_nic("853451234V", "927891234X")
    assert res.status == MatchStatus.MISMATCH

def test_compare_nic_unavailable():
    res = compare_nic("853451234V", None)
    assert res.status == MatchStatus.UNAVAILABLE

def test_compare_dob_exact():
    res = compare_dob("1985-12-11", "1985-12-11", "1985-12-11")
    assert res.status == MatchStatus.MATCH
    assert res.confidence == 1.0

def test_compare_dob_leap_year_tolerance():
    # 1 day difference in non-leap year DRP convention
    res = compare_dob("1985-12-10", "1985-12-11", "1985-12-11")
    assert res.status == MatchStatus.MATCH
    assert res.confidence >= 0.90

def test_compare_dob_mismatch():
    res = compare_dob("1985-12-11", "1990-05-20", "1990-05-20")
    assert res.status == MatchStatus.MISMATCH

def test_compare_names_exact_and_reordered():
    # Exact
    res1 = compare_names("Kamal Anuradha Perera", "Kamal Anuradha Perera")
    assert res1.status == MatchStatus.MATCH
    assert res1.confidence == 1.0

    # Reordered
    res2 = compare_names("Perera Kamal Anuradha", "Kamal Anuradha Perera")
    assert res2.status == MatchStatus.MATCH
    assert res2.confidence >= 0.95

def test_compare_names_initials_and_surname():
    # K. A. Perera vs Kamal Anuradha Perera
    res = compare_names("Kamal Anuradha Perera", "K. A. Perera")
    assert res.status == MatchStatus.MATCH
    assert res.confidence >= 0.90

    # Reverse
    res_rev = compare_names("K. A. Perera", "Kamal Anuradha Perera")
    assert res_rev.status == MatchStatus.MATCH

def test_compare_names_transliteration_uncertain():
    # Similar sounding/transliterated variations should yield UNCERTAIN rather than guessing
    res = compare_names("Priyadharshani", "Priyangika")
    assert res.status in [MatchStatus.UNCERTAIN, MatchStatus.MISMATCH]
