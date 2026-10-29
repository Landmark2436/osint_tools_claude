"""Browser adapters with a real headless Chromium against the local fixture server.

Skipped when Playwright or its Chromium is not installed.
"""

import pytest

from selector_recon.browser import BrowserSession
from selector_recon.models import Finding, Selector, SelectorType, Status
from selector_recon.modules.hibp_web import HibpWeb, classify
from selector_recon.modules.screenshots import Screenshots
from selector_recon.runner import RunConfig, Runner

pytest.importorskip("playwright")

ALICE = Selector("alice_ctf", SelectorType.USERNAME)


@pytest.fixture
def bctx(ctx, tmp_path):
    session = BrowserSession(out_dir=tmp_path, user_agent=ctx.user_agent, timeout=15)
    try:
        session.new_page().close()
    except Exception as exc:
        pytest.skip(f"no usable Chromium: {exc}")
    ctx.browser = session
    ctx.out_dir = tmp_path
    yield ctx
    session.close()


def test_classify():
    assert classify("Good news — no pwnage found!")[0] is Status.NOT_FOUND
    assert classify("Oh no — pwned! found in 3 data breaches") == (Status.FOUND, "website: pwned in 3 breach(es)")
    assert classify("something else")[0] is Status.UNKNOWN


def wmn_found(url, source):
    return Finding("alice_ctf", SelectorType.USERNAME, "wmn", source, Status.FOUND, url=url)


def test_screenshots_attach_and_flag(bctx, server, tmp_path):
    server.add_fixture("/u/alice_ctf", "profile_found.html")
    server.add_fixture("/cf/alice_ctf", "cloudflare_challenge.html", status=403)
    server.add("/gone/alice_ctf", 404, "<h1>gone</h1>")
    ok, cf, gone = (wmn_found(f"{server.base}{p}", s) for p, s in
                    (("/u/alice_ctf", "Good"), ("/cf/alice_ctf", "Challenge"), ("/gone/alice_ctf", "Gone")))
    other = Finding("alice_ctf", SelectorType.USERNAME, "dns", "x", Status.FOUND, url=f"{server.base}/u/alice_ctf")
    bctx.findings = [ok, cf, gone, other]
    assert Screenshots().run(ALICE, bctx) == []
    assert ok.screenshot and (tmp_path / ok.screenshot).is_file()
    assert any("Cloudflare challenge" in fl for fl in cf.flags)
    assert any("HTTP 404" in fl for fl in gone.flags)
    assert other.screenshot == ok.screenshot  # same URL shares the screenshot
    assert "3 screenshot(s)" in bctx.note


def test_screenshots_respect_robots(bctx, server):
    server.add("/robots.txt", 200, "User-agent: *\nDisallow: /private/\n")
    f = wmn_found(f"{server.base}/private/alice_ctf", "Private")
    bctx.findings = [f]
    Screenshots().run(ALICE, bctx)
    assert f.screenshot is None and "robots.txt" in f.flags[0]


@pytest.mark.parametrize("address, status", [("pwned@example.com", Status.FOUND), ("clean@example.com", Status.NOT_FOUND)])
def test_hibp_web(bctx, server, monkeypatch, address, status):
    monkeypatch.delenv("HIBP_API_KEY", raising=False)
    monkeypatch.setattr(HibpWeb, "site", f"{server.base}/")
    server.add_fixture("/", "hibp_form.html")
    (f,) = HibpWeb().run(Selector(address, SelectorType.EMAIL), bctx)
    assert f.status is status and f.screenshot


def test_hibp_web_challenge_is_blocked(bctx, server, monkeypatch):
    monkeypatch.delenv("HIBP_API_KEY", raising=False)
    monkeypatch.setattr(HibpWeb, "site", f"{server.base}/")
    server.add_fixture("/", "cloudflare_challenge.html", status=403)
    (f,) = HibpWeb().run(Selector("a@example.com", SelectorType.EMAIL), bctx)
    assert f.status is Status.BLOCKED and f.manual and f.screenshot


def test_missing_browser_skips_cleanly(tmp_path, server, monkeypatch):
    monkeypatch.setattr(HibpWeb, "site", f"{server.base}/")
    runner = Runner(RunConfig(out_dir=tmp_path, modules="hibp_web", browser_path="/nonexistent/chrome"), progress=lambda m: None)
    result = runner.run([Selector("a@example.com", SelectorType.EMAIL)])
    (run,) = result.module_runs
    assert run.state == "skipped" and "cannot start Chromium" in run.reason
    assert result.findings == []
    assert server.requests == []  # nothing fetched before the browser check


def test_no_browser_flag(tmp_path):
    runner = Runner(RunConfig(out_dir=tmp_path, modules="hibp_web", no_browser=True), progress=lambda m: None)
    (run,) = runner.run([Selector("a@example.com", SelectorType.EMAIL)]).module_runs
    assert run.reason == "browser disabled (--no-browser)"
