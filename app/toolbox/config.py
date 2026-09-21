"""项目路径与配置持久化。

整个工具箱是便携的：默认路径全部基于项目根目录计算，
config.json 只在用户于设置对话框中修改过路径时才与默认值不同。
"""
import json
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent          # app/toolbox
PROJECT_ROOT = APP_DIR.parent.parent               # 项目根目录
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULTS = {
    "php_exe": str(PROJECT_ROOT / "runtime" / "php" / "php.exe"),
    "phpggc_dir": str(PROJECT_ROOT / "phpggc"),
}


def load_config() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.is_file():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save_config(cfg: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
