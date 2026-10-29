"""Sherlock and Maigret wrappers, run for real against the local fixture server."""

import json

import pytest

from selector_recon.models import Selector, SelectorType, Status

from .conftest import load_fixture_json

ALICE = Selector("alice_ctf", SelectorType.USERNAME)


def by_source(findings):
    return {f.source: f for f in findings}


def write_data(tmp_path, name, server):
    path = tmp_path / name
    path.write_text(json.dumps(load_fixture_json(name, server.base)), encoding="utf-8")
    return str(path)


@pytest.fixture
def routes(server):
    server.add_fixture("/u/alice_ctf", "profile_found.html")
    server.add_fixture("/missing/alice_ctf", "profile_missing.html", status=200)
    server.add_fixture("/waf/alice_ctf", "waf_challenge.html", status=200)
    server.add_fixture("/nsfw/alice_ctf", "profile_found.html")
    server.add_fixture("/tls/alice_ctf", "profile_found.html")
    server.add_fixture("/ua/alice_ctf", "profile_found.html")
    return server


class TestSherlock:
    @pytest.fixture
    def module(self):
        pytest.importorskip("sherlock_project")
        from selector_recon.modules.sherlock_wrap import Sherlock

        return Sherlock()

    @pytest.fixture
    def sctx(self, ctx, routes, tmp_path):
        ctx.options.update(sherlock_data=write_data(tmp_path, "sherlock-mini.json", routes), sherlock_exclusions=False)
        return ctx

    def test_statuses(self, module, sctx, routes):
        results = by_source(module.run(ALICE, sctx))
        assert results["FoundSite"].status is Status.FOUND
        assert results["FoundSite"].url == f"{routes.base}/u/alice_ctf"
        assert results["MessageSite"].status is Status.NOT_FOUND
        assert results["WafSite"].status is Status.BLOCKED
        assert results["StrictSite"].status is Status.NOT_FOUND
        assert "not allowed" in results["StrictSite"].evidence
        assert results["AdultSite"].status is Status.FOUND

    def test_honest_user_agent(self, module, sctx, routes):
        module.run(ALICE, sctx)
        agents = {r[2].get("User-Agent") for r in routes.requests}
        assert agents and all(a.startswith("selector-recon/") for a in agents)

    def test_nsfw_excluded(self, module, sctx):
        sctx.include_nsfw = False
        assert "AdultSite" not in by_source(module.run(ALICE, sctx))


class TestMaigret:
    @pytest.fixture
    def module(self):
        pytest.importorskip("maigret")
        from selector_recon.modules.maigret_wrap import Maigret

        return Maigret()

    @pytest.fixture
    def mctx(self, ctx, routes, tmp_path):
        ctx.options["maigret_data"] = write_data(tmp_path, "maigret-mini.json", routes)
        return ctx

    def test_statuses_and_tls_sites_skipped(self, module, mctx, routes):
        results = by_source(module.run(ALICE, mctx))
        assert results["FoundSite"].status is Status.FOUND
        assert results["MessageSite"].status is Status.NOT_FOUND
        assert "TlsSite" not in results
        assert "1 site(s) skipped" in results["Maigret (skipped sites)"].evidence
        assert not any(r[1].startswith("/tls/") for r in routes.requests)

    def test_honest_user_agent(self, module, mctx, routes):
        module.run(ALICE, mctx)
        agents = {r[2].get("User-Agent") for r in routes.requests}
        assert agents and all(a.startswith("selector-recon/") for a in agents)
