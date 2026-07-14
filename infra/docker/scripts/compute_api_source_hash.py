#!/usr/bin/env python3
"""计算 apps/api 源码树哈希，供镜像新鲜度校验。"""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
SCAN_DIRS = ("config", "mentora")
# 依赖与镜像构建变更也应触发重建
BUILD_FILES = ("pyproject.toml", "Dockerfile")


def compute_hash() -> str:
    digest = hashlib.sha256()
    for scan_dir in SCAN_DIRS:
        root = API_ROOT / scan_dir
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(API_ROOT).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    for name in BUILD_FILES:
        path = API_ROOT / name
        if not path.is_file():
            continue
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> None:
    print(compute_hash())


if __name__ == "__main__":
    main()
