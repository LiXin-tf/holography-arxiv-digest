from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from xml.etree import ElementTree as ET


@dataclass
class Paper:
    arxiv_id: str
    version: int
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    updated: str
    published: str
    source_category: str
    abs_url: str = ""
    pdf_url: str = ""
    classification: dict = field(default_factory=dict)

    @property
    def is_first_version(self) -> bool:
        return self.version == 1

    @property
    def versioned_id(self) -> str:
        return f"{self.arxiv_id}v{self.version}"


_ID_RE = re.compile(r"(?:(?:https?://)?(?:export\.)?arxiv\.org/abs/|arXiv:|oai:arXiv\.org:)?(?P<id>(?:[a-z-]+(?:\.[A-Z-]+)?/\d{7}|\d{4}\.\d{4,5}))v(?P<version>\d+)$", re.I)


def normalize_arxiv_id(value: str) -> tuple[str, int]:
    match = _ID_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"无效的 arXiv ID: {value}")
    return match.group("id"), int(match.group("version"))


def _text(entry: ET.Element, tag: str) -> str:
    node = entry.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
    return " ".join((node.text or "").split()) if node is not None else ""


def parse_atom(content: bytes, source_category: str) -> list[Paper]:
    root = ET.fromstring(content)
    ns = "{http://www.w3.org/2005/Atom}"
    papers: list[Paper] = []
    for entry in root.findall(f"{ns}entry"):
        arxiv_id, version = normalize_arxiv_id(_text(entry, "id"))
        links = {link.get("type", ""): link.get("href", "") for link in entry.findall(f"{ns}link")}
        authors = [_text(author, "name") for author in entry.findall(f"{ns}author")]
        if not authors:
            creator = entry.find("{http://purl.org/dc/elements/1.1/}creator")
            authors = [name.strip() for name in (creator.text or "").split(",") if name.strip()] if creator is not None else []
        abstract = _text(entry, "summary")
        abstract = re.sub(r"^arXiv:\S+\s+Announce Type:\s*\S+\s+Abstract:\s*", "", abstract, flags=re.I)
        papers.append(Paper(
            arxiv_id=arxiv_id,
            version=version,
            title=_text(entry, "title"),
            abstract=abstract,
            authors=authors,
            categories=[node.get("term", "") for node in entry.findall(f"{ns}category")],
            updated=_text(entry, "updated"),
            published=_text(entry, "published"),
            source_category=source_category,
            abs_url=f"https://arxiv.org/abs/{arxiv_id}v{version}",
            pdf_url=links.get("application/pdf", f"https://arxiv.org/pdf/{arxiv_id}v{version}"),
        ))
    return papers
