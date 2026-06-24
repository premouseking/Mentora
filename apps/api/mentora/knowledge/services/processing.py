"""
资料版本解析与入库编排。

约定：
- worker 从对象存储读取原文件，不写本地路径到数据库
- 解析产物 JSON 写入对象存储 artifact_ref
- 测试环境可同步执行 run_processing_for_version

@module mentora/knowledge/services/processing
"""

import hashlib
import os
import tempfile

from django.db import transaction
from django.utils import timezone

from mentora.common.storage import ObjectStorageService
from mentora.knowledge.models import (
    ProcessingRun,
    ProcessingRunStatus,
    ProcessingStatus,
    SourceVersion,
)
from mentora.knowledge.services.persist_evidence import persist_evidence_units
from mentora.parsing.adapters import parse
from mentora.parsing.adapters.exceptions import (
    CorruptedPDFError,
    EncryptedPDFError,
    ImageOnlyPDFError,
    ParsingError,
    UnsupportedFormatError,
)
from mentora.parsing.evidence import split_evidence


def _make_version_idempotency_key(
    source_version_id: str,
    content_hash: str,
    parser_name: str,
    parser_version: str,
) -> str:
    raw = f"{source_version_id}:{content_hash}:{parser_name}:{parser_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def run_processing_for_version(
    source_version_id: str,
    parser_version: str = "1.23.0",
    sync: bool = True,
) -> ProcessingRun:
    """
    为指定 SourceVersion 执行解析与证据入库。

    sync=True 时在当前进程同步执行（测试/smoke 用）；False 时投递 Celery。
    """
    source_version = SourceVersion.objects.select_related("source").get(id=source_version_id)
    idem_key = _make_version_idempotency_key(
        str(source_version.id),
        source_version.content_sha256,
        "pymupdf",
        parser_version,
    )

    existing = ProcessingRun.objects.filter(idempotency_key=idem_key).first()
    if existing and existing.status == ProcessingRunStatus.COMPLETED:
        return existing

    with transaction.atomic():
        run, created = ProcessingRun.objects.get_or_create(
            idempotency_key=idem_key,
            defaults={
                "source_version": source_version,
                "parser_name": "pymupdf",
                "parser_version": parser_version,
                "status": ProcessingRunStatus.PENDING,
            },
        )
        if not created and run.status == ProcessingRunStatus.COMPLETED:
            return run

        run.status = ProcessingRunStatus.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at"])

    if not sync:
        from mentora.knowledge.tasks import run_processing

        run_processing.delay(str(source_version.id), parser_version)
        return run

    try:
        _execute_processing(run, source_version, parser_version)
    except Exception as exc:
        run.status = ProcessingRunStatus.FAILED
        run.error_code = type(exc).__name__
        run.error_message = str(exc)
        run.completed_at = timezone.now()
        run.save()

        source_version.processing_status = ProcessingStatus.FAILED
        source_version.error_code = run.error_code
        source_version.error_message = run.error_message
        source_version.save(
            update_fields=["processing_status", "error_code", "error_message"]
        )
        raise

    return run


def _extract_and_upload_images(
    bundle,
    pdf_path: str,
    source_version_id: str,
    storage,
) -> None:
    """从 PDF 提取内嵌图片并上传到对象存储，回填 artifact_ref 到 IMAGE 元素。"""
    from mentora.parsing.schemas import ElementType
    import hashlib

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return

    try:
        for page_idx, page_data in enumerate(bundle.pages):
            for elem in page_data.elements:
                if elem.type != ElementType.IMAGE:
                    continue
                if not elem.extra or "xref" not in elem.extra:
                    continue
                xref = elem.extra["xref"]
                try:
                    img_dict = doc.extract_image(xref)
                except Exception:
                    continue

                img_bytes = img_dict.get("image")
                if not img_bytes:
                    continue

                ext = img_dict.get("ext", "png")
                img_hash = hashlib.sha256(img_bytes).hexdigest()[:12]
                object_key = (
                    f"images/{source_version_id}/p{page_idx + 1}_{img_hash}.{ext}"
                )
                try:
                    storage.put_object(
                        object_key,
                        img_bytes,
                        content_type=f"image/{ext}",
                    )
                    elem.extra["artifact_ref"] = object_key
                except Exception:
                    elem.extra["artifact_ref"] = ""
    finally:
        doc.close()


def _execute_processing(
    run: ProcessingRun,
    source_version: SourceVersion,
    parser_version: str,
) -> None:
    storage = ObjectStorageService()
    storage.ensure_bucket()

    source_version.processing_status = ProcessingStatus.PROCESSING
    source_version.save(update_fields=["processing_status"])

    file_bytes = storage.get_object_bytes(source_version.object_key)
    suffix = ".pdf"
    if source_version.original_filename.lower().endswith(".pdf"):
        suffix = ".pdf"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        bundle = parse(tmp_path, parser_version)
        bundle.source_version_id = str(source_version.id)
        bundle.content_hash = source_version.content_sha256

        # 提取内嵌图片并上传到对象存储
        _extract_and_upload_images(bundle, tmp_path, str(source_version.id), storage)

        artifact_key = storage.artifact_key_for_bundle(str(bundle.id))
        bundle.artifact_ref = artifact_key
        storage.put_object(
            artifact_key,
            bundle.model_dump_json(indent=2).encode("utf-8"),
            content_type="application/json",
        )

        evidence_units = split_evidence(bundle)
        count = persist_evidence_units(evidence_units, str(source_version.id))

        # 解析完成后自动构建 Chunk 并异步生成 embedding
        from mentora.retrieval.chunk_builder import build_chunks
        from mentora.retrieval.models import EvidenceUnit as ORMEvidenceUnit

        units = list(
            ORMEvidenceUnit.objects.filter(
                source_version_id=str(source_version.id)
            ).order_by("page_number")
        )
        for chunk in build_chunks(units):
            chunk.save()

        from mentora.retrieval.tasks import generate_chunk_embeddings, generate_sentence_embeddings
        generate_chunk_embeddings.delay(str(source_version.id))
        generate_sentence_embeddings.delay(str(source_version.id))

        source_version.processing_status = ProcessingStatus.COMPLETED
        source_version.artifact_ref = artifact_key
        source_version.parser_name = "pymupdf"
        source_version.parser_version = parser_version
        source_version.error_code = ""
        source_version.error_message = ""
        source_version.save(
            update_fields=[
                "processing_status",
                "artifact_ref",
                "parser_name",
                "parser_version",
                "error_code",
                "error_message",
            ]
        )

        run.status = ProcessingRunStatus.COMPLETED
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])

        if count == 0:
            raise ParsingError("解析未产生任何证据单元")
    except (
        EncryptedPDFError,
        CorruptedPDFError,
        ImageOnlyPDFError,
        UnsupportedFormatError,
        ParsingError,
    ) as exc:
        raise exc
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
