import pytest

from universal_paper.canon import CanonError, content_hash, jcs
from universal_paper.values import add_period, dec, opens, round_dec, seal_of


def test_jcs_sorts_keys_and_has_no_whitespace():
    assert jcs({"b": 1, "a": [True, False, "x"]}) == b'{"a":[true,false,"x"],"b":1}'


def test_jcs_escapes_like_ecmascript():
    assert jcs({"s": 'q"\\\n\t\x01é'}) == '{"s":"q\\"\\\\\\n\\t\\u0001é"}'.encode()


@pytest.mark.parametrize("bad", [1.5, None, 2**60])
def test_jcs_rejects_floats_null_and_big_ints(bad):
    with pytest.raises(CanonError):
        jcs({"x": bad})


def test_hash_ignores_signatures_only():
    o = {"type": "X", "spec": "s", "v": 1}
    assert content_hash(o) == content_hash({**o, "sigs": [{"key": "k"}]})
    assert content_hash(o) != content_hash({**o, "v": 2})


def test_seal_and_disclosure():
    salt = "ab" * 32
    s = seal_of({"value": "9.10", "currency": "USD"}, salt)
    assert opens({"seal": s["seal"], "salt": salt, "value": {"value": "9.10", "currency": "USD"}}, s)
    assert not opens({"seal": s["seal"], "salt": salt, "value": {"value": "9.11", "currency": "USD"}}, s)


def test_month_arithmetic_clamps_and_does_not_drift():
    m = {"unit": "month", "count": 1}
    assert add_period("2027-01-31T00:00:00Z", m) == "2027-02-28T00:00:00Z"
    assert add_period("2027-01-31T00:00:00Z", m, 2) == "2027-03-31T00:00:00Z"  # computed directly, not 31→28→28


def test_rounding_modes_are_exact():
    assert str(round_dec(dec("2.345"), {"scale": 2, "mode": "half-even"})) == "2.34"
    assert str(round_dec(dec("2.345"), {"scale": 2, "mode": "half-up"})) == "2.35"
    assert str(round_dec(dec("2.349"), {"scale": 2, "mode": "down"})) == "2.34"
