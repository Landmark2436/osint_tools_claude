"""Offline phone number analysis with phonenumbers (Google libphonenumber port)."""

from __future__ import annotations

from ..models import Confidence, Finding, Selector, SelectorType, Status
from .base import Module, RunContext


def analyze(value: str, region: str | None = None) -> dict:
    """Parse and describe a phone number. Pure function, no I/O. Raises ValueError if unparseable."""
    import phonenumbers
    from phonenumbers import PhoneNumberFormat as F
    from phonenumbers import carrier, geocoder, timezone

    try:
        n = phonenumbers.parse(value, region.upper() if region else None)
    except phonenumbers.NumberParseException as exc:
        raise ValueError(str(exc)) from None
    region_code = phonenumbers.region_code_for_number(n)
    number_type = phonenumbers.number_type(n)
    type_name = next((k for k, v in vars(phonenumbers.PhoneNumberType).items() if v == number_type and k.isupper()), "UNKNOWN")
    national = str(n.national_number)
    return {
        "e164": phonenumbers.format_number(n, F.E164),
        "international": phonenumbers.format_number(n, F.INTERNATIONAL),
        "national": phonenumbers.format_number(n, F.NATIONAL),
        "country_code": n.country_code,
        "national_number": national,
        "region": region_code,
        "country": geocoder.country_name_for_number(n, "en") or None,
        "location": geocoder.description_for_number(n, "en") or None,
        "carrier": carrier.name_for_number(n, "en") or None,
        "type": type_name.lower(),
        "time_zones": list(timezone.time_zones_for_number(n)),
        "valid": phonenumbers.is_valid_number(n),
        "possible": phonenumbers.is_possible_number(n),
        # NANP 555-0100..0199 is reserved for fiction (films, examples, CTF personas).
        "fictional": n.country_code == 1 and len(national) == 10 and national[3:6] == "555" and national[6:8] == "01",
    }


class PhoneInfo(Module):
    name = "phone_info"
    title = "phonenumbers"
    selector_types = frozenset({SelectorType.PHONE})
    needs_network = False
    description = "Offline: validity, E.164, country/region, original carrier, number type, time zones."
    homepage = "https://github.com/daviddrysdale/python-phonenumbers"
    license = "Apache-2.0"
    tos = "No network access."
    can_notify = "no"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        try:
            a = analyze(selector.value, ctx.options.get("region"))
        except ValueError as exc:
            hint = "" if ctx.options.get("region") else " (no +country code: pass --region, e.g. --region DE)"
            return [self.finding(selector, self.title, Status.NOT_FOUND, confidence=Confidence.HIGH,
                                 evidence=f"cannot parse: {exc}{hint}")]
        loc, country = a["location"], a["country"]
        place = f"{loc}, {country}" if loc and country and loc != country else (loc or country or a["region"] or "")
        parts = [
            "valid" if a["valid"] else ("possible but not valid" if a["possible"] else "invalid"),
            a["type"].replace("_", " "),
            a["e164"],
            place,
        ]
        if a["carrier"]:
            parts.append(f"carrier {a['carrier']} (original allocation; ported numbers differ)")
        if a["time_zones"]:
            parts.append("tz " + ", ".join(a["time_zones"][:3]))
        flags = ["fictional NANP 555-01xx number"] if a["fictional"] else []
        status = Status.FOUND if a["valid"] else Status.NOT_FOUND
        return [self.finding(selector, self.title, status, confidence=Confidence.HIGH,
                             evidence="; ".join(p for p in parts if p), data=a, flags=flags)]
