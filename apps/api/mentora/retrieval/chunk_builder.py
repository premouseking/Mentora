"""
EvidenceUnit 聚合为 ChunkProjection（滑动窗口）。

约定：
- 同一 source_version_id 的 EvidenceUnit 按 page_number + element_indices 排序
- 目标 token 数 ≤ chunk_size（默认 512），超过则启动新 Chunk
- 相邻 Chunk 重叠 overlap 个 EvidenceUnit
- Token 估算：中文 ~1.5 char/token，英文/数字 ~4 char/token

@module mentora/retrieval/chunk_builder
"""

import re
from typing import Protocol


class _EvidenceLike(Protocol):
    id: object
    content: str
    source_version_id: str


def estimate_tokens(text: str) -> int:
    """
    粗略估算 token 数。

    中文/标点：1.5 字符 ≈ 1 token
    英文/数字/空格：4 字符 ≈ 1 token
    """
    cjk = len(re.findall(r"[一-鿿　-〿＀-￯]", text))
    ascii_len = len(text) - cjk
    return max(1, int(cjk / 1.5 + ascii_len / 4))


def build_chunks(
    evidence_units: list,
    chunk_size: int = 512,
    overlap: int = 1,
) -> list:
    """
    将 EvidenceUnit 列表按滑动窗口聚合为 ChunkProjection。

    参数：
        evidence_units: 已排序的 EvidenceUnit 列表
        chunk_size: 每个 Chunk 的最大 token 数
        overlap: 相邻 Chunk 重叠的 EvidenceUnit 数

    返回：ChunkProjection ORM 实例列表（未 save）
    """
    from mentora.retrieval.models import ChunkProjection

    if not evidence_units:
        return []

    chunks: list = []
    i = 0
    n = len(evidence_units)

    while i < n:
        current_tokens = 0
        current_ids: list = []
        current_parts: list[str] = []

        j = i
        while j < n:
            unit = evidence_units[j]
            tokens = estimate_tokens(unit.content)

            # 第一个 unit 即使超过 chunk_size 也放入（避免死循环）
            if not current_parts or current_tokens + tokens <= chunk_size:
                current_ids.append(unit.id)
                current_parts.append(unit.content)
                current_tokens += tokens
                j += 1
            else:
                break

        # 创建 Chunk
        chunks.append(ChunkProjection(
            source_version_id=evidence_units[i].source_version_id,
            evidence_ids=[str(eid) for eid in current_ids],
            content="\n\n".join(current_parts),
            token_count=current_tokens,
        ))

        # 下一个窗口起点：当前窗口末尾 - overlap
        if j >= n:
            break  # 已处理完所有 unit

        i = j - overlap if j - overlap > i else j

    return chunks
