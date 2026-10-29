"""DNS lookups: MX/SPF/DMARC for email domains, common records for domains, PTR for IPs."""

from __future__ import annotations

from ..dnsutil import DnsClient, DnsResult
from ..models import Confidence, Finding, Pivot, Selector, SelectorType, Status
from ..util import data_list, short
from .base import Module, RunContext

# MX host suffix -> mail provider
MX_PROVIDERS = {
    "google.com": "Google (Gmail / Workspace)",
    "googlemail.com": "Google (Gmail / Workspace)",
    "outlook.com": "Microsoft (Outlook / Microsoft 365)",
    "protection.outlook.com": "Microsoft 365",
    "protonmail.ch": "Proton Mail",
    "icloud.com": "Apple iCloud",
    "messagingengine.com": "Fastmail",
    "zoho.com": "Zoho Mail",
    "zoho.eu": "Zoho Mail",
    "yandex.net": "Yandex",
    "yandex.ru": "Yandex",
    "mail.ru": "Mail.ru",
    "gmx.net": "GMX / 1&1",
    "web.de": "WEB.DE / 1&1",
    "kundenserver.de": "IONOS",
    "ionos.com": "IONOS",
    "secureserver.net": "GoDaddy",
    "mimecast.com": "Mimecast (filtering gateway)",
    "pphosted.com": "Proofpoint (filtering gateway)",
    "amazonaws.com": "Amazon SES / AWS",
    "tutanota.de": "Tuta",
    "mailbox.org": "mailbox.org",
    "posteo.de": "Posteo",
    "t-online.de": "Telekom (t-online)",
}

DOMAIN_RECORDS = ("A", "AAAA", "NS", "MX", "TXT", "CAA", "SOA")


def mx_provider(hosts: list[str]) -> str | None:
    for host in hosts:
        h = host.lower()
        for suffix, provider in MX_PROVIDERS.items():
            if h == suffix or h.endswith("." + suffix):
                return provider
    return None


class Dns(Module):
    name = "dns"
    title = "DNS"
    selector_types = frozenset({SelectorType.EMAIL, SelectorType.DOMAIN, SelectorType.IP})
    description = "Email: MX/SPF/DMARC and mail provider. Domain: A/AAAA/NS/MX/TXT/CAA/SOA/DMARC. IP: reverse DNS."
    homepage = "https://www.dnspython.org/"
    license = "dnspython ISC"
    tos = "Standard DNS queries via your resolver."
    can_notify = "no (the domain's nameserver only sees a query from your resolver)"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        dns = ctx.dns or DnsClient(timeout=min(ctx.timeout, 5.0))
        if selector.type is SelectorType.EMAIL:
            return self.email(selector, selector.value.rpartition("@")[2], dns)
        if selector.type is SelectorType.DOMAIN:
            return self.domain(selector, dns)
        return self.ptr(selector, dns)

    def _error(self, selector: Selector, source: str, res: DnsResult) -> Finding:
        status = Status.NOT_FOUND if res.error in ("NXDOMAIN", "NoAnswer") else Status.ERROR
        if res.error == "UntrustedResolver":
            return self.finding(selector, source, status, evidence=f"{res.rtype} {res.name}: resolver answers NXDOMAIN even "
                                "for known names (filtered network?); use --dns-server")
        return self.finding(selector, source, status, evidence=f"{res.rtype} {res.name}: {res.error}")

    def email(self, selector: Selector, domain: str, dns: DnsClient) -> list[Finding]:
        out = []
        mx = dns.query(domain, "MX")
        if mx.error == "UntrustedResolver":
            return [self._error(selector, "DNS", mx)]
        if mx.nxdomain:
            return [self.finding(selector, "MX", Status.NOT_FOUND, confidence=Confidence.HIGH,
                                 evidence=f"domain {domain} does not exist (NXDOMAIN): the address cannot receive mail")]
        if mx.records:
            hosts = [r.split()[-1] for r in mx.records]
            # A null MX ("0 .") arrives here as just the preference, since trailing dots are stripped.
            if all(len(r.split()) == 1 for r in mx.records):
                out.append(self.finding(selector, "MX", Status.NOT_FOUND, confidence=Confidence.HIGH,
                                        evidence=f"null MX: {domain} accepts no mail (RFC 7505)", data={"mx": mx.records}))
            else:
                provider = mx_provider(hosts)
                ev = "MX " + ", ".join(mx.records[:5]) + (f"; provider: {provider}" if provider else "")
                out.append(self.finding(selector, "MX", Status.FOUND, evidence=short(ev, 200),
                                        data={"mx": mx.records, "provider": provider}))
        elif mx.error == "NoAnswer":
            a = dns.query(domain, "A")
            ev = f"no MX; {'A record exists, mail would go to ' + ', '.join(a.records) if a.records else 'no A record either'}"
            out.append(self.finding(selector, "MX", Status.NOT_FOUND, evidence=ev))
        else:
            out.append(self._error(selector, "MX", mx))
        out.append(self.spf(selector, domain, dns))
        out.append(self.dmarc(selector, domain, dns))
        return out

    def spf(self, selector: Selector, domain: str, dns: DnsClient) -> Finding:
        txt = dns.query(domain, "TXT")
        if txt.error and txt.error not in ("NoAnswer",):
            return self._error(selector, "SPF", txt)
        spf = [r for r in txt.records if r.lower().startswith("v=spf1")]
        if not spf:
            return self.finding(selector, "SPF", Status.NOT_FOUND, evidence=f"no SPF record for {domain}")
        includes = [t.split(":", 1)[1] for t in spf[0].split() if t.lower().startswith(("include:", "redirect="))]
        return self.finding(selector, "SPF", Status.FOUND, evidence=short(spf[0], 200), data={"spf": spf[0], "includes": includes})

    def dmarc(self, selector: Selector, domain: str, dns: DnsClient) -> Finding:
        res = dns.query(f"_dmarc.{domain}", "TXT")
        rec = [r for r in res.records if r.lower().startswith("v=dmarc1")]
        if rec:
            return self.finding(selector, "DMARC", Status.FOUND, evidence=short(rec[0], 200), data={"dmarc": rec[0]})
        if res.error in (None, "NXDOMAIN", "NoAnswer"):
            return self.finding(selector, "DMARC", Status.NOT_FOUND, evidence=f"no DMARC record at _dmarc.{domain}")
        return self._error(selector, "DMARC", res)

    def domain(self, selector: Selector, dns: DnsClient) -> list[Finding]:
        d = selector.value
        out, pivots = [], []
        results = {rtype: dns.query(d, rtype) for rtype in DOMAIN_RECORDS}
        if all(r.error == "UntrustedResolver" for r in results.values()):
            return [self._error(selector, "DNS", results["A"])]
        if all(r.nxdomain for r in results.values()):
            return [self.finding(selector, "DNS", Status.NOT_FOUND, confidence=Confidence.HIGH,
                                 evidence=f"{d} does not exist (NXDOMAIN)")]
        for rtype, res in results.items():
            if res.records:
                if rtype in ("A", "AAAA"):
                    pivots = [Pivot(SelectorType.IP, ip, f"{rtype} record of {d}") for ip in res.records]
                else:
                    pivots = []
                if rtype == "MX":
                    provider = mx_provider([r.split()[-1] for r in res.records])
                    extra = f"; provider: {provider}" if provider else ""
                else:
                    extra = ""
                out.append(self.finding(selector, rtype, Status.FOUND, evidence=short(f"{rtype} " + ", ".join(res.records) + extra, 240),
                                        data={"records": res.records}, pivots=pivots))
            elif res.error in ("NoAnswer", "NXDOMAIN"):
                continue  # absent record types are not worth a row
            else:
                out.append(self._error(selector, rtype, res))
        out.append(self.dmarc(selector, d, dns))
        if out and d in data_list("disposable_domains.txt"):
            out[0].flags.append("disposable-address domain")
        return out

    def ptr(self, selector: Selector, dns: DnsClient) -> list[Finding]:
        if blocked := self.not_public(selector):
            return blocked
        res = dns.reverse(selector.value)
        if res.records:
            pivots = [Pivot(SelectorType.DOMAIN, h, "reverse DNS name") for h in res.records]
            return [self.finding(selector, "PTR", Status.FOUND, evidence="PTR " + ", ".join(res.records),
                                 data={"ptr": res.records}, pivots=pivots)]
        if res.error in ("NXDOMAIN", "NoAnswer"):
            return [self.finding(selector, "PTR", Status.NOT_FOUND, evidence="no reverse DNS name")]
        return [self._error(selector, "PTR", res)]
