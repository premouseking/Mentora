"""
EvidenceUnit 聚合为 ChunkProjection（滑动窗口 + 结构感知）。

约定：
- 同一 source_version_id 的 EvidenceUnit 按 page_number + element_indices 排序
- 遇 HEADING 元素且当前窗口非空时，先输出已有内容再开启新 Chunk
- 同一 Chunk 内按 token 数控制大小（默认 512）
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
    structure_type: str


def estimate_tokens(text: str) -> int:
    """
    粗略估算 token 数。

    中文/标点：1.5 字符 ≈ 1 token
    英文/数字/空格：4 字符 ≈ 1 token
    """
    cjk = len(re.findall(r"[一-鿿　-〿＀-￯]", text))
    ascii_len = len(text) - cjk
    return max(1, int(cjk / 1.5 + ascii_len / 4))


def _flush_chunk(source_version_id: str, ids: list, parts: list[str], tokens: int):
    """输出一个 ChunkProjection 实例（未 save）。"""
    from mentora.retrieval.models import ChunkProjection

    return ChunkProjection(
        source_version_id=source_version_id,
        evidence_ids=[str(eid) for eid in ids],
        content="\n\n".join(parts),
        token_count=tokens,
    )


def build_chunks(
    evidence_units: list,
    chunk_size: int = 512,
    overlap: int = 1,
) -> list:
    """
    将 EvidenceUnit 列表按滑动窗口聚合为 ChunkProjection。

    结构感知：header 元素触发 Chunk 边界分界。
    标题永远出现在 Chunk 开头，不会跨小节混搭到上一个 Chunk 末尾。

    参数：
        evidence_units: 已排序的 EvidenceUnit 列表
        chunk_size: 每个 Chunk 的最大 token 数
        overlap: 相邻 Chunk 重叠的 EvidenceUnit 数

    返回：ChunkProjection ORM 实例列表（未 save）
    """
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
            is_heading = getattr(unit, "structure_type", None) == "heading"

            # 标题且窗口非空 → 先输出当前 Chunk，新标题开新 Chunk
            if is_heading and current_parts:
                chunks.append(_flush_chunk(
                    evidence_units[i].source_version_id,
                    current_ids,
                    current_parts,
                    current_tokens,
                ))
                # 从当前标题重新开始窗口
                current_tokens = 0
                current_ids = []
                current_parts = []
                i = j  # 窗口起点更新为标题位置
                break

            # 第一个 unit 即使超过 chunk_size 也放入（避免死循环）
            if not current_parts or current_tokens + tokens <= chunk_size:
                current_ids.append(unit.id)
                current_parts.append(unit.content)
                current_tokens += tokens
                j += 1
            else:
                break

        # 输出当前窗口（如果还有内容且未因标题分界提前输出）
        if current_parts:
            chunks.append(_flush_chunk(
                evidence_units[i].source_version_id,
                current_ids,
                current_parts,
                current_tokens,
            ))

        # 下一个窗口起点
        if j >= n:
            break

        i = j - overlap if j - overlap > i else j

    return chunks
