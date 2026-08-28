from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")
START = time(13, 0)
END = time(20, 0)


def is_allowed_time(now: datetime | None = None) -> bool:
    """Allow scheduled processing only in the Beijing daytime window."""
    current = now or datetime.now(BEIJING)
    local = current.astimezone(BEIJING)
    return START <= local.time() < END


def main() -> int:
    import os
    allowed = is_allowed_time()
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"allowed={'true' if allowed else 'false'}\n")
    print(f"北京时间推送窗口: {'允许' if allowed else '跳过'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
