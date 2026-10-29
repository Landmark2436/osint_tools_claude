import hashlib
import json

import pytest

from selector_recon.models import Selector, SelectorType, Status
from selector_recon.modules import wmn
from selector_recon.modules.wmn import WhatsMyName, load_wmn_data

from .conftest import load_fixture_json

ALICE = Selector("alice_ctf", SelectorType.USERNAME)


@pytest.fixture
def wmn_ctx(ctx, server, tmp_path):
    data = load_fixture_json("wmn-mini.json", server.base)
    path = tmp_path / "wmn.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    ctx.options["wmn_data"] = str(path)
    server.add_fixture("/u/alice_ctf", "profile_found.html")
    server.add_fixture("/missing/alice_ctf", "profile_missing.html", status=404)
    server.add_fixture("/graphql", "api_user.json", method="POST")
    server.add_fixture("/cf/alice_ctf", "cloudflare_challenge.html", status=403)
    server.add("/broken/alice_ctf", 500, "Internal Server Error")
    server.add("/r/alice_ctf", 302, "", headers={"Location": "/login"})
    server.add_fixture("/nsfw/alice_ctf", "profile_found.html")
    server.add_fixture("/s/alicectf", "profile_found.html")
    return ctx


def by_source(findings):
    return {f.source: f for f in findings}


def test_statuses_per_site(wmn_ctx, server):
    results = by_source(WhatsMyName().run(ALICE, wmn_ctx))
    assert results["FoundSite"].status is Status.FOUND
    assert "profile-header" in results["FoundSite"].evidence
    assert results["FoundSite"].http_status == 200
    assert results["MissingSite"].status is Status.NOT_FOUND
    assert results["MissingSite"].url == f"{server.base}/profile/alice_ctf"  # uri_pretty wins
    assert results["ApiSite"].status is Status.FOUND
    assert results["ChallengeSite"].status is Status.BLOCKED
    assert results["ChallengeSite"].manual is True
    assert results["BrokenSite"].status is Status.UNKNOWN
    assert results["RedirectSite"].status is Status.NOT_FOUND  # redirects are not followed
    assert results["StripSite"].status is Status.FOUND  # "_" stripped before the request
    assert "DisabledSite" not in results
    assert results["AdultSite"].status is Status.FOUND


def test_post_body_and_honest_user_agent(wmn_ctx, server):
    WhatsMyName().run(ALICE, wmn_ctx)
    posts = [r for r in server.requests if r[0] == "POST"]
    assert len(posts) == 1
    _, _, headers, body = posts[0]
    assert b'User(name:\\"alice_ctf\\")' in body
    assert headers["User-Agent"].startswith("selector-recon/")  # the site's fake UA is dropped
    assert headers["Content-Type"] == "application/json"


def test_nsfw_can_be_excluded(wmn_ctx):
    wmn_ctx.include_nsfw = False
    assert "AdultSite" not in by_source(WhatsMyName().run(ALICE, wmn_ctx))


def test_connection_error_is_a_finding(wmn_ctx):
    site = {"name": "Dead", "uri_check": "http://127.0.0.1:9/u/{account}", "e_code": 200, "e_string": "x",
            "m_string": "y", "m_code": 404, "known": [], "cat": "social"}
    finding = WhatsMyName().check_site(ALICE, site, wmn_ctx)
    assert finding.status is Status.ERROR


def test_pinned_download_is_verified_and_cached(ctx, server, monkeypatch):
    body = '{"sites": []}'
    server.add("/wmn-data.json", 200, body)
    monkeypatch.setattr(wmn, "WMN_URL", f"{server.base}/wmn-data.json")
    monkeypatch.setattr(wmn, "WMN_SHA256", hashlib.sha256(body.encode()).hexdigest())
    assert load_wmn_data(ctx) == {"sites": []}
    assert load_wmn_data(ctx) == {"sites": []}
    assert sum(1 for r in server.requests if r[1] == "/wmn-data.json") == 1  # second load from cache


def test_hash_mismatch_is_rejected(ctx, server, monkeypatch):
    server.add("/wmn-data.json", 200, '{"sites": ["tampered"]}')
    monkeypatch.setattr(wmn, "WMN_URL", f"{server.base}/wmn-data.json")
    with pytest.raises(RuntimeError, match="sha256"):
        load_wmn_data(ctx)
