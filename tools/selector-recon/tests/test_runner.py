from pathlib import Path

import pytest

from selector_recon import runner as runner_mod
from selector_recon.models import Pivot, Selector, SelectorType, Status
from selector_recon.modules import Module
from selector_recon.runner import RunConfig, Runner, cross_check, parse_module_spec
from selector_recon.util import site_key


class Good(Module):
    name = "good"
    title = "Good"
    selector_types = frozenset({SelectorType.USERNAME, SelectorType.EMAIL})
    needs_network = False

    def run(self, selector, ctx):
        pivots = [Pivot(SelectorType.EMAIL, "alice@example.com", "seen on profile")] if selector.type is SelectorType.USERNAME else []
        return [self.finding(selector, "SiteX", Status.FOUND, url="https://sitex.example/alice", site_key="sitex.example", pivots=pivots)]


class Broken(Module):
    name = "broken"
    title = "Broken"
    selector_types = frozenset({SelectorType.USERNAME})
    needs_network = False

    def run(self, selector, ctx):
        raise RuntimeError("boom")


class Online(Module):
    name = "online"
    title = "Online"
    selector_types = frozenset({SelectorType.USERNAME})
    default_enabled = False

    def run(self, selector, ctx):
        return []


@pytest.fixture
def fake_modules(monkeypatch):
    mods = {"broken": Broken(), "good": Good(), "online": Online()}
    monkeypatch.setattr(runner_mod, "all_modules", lambda: mods)
    monkeypatch.setattr(runner_mod, "get_module", lambda n: mods[n])
    return mods


def make_runner(tmp_path: Path, **kw) -> Runner:
    return Runner(RunConfig(out_dir=tmp_path, **kw), progress=lambda m: None)


ALICE = Selector("alice", SelectorType.USERNAME)


def test_module_spec(fake_modules):
    assert parse_module_spec(None) == ["broken", "good"]
    assert parse_module_spec("online") == ["online"]
    assert parse_module_spec("+online,-broken") == ["good", "online"]
    assert parse_module_spec("all") == ["broken", "good", "online"]
    with pytest.raises(ValueError):
        parse_module_spec("good,-broken")


def test_failing_module_does_not_fail_run(fake_modules, tmp_path):
    result = make_runner(tmp_path).run([ALICE])
    states = {r.module: r.state for r in result.module_runs}
    assert states == {"broken": "failed", "good": "ran"}
    errors = [f for f in result.findings if f.status is Status.ERROR]
    assert len(errors) == 1 and "boom" in errors[0].evidence


def test_offline_skips_network_modules(fake_modules, tmp_path):
    result = make_runner(tmp_path, modules="+online", offline=True).run([ALICE])
    online = [r for r in result.module_runs if r.module == "online"][0]
    assert online.state == "skipped" and online.reason == "offline mode"


def test_pivots_listed_not_followed(fake_modules, tmp_path):
    result = make_runner(tmp_path, modules="good").run([ALICE])
    assert [s.value for s in result.selectors] == ["alice"]
    assert [p.value for p, _ in result.pivots] == ["alice@example.com"]


def test_pivot_one_level(fake_modules, tmp_path):
    result = make_runner(tmp_path, modules="good", pivot=1).run([ALICE])
    assert [s.value for s in result.selectors] == ["alice", "alice@example.com"]
    assert {f.round for f in result.findings} == {0, 1}


def test_cross_check_flags():
    g = Good()
    sel = ALICE
    agree = [g.finding(sel, "A", Status.FOUND, site_key="a.com"), g.finding(sel, "A", Status.FOUND, site_key="a.com")]
    agree[1].module = "other"
    disagree = [g.finding(sel, "B", Status.FOUND, site_key="b.com"), g.finding(sel, "B", Status.NOT_FOUND, site_key="b.com")]
    disagree[1].module = "other"
    cross_check(agree + disagree)
    assert agree[0].confidence.value == "high" and "confirmed by 2 modules" in agree[0].flags
    assert disagree[0].confidence.value == "low" and disagree[0].flags[0].startswith("sources disagree")


@pytest.mark.parametrize(
    "url, key",
    [
        ("https://www.github.com/alice", "github.com"),
        ("https://api.github.com/users/alice", "github.com"),
        ("https://alice.tumblr.com/", "tumblr.com"),
        ("https://forum.example.co.uk/u/alice", "example.co.uk"),
        ("http://127.0.0.1:8000/u/alice", "127.0.0.1"),
        (None, "Some Site!"),
    ],
)
def test_site_key(url, key):
    assert site_key(url, "Some Site!") == key.replace("Some Site!", "somesite")
