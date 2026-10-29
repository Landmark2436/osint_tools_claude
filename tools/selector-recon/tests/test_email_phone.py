"""Email and phone modules. Network modules talk to the local fixture server, DNS to a fake resolver."""

import pytest

from selector_recon.dnsutil import DnsResult
from selector_recon.models import Selector, SelectorType, Status
from selector_recon.modules.dns_records import Dns
from selector_recon.modules.email_info import EmailInfo, analyze
from selector_recon.modules.gravatar import Gravatar, gravatar_hash
from selector_recon.modules.hibp import Hibp
from selector_recon.modules.holehe_wrap import Holehe
from selector_recon.modules.phone_info import PhoneInfo
from selector_recon.modules.phone_links import PhoneLinks
from selector_recon.modules.proton import Proton


def email(v):
    return Selector(v, SelectorType.EMAIL)


class FakeDns:
    def __init__(self, answers):
        self.answers = answers  # {(name, rtype): [records] | "NXDOMAIN" | "NoAnswer"}

    def query(self, name, rtype):
        a = self.answers.get((name, rtype), "NoAnswer")
        return DnsResult(name, rtype, error=a) if isinstance(a, str) else DnsResult(name, rtype, sorted(a))

    def reverse(self, ip):
        return self.query(ip, "PTR")


# --- email_info -----------------------------------------------------------

def test_gmail_normalization():
    a = analyze("John.Doe+ctf@googlemail.com")
    assert a["valid"] and a["canonical"] == "johndoe@gmail.com" and a["subaddress_tag"] == "ctf" and a["freemail"]


def test_plus_on_unknown_provider_is_kept():
    a = analyze("john+x@example.com")
    assert a["canonical"] == "john+x@example.com" and a["possible_tag"]


@pytest.mark.parametrize("bad", ["john..doe@example.com", ".john@example.com", "john@example.invalidtld", "a" * 65 + "@example.com"])
def test_invalid(bad):
    assert not analyze(bad)["valid"]


def test_email_info_pivots(ctx):
    (f,) = EmailInfo().run(email("jane.roe@example.com"), ctx)
    assert f.status is Status.FOUND
    assert {(p.type, p.value) for p in f.pivots} == {(SelectorType.USERNAME, "jane.roe"), (SelectorType.DOMAIN, "example.com")}
    (g,) = EmailInfo().run(email("jane.roe@gmail.com"), ctx)
    assert "free-mail provider" in g.flags
    assert {p.value for p in g.pivots} == {"janeroe", "jane.roe"}  # no gmail.com domain pivot


def test_disposable_flag(ctx):
    (f,) = EmailInfo().run(email("x@mailinator.com"), ctx)
    assert "disposable-address domain" in f.flags


# --- dns --------------------------------------------------------------------

def test_email_dns(ctx):
    ctx.dns = FakeDns({
        ("example.com", "MX"): ["10 aspmx.l.google.com"],
        ("example.com", "TXT"): ["v=spf1 include:_spf.google.com ~all", "google-site-verification=abc"],
        ("_dmarc.example.com", "TXT"): ["v=DMARC1; p=reject"],
    })
    res = {f.source: f for f in Dns().run(email("a@example.com"), ctx)}
    assert res["MX"].status is Status.FOUND and "Google" in res["MX"].evidence
    assert res["SPF"].data["includes"] == ["_spf.google.com"]
    assert res["DMARC"].status is Status.FOUND


def test_email_dns_nxdomain_and_null_mx(ctx):
    ctx.dns = FakeDns({("nope.example", "MX"): "NXDOMAIN"})
    (f,) = Dns().run(email("a@nope.example"), ctx)
    assert f.status is Status.NOT_FOUND and "does not exist" in f.evidence
    ctx.dns = FakeDns({("null.example", "MX"): ["0"]})
    res = {f.source: f for f in Dns().run(email("a@null.example"), ctx)}
    assert "null MX" in res["MX"].evidence


# --- gravatar ---------------------------------------------------------------

def test_gravatar_hash():
    assert gravatar_hash(" User@Example.com ") == gravatar_hash("user@example.com")
    assert len(gravatar_hash("user@example.com")) == 64


def test_gravatar_profile(ctx, server, monkeypatch):
    h = gravatar_hash("alice@example.com")
    monkeypatch.setattr(Gravatar, "avatar_base", f"{server.base}/avatar/")
    monkeypatch.setattr(Gravatar, "api_base", f"{server.base}/v3/profiles/")
    server.add(f"/avatar/{h}?d=404&s=200", 200, "PNG")
    server.add_fixture(f"/v3/profiles/{h}", "gravatar_profile.json")
    avatar, profile = Gravatar().run(email("alice@example.com"), ctx)
    assert avatar.status is Status.FOUND and profile.status is Status.FOUND
    assert profile.url == "https://gravatar.com/alicectf"
    assert {p.value for p in profile.pivots} == {"alicectf", "alice-ctf"}  # hidden account not used
    assert "Springfield" in profile.evidence


def test_gravatar_missing(ctx, server, monkeypatch):
    monkeypatch.setattr(Gravatar, "avatar_base", f"{server.base}/avatar/")
    monkeypatch.setattr(Gravatar, "api_base", f"{server.base}/v3/profiles/")
    avatar, profile = Gravatar().run(email("nobody@example.com"), ctx)
    assert avatar.status is Status.NOT_FOUND and profile.status is Status.NOT_FOUND


# --- proton -----------------------------------------------------------------

def test_proton(ctx, server, monkeypatch):
    monkeypatch.setattr(Proton, "base", f"{server.base}/pks/lookup")
    server.add_fixture("/pks/lookup?op=index&options=mr&search=alice@proton.me", "proton_index.txt")
    server.add_fixture("/pks/lookup?op=index&options=mr&search=bob@example.com", "proton_none.txt")
    (f,) = Proton().run(email("alice@proton.me"), ctx)
    assert f.status is Status.FOUND and "2021-01-01T00:00:00Z" in f.evidence
    (g,) = Proton().run(email("bob@example.com"), ctx)
    assert g.status is Status.NOT_FOUND


# --- hibp -------------------------------------------------------------------

def test_hibp_without_key_is_manual(ctx, monkeypatch):
    monkeypatch.delenv("HIBP_API_KEY", raising=False)
    (f,) = Hibp().run(email("a@example.com"), ctx)
    assert f.manual and f.status is Status.UNKNOWN


def test_hibp_with_key(ctx, server, monkeypatch):
    monkeypatch.setenv("HIBP_API_KEY", "test-key-123")
    monkeypatch.setattr(Hibp, "api", f"{server.base}/api/v3/breachedaccount/")
    ctx.options["hibp_interval"] = 0
    server.add_fixture("/api/v3/breachedaccount/a@example.com?truncateResponse=false", "hibp_breaches.json")
    found = Hibp().run(email("a@example.com"), ctx)
    assert [f.source for f in found] == ["HIBP: Example Forum", "HIBP: Example List"]
    assert found[0].data["data_classes"] == ["Email addresses", "Usernames", "Passwords"]
    assert "unverified breach" in found[1].flags
    assert server.requests[-1][2]["hibp-api-key"] == "test-key-123"
    assert all("test-key-123" not in str(f.to_dict()) for f in found)
    (none,) = Hibp().run(email("b@example.com"), ctx)
    assert none.status is Status.NOT_FOUND


# --- holehe -----------------------------------------------------------------

def test_holehe_mapping():
    h = Holehe()
    sel = email("a@example.com")
    assert h.to_finding(sel, {"name": "protonmail", "domain": "protonmail.ch", "exists": True,
                              "others": {"Date, time of the creation": "2021-01-01"}}).status is Status.FOUND
    assert h.to_finding(sel, {"name": "duolingo", "domain": "duolingo.com", "exists": False, "rateLimit": True}).status is Status.BLOCKED
    assert h.to_finding(sel, {"name": "office365", "domain": None, "error": "boom"}).status is Status.ERROR
    assert h.to_finding(sel, {"name": "protonmail", "domain": "protonmail.ch", "exists": False}).site_key == "proton.me"


def test_holehe_is_opt_in():
    assert Holehe.default_enabled is False


# --- phone ------------------------------------------------------------------

def test_phone_info_example_numbers(ctx):
    (f,) = PhoneInfo().run(Selector("+4915123456789", SelectorType.PHONE), ctx)
    assert f.status is Status.FOUND and f.data["region"] == "DE" and f.data["type"] == "mobile"
    (g,) = PhoneInfo().run(Selector("+1 201-555-0123", SelectorType.PHONE), ctx)
    assert "fictional NANP 555-01xx number" in g.flags


def test_phone_national_needs_region(ctx):
    (f,) = PhoneInfo().run(Selector("015123456789", SelectorType.PHONE), ctx)
    assert f.status is Status.NOT_FOUND and "--region" in f.evidence
    ctx.options["region"] = "DE"
    (g,) = PhoneInfo().run(Selector("015123456789", SelectorType.PHONE), ctx)
    assert g.data["e164"] == "+4915123456789"


def test_phone_links_are_manual_only(ctx, server):
    links = PhoneLinks().run(Selector("+4915123456789", SelectorType.PHONE), ctx)
    assert links and all(f.manual and f.status is Status.UNKNOWN for f in links)
    assert any(f.url == "https://wa.me/4915123456789" for f in links)
    assert server.requests == []  # nothing fetched


def test_holehe_runs_only_reviewed_checks(ctx, monkeypatch):
    """Real holehe functions, with their hardcoded URLs answered by an httpx mock transport."""
    pytest.importorskip("holehe")
    import httpx

    from .conftest import FIXTURES

    seen = []

    def handler(request):
        seen.append(request.url.host)
        if request.url.host == "api.protonmail.ch":
            return httpx.Response(200, text=(FIXTURES / "http" / "proton_index.txt").read_text())
        if request.url.host == "www.duolingo.com":
            return httpx.Response(200, json={"users": [{"username": "alice_ctf"}]})
        return httpx.Response(404, text="not found")

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    res = {f.source: f for f in Holehe().run(email("alice@proton.me"), ctx)}
    assert res["holehe: protonmail"].status is Status.FOUND
    assert res["holehe: duolingo"].status is Status.FOUND
    assert res["holehe: gravatar"].status is Status.NOT_FOUND
    assert "--browser-ua" in res["holehe: office365"].evidence  # not run with the honest UA
    assert set(seen) == {"api.protonmail.ch", "en.gravatar.com", "www.duolingo.com"}
