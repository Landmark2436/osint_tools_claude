import pytest

from selector_recon.detect import detect_type, make_selector
from selector_recon.models import SelectorType as T


@pytest.mark.parametrize(
    "value, expected",
    [
        ("user@example.com", T.EMAIL),
        ("first.last+tag@sub.example.org", T.EMAIL),
        ("+1 201-555-0123", T.PHONE),
        ("+49 30 123456", T.PHONE),
        ("030 1234567", T.PHONE),
        ("example.com", T.DOMAIN),
        ("sub.example.co.uk", T.DOMAIN),
        ("192.0.2.1", T.IP),
        ("2001:db8::1", T.IP),
        ("alice_ctf", T.USERNAME),
        ("john.doe", T.USERNAME),  # .doe is not a TLD
        ("@alice", T.USERNAME),
        ("123", T.USERNAME),  # too short for a phone number
    ],
)
def test_detect(value, expected):
    assert detect_type(value) is expected


def test_normalize():
    assert make_selector("  @Alice ").value == "Alice"
    assert make_selector("User@Example.COM").value == "user@example.com"
    assert make_selector("Example.com.").value == "example.com"
    assert make_selector("2001:DB8:0::1").value == "2001:db8::1"


def test_forced_type():
    assert make_selector("john.dev", T.USERNAME).type is T.USERNAME
    assert make_selector("john.dev").type is T.DOMAIN
