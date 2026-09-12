#!/usr/bin/env python3
"""The citation-stability rule, in one place.

Admissibility asks whether a source is a credible KIND of source. Stability asks
whether the cited page will still contain the claim tomorrow. A rotating "current
top ten" index passes the first and fails the second: the claim stays true while
the citation goes false. That is the worst failure mode for a citation read aloud
at a board meeting, and it is what the accuracy gate found in the sample run
(3 of 35 known-list flags; see accuracy-gate-2026-08-21.md).

Single source of truth for the rule, imported by qc-sweep.py, accuracy-gate.py,
and both report renderers, so a citation that fails the sweep cannot silently
render as a clean link.
"""
import re

# Pages whose contents are replaced each cycle.
ROTATING_INDEX = re.compile(
    r"/(top10|topten|top-10|frequentlychallengedbooks/?$|banned-?books-?week/?$)", re.I)
# Anchors that pin a page to a fixed edition: an explicit year, a decade
# retrospective, or an archive snapshot.
STABLE_ANCHOR = re.compile(r"(19|20)\d\d|decade|web\.archive\.org", re.I)
DATED_CLAIM = re.compile(r"\b(19|20)\d\d\b")

MARKER = "⚠ citation needs repointing to a dated or archived page"


def _path(url: str) -> str:
    return url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url


def is_unstable(url: str, claim: str) -> bool:
    """True when a claim asserting a specific year cites a rotating index.

    `claim` is whatever text carries the date: a known-list flag's `claim`, or a
    category source's `date_or_year`. The defect is the same in both layers —
    the accuracy gate found it in the flag layer first, but five category
    sources in the same sample carry it too.
    """
    return bool(
        ROTATING_INDEX.search(url)
        and not STABLE_ANCHOR.search(_path(url))
        and DATED_CLAIM.search(claim or "")
    )


def annotate(url: str, claim: str) -> str:
    """Marker to append to a rendered citation, or an empty string."""
    return f" _({MARKER})_" if is_unstable(url, claim) else ""
