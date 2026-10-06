"""Creative Commons license parsing and the practice catalog's license policy.

Policy (see reports/Free house music audio sources.md for the research):
- The app is free and never monetized (no paid tier, no ads), so
  NonCommercial (NC) tracks are usable. If that ever changes, flip
  `ALLOW_NONCOMMERCIAL` and rebuild the catalog -- NC tracks would have to go.
- NoDerivatives (ND) tracks are excluded by default. A DJ mix time-stretches
  and overlaps two tracks, which very likely makes it an adaptation; pre-4.0
  ND licenses don't grant adaptation rights at all, and 4.0 ND only allows
  private adaptations that can never be shared. Excluding ND keeps a future
  "export your practice mix" feature open.
- Anything we can't positively identify as a CC license (or a public-domain
  mark) is rejected: no license means all rights reserved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ALLOW_NONCOMMERCIAL = True
ALLOW_NODERIVATIVES = False

_CC_LICENSE_RE = re.compile(
    r"creativecommons\.org/licenses/(?P<code>[a-z\-]+)(?:/(?P<version>[\d.]+))?", re.IGNORECASE
)
_PUBLIC_DOMAIN_RE = re.compile(r"creativecommons\.org/(?:publicdomain/(?:zero|mark)|licenses/publicdomain)", re.IGNORECASE)

_KNOWN_CODES = {"by", "by-sa", "by-nc", "by-nc-sa", "by-nd", "by-nc-nd"}


@dataclass(frozen=True)
class License:
    url: str
    name: str  # e.g. "CC BY-NC-SA 3.0", "CC0 / Public Domain"
    attribution_required: bool
    commercial_ok: bool
    adaptations_ok: bool  # may a DJ mix (an adaptation) be made and shared?
    share_alike: bool


def parse_license(url: str | None) -> License | None:
    """Parse a Creative Commons license URL. Returns None for anything else."""
    if not url:
        return None
    url = url.strip()

    if _PUBLIC_DOMAIN_RE.search(url):
        return License(url, "CC0 / Public Domain", False, True, True, False)

    match = _CC_LICENSE_RE.search(url)
    if not match:
        return None
    code = match.group("code").lower().rstrip("-")
    if code not in _KNOWN_CODES:
        return None
    version = match.group("version") or ""
    name = f"CC {code.upper()} {version}".strip()
    return License(
        url=url,
        name=name,
        attribution_required=True,
        commercial_ok="nc" not in code.split("-"),
        adaptations_ok="nd" not in code.split("-"),
        share_alike="sa" in code.split("-"),
    )


def is_allowed(lic: License | None) -> bool:
    """Whether a track under `lic` may go into the practice catalog."""
    if lic is None:
        return False
    if not lic.commercial_ok and not ALLOW_NONCOMMERCIAL:
        return False
    if not lic.adaptations_ok and not ALLOW_NODERIVATIVES:
        return False
    return True
