import json
import os

from selector_recon.cli import load_env_file, main
from selector_recon.http import BROWSER_USER_AGENT, USER_AGENT
from selector_recon.runner import RunConfig, Runner


def test_env_file_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nexport SR_TEST_A='one'\nSR_TEST_B=two\nSR_TEST_EMPTY=\n", encoding="utf-8")
    monkeypatch.setenv("SR_TEST_B", "already-set")
    monkeypatch.delenv("SR_TEST_A", raising=False)
    monkeypatch.delenv("SR_TEST_EMPTY", raising=False)
    assert load_env_file(env) == ["SR_TEST_A"]
    assert os.environ["SR_TEST_A"] == "one" and os.environ["SR_TEST_B"] == "already-set"
    assert "SR_TEST_EMPTY" not in os.environ
    monkeypatch.delenv("SR_TEST_A")


def test_browser_ua_is_opt_in(tmp_path):
    assert Runner(RunConfig(out_dir=tmp_path)).ctx.user_agent == USER_AGENT
    assert Runner(RunConfig(out_dir=tmp_path, browser_ua=True)).ctx.user_agent == BROWSER_USER_AGENT


def test_offline_run_end_to_end(tmp_path, capsys):
    out = tmp_path / "run"
    rc = main(["--offline", "-q", "--env-file", str(tmp_path / "none"), "--out", str(out),
               "user@example.com", "+4915123456789", "192.0.2.1", "alice_ctf"])
    assert rc == 0
    data = json.loads((out / "findings.json").read_text())
    modules = {f["module"] for f in data["findings"]}
    assert modules == {"email_info", "phone_info", "phone_links", "ip_info"}
    skipped = {r["module"] for r in data["module_runs"] if r["state"] == "skipped"}
    assert {"dns", "gravatar", "wmn", "shodan"} <= skipped
    assert (out / "report.html").is_file() and (out / "findings.md").is_file()


def test_unknown_module_is_usage_error(capsys):
    try:
        main(["--modules", "nope", "alice"])
    except SystemExit as exc:
        assert exc.code == 2
    assert "unknown module" in capsys.readouterr().err
