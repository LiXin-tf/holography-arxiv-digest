from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .feed import Paper


SCHEMA_VERSION = 2
ARCHIVE_SCHEMA_VERSION = 1
MAX_PUSH_LOGS = 400
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def dedupe_papers(papers: list[Paper]) -> list[Paper]:
    unique: dict[str, Paper] = {}
    for paper in papers:
        if paper.arxiv_id not in unique:
            unique[paper.arxiv_id] = paper
            continue
        existing = unique[paper.arxiv_id]
        merged_categories = list(dict.fromkeys(existing.categories + paper.categories))
        chosen = paper if paper.version > existing.version else existing
        chosen.categories = merged_categories
        unique[paper.arxiv_id] = chosen
    return list(unique.values())


def paper_to_dict(paper: Paper) -> dict:
    return asdict(paper)


def paper_from_dict(data: dict) -> Paper:
    fields = {
        key: data[key]
        for key in (
            "arxiv_id",
            "version",
            "title",
            "abstract",
            "authors",
            "categories",
            "updated",
            "published",
            "source_category",
            "abs_url",
            "pdf_url",
            "classification",
        )
        if key in data
    }
    return Paper(**fields)


def paper_month(paper: Paper) -> str:
    for value in (paper.updated, paper.published):
        month = (value or "")[:7]
        if _MONTH_RE.fullmatch(month):
            return month
    raise ValueError(f"论文 {paper.versioned_id} 缺少有效年月")


class StateStore:
    """Lightweight dedupe index plus immutable-ish monthly paper archives."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.archive_dir = self.path.parent / "archive"
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"schema_version": SCHEMA_VERSION, "papers": {}, "pushes": []}
        if self.data.get("schema_version", 1) < SCHEMA_VERSION or self._has_embedded_papers():
            self._migrate_legacy_state()

    def _has_embedded_papers(self) -> bool:
        return any(
            "paper" in record or "version_records" in record
            for record in self.data.get("papers", {}).values()
        )

    def _archive_path(self, month: str) -> Path:
        return self.archive_dir / f"{month}.json"

    def _load_archive(self, month: str) -> dict:
        path = self._archive_path(month)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {
            "schema_version": ARCHIVE_SCHEMA_VERSION,
            "month": month,
            "papers": {},
        }

    def _save_archive(self, month: str, archive: dict) -> None:
        path = self._archive_path(month)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(archive, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _migrate_legacy_state(self) -> None:
        new_papers: dict[str, dict] = {}
        archives: dict[str, dict] = {}
        for arxiv_id, old in self.data.get("papers", {}).items():
            raw_versions = dict(old.get("version_records") or {})
            if not raw_versions and old.get("paper"):
                raw = old["paper"]
                raw_versions[str(raw.get("version", old.get("latest_version", 1)))] = raw

            version_months: dict[str, str] = {}
            versions = sorted({int(v) for v in old.get("versions", [])} | {int(v) for v in raw_versions})
            for version, raw in raw_versions.items():
                paper = paper_from_dict(raw)
                month = paper_month(paper)
                version_months[str(version)] = month
                archive = archives.setdefault(month, self._load_archive(month))
                archive["papers"][paper.versioned_id] = paper_to_dict(paper)

            new_papers[arxiv_id] = {
                "latest_version": max(versions) if versions else int(old.get("latest_version", 1)),
                "versions": versions,
                "sent_versions": sorted({int(v) for v in old.get("sent_versions", [])}),
                "version_months": version_months,
            }

        for month, archive in archives.items():
            self._save_archive(month, archive)
        self.data = {
            "schema_version": SCHEMA_VERSION,
            "papers": new_papers,
            "pushes": list(self.data.get("pushes", []))[-MAX_PUSH_LOGS:],
        }
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["schema_version"] = SCHEMA_VERSION
        self.data["pushes"] = list(self.data.get("pushes", []))[-MAX_PUSH_LOGS:]
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record(self, papers: list[Paper]) -> list[Paper]:
        pushable: list[Paper] = []
        dirty_archives: dict[str, dict] = {}
        for paper in dedupe_papers(papers):
            old = self.data["papers"].get(paper.arxiv_id, {})
            versions = sorted(set(old.get("versions", [])) | {paper.version})
            sent_versions = sorted({int(v) for v in old.get("sent_versions", [])})
            version_months = dict(old.get("version_months", {}))
            month = version_months.get(str(paper.version)) or paper_month(paper)
            version_months[str(paper.version)] = month

            archive = dirty_archives.setdefault(month, self._load_archive(month))
            archive["papers"][paper.versioned_id] = paper_to_dict(paper)
            self.data["papers"][paper.arxiv_id] = {
                "latest_version": max(versions),
                "versions": versions,
                "sent_versions": sent_versions,
                "version_months": version_months,
            }
            if paper.version == 1 and 1 not in sent_versions:
                pushable.append(paper)

        for month, archive in dirty_archives.items():
            self._save_archive(month, archive)
        self.save()
        return pushable

    def mark_sent(
        self,
        papers: list[Paper],
        short_code: str | None = None,
        status: str = "accepted_pending_verification",
    ) -> None:
        for paper in papers:
            record = self.data["papers"][paper.arxiv_id]
            record["sent_versions"] = sorted(
                set(record.get("sent_versions", [])) | {paper.version}
            )
        self.data.setdefault("pushes", []).append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "shortCode": short_code,
                "paper_ids": [paper.versioned_id for paper in papers],
            }
        )
        self.save()

    def all_papers(self) -> list[Paper]:
        papers: dict[str, Paper] = {}
        if not self.archive_dir.exists():
            return []
        for path in sorted(self.archive_dir.glob("????-??.json")):
            archive = json.loads(path.read_text(encoding="utf-8"))
            for versioned_id, raw in archive.get("papers", {}).items():
                papers[versioned_id] = paper_from_dict(raw)
        return sorted(
            papers.values(),
            key=lambda paper: (paper.updated or paper.published, paper.arxiv_id, paper.version),
        )

    def pending_v1(self) -> list[Paper]:
        pending: list[Paper] = []
        for arxiv_id, record in self.data.get("papers", {}).items():
            if 1 not in record.get("versions", []) or 1 in record.get("sent_versions", []):
                continue
            month = record.get("version_months", {}).get("1")
            if not month:
                continue
            archive = self._load_archive(month)
            raw = archive.get("papers", {}).get(f"{arxiv_id}v1")
            if raw:
                pending.append(paper_from_dict(raw))
        return pending
