"""Small cached DNS client on top of dnspython. Uses the system resolver unless nameservers are given."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class DnsResult:
    name: str
    rtype: str
    records: list[str] = field(default_factory=list)
    error: str | None = None  # NXDOMAIN, NoAnswer, NoNameservers, Timeout, ...

    @property
    def nxdomain(self) -> bool:
        return self.error == "NXDOMAIN"


# Names that always exist. If one of them is NXDOMAIN, the resolver lies (filtered network,
# captive portal, sandbox) and NXDOMAIN answers cannot be trusted.
CANARY = "iana.org"


class DnsClient:
    def __init__(self, timeout: float = 5.0, nameservers: list[str] | None = None) -> None:
        self.timeout = timeout
        self.nameservers = nameservers
        self._cache: dict[tuple[str, str], DnsResult] = {}
        self._lock = threading.Lock()
        self._resolver = None
        self._trusted: bool | None = None

    def _get_resolver(self):
        if self._resolver is None:
            import dns.resolver

            resolver = dns.resolver.Resolver(configure=not self.nameservers)
            if self.nameservers:
                resolver.nameservers = list(self.nameservers)
            resolver.lifetime = self.timeout
            self._resolver = resolver
        return self._resolver

    def query(self, name: str, rtype: str) -> DnsResult:
        key = (name.lower().rstrip("."), rtype.upper())
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        result = self._query(*key)
        if result.nxdomain and key[0] != CANARY and not self.resolver_trusted():
            result = DnsResult(result.name, result.rtype, error="UntrustedResolver")
        with self._lock:
            self._cache[key] = result
        return result

    def resolver_trusted(self) -> bool:
        """False if the resolver claims that a name which always exists does not exist."""
        if self._trusted is None:
            self._trusted = not self._query(CANARY, "A").nxdomain
        return self._trusted

    def _query(self, name: str, rtype: str) -> DnsResult:
        import dns.exception
        import dns.resolver

        try:
            answer = self._get_resolver().resolve(name, rtype)
        except dns.resolver.NXDOMAIN:
            return DnsResult(name, rtype, error="NXDOMAIN")
        except dns.resolver.NoAnswer:
            return DnsResult(name, rtype, error="NoAnswer")
        except dns.resolver.NoNameservers:
            return DnsResult(name, rtype, error="NoNameservers")
        except dns.exception.Timeout:
            return DnsResult(name, rtype, error="Timeout")
        except dns.exception.DNSException as exc:
            return DnsResult(name, rtype, error=type(exc).__name__)
        records = []
        for rdata in answer:
            if rtype == "TXT":
                records.append(b"".join(rdata.strings).decode("utf-8", "replace"))
            else:
                records.append(rdata.to_text().rstrip("."))
        return DnsResult(name, rtype, sorted(records))

    def reverse(self, ip: str) -> DnsResult:
        import dns.reversename

        return self.query(dns.reversename.from_address(ip).to_text(), "PTR")
