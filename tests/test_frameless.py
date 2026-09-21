"""无边框窗口交互逻辑离屏测试（不弹窗、不依赖前台）。"""
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from toolbox.theme import apply_theme
from toolbox.main_window import MainWindow


def mouse_event(etype, x, y, button=None, buttons=None):
    return QMouseEvent(
        etype, QPointF(x, y), QPointF(x, y),
        button or Qt.NoButton, buttons or Qt.NoButton, Qt.NoModifier,
    )


def main():
    app = QApplication(sys.argv)
    apply_theme(app)
    win = MainWindow()
    win.show()
    app.processEvents()

    # 1. 标题与无边框
    assert win.windowTitle() == "PHPGGC GUI"
    assert bool(win.windowFlags() & Qt.FramelessWindowHint)

    # 2. 顶栏拖动：按下 → 移动 → 窗口位移 50,60
    bar = win.topbar
    geo0 = win.frameGeometry().topLeft()
    QApplication.sendEvent(bar, mouse_event(QEvent.MouseButtonPress, 300, 10,
                                            Qt.LeftButton, Qt.LeftButton))
    QApplication.sendEvent(bar, mouse_event(QEvent.MouseMove, 350, 70,
                                            Qt.NoButton, Qt.LeftButton))
    QApplication.sendEvent(bar, mouse_event(QEvent.MouseButtonRelease, 350, 70,
                                            Qt.LeftButton, Qt.LeftButton))
    geo1 = win.frameGeometry().topLeft()
    dx, dy = geo1.x() - geo0.x(), geo1.y() - geo0.y()
    assert (dx, dy) == (50, 60), f"拖动位移错误: {dx},{dy}"

    # 3. 双击顶栏最大化 → 覆盖可用区域（避开任务栏）；再双击还原
    # 注：offscreen 虚拟屏幕可能小于窗口最小尺寸，此时被 setMinimumSize 钳制
    QApplication.sendEvent(bar, mouse_event(QEvent.MouseButtonDblClick, 300, 10,
                                            Qt.LeftButton, Qt.LeftButton))
    app.processEvents()
    avail = app.primaryScreen().availableGeometry()
    exp_w, exp_h = max(avail.width(), 1000), max(avail.height(), 640)
    assert win._maximized, "最大化标志未置位"
    assert (win.width(), win.height()) == (exp_w, exp_h), \
        f"最大化尺寸 {(win.width(), win.height())} != {(exp_w, exp_h)}"
    QApplication.sendEvent(bar, mouse_event(QEvent.MouseButtonDblClick, 300, 10,
                                            Qt.LeftButton, Qt.LeftButton))
    app.processEvents()
    assert not win._maximized, "还原失败"

    # 4. 边缘热区判定
    assert win._edge_at(QPoint(2, 100)) == 1
    assert win._edge_at(QPoint(100, 2)) == 4
    assert win._edge_at(QPoint(win.width() - 1, 100)) == 2
    assert win._edge_at(QPoint(win.width() - 1, win.height() - 1)) == 10
    assert win._edge_at(QPoint(win.width() // 2, win.height() // 2)) == 0

    # 5. 最大化状态下拖动顶栏 → 自动还原并跟随鼠标比例
    QApplication.sendEvent(bar, mouse_event(QEvent.MouseButtonDblClick, 300, 10,
                                            Qt.LeftButton, Qt.LeftButton))
    assert win._maximized
    QApplication.sendEvent(bar, mouse_event(QEvent.MouseButtonPress, 300, 10,
                                            Qt.LeftButton, Qt.LeftButton))
    assert not win._maximized, "最大化状态拖动应先还原"
    QApplication.sendEvent(bar, mouse_event(QEvent.MouseButtonRelease, 300, 10,
                                            Qt.LeftButton, Qt.LeftButton))

    # 6. 等待链加载线程结束再退出，避免 QThread 销毁告警
    import time
    for _ in range(100):
        if not any(w.isRunning() for w in win._workers):
            break
        app.processEvents()
        time.sleep(0.1)

    win.close()
    app.processEvents()
    print("frameless 测试全部通过")


if __name__ == "__main__":
    main()
