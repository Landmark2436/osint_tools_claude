"""Offline IP address facts: version, scope (public/private/reserved), reverse-DNS name."""

from __future__ import annotations

import ipaddress

from ..models import Confidence, Finding, Selector, SelectorType, Status
from .base import Module, RunContext


def scope(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    for attr in ("is_loopback", "is_link_local", "is_multicast", "is_private", "is_reserved", "is_unspecified"):
        if getattr(ip, attr):
            return attr[3:].replace("_", "-")
    return "public" if ip.is_global else "special-purpose"


class IpInfo(Module):
    name = "ip_info"
    title = "IP address"
    selector_types = frozenset({SelectorType.IP})
    needs_network = False
    description = "Offline: IP version, scope (public, private, reserved, documentation ranges), PTR name."
    license = "own code"
    tos = "No network access."
    can_notify = "no"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        ip = ipaddress.ip_address(selector.value)
        data = {"version": ip.version, "scope": scope(ip), "reverse_pointer": ip.reverse_pointer, "is_global": ip.is_global}
        flags = []
        docs = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32")]
        if any(ip in n for n in docs if n.version == ip.version):
            flags.append("documentation range (RFC 5737/3849): example address")
        return [self.finding(selector, self.title, Status.FOUND, confidence=Confidence.HIGH, data=data, flags=flags,
                             evidence=f"IPv{ip.version}, {data['scope']}; PTR name {ip.reverse_pointer}")]
