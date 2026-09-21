"""payload 生成历史记录，持久化到 data/history.json。"""
import json
import time
from pathlib import Path


class HistoryStore:
    MAX_ENTRIES = 200

    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: list[dict] = []
        self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.entries = data
        except (OSError, json.JSONDecodeError):
            self.entries = []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, chain: str, params: list[str], options_desc: str,
            payload: str, kind: str = "text") -> dict:
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chain": chain,
            "params": params,
            "options": options_desc,
            "payload": payload if kind == "text" else "",
            "kind": kind,
        }
        self.entries.insert(0, entry)
        del self.entries[self.MAX_ENTRIES:]
        try:
            self._save()
        except OSError:
            pass
        return entry

    def remove(self, index: int):
        if 0 <= index < len(self.entries):
            del self.entries[index]
            try:
                self._save()
            except OSError:
                pass

    def clear(self):
        self.entries = []
        try:
            self._save()
        except OSError:
            pass
