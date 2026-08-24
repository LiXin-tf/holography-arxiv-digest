from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


DEFAULT_WARN_BYTES = 20 * 1024 * 1024
DEFAULT_HARD_BYTES = 90 * 1024 * 1024


class FileSizeLimitError(RuntimeError):
    pass


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for item in paths:
        path = Path(item)
        if path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield path
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    resolved = child.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        yield child


def check_file_sizes(
    paths: Iterable[Path],
    *,
    warn_bytes: int = DEFAULT_WARN_BYTES,
    hard_bytes: int = DEFAULT_HARD_BYTES,
    fail_on_hard: bool = False,
) -> dict:
    files = sorted(
        ((path, path.stat().st_size) for path in _iter_files(paths)),
        key=lambda item: item[1],
        reverse=True,
    )
    warnings = [
        {"path": str(path), "bytes": size}
        for path, size in files
        if warn_bytes <= size < hard_bytes
    ]
    hard = [
        {"path": str(path), "bytes": size}
        for path, size in files
        if size >= hard_bytes
    ]
    result = {
        "files_checked": len(files),
        "largest_file": str(files[0][0]) if files else None,
        "largest_bytes": files[0][1] if files else 0,
        "warnings": warnings,
        "hard_limit_violations": hard,
    }
    if fail_on_hard and hard:
        names = ", ".join(item["path"] for item in hard)
        raise FileSizeLimitError(
            f"文件已达到 {hard_bytes} 字节硬警戒线，请先拆分归档：{names}"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="监控归档和网站的单文件大小")
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("data"), Path("docs")])
    parser.add_argument("--warn-mb", type=float, default=20)
    parser.add_argument("--hard-mb", type=float, default=90)
    args = parser.parse_args()
    warn = int(args.warn_mb * 1024 * 1024)
    hard = int(args.hard_mb * 1024 * 1024)
    try:
        result = check_file_sizes(
            args.paths,
            warn_bytes=warn,
            hard_bytes=hard,
            fail_on_hard=True,
        )
    except FileSizeLimitError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
