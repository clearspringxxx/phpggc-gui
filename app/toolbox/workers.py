"""一次性后台任务线程，避免子进程调用阻塞 UI。"""
from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    done = Signal(object)
    fail = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            self.done.emit(self._fn(*self._args, **self._kwargs))
        except Exception as e:  # 后端错误全部转成字符串交给 UI 展示
            self.fail.emit(str(e))
