from __future__ import annotations

import re
from .feed import Paper

INCLUDE_TERMS = (
    "holograph", "ads/cft", "gauge-gravity", "gauge/gravity", "gauge gravity",
    "black brane", "fluid/gravity", "entanglement wedge", "ryu-takayanagi",
    "bulk-boundary", "anti-de sitter", "ads2", "ads3", "ads4", "ads5",
    "janus", "double-trace", "multi-trace", "quasinormal mode", "qnm",
    "sakharov", "syk", "jackiw-teitelboim", "celestial holography",
)
EXCLUDE_PATTERNS = (
    r"\b(optical|digital|computer[- ]generated|acoustic|microwave) holograph",
    r"holographic (image|imaging|display|microscopy|interferometry|storage)",
    r"laser.*holograph",
)


def is_candidate(paper: Paper) -> bool:
    if paper.source_category == "hep-th":
        return True
    text = f"{paper.title} {paper.abstract}".lower()
    if any(re.search(pattern, text) for pattern in EXCLUDE_PATTERNS):
        return False
    return any(term in text for term in INCLUDE_TERMS)
