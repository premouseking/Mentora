"""Shared test fixtures for parsing tests."""

import os

import fitz
import psycopg
import pytest
from django.conf import settings


def pytest_configure(config):
    """检测 PostgreSQL 是否可用，不可用时跳过 django_db 测试。"""
    database = settings.DATABASES["default"]
    try:
        with psycopg.connect(
            dbname=database["NAME"],
            user=database["USER"],
            password=database["PASSWORD"],
            host=database["HOST"],
            port=database["PORT"],
            connect_timeout=2,
        ):
            pass
        config._postgres_available = True
    except Exception:
        config._postgres_available = False


def pytest_collection_modifyitems(config, items):
    if getattr(config, "_postgres_available", True):
        return
    skip_marker = pytest.mark.skip(reason="PostgreSQL 不可用，跳过数据库测试")
    for item in items:
        if "django_db" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def fixtures_dir():
    """测试 Fixture 目录。"""
    d = os.path.join(os.path.dirname(__file__), "fixtures")
    os.makedirs(d, exist_ok=True)
    return d


def _make_pdf(path: str, pages: list[list[tuple[str, float, tuple]]]):
    """
    用 PyMuPDF 生成测试 PDF。

    pages: 每页是一个列表，每项为 (text, font_size, (x0, y0, x1, y1))
    """
    doc = fitz.open()
    for page_items in pages:
        page = doc.new_page(width=595, height=842)  # A4
        y = 72
        for text, font_size, _ in page_items:
            page.insert_text((72, y), text, fontsize=font_size)
            y += font_size * 1.4 + 4
    doc.save(path)
    doc.close()


@pytest.fixture(scope="session")
def normal_pdf(fixtures_dir):
    """正常文本 PDF：2 段正文。"""
    path = os.path.join(fixtures_dir, "normal.pdf")
    if not os.path.exists(path):
        _make_pdf(
            path,
            [[
                ("第一章 计算机系统概述", 16, (72, 72, 500, 90)),
                ("计算机系统由硬件和软件两部分组成。硬件包括运算器、控制器、"
                 "存储器、输入设备和输出设备五大部件。", 11, (72, 100, 500, 120)),
                ("软件分为系统软件和应用软件。操作系统是最基本的系统软件，"
                 "负责管理计算机的硬件资源。", 11, (72, 130, 500, 150)),
            ]],
        )
    return path


@pytest.fixture(scope="session")
def heading_pdf(fixtures_dir):
    """含标题分级的 PDF：一级标题 + 二级标题 + 正文。"""
    path = os.path.join(fixtures_dir, "headings.pdf")
    if not os.path.exists(path):
        _make_pdf(
            path,
            [[
                ("计算机组成原理", 20, (72, 72, 500, 95)),
                ("第三章 存储系统", 16, (72, 110, 500, 130)),
                ("存储器是计算机系统中用于存储程序和数据的部件。", 11, (72, 150, 500, 170)),
                ("存储系统采用层次化结构，从寄存器、Cache、主存到外存。", 11, (72, 190, 500, 210)),
                ("Cache 存储原理", 14, (72, 240, 500, 258)),
                ("Cache 是位于 CPU 和主存之间的高速缓冲存储器。", 11, (72, 275, 500, 295)),
            ]],
        )
    return path


@pytest.fixture(scope="session")
def multi_column_pdf(fixtures_dir):
    """多栏排版 PDF（通过两列 x 坐标差异模拟）。"""
    path = os.path.join(fixtures_dir, "multi_column.pdf")
    if not os.path.exists(path):
        _make_pdf(
            path,
            [[
                ("左栏：计算机组成原理是计算机科学与技术专业的核心课程。", 10, (50, 100, 250, 120)),
                ("左栏：本课程介绍计算机各部件的结构与工作原理。", 10, (50, 135, 250, 155)),
                ("右栏：考研中组成原理占比约 15%，是重点科目之一。", 10, (310, 100, 540, 120)),
                ("右栏：推荐使用唐朔飞版教材，配合王道考研辅导书。", 10, (310, 135, 540, 155)),
            ]],
        )
    return path
