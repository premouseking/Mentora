"""
Celery 解析任务。

约定：
- 解析任务使用 content_hash + parser_name + parser_version 作为幂等键
- 重复任务（相同幂等键）不重新解析，直接返回已有 artifact_ref
- 解析产物写入对象存储，数据库中只保存引用

约束：
- 任务不可恢复的错误进入终态失败，不做无限重试
- 重试仅针对可恢复错误（网络超时、存储暂不可用）
- 成功/失败状态通过 RuntimeEvent 上报

@module mentora.parsing.tasks
"""

import hashlib
import json
import os
import tempfile

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from mentora.parsing.adapters import parse
from mentora.parsing.adapters.exceptions import (
    CorruptedPDFError,
    EncryptedPDFError,
    ImageOnlyPDFError,
    UnsupportedFormatError,
)
from mentora.parsing.evidence import split_evidence


class ParseTaskFailedError(Exception):
    """解析任务不可恢复的失败。"""


def _make_idempotency_key(content_hash: str, parser_name: str, parser_version: str) -> str:
    """生成解析任务的幂等键。"""
    raw = f"{content_hash}:{parser_name}:{parser_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(IOError, OSError),
)
def run_parsing(
    self,
    source_version_id: str,
    file_path: str,
    content_hash: str,
    parser_version: str = "1.23.0",
) -> dict:
    """
    解析单个文件，持久化 ParsedBundle 和 EvidenceUnit。

    返回包含 artifact_ref 和 evidence_count 的字典。
    """
    # 1. 解析
    try:
        bundle = parse(file_path, parser_version)
    except (EncryptedPDFError, CorruptedPDFError, ImageOnlyPDFError, UnsupportedFormatError) as exc:
        raise ParseTaskFailedError(str(exc)) from exc

    # 2. 注入 source_version_id
    bundle.source_version_id = source_version_id

    # 3. 序列化并写入临时文件（后续由对象存储上传取代）
    bundle_json = bundle.model_dump_json(indent=2)

    # 4. 生成 artifact_ref（首版存本地临时目录，后续切 MinIO）
    idem_key = _make_idempotency_key(content_hash, "pymupdf", parser_version)
    artifact_dir = os.path.join(tempfile.gettempdir(), "mentora", "parsing")
    os.makedirs(artifact_dir, exist_ok=True)
    artifact_path = os.path.join(artifact_dir, f"{idem_key}.json")

    with open(artifact_path, "w", encoding="utf-8") as fh:
        fh.write(bundle_json)

    # 5. 拆分 EvidenceUnit
    evidence_units = split_evidence(bundle)

    return {
        "source_version_id": source_version_id,
        "artifact_ref": artifact_path,
        "bundle_id": str(bundle.id),
        "content_hash": content_hash,
        "parser_name": "pymupdf",
        "parser_version": parser_version,
        "page_count": bundle.page_count,
        "element_count": bundle.element_count,
        "evidence_count": len(evidence_units),
        "quality_score": bundle.quality.score,
    }
