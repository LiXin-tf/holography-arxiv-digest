from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="全息 arXiv 每日推送")
    parser.add_argument("--dry-run", action="store_true", help="完全离线演练，不访问网络或读取密钥")
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/sample_atom.xml"))
    parser.add_argument("--state", type=Path, default=Path("data/state.json"))
    parser.add_argument("--docs", type=Path, default=Path("docs"))
    parser.add_argument("--preview", type=Path, default=Path("pushplus-preview.json"))
    parser.add_argument("--target-date", help="仅在线模式：指定 UTC 日期 YYYY-MM-DD")
    args = parser.parse_args()
    result = run_pipeline(dry_run=args.dry_run, fixture=args.fixture, state_path=args.state,
                          docs_dir=args.docs, preview_path=args.preview, target_date=args.target_date)
    prefix = "DRY-RUN 完成（未发送）" if args.dry_run else "运行完成"
    print(prefix + ": " + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
