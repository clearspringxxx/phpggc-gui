"""PHPGGC 反序列化漏洞利用工具箱 —— 入口。

由项目内 runtime/python 启动，用法见项目根目录的 启动工具箱.bat。
"""
import sys
import traceback
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent          # app/
PROJECT_ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))


def _log_crash(text: str):
    try:
        (PROJECT_ROOT / "data").mkdir(exist_ok=True)
        (PROJECT_ROOT / "data" / "error.log").write_text(text, encoding="utf-8")
    except OSError:
        pass


def main() -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from toolbox.main_window import MainWindow
    from toolbox.theme import apply_theme

    app = QApplication(sys.argv)
    app.setApplicationName("PHPGGC GUI")
    app.setOrganizationName("phpggc-gui")
    apply_theme(app)

    def excepthook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        _log_crash(text)
        QMessageBox.critical(None, "未处理的异常", text[-2000:])

    sys.excepthook = excepthook

    try:
        win = MainWindow()
        win.show()
    except Exception:
        text = traceback.format_exc()
        _log_crash(text)
        QMessageBox.critical(None, "启动失败", text[-2000:])
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
