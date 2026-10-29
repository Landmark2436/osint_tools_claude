"""Domain and IP modules against the local fixture server and a fake resolver."""

from selector_recon.models import Selector, SelectorType, Status
from selector_recon.modules.censys import Censys
from selector_recon.modules.crtsh import CrtSh
from selector_recon.modules.dns_records import Dns
from selector_recon.modules.ip_info import IpInfo
from selector_recon.modules.rdap import Rdap
from selector_recon.modules.shodan import Shodan, ShodanDns
from selector_recon.modules.wayback import Wayback

from .test_email_phone import FakeDns

DOMAIN = Selector("example.com", SelectorType.DOMAIN)
IP = Selector("8.8.8.8", SelectorType.IP)
PRIVATE = Selector("10.0.0.1", SelectorType.IP)


def test_domain_dns_records_and_ip_pivots(ctx):
    ctx.dns = FakeDns({
        ("example.com", "A"): ["93.184.215.14"],
        ("example.com", "NS"): ["a.iana-servers.net", "b.iana-servers.net"],
        ("example.com", "MX"): ["0"],
        ("_dmarc.example.com", "TXT"): ["v=DMARC1;p=reject"],
    })
    res = {f.source: f for f in Dns().run(DOMAIN, ctx)}
    assert set(res) == {"A", "NS", "MX", "DMARC"}
    assert [p.value for p in res["A"].pivots] == ["93.184.215.14"]


def test_ptr(ctx):
    ctx.dns = FakeDns({("8.8.8.8", "PTR"): ["dns.google"]})
    (f,) = Dns().run(IP, ctx)
    assert f.status is Status.FOUND and f.pivots[0].value == "dns.google"
    (p,) = Dns().run(PRIVATE, ctx)
    assert p.status is Status.NOT_FOUND and "not a public address" in p.evidence


def test_ip_info(ctx):
    (f,) = IpInfo().run(Selector("192.0.2.1", SelectorType.IP), ctx)
    assert f.data["is_global"] is False
    assert any("documentation range" in x for x in f.flags)


def test_rdap_domain_and_ip(ctx, server, monkeypatch):
    monkeypatch.setattr(Rdap, "base", f"{server.base}/")
    server.add_fixture("/domain/example.com", "rdap_domain.json")
    server.add_fixture("/ip/8.8.8.8", "rdap_ip.json")
    (d,) = Rdap().run(Selector("www.example.com", SelectorType.DOMAIN), ctx)
    assert d.status is Status.FOUND
    assert "registrar Example Registrar, Inc." in d.evidence and "registration 1995-08-14" in d.evidence
    assert d.pivots[0].value == "example.com"
    (i,) = Rdap().run(IP, ctx)
    assert "8.8.8.0 - 8.8.8.255" in i.evidence and i.data["entities"]["registrant"] == "Example Networks LLC"
    (missing,) = Rdap().run(Selector("unregistered.example", SelectorType.DOMAIN), ctx)
    assert missing.status is Status.NOT_FOUND and missing.manual


def test_crtsh(ctx, server, monkeypatch):
    monkeypatch.setattr(CrtSh, "base", f"{server.base}/")
    server.add_fixture("/?q=%25.example.com&output=json", "crtsh.json")
    (f,) = CrtSh().run(DOMAIN, ctx)
    assert f.data["hostnames"] == ["example.com", "mail.example.com", "www.example.com"]  # other.test dropped
    assert {p.value for p in f.pivots} == {"mail.example.com", "www.example.com"}
    assert "first 2020-01-01, latest 2024-06-01" in f.evidence


def test_crtsh_overloaded_is_manual(ctx, server, monkeypatch):
    monkeypatch.setattr(CrtSh, "base", f"{server.base}/")
    server.add("/?q=%25.example.com&output=json", 502, "Bad Gateway")
    (f,) = CrtSh().run(DOMAIN, ctx)
    assert f.status is Status.ERROR and f.manual


def test_wayback(ctx, server, monkeypatch):
    monkeypatch.setattr(Wayback, "base", f"{server.base}/")
    q = "/cdx/search/cdx?url=example.com&matchType=domain&output=json&fl=timestamp,original,statuscode&limit="
    server.add_fixture(q + "1", "wayback_first.json")
    server.add_fixture(q + "-1", "wayback_last.json")
    (f,) = Wayback().run(DOMAIN, ctx)
    assert "first capture 2002-01-20" in f.evidence and "latest 2026-10-20" in f.evidence


def test_shodan_internetdb_without_key(ctx, server, monkeypatch):
    monkeypatch.delenv("SHODAN_API_KEY", raising=False)
    monkeypatch.setattr(Shodan, "internetdb", f"{server.base}/")
    server.add_fixture("/8.8.8.8", "internetdb.json")
    (f,) = Shodan().run(IP, ctx)
    assert f.source == "Shodan InternetDB" and f.data["ports"] == [53, 443]
    assert f.pivots[0].value == "dns.example"
    (p,) = Shodan().run(PRIVATE, ctx)
    assert p.status is Status.NOT_FOUND and len(server.requests) == 1


def test_shodan_host_api_with_key_never_leaks_key(ctx, server, monkeypatch):
    monkeypatch.setenv("SHODAN_API_KEY", "shodan-secret")
    monkeypatch.setattr(Shodan, "api", f"{server.base}/")
    server.add_fixture("/shodan/host/8.8.8.8?key=shodan-secret&minify=true", "shodan_host.json")
    (f,) = Shodan().run(IP, ctx)
    assert f.source == "Shodan host API" and f.data["vulns"] == ["CVE-2020-0001"] and f.data["org"] == "Example Org"
    assert "shodan-secret" not in str(f.to_dict())


def test_shodan_dns_needs_key(ctx, server, monkeypatch):
    monkeypatch.delenv("SHODAN_API_KEY", raising=False)
    assert "SHODAN_API_KEY" in ShodanDns().unavailable_reason()
    assert ShodanDns.default_enabled is False
    monkeypatch.setenv("SHODAN_API_KEY", "k")
    monkeypatch.setattr(ShodanDns, "api", f"{server.base}/")
    server.add_fixture("/dns/domain/example.com?key=k", "shodan_dns.json")
    (f,) = ShodanDns().run(DOMAIN, ctx)
    assert f.data["subdomains"] == ["mail.example.com", "www.example.com"]


def test_censys(ctx, server, monkeypatch):
    monkeypatch.delenv("CENSYS_API_TOKEN", raising=False)
    assert "CENSYS_API_TOKEN" in Censys().unavailable_reason()
    monkeypatch.setenv("CENSYS_API_TOKEN", "censys-secret")
    monkeypatch.setenv("CENSYS_ORG_ID", "org-1")
    monkeypatch.setattr(Censys, "api", f"{server.base}/v3/global/asset/host/")
    server.add_fixture("/v3/global/asset/host/8.8.8.8", "censys_host.json")
    (f,) = Censys().run(IP, ctx)
    assert "53/DNS" in f.evidence and "AS15169" in f.evidence
    assert [p.value for p in f.pivots] == ["dns.example", "dns2.example"]
    headers = server.requests[-1][2]
    assert headers["Authorization"] == "Bearer censys-secret" and headers["X-Organization-ID"] == "org-1"
    assert "censys-secret" not in str(f.to_dict())


def test_lying_resolver_is_not_a_negative(monkeypatch):
    from selector_recon.dnsutil import DnsClient, DnsResult

    client = DnsClient()
    monkeypatch.setattr(client, "_query", lambda name, rtype: DnsResult(name, rtype, error="NXDOMAIN"))
    assert client.query("example.com", "MX").error == "UntrustedResolver"


def test_honest_nxdomain_is_kept(monkeypatch):
    from selector_recon.dnsutil import CANARY, DnsClient, DnsResult

    client = DnsClient()
    monkeypatch.setattr(client, "_query", lambda name, rtype: DnsResult(name, rtype, ["192.0.2.1"]) if name == CANARY
                        else DnsResult(name, rtype, error="NXDOMAIN"))
    assert client.query("nope.example", "MX").nxdomain
