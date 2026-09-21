"""PHPGGC 后端：封装 php.exe 子进程调用。

- 链目录解析（phpggc -l）
- 链详情 / 参数名解析（phpggc -i <chain>）
- payload 生成（phpggc <chain> <args...> [options]）

PHP 以 `-n`（忽略 php.ini）+ `-d phar.readonly=0` 运行，
phpggc 所需的 phar/zlib/json/hash 在 Windows 构建中均为内置模块，
因此不依赖任何外部 php.ini，天然便携。
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


class BackendError(Exception):
    """可直接展示给用户的后端错误。"""


@dataclass
class ChainInfo:
    name: str          # 完整链名，如 ThinkPHP/RCE1
    framework: str     # ThinkPHP
    name_only: str     # RCE1
    version: str
    type_desc: str     # RCE: Function Call
    type_short: str    # RCE
    vector: str        # __destruct
    starred: bool

    @property
    def summary(self) -> str:
        return f"{self.name} [{self.type_short}] {self.vector}"


def parse_chain_list(text: str) -> list[ChainInfo]:
    """解析 `phpggc -l` 的等宽表格输出。

    每列按最大宽度补空格后跟 4 个空格分隔，因此以连续 4+ 空格切分即可，
    列内仅含单个空格（版本区间如 "5.0.0 <= 5.0.23"）。
    """
    chains: list[ChainInfo] = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        parts = re.split(r"\s{4,}", line.strip())
        if len(parts) < 4:
            continue
        name = parts[0]
        if name.upper() == "NAME" or "/" not in name:
            continue
        framework, _, name_only = name.partition("/")
        chains.append(
            ChainInfo(
                name=name,
                framework=framework,
                name_only=name_only,
                version=parts[1] if len(parts) > 1 else "?",
                type_desc=parts[2] if len(parts) > 2 else "",
                type_short=(parts[2].split(":", 1)[0].strip()
                            if len(parts) > 2 and parts[2] else "?"),
                vector=parts[3] if len(parts) > 3 else "",
                starred=(len(parts) > 4 and parts[4].strip() == "*"),
            )
        )
    return chains


class PHPGGCBackend:
    LIST_TIMEOUT = 60
    INFO_TIMEOUT = 60
    GEN_TIMEOUT = 180

    def __init__(self, php_exe: str, phpggc_dir: str):
        self.php_exe = str(php_exe)
        self.script = str(Path(phpggc_dir) / "phpggc")

    # ---- 基础执行 ----

    def _base_cmd(self) -> list[str]:
        if not Path(self.php_exe).is_file():
            raise BackendError(
                f"未找到 PHP：{self.php_exe}\n请打开「设置」选择 php.exe。"
            )
        if not Path(self.script).is_file():
            raise BackendError(
                f"未找到 phpggc 脚本：{self.script}\n请打开「设置」选择 phpggc 目录。"
            )
        return [self.php_exe, "-n", "-d", "phar.readonly=0", self.script]

    def _run(self, args: list[str], timeout: int):
        cmd = self._base_cmd() + args
        kwargs = {}
        if os.name == "nt":
            # 从无控制台的 GUI 进程启动子进程时避免黑窗闪烁
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=timeout, **kwargs
            )
        except FileNotFoundError as e:
            raise BackendError(f"PHP 启动失败：{e}") from e
        except subprocess.TimeoutExpired as e:
            raise BackendError("执行超时。") from e
        return proc.returncode, proc.stdout, proc.stderr

    # ---- 各功能 ----

    def check_php(self) -> str:
        """返回 `php -v` 的第一行，用于设置对话框测试。"""
        if not Path(self.php_exe).is_file():
            raise BackendError(f"未找到 PHP：{self.php_exe}")
        cmd = [self.php_exe, "-n", "-v"]
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=30, **kwargs)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise BackendError(f"PHP 启动失败：{e}") from e
        first = proc.stdout.decode("utf-8", "replace").splitlines()
        if proc.returncode != 0 or not first:
            raise BackendError(
                "PHP 无法运行：" + proc.stderr.decode("utf-8", "replace")[:300]
            )
        return first[0].strip()

    def list_chains(self) -> list[ChainInfo]:
        rc, out, err = self._run(["-l"], self.LIST_TIMEOUT)
        text = out.decode("utf-8", "replace")
        chains = parse_chain_list(text)
        if not chains:
            detail = err.decode("utf-8", "replace") or text
            raise BackendError(f"获取链列表失败：\n{detail[:500]}")
        return chains

    def chain_info(self, name: str) -> dict:
        """返回 {'params': [参数名...], 'text': -i 原始输出}。"""
        rc, out, err = self._run(["-i", name], self.INFO_TIMEOUT)
        text = out.decode("utf-8", "replace")
        params: list[str] = []
        for line in reversed(text.splitlines()):
            if line.strip().startswith("./phpggc"):
                params = re.findall(r"<([^>]+)>", line)
                break
        if rc != 0 and not params:
            raise BackendError(
                f"获取链信息失败（{name}）：\n{text or err.decode('utf-8', 'replace')}"
            )
        return {"params": params, "text": text}

    def generate(self, name: str, params: list[str], flags: list[str]) -> dict:
        t0 = time.perf_counter()
        rc, out, err = self._run([name, *params, *flags], self.GEN_TIMEOUT)
        return {
            "stdout": out,
            "stderr": err,
            "rc": rc,
            "elapsed": time.perf_counter() - t0,
        }

    def run_args(self, args: list[str]) -> dict:
        """自定义命令行模式：直接透传 phpggc 参数。"""
        t0 = time.perf_counter()
        rc, out, err = self._run(list(args), self.GEN_TIMEOUT)
        return {
            "stdout": out,
            "stderr": err,
            "rc": rc,
            "elapsed": time.perf_counter() - t0,
        }
