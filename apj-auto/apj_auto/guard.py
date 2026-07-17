# -*- coding: utf-8 -*-
"""実行ガード: 営業日判定と同日二重実行の防止。"""

import datetime
import json
from pathlib import Path

import jpholiday


def is_business_day(d: datetime.date) -> bool:
    """平日かつ日本の祝日でない日のみ True。"""
    if d.weekday() >= 5:  # 土日
        return False
    if jpholiday.is_holiday(d):
        return False
    return True


class RunState:
    """当日の実行状態を state/YYYY-MM-DD.json に永続化する。

    - 同日2回目の実行は completed なら即スキップ（二重発注防止）
    - 途中失敗時は「どこまで完了したか」を保持し、再実行時に
      メール送信済みなら再送せず GoQ 更新のみ再開できるようにする
    """

    STEPS = ("fetched", "xlsx", "review_sent", "mail_sent", "memo_done",
             "status_done")

    def __init__(self, state_dir: Path, day: datetime.date):
        self.path = state_dir / f"{day.isoformat()}.json"
        self.data = {
            "date": day.isoformat(),
            "order_ids": [],
            "xlsx_path": "",
            "steps": {k: False for k in self.STEPS},
            "completed": False,
            "note": "",
        }
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass  # 壊れたstateは新規として扱う（メール再送はmail_sentで別途防止）

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @property
    def completed(self) -> bool:
        return bool(self.data.get("completed"))

    def step_done(self, step: str) -> bool:
        return bool(self.data["steps"].get(step))

    def mark(self, step: str, **extra):
        self.data["steps"][step] = True
        self.data.update(extra)
        self.save()

    def finish(self, note: str = ""):
        self.data["completed"] = True
        self.data["note"] = note
        self.save()
