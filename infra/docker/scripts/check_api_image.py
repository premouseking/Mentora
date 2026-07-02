#!/usr/bin/env python3
"""
启动前校验 API Docker 镜像与运行中容器是否与工作区代码一致。

检查项：
1. 镜像是否存在
2. 镜像内源码哈希是否匹配工作区 apps/api
3. 关键 Python 模块是否存在于镜像
4. 运行中容器（若存在）路由是否与 config/urls.py 一致
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
COMPOSE_FILE = REPO_ROOT / "infra" / "docker" / "docker-compose.dev.yml"
ENV_FILE = REPO_ROOT / ".env"
IMAGE_NAME = "mentora-api"
CONTAINER_NAME = "mentora-api-1"

REQUIRED_MODULES = (
    "mentora/knowledge/reader_views.py",
    "mentora/knowledge/asset_streaming.py",
    "mentora/knowledge/layout_converter.py",
    "mentora/parsing/contract.py",
    "config/urls.py",
)

# urls.py 中 path("api/", include(...)) 挂载的子路由，按前缀匹配即可
INCLUDE_PREFIXES = (
    "api/chat/",
    "api/model-requests/",
    "api/model-usage/",
    "api/runs/",
    "api/workflows/",
)


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def compute_source_hash() -> str:
    proc = run([sys.executable, str(SCRIPT_DIR / "compute_api_source_hash.py")])
    return proc.stdout.strip()


def image_exists() -> bool:
    proc = run(["docker", "image", "inspect", IMAGE_NAME], check=False)
    return proc.returncode == 0


def image_source_hash() -> str | None:
    proc = run(
        [
            "docker",
            "image",
            "inspect",
            IMAGE_NAME,
            "--format",
            "{{ index .Config.Labels \"mentora.api.source_hash\" }}",
        ],
        check=False,
    )
    value = proc.stdout.strip()
    return value or None


def container_running() -> bool:
    proc = run(
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER_NAME],
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def module_exists_in_image(relpath: str) -> bool:
    proc = run(
        ["docker", "run", "--rm", "--entrypoint", "test", IMAGE_NAME, "-f", f"/app/{relpath}"],
        check=False,
    )
    return proc.returncode == 0


def parse_expected_direct_routes() -> set[str]:
    """解析 config/urls.py 中直接声明的 path，不含 include 挂载点。"""
    urls_path = API_ROOT / "config" / "urls.py"
    text = urls_path.read_text(encoding="utf-8")
    routes: set[str] = set()
    for block in re.finditer(r"path\([^)]+\)", text, re.DOTALL):
        fragment = block.group(0)
        if "include(" in fragment:
            continue
        match = re.search(r'["\']([^"\']+)["\']', fragment)
        if not match:
            continue
        route = match.group(1).lstrip("/").rstrip("/")
        if not route or route == "api":
            continue
        routes.add(route)
    return routes


def check_include_prefixes(actual: set[str]) -> list[str]:
    """校验 include 子路由是否至少有一条对应前缀已注册。"""
    act = {normalize_route(r) for r in actual}
    missing: list[str] = []
    for prefix in INCLUDE_PREFIXES:
        norm = normalize_route(prefix)
        if not any(a == norm or a.startswith(f"{norm}/") for a in act):
            missing.append(prefix)
    return missing


def fetch_container_routes() -> set[str]:
    proc = run(
        [
            "docker",
            "exec",
            CONTAINER_NAME,
            "python",
            "-c",
            """
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.urls import get_resolver

def collect(resolver, prefix=""):
    out = []
    for pattern in resolver.url_patterns:
        if hasattr(pattern, "url_patterns"):
            out.extend(collect(pattern, prefix + str(pattern.pattern)))
        else:
            out.append(prefix + str(getattr(pattern.pattern, "_route", pattern.pattern)))
    return out

for route in sorted(set(r for r in collect(get_resolver()) if r.startswith("api/"))):
    print(route)
""",
        ],
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "无法读取容器路由")
    return {line.strip() for line in proc.stdout.splitlines() if line.startswith("api/")}


def normalize_route(route: str) -> str:
    return route.rstrip("/")


def module_exists_in_container(relpath: str) -> bool:
    proc = run(
        ["docker", "exec", CONTAINER_NAME, "test", "-f", f"/app/{relpath}"],
        check=False,
    )
    return proc.returncode == 0


def compare_direct_routes(expected: set[str], actual: set[str]) -> tuple[list[str], list[str]]:
    exp = {normalize_route(r) for r in expected}
    act = {normalize_route(r) for r in actual}
    missing: list[str] = []
    for route in sorted(exp):
        if route in act:
            continue
        if any(a == route or a.startswith(f"{route}/") for a in act):
            continue
        missing.append(route)
    extra = sorted(act - exp)
    return missing, extra


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 Mentora API Docker 镜像与路由")
    parser.add_argument("--require-container", action="store_true", help="要求容器正在运行")
    parser.add_argument(
        "--allow-stale-image",
        action="store_true",
        help="镜像哈希不一致时仅告警（容器路由/模块已对齐时可临时通过）",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    def log(msg: str) -> None:
        if not args.quiet:
            print(msg)

    errors: list[str] = []
    workspace_hash = compute_source_hash()
    log(f"工作区源码哈希: {workspace_hash[:12]}…")

    if not image_exists():
        errors.append(f"镜像 {IMAGE_NAME} 不存在，请先运行 pnpm api:docker:build")
    else:
        label_hash = image_source_hash()
        if not label_hash:
            msg = "镜像缺少 mentora.api.source_hash 标签，请重新构建镜像"
            if args.allow_stale_image:
                log(f"警告: {msg}")
            else:
                errors.append(msg)
        elif label_hash != workspace_hash:
            msg = (
                "镜像源码哈希与工作区不一致："
                f"image={label_hash[:12]}… workspace={workspace_hash[:12]}…"
            )
            if args.allow_stale_image:
                log(f"警告: {msg}")
            else:
                errors.append(msg)
        else:
            log("镜像源码哈希: 一致")

        for module in REQUIRED_MODULES:
            in_image = module_exists_in_image(module)
            in_container = container_running() and module_exists_in_container(module)
            if not in_image and not in_container:
                errors.append(f"缺少关键模块: {module}")
            elif not in_image and in_container:
                log(f"模块在容器中 OK（镜像待重建）: {module}")
            else:
                log(f"模块 OK: {module}")

    expected_routes = parse_expected_direct_routes()
    if container_running():
        try:
            actual_routes = fetch_container_routes()
            missing_direct, extra = compare_direct_routes(expected_routes, actual_routes)
            missing_prefixes = check_include_prefixes(actual_routes)
            if missing_direct:
                errors.append("容器缺少直接路由:\n  - " + "\n  - ".join(missing_direct))
            if missing_prefixes:
                errors.append(
                    "容器缺少 include 子路由前缀:\n  - " + "\n  - ".join(missing_prefixes)
                )
            direct_ok = len(expected_routes) - len(missing_direct)
            prefix_ok = len(INCLUDE_PREFIXES) - len(missing_prefixes)
            log(
                f"直接路由校验: {direct_ok}/{len(expected_routes)} OK；"
                f"include 前缀校验: {prefix_ok}/{len(INCLUDE_PREFIXES)} OK；"
                f"容器共 {len(actual_routes)} 条 api/* 路由"
            )
            if extra:
                log("容器额外路由（含 include 子路由）: " + ", ".join(extra[:20]) + ("…" if len(extra) > 20 else ""))
        except RuntimeError as exc:
            errors.append(str(exc))
    elif args.require_container:
        errors.append(f"容器 {CONTAINER_NAME} 未运行")

    if errors:
        print("API 镜像/容器校验失败:", file=sys.stderr)
        for err in errors:
            print(f"  • {err}", file=sys.stderr)
        print(
            "\n建议: pnpm api:docker:build && pnpm api:docker:up",
            file=sys.stderr,
        )
        return 1

    log("API 镜像/容器校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
