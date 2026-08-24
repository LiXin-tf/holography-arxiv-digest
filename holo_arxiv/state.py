from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from .feed import Paper


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
    fields = {key: data[key] for key in (
        "arxiv_id", "version", "title", "abstract", "authors", "categories",
        "updated", "published", "source_category", "abs_url", "pdf_url", "classification"
    ) if key in data}
    return Paper(**fields)


class StateStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"schema_version": 1, "papers": {}, "pushes": []}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, papers: list[Paper]) -> list[Paper]:
        pushable = []
        for paper in dedupe_papers(papers):
            old = self.data["papers"].get(paper.arxiv_id, {})
            versions = sorted(set(old.get("versions", [])) | {paper.version})
            sent_versions = old.get("sent_versions", [])
            version_records = old.get("version_records", {})
            if not version_records and old.get("paper"):
                previous = old["paper"]
                version_records[str(previous.get("version", old.get("latest_version", 1)))] = previous
            version_records[str(paper.version)] = paper_to_dict(paper)
            record = {
                "latest_version": max(versions),
                "versions": versions,
                "sent_versions": sent_versions,
                "version_records": version_records,
                "paper": version_records[str(max(versions))],
            }
            self.data["papers"][paper.arxiv_id] = record
            if paper.version == 1 and 1 not in sent_versions:
                pushable.append(paper)
        self.save()
        return pushable

    def mark_sent(self, papers: list[Paper], short_code: str | None = None,
                  status: str = "accepted_pending_verification") -> None:
        for paper in papers:
            record = self.data["papers"][paper.arxiv_id]
            record["sent_versions"] = sorted(set(record["sent_versions"]) | {paper.version})
        self.data["pushes"].append({
            "at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "shortCode": short_code,
            "paper_ids": [paper.versioned_id for paper in papers],
        })
        self.save()

    def all_papers(self) -> list[Paper]:
        papers: list[Paper] = []
        for record in self.data["papers"].values():
            version_records = record.get("version_records")
            if version_records:
                papers.extend(paper_from_dict(value) for _, value in sorted(version_records.items(), key=lambda item: int(item[0])))
            else:
                papers.append(paper_from_dict(record["paper"]))
        return papers
