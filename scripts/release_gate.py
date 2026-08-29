#!/usr/bin/env python3
# Copyright 2026 ScholarSeed contributors
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE.
# Commercial use requires a separate license from the maintainers.
"""ScholarSeed 发布前门禁聚合器。

按顺序执行并汇总：
1. 单元测试（unittest discover -s tests）
2. 清理测试产生的 __pycache__ 字节码残留
3. validate_plugin.validate() —— 插件规范 + 声明一致性 + 版本一致性 + 死代码 + 词数口径

单元测试在前、清理居中：避免 unittest / import 产生的 __pycache__ 被
validate_plugin 误判为构建产物。任一环节失败即整体失败（exit 1）。

提交 PR / 发布前必须先跑本脚本。

用法（仓库根目录）：
    python scripts/release_gate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

import validate_plugin

ROOT = Path(__file__).resolve().parent.parent


def _clean_pycache(root: Path) -> None:
    """递归删除 root 下所有 __pycache__ 目录（测试运行副产物）。"""
    for path in list(root.rglob("__pycache__")):
        shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    failures: list = []

    print("=" * 60)
    print("STEP 1/3: 单元测试")
    print("=" * 60)
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
    )
    if proc.returncode != 0:
        failures.append("unit tests")

    print()
    print("=" * 60)
    print("STEP 2/3: 清理 __pycache__ 残留")
    print("=" * 60)
    _clean_pycache(ROOT)
    print("已清理测试产生的字节码目录")

    print()
    print("=" * 60)
    print("STEP 3/3: validate_plugin（规范/一致性/版本/死代码/词数口径）")
    print("=" * 60)
    if not validate_plugin.validate(ROOT):
        failures.append("validate_plugin")

    print()
    print("=" * 60)
    if failures:
        print(f"RELEASE GATE FAILED: {', '.join(failures)}")
        return 1
    print("RELEASE GATE PASSED: validate_plugin + unit tests 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
