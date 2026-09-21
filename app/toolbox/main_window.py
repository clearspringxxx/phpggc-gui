"""主窗口：链浏览 / 筛选 / 参数表单 / payload 生成 / 历史 / 自定义命令。"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

from PySide6.QtCore import QPoint, QEvent, Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
    QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .backend import BackendError, ChainInfo, PHPGGCBackend
from .config import DATA_DIR, PROJECT_ROOT, load_config, save_config
from .history import HistoryStore
from .theme import ACCENT, DANGER, MUTED
from .workers import Worker

FW_ALL, TYPE_ALL, VEC_ALL = "全部框架", "全部类型", "全部向量"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 无边框窗口：去掉系统标题栏，窗口控制键集成在顶部栏
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowTitle("PHPGGC GUI")
        self.resize(1240, 780)
        self.setMinimumSize(1000, 640)

        # 无边框窗口状态
        self._maximized = False
        self._normal_geo = None
        self._drag_offset = None
        self._resize = None

        self.config = load_config()
        self.backend = PHPGGCBackend(
            self.config["php_exe"], self.config["phpggc_dir"]
        )
        self.history = HistoryStore(DATA_DIR / "history.json")

        self._chains: list[ChainInfo] = []
        self._workers: list[Worker] = []
        self._current: ChainInfo | None = None
        self._info_cache: dict[str, dict] = {}
        self._info_token = 0
        self._generating = False
        self._last_raw: bytes = b""

        self._build_ui()
        self._start_chain_load()

    # ================= UI 构建 =================

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 6)
        root.setSpacing(8)

        topbar = QWidget()
        topbar.setObjectName("topbar")
        topbar.setLayout(self._build_topbar())
        topbar.installEventFilter(self)   # 顶栏拖动 / 双击最大化
        self.topbar = topbar
        root.addWidget(topbar)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self._build_left_panel())
        split.addWidget(self._build_right_panel())
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 6)
        split.setSizes([470, 730])

        # 垂直分割：上方链操作区 / 下方输出区，可拖拽调整
        vsplit = QSplitter(Qt.Vertical)
        vsplit.addWidget(split)
        vsplit.addWidget(self._build_output_panel())
        vsplit.setStretchFactor(0, 7)
        vsplit.setStretchFactor(1, 3)
        vsplit.setSizes([580, 270])
        vsplit.setHandleWidth(8)
        root.addWidget(vsplit, 1)

        self._build_statusbar()

    def _build_topbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)
        title = QLabel("PHPGGC GUI")
        title.setObjectName("title")
        bar.addWidget(title)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("搜索链名 / 框架 / 版本…")
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.setFixedHeight(30)
        self.edit_search.textChanged.connect(self.apply_filters)
        bar.addWidget(self.edit_search, 2)

        self.combo_framework = QComboBox()
        self.combo_type = QComboBox()
        self.combo_vector = QComboBox()
        for combo, tip in (
            (self.combo_framework, "按框架筛选"),
            (self.combo_type, "按漏洞类型筛选"),
            (self.combo_vector, "按触发向量筛选"),
        ):
            combo.setFixedHeight(30)
            combo.setMinimumWidth(110)
            combo.currentIndexChanged.connect(self.apply_filters)
            combo.setToolTip(tip)
            bar.addWidget(combo)

        btn_refresh = QPushButton("刷新")
        btn_refresh.setFixedHeight(30)
        btn_refresh.clicked.connect(self._start_chain_load)
        bar.addWidget(btn_refresh)

        btn_settings = QPushButton("设置")
        btn_settings.setFixedHeight(30)
        btn_settings.clicked.connect(self.open_settings)
        bar.addWidget(btn_settings)

        # 无边框窗口控制键
        bar.addSpacing(4)
        bar.addWidget(self._win_btn("–", self.showMinimized, "最小化"))
        bar.addWidget(self._win_btn("□", self.toggle_max, "最大化 / 还原"))
        bar.addWidget(self._win_btn("✕", self.close, "关闭", danger=True))
        return bar

    @staticmethod
    def _win_btn(text: str, slot, tip: str, danger: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(36, 26)
        btn.setObjectName("winbtn-danger" if danger else "winbtn")
        btn.setToolTip(tip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    # ---- 无边框窗口：拖动 / 缩放 / 最大化 ----

    def toggle_max(self):
        if self._maximized:
            self.setGeometry(self._normal_geo)
            self._maximized = False
        else:
            self._normal_geo = self.geometry()
            self.setGeometry(QApplication.primaryScreen().availableGeometry())
            self._maximized = True

    def eventFilter(self, obj, event):
        if obj.objectName() == "topbar":
            t = event.type()
            if t == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if self._maximized:
                    # 最大化状态下拖动：还原窗口并让鼠标保持在标题上
                    ratio = max(0.0, min(1.0, event.position().x() / self.width()))
                    self.toggle_max()
                    self._drag_offset = QPoint(int(self.width() * ratio), 16)
                else:
                    self._drag_offset = (
                        event.globalPosition().toPoint()
                        - self.frameGeometry().topLeft()
                    )
                return True
            if t == QEvent.MouseMove and self._drag_offset is not None:
                if event.buttons() & Qt.LeftButton:
                    self.move(event.globalPosition().toPoint() - self._drag_offset)
                    return True
            if t == QEvent.MouseButtonRelease:
                self._drag_offset = None
            if t == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self.toggle_max()
                return True
        return super().eventFilter(obj, event)

    _M = 6  # 边缘热区宽度

    def _edge_at(self, pos):
        if self._maximized:
            return 0
        m, r = self._M, self.rect()
        e = 0
        if pos.x() <= m:
            e |= 1
        if pos.x() >= r.width() - m:
            e |= 2
        if pos.y() <= m:
            e |= 4
        if pos.y() >= r.height() - m:
            e |= 8
        return e

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            edge = self._edge_at(e.position().toPoint())
            if edge:
                self._resize = (edge, self.geometry(), e.globalPosition().toPoint())
                return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._resize:
            edge, geo, g0 = self._resize
            d = e.globalPosition().toPoint() - g0
            x, y, w, h = geo.x(), geo.y(), geo.width(), geo.height()
            if edge & 1:
                x, w = geo.x() + d.x(), geo.width() - d.x()
            elif edge & 2:
                w = geo.width() + d.x()
            if edge & 4:
                y, h = geo.y() + d.y(), geo.height() - d.y()
            elif edge & 8:
                h = geo.height() + d.y()
            if w >= self.minimumWidth() and h >= self.minimumHeight():
                self.setGeometry(x, y, w, h)
            return
        if not e.buttons():
            edge = self._edge_at(pos)
            if edge in (1, 2):
                self.setCursor(Qt.SizeHorCursor)
            elif edge in (4, 8):
                self.setCursor(Qt.SizeVerCursor)
            elif edge in (5, 10):
                self.setCursor(Qt.SizeFDiagCursor)
            elif edge in (6, 9):
                self.setCursor(Qt.SizeBDiagCursor)
            else:
                self.unsetCursor()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._resize = None
        super().mouseReleaseEvent(e)

    def _build_left_panel(self) -> QTreeWidget:
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["链", "影响版本", "类型", "向量"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.header().resizeSection(0, 138)
        self.tree.header().resizeSection(1, 112)
        self.tree.header().resizeSection(2, 52)
        self.tree.itemSelectionChanged.connect(self.on_tree_selection)
        return self.tree

    def _build_right_panel(self) -> QTabWidget:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._wrap_scroll(self._build_generate_tab()),
                         "生成 Payload")
        self.tabs.addTab(self._build_history_tab(), "历史记录")
        self.tabs.addTab(self._build_custom_tab(), "自定义命令")
        return self.tabs

    @staticmethod
    def _wrap_scroll(widget: QWidget) -> QScrollArea:
        """内容超出高度时可滚动，避免控件被挤压重叠。"""
        area = QScrollArea()
        area.setWidget(widget)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        return area

    # ---- 生成 tab ----

    def _build_generate_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(8)

        info_box = QGroupBox("链信息")
        grid = QGridLayout(info_box)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(2)
        self.lbl_name = self._info_label(bold=True)
        self.lbl_version = self._info_label()
        self.lbl_type = self._info_label()
        self.lbl_vector = self._info_label()
        grid.addWidget(QLabel("名称："), 0, 0)
        grid.addWidget(self.lbl_name, 0, 1)
        grid.addWidget(QLabel("版本："), 0, 2)
        grid.addWidget(self.lbl_version, 0, 3)
        grid.addWidget(QLabel("类型："), 1, 0)
        grid.addWidget(self.lbl_type, 1, 1)
        grid.addWidget(QLabel("向量："), 1, 2)
        grid.addWidget(self.lbl_vector, 1, 3)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(3, 2)
        self.lbl_desc = QLabel("（选中左侧链后自动加载描述）")
        self.lbl_desc.setObjectName("muted")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(QLabel("说明："), 2, 0, Qt.AlignTop)
        grid.addWidget(self.lbl_desc, 2, 1, 1, 3)
        lay.addWidget(info_box)

        self.param_box = QGroupBox("链参数")
        self.param_form = QFormLayout(self.param_box)
        self.param_form.setLabelAlignment(Qt.AlignRight)
        lay.addWidget(self.param_box)

        lay.addWidget(self._build_options_group())

        row = QHBoxLayout()
        self.btn_generate = QPushButton("生成 Payload")
        self.btn_generate.setObjectName("primary")
        self.btn_generate.clicked.connect(self.on_generate)
        row.addStretch(1)
        row.addWidget(self.btn_generate)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return page

    def _info_label(self, bold=False) -> QLabel:
        lbl = QLabel("—")
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if bold:
            f = lbl.font()
            f.setBold(True)
            lbl.setFont(f)
        return lbl

    def _build_options_group(self) -> QGroupBox:
        box = QGroupBox("生成选项")
        cols = QHBoxLayout(box)
        cols.setSpacing(14)

        # 左列：增强变换
        left = QVBoxLayout()
        left.addWidget(self._col_label("增强变换"))
        self.chk_fast_destruct = QCheckBox("fast-destruct（快速析构）")
        self.chk_pub_props = QCheckBox("public-properties（去保护属性空字节）")
        self.chk_ascii = QCheckBox("ascii-strings（S 格式转义非 ASCII）")
        self.chk_armor = QCheckBox("armor-strings（S 格式转义全部字符）")
        self.chk_session = QCheckBox("session-encode（session 序列化）")
        left.addWidget(self.chk_fast_destruct)
        left.addWidget(self.chk_pub_props)
        left.addWidget(self.chk_ascii)
        left.addWidget(self.chk_armor)
        left.addWidget(self.chk_session)
        # ascii 与 armor 互斥
        self.chk_ascii.toggled.connect(
            lambda on: on and self.chk_armor.setChecked(False))
        self.chk_armor.toggled.connect(
            lambda on: on and self.chk_ascii.setChecked(False))
        left.addStretch(1)
        cols.addLayout(left, 4)

        # 中列：编码 + plus-numbers
        mid = QVBoxLayout()
        mid.addWidget(self._col_label("编码（按勾选顺序应用）"))
        self.chk_soft = QCheckBox("soft URL")
        self.chk_url = QCheckBox("URL")
        self.chk_base64 = QCheckBox("base64")
        self.chk_json = QCheckBox("JSON")
        for c in (self.chk_soft, self.chk_url, self.chk_base64, self.chk_json):
            mid.addWidget(c)
        pn_row = QHBoxLayout()
        pn_row.addWidget(QLabel("plus-numbers:"))
        self.edit_plus_numbers = QLineEdit()
        self.edit_plus_numbers.setPlaceholderText("如 iO，可留空")
        pn_row.addWidget(self.edit_plus_numbers, 1)
        mid.addLayout(pn_row)
        mid.addStretch(1)
        cols.addLayout(mid, 3)

        # 右列：PHAR 构造
        right = QVBoxLayout()
        right.addWidget(self._col_label("PHAR 构造（二进制输出，保存于生成后）"))
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("格式:"))
        self.combo_phar = QComboBox()
        self.combo_phar.addItems(["无", "phar", "tar", "zip"])
        fmt_row.addWidget(self.combo_phar, 1)
        right.addLayout(fmt_row)

        self.edit_phar_jpeg = QLineEdit()
        self.edit_phar_jpeg.setPlaceholderText("JPEG 多态文件（可选）")
        self.edit_phar_jpeg.setReadOnly(True)
        btn_jpeg = QPushButton("选择…")
        btn_jpeg.clicked.connect(lambda: self._pick_file(self.edit_phar_jpeg, "图片 (*.jpg *.jpeg)"))
        right.addLayout(self._file_row(self.edit_phar_jpeg, btn_jpeg))

        self.edit_phar_prefix = QLineEdit()
        self.edit_phar_prefix.setPlaceholderText("PHAR 前缀文件（可选）")
        self.edit_phar_prefix.setReadOnly(True)
        btn_prefix = QPushButton("选择…")
        btn_prefix.clicked.connect(lambda: self._pick_file(self.edit_phar_prefix, "任意文件 (*)"))
        right.addLayout(self._file_row(self.edit_phar_prefix, btn_prefix))

        fname_row = QHBoxLayout()
        fname_row.addWidget(QLabel("内部文件名:"))
        self.edit_phar_filename = QLineEdit("test.txt")
        fname_row.addWidget(self.edit_phar_filename, 1)
        right.addLayout(fname_row)
        right.addStretch(1)
        cols.addLayout(right, 5)
        return box

    @staticmethod
    def _col_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("muted")
        return lbl

    _TYPE_ABBR = {
        "File write": "FW",
        "File read": "FR",
        "File delete": "FD",
        "File include": "FI",
        "PHP code": "PHP",
        "Function call": "FC",
    }

    @classmethod
    def _type_abbr(cls, type_desc: str) -> str:
        """树里的类型列用短码显示，完整描述放在悬停提示里。"""
        first = type_desc.split(":", 1)[0].strip()
        return cls._TYPE_ABBR.get(first, first)

    @staticmethod
    def _file_row(edit: QLineEdit, btn: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        row.addWidget(btn)
        return row

    def _pick_file(self, edit: QLineEdit, filter_: str):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", filter_)
        if path:
            edit.setText(path)

    # ---- 历史 tab ----

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        self.hist_list = QListWidget()
        self.hist_list.currentRowChanged.connect(self.on_history_select)
        lay.addWidget(self.hist_list, 3)
        self.hist_detail = QPlainTextEdit()
        self.hist_detail.setReadOnly(True)
        lay.addWidget(self.hist_detail, 2)

        row = QHBoxLayout()
        btn_copy = QPushButton("复制")
        btn_copy.clicked.connect(lambda: self._copy_text(self.hist_detail.toPlainText()))
        btn_save = QPushButton("保存到文件")
        btn_save.clicked.connect(lambda: self._save_text(self.hist_detail.toPlainText()))
        btn_del = QPushButton("删除选中")
        btn_del.clicked.connect(self.on_history_delete)
        btn_clear = QPushButton("清空历史")
        btn_clear.clicked.connect(self.on_history_clear)
        for b in (btn_copy, btn_save, btn_del, btn_clear):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.refresh_history()
        return page

    # ---- 自定义命令 tab ----

    def _build_custom_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        hint = QLabel(
            "直接输入 phpggc 命令行参数（支持引号包裹的参数），例如：\n"
            "    Laravel/RCE1 system id -b\n"
            "    SwiftMailer/FW1 /var/www/shell.php ./shell.txt -u\n"
            "高级用法：-w 包装器.php ｜ -pj 图片.jpg ｜ -se 等，等效于命令行 ./phpggc <参数>"
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        row = QHBoxLayout()
        self.edit_custom = QLineEdit()
        self.edit_custom.setPlaceholderText("phpggc 参数…")
        row.addWidget(self.edit_custom, 1)
        btn = QPushButton("执行")
        btn.setObjectName("primary")
        btn.clicked.connect(self.on_custom_run)
        row.addWidget(btn)
        lay.addLayout(row)
        lay.addStretch(1)
        return page

    # ---- 输出面板 + 状态栏 ----

    def _build_output_panel(self) -> QGroupBox:
        box = QGroupBox("输出")
        box.setMinimumHeight(160)
        lay = QVBoxLayout(box)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(20000)
        self.output.setPlaceholderText("[*] 等待生成 — payload 输出将显示在此处（可选中复制）")
        f = QFont("Consolas", 10)
        self.output.setFont(f)
        lay.addWidget(self.output)

        row = QHBoxLayout()
        btn_copy = QPushButton("复制")
        btn_copy.clicked.connect(lambda: self._copy_text(self.output.toPlainText()))
        btn_save = QPushButton("保存到文件")
        btn_save.clicked.connect(self.on_save_output)
        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self.output.clear)
        row.addWidget(btn_copy)
        row.addWidget(btn_save)
        row.addWidget(btn_clear)
        row.addStretch(1)
        self.lbl_gen_info = QLabel("")
        self.lbl_gen_info.setObjectName("muted")
        row.addWidget(self.lbl_gen_info)
        lay.addLayout(row)
        return box

    def _build_statusbar(self):
        self.status_left = QLabel()
        self.status_right = QLabel()
        self.statusBar().addWidget(self.status_left, 1)
        self.statusBar().addPermanentWidget(self.status_right)
        self._update_status_paths()
        self.status_right.setText("正在加载链列表…")

    def _update_status_paths(self):
        try:
            php = str(Path(self.config["php_exe"]).relative_to(PROJECT_ROOT))
        except ValueError:
            php = self.config["php_exe"]
        try:
            gc = str(Path(self.config["phpggc_dir"]).relative_to(PROJECT_ROOT))
        except ValueError:
            gc = self.config["phpggc_dir"]
        self.status_left.setText(f"PHP: {php}    |    PHPGGC: {gc}")

    # ================= 数据加载 =================

    def _start_worker(self, worker: Worker) -> Worker:
        self._workers.append(worker)
        worker.finished.connect(lambda w=worker: self._workers.remove(w)
                                if w in self._workers else None)
        worker.start()
        return worker

    def _start_chain_load(self):
        self.status_right.setText("正在加载链列表…")
        worker = self._start_worker(Worker(self.backend.list_chains))
        worker.done.connect(self.on_chains_loaded)
        worker.fail.connect(self.on_worker_fail)

    def on_chains_loaded(self, chains: list[ChainInfo]):
        self._chains = chains
        self._populate_tree()
        self._rebuild_combos()
        self.apply_filters()
        self.status_right.setText(f"就绪    |    框架数: {self.tree.topLevelItemCount()}    |    链数: {len(chains)}")

    def on_worker_fail(self, msg: str):
        self.status_right.setText("加载失败")
        QMessageBox.warning(self, "错误", msg)
        if not self._chains:
            self.open_settings(first_run=True)

    def _populate_tree(self):
        self.tree.clear()
        groups: dict[str, list[ChainInfo]] = {}
        for ci in self._chains:
            groups.setdefault(ci.framework, []).append(ci)
        fw_color = QBrush(QColor(ACCENT))
        bold = self.tree.font()
        bold.setBold(True)
        for fw in sorted(groups):
            parent = QTreeWidgetItem([f"{fw} ({len(groups[fw])})", "", "", ""])
            parent.setForeground(0, fw_color)
            parent.setFont(0, bold)
            parent.setData(0, Qt.UserRole, fw)
            for ci in groups[fw]:
                name = ci.name_only + ("  *" if ci.starred else "")
                item = QTreeWidgetItem([name, ci.version, self._type_abbr(ci.type_desc), ci.vector])
                item.setData(0, Qt.UserRole, ci)
                item.setToolTip(0, ci.name)
                item.setToolTip(1, ci.version)
                item.setToolTip(2, ci.type_desc)
                parent.addChild(item)
            self.tree.addTopLevelItem(parent)

    def _rebuild_combos(self):
        specs = (
            (self.combo_framework, FW_ALL, sorted({c.framework for c in self._chains})),
            (self.combo_type, TYPE_ALL, sorted({c.type_short for c in self._chains})),
            (self.combo_vector, VEC_ALL, sorted({c.vector for c in self._chains if c.vector})),
        )
        for combo, all_text, values in specs:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(all_text)
            combo.addItems(values)
            combo.blockSignals(False)

    # ================= 筛选 =================

    def apply_filters(self):
        q = self.edit_search.text().strip().lower()
        fw = self.combo_framework.currentText()
        ty = self.combo_type.currentText()
        vc = self.combo_vector.currentText()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            fw_item = root.child(i)
            fw_name = fw_item.data(0, Qt.UserRole)
            visible = 0
            for j in range(fw_item.childCount()):
                item = fw_item.child(j)
                ci: ChainInfo = item.data(0, Qt.UserRole)
                ok = True
                if fw != FW_ALL and ci.framework != fw:
                    ok = False
                if ok and ty != TYPE_ALL and ci.type_short != ty:
                    ok = False
                if ok and vc != VEC_ALL and ci.vector != vc:
                    ok = False
                if ok and q:
                    hay = (f"{ci.name} {ci.version} {ci.type_desc} "
                           f"{ci.vector} {ci.framework}").lower()
                    if q not in hay:
                        ok = False
                item.setHidden(not ok)
                visible += ok
            fw_item.setHidden(visible == 0)
        if q or fw != FW_ALL or ty != TYPE_ALL or vc != VEC_ALL:
            self.tree.expandAll()
        else:
            self.tree.collapseAll()

    # ================= 链选择与详情 =================

    def on_tree_selection(self):
        items = self.tree.selectedItems()
        if not items:
            return
        item = items[0]
        ci: ChainInfo | None = item.data(0, Qt.UserRole)
        if not isinstance(ci, ChainInfo):
            return  # 框架分组节点
        self._current = ci
        self.lbl_name.setText(ci.name)
        self.lbl_version.setText(ci.version)
        self.lbl_type.setText(ci.type_desc)
        self.lbl_vector.setText(ci.vector)
        self.lbl_desc.setText("加载中…")
        self._info_token += 1
        token = self._info_token

        cached = self._info_cache.get(ci.name)
        if cached is not None:
            self._apply_chain_info(ci, cached, token)
            return
        worker = self._start_worker(Worker(self.backend.chain_info, ci.name))
        worker.done.connect(
            lambda data, n=ci.name, t=token: self.on_info_done(n, data, t)
        )
        worker.fail.connect(lambda msg, n=ci.name, t=token: self.on_info_fail(n, msg, t))

    def on_info_done(self, name: str, data: dict, token: int):
        if token != self._info_token:
            return
        self._info_cache[name] = data
        if self._current and self._current.name == name:
            self._apply_chain_info(self._current, data, token)

    def on_info_fail(self, name: str, msg: str, token: int):
        if token != self._info_token:
            return
        self.lbl_desc.setText("（描述加载失败）")
        self.statusBar().showMessage(f"链信息加载失败 {name}: {msg[:120]}", 5000)

    def _apply_chain_info(self, ci: ChainInfo, data: dict, token: int):
        if token != self._info_token:
            return
        params: list[str] = data["params"]
        info_text = data["text"].strip()
        # -i 输出的 Name/Version/Type/Vector 已在上方字段展示，说明里去掉这四行
        desc_lines = [
            ln for ln in info_text.splitlines()
            if ln.strip()
            and not ln.strip().startswith("./phpggc")
            and not re.match(r"^(Name|Version|Type|Vector)\s*:", ln.strip())
        ]
        self.lbl_desc.setText("\n".join(desc_lines).strip() or "（无说明）")
        self._rebuild_param_form(params)

    def _rebuild_param_form(self, params: list[str]):
        self.param_edits: list[QLineEdit] = []
        form = self.param_form
        while form.rowCount():
            form.removeRow(0)
        self.param_box.setTitle(f"链参数（共 {len(params)} 个）")
        if not params:
            lbl = QLabel("该链无需参数")
            lbl.setObjectName("muted")
            form.addRow(lbl)
            return
        for i, p in enumerate(params, 1):
            edit = QLineEdit()
            edit.setPlaceholderText(f"第 {i} 个参数{'' if i < len(params) else '（最后一个）'}")
            form.addRow(f"{p}：", edit)
            self.param_edits.append(edit)

    # ================= payload 生成 =================

    def build_option_flags(self) -> tuple[list[str], str, bool]:
        """返回 (命令行 flags, 选项描述, 是否 PHAR 二进制输出)。"""
        flags: list[str] = []
        if self.chk_fast_destruct.isChecked():
            flags.append("--fast-destruct")
        if self.chk_pub_props.isChecked():
            flags.append("--public-properties")
        if self.chk_ascii.isChecked():
            flags.append("--ascii-strings")
        if self.chk_armor.isChecked():
            flags.append("--armor-strings")
        pn = self.edit_plus_numbers.text().strip()
        if pn:
            flags += ["--plus-numbers", pn]
        if self.chk_session.isChecked():
            flags.append("--session-encode")
        # 编码顺序：soft -> url -> base64 -> json
        if self.chk_soft.isChecked():
            flags.append("--soft")
        if self.chk_url.isChecked():
            flags.append("--url")
        if self.chk_base64.isChecked():
            flags.append("--base64")
        if self.chk_json.isChecked():
            flags.append("--json")
        # PHAR
        phar_binary = False
        fmt = self.combo_phar.currentText()
        jpeg = self.edit_phar_jpeg.text().strip()
        if jpeg:
            flags += ["--phar-jpeg", jpeg]
            phar_binary = True
        elif fmt != "无":
            flags += ["--phar", fmt]
            phar_binary = True
        prefix = self.edit_phar_prefix.text().strip()
        if prefix:
            flags += ["--phar-prefix", prefix]
        fname = self.edit_phar_filename.text().strip()
        if fname and fname != "test.txt":
            flags += ["--phar-filename", fname]
        desc = " ".join(f.replace("--", "") for f in flags)
        return flags, desc, phar_binary

    def on_generate(self):
        if self._generating:
            return
        ci = self._current
        if ci is None:
            QMessageBox.information(self, "提示", "请先在左侧选择一条链。")
            return
        params = [e.text() for e in getattr(self, "param_edits", [])]
        if any(p.startswith("-") for p in params):
            QMessageBox.warning(
                self, "参数错误",
                "参数不能以“-”开头（会被 phpggc 误认为选项）。\n"
                "如需此类参数请改用「自定义命令」页并自行处理。"
            )
            return
        flags, desc, phar_binary = self.build_option_flags()
        if self.chk_ascii.isChecked() and self.chk_armor.isChecked():
            QMessageBox.warning(self, "选项冲突", "ascii-strings 与 armor-strings 互斥，请只勾选其一。")
            return

        self._generating = True
        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("生成中…")
        self.status_right.setText(f"正在生成 {ci.name} …")
        worker = self._start_worker(Worker(self.backend.generate, ci.name, params, flags))
        worker.done.connect(lambda res: self.on_generate_done(ci, params, desc, phar_binary, res))
        worker.fail.connect(self.on_generate_fail)

    def on_generate_done(self, ci: ChainInfo, params: list[str],
                         options_desc: str, phar_binary: bool, res: dict):
        self._generating = False
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("生成 Payload")
        raw: bytes = res["stdout"]
        self._last_raw = raw
        text = raw.decode("utf-8", "backslashreplace")
        if res["rc"] != 0:
            self.output.setPlainText(f"[生成失败] {text.strip() or res['stderr'].decode('utf-8', 'replace')}")
            self.lbl_gen_info.setText("")
            self.status_right.setText("生成失败")
            return
        self.output.setPlainText(text if text.strip() else "（空输出）")
        self.lbl_gen_info.setText(f"{ci.name}    耗时 {res['elapsed'] * 1000:.0f} ms    {len(raw)} 字节")
        self.status_right.setText(f"生成成功    |    {ci.name}")
        entry = self.history.add(ci.name, params, options_desc, text, kind="text")
        self.refresh_history()
        if phar_binary:
            suffix = ".jpg" if self.edit_phar_jpeg.text().strip() else ".phar"
            self._save_raw_dialog("保存 PHAR 文件", f"payload{suffix}")

    def on_generate_fail(self, msg: str):
        self._generating = False
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("生成 Payload")
        self.status_right.setText("生成失败")
        QMessageBox.warning(self, "生成失败", msg)

    # ================= 自定义命令 =================

    def on_custom_run(self):
        raw = self.edit_custom.text().strip()
        if not raw:
            return
        if self._generating:
            return
        try:
            args = shlex.split(raw)
        except ValueError as e:
            QMessageBox.warning(self, "解析失败", f"命令行解析失败：{e}")
            return
        self._generating = True
        self.status_right.setText("正在执行自定义命令…")
        worker = self._start_worker(Worker(self.backend.run_args, args))
        worker.done.connect(self.on_custom_done)
        worker.fail.connect(self.on_generate_fail)

    def on_custom_done(self, res: dict):
        self._generating = False
        raw: bytes = res["stdout"]
        self._last_raw = raw
        text = raw.decode("utf-8", "backslashreplace")
        if res["rc"] != 0:
            self.output.setPlainText(f"[执行失败] {text.strip() or res['stderr'].decode('utf-8', 'replace')}")
            self.status_right.setText("执行失败")
            return
        self.output.setPlainText(text if text.strip() else "（空输出）")
        self.lbl_gen_info.setText(f"自定义命令    耗时 {res['elapsed'] * 1000:.0f} ms")
        self.status_right.setText("执行成功")
        self.history.add("(自定义命令)", [], self.edit_custom.text().strip(), text)
        self.refresh_history()

    # ================= 历史 =================

    def refresh_history(self):
        self.hist_list.blockSignals(True)
        self.hist_list.clear()
        for entry in self.history.entries:
            params = " ".join(entry.get("params", []))
            text = f"[{entry['time']}]  {entry['chain']}"
            if params:
                text += f"  <{params}>"
            if entry.get("options"):
                text += f"  [{entry['options']}]"
            item = QListWidgetItem(text)
            self.hist_list.addItem(item)
        self.hist_list.blockSignals(False)
        self.hist_detail.clear()

    def on_history_select(self, row: int):
        if 0 <= row < len(self.history.entries):
            entry = self.history.entries[row]
            if entry.get("kind") == "text" and entry.get("payload"):
                self.hist_detail.setPlainText(entry["payload"])
            else:
                self.hist_detail.setPlainText(
                    "（该记录为二进制/无内容，请重新生成）"
                )

    def on_history_delete(self):
        row = self.hist_list.currentRow()
        if row < 0:
            return
        self.history.remove(row)
        self.refresh_history()

    def on_history_clear(self):
        if QMessageBox.question(self, "确认", "确定清空全部历史记录？") == QMessageBox.Yes:
            self.history.clear()
            self.refresh_history()

    # ================= 输出操作 =================

    def _copy_text(self, text: str):
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("已复制到剪贴板", 2000)

    def _save_text(self, text: str):
        path, _ = QFileDialog.getSaveFileName(self, "保存文件", "payload.txt")
        if path:
            Path(path).write_text(text, encoding="utf-8")
            self.statusBar().showMessage(f"已保存：{path}", 3000)

    def on_save_output(self):
        if not self._last_raw:
            QMessageBox.information(self, "提示", "当前没有可保存的输出。")
            return
        self._save_raw_dialog("保存输出", "payload.txt")

    def _save_raw_dialog(self, title: str, suggested: str):
        path, _ = QFileDialog.getSaveFileName(self, title, suggested)
        if not path:
            if self._last_raw[:2] not in (b"<?", b"O:"):
                self.statusBar().showMessage("已取消保存（数据仍可用“保存到文件”导出）", 4000)
            return
        try:
            Path(path).write_bytes(self._last_raw)
            self.statusBar().showMessage(f"已保存：{path}（{len(self._last_raw)} 字节）", 4000)
            self.output.setPlainText(
                self.output.toPlainText()
                + ("" if self.output.toPlainText().endswith("\n") or not self.output.toPlainText() else "\n")
                + f"--> 二进制已保存到：{path}（{len(self._last_raw)} 字节）"
            )
        except OSError as e:
            QMessageBox.warning(self, "保存失败", str(e))

    # ================= 设置 =================

    def open_settings(self, first_run: bool = False):
        dlg = SettingsDialog(self, self.config)
        if first_run:
            dlg.setWindowTitle("初始设置：请指定 PHP 与 phpggc 路径")
        if dlg.exec() == QDialog.Accepted:
            self.config = load_config()
            self.backend = PHPGGCBackend(
                self.config["php_exe"], self.config["phpggc_dir"]
            )
            self._info_cache.clear()
            self._update_status_paths()
            self._start_chain_load()


class SettingsDialog(QDialog):
    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(560)
        self._config = dict(config)

        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.edit_php = QLineEdit(config.get("php_exe", ""))
        btn_php = QPushButton("浏览…")
        btn_php.clicked.connect(self._browse_php)
        form.addRow("php.exe 路径：", self._row(self.edit_php, btn_php))
        self.edit_dir = QLineEdit(config.get("phpggc_dir", ""))
        btn_dir = QPushButton("浏览…")
        btn_dir.clicked.connect(self._browse_dir)
        form.addRow("phpggc 目录：", self._row(self.edit_dir, btn_dir))
        lay.addLayout(form)

        self.lbl_test = QLabel("点击「测试」验证配置；「保存」后自动重新加载链列表。")
        self.lbl_test.setObjectName("muted")
        self.lbl_test.setWordWrap(True)
        lay.addWidget(self.lbl_test)

        row = QHBoxLayout()
        btn_test = QPushButton("测试")
        btn_test.clicked.connect(self.on_test)
        btn_save = QPushButton("保存")
        btn_save.setObjectName("primary")
        btn_save.clicked.connect(self.on_save)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(btn_test)
        row.addWidget(btn_save)
        row.addWidget(btn_cancel)
        lay.addLayout(row)

    @staticmethod
    def _row(edit: QLineEdit, btn: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        row.addWidget(btn)
        return row

    def _browse_php(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 php.exe", "", "php.exe (php.exe)")
        if path:
            self.edit_php.setText(path)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择 phpggc 目录")
        if path:
            self.edit_dir.setText(path)

    def on_test(self):
        backend = PHPGGCBackend(self.edit_php.text().strip(), self.edit_dir.text().strip())
        try:
            version = backend.check_php()
            count = len(backend.list_chains())
            self.lbl_test.setStyleSheet(f"color: {ACCENT};")
            self.lbl_test.setText(f"测试通过：{version}，共 {count} 条链。")
        except BackendError as e:
            self.lbl_test.setStyleSheet(f"color: {DANGER};")
            self.lbl_test.setText(str(e))

    def on_save(self):
        self._config["php_exe"] = self.edit_php.text().strip()
        self._config["phpggc_dir"] = self.edit_dir.text().strip()
        save_config(self._config)
        self.accept()
