import json

from selector_recon.models import Finding, Pivot, Selector, SelectorType, Status
from selector_recon.output import write_all
from selector_recon.output.markdown import render_markdown
from selector_recon.runner import ModuleRun, RunResult


def sample_result():
    sel = Selector("alice", SelectorType.USERNAME)
    findings = [
        Finding("alice", SelectorType.USERNAME, "wmn", "SiteA", Status.FOUND, url="https://a.example/alice",
                evidence="HTTP 200 | marker", pivots=[Pivot(SelectorType.EMAIL, "alice@example.com", "profile")]),
        Finding("alice", SelectorType.USERNAME, "wmn", "SiteB", Status.BLOCKED, url="https://b.example/alice",
                evidence="Cloudflare challenge"),
        Finding("alice", SelectorType.USERNAME, "wmn", "SiteC", Status.NOT_FOUND, url="https://c.example/alice"),
        Finding("alice", SelectorType.USERNAME, "wmn", "Evil", Status.FOUND, url="javascript:alert(1)",
                evidence="</script><script>alert(1)</script>"),
    ]
    runs = [ModuleRun("alice", "wmn", "ran", findings=4), ModuleRun("alice", "sherlock", "skipped", "missing package")]
    return RunResult("2026-10-29T10:00:00Z", "2026-10-29T10:01:00Z", [sel], findings, runs, {"modules_resolved": ["wmn"]})


def test_write_all(tmp_path):
    paths = write_all(sample_result(), tmp_path / "run")
    assert [p.name for p in paths] == ["findings.json", "findings.md", "report.html"]
    data = json.loads((tmp_path / "run" / "findings.json").read_text())
    assert data["summary"]["found"] == 2 and data["summary"]["blocked"] == 1
    assert data["manual_checks"][0]["url"] == "https://b.example/alice"
    assert data["pivots"][0]["value"] == "alice@example.com"


def test_markdown_escapes_and_hides_not_found():
    md = render_markdown(sample_result())
    assert "HTTP 200 \\| marker" in md
    assert "SiteC" not in md and "1 source(s) reported not found" in md
    assert "- [ ] `alice` — SiteB: <https://b.example/alice>" in md
    assert "sherlock: skipped (missing package)" in md


def test_html_is_self_contained_and_safe(tmp_path):
    write_all(sample_result(), tmp_path)
    html = (tmp_path / "report.html").read_text()
    assert "</script><script>alert(1)" not in html  # evidence cannot close the data block
    assert "\\u003c/script>" in html
    assert "src=\"http" not in html and "<link" not in html
