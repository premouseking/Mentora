"""
EvidenceUnit 内容拆分为 SentenceProjection。

约定：
- 中文标点（。！？；换行符）和英文句尾标点（. ! ?）作为句子边界
- 保留小数点和版本号中的点号不被误切
- 以句末标点结尾的短句不合并（"好。" 是完整句子）
- 仅对无句末标点的过短碎片合并到相邻句

@module mentora/retrieval/sentence_splitter
"""

import re

_DOT_MARKER = "<<DOT>>"

_SENTENCE_BOUNDARY = re.compile(
    r"(?<=[。！？；\n])(?=[^\n])"
    r"|(?<=[.!?])(?=\s+[A-Z一-鿿])"
    r"|(?<=[.!?])(?=$)"
)

_DECIMAL_OR_VERSION = re.compile(r"\d\.\d")


def split_sentences(content: str) -> list[str]:
    """按标点符号拆分文本为句子列表。"""
    if not content.strip():
        return []

    protected = _DECIMAL_OR_VERSION.sub(
        lambda m: m.group().replace(".", _DOT_MARKER),
        content,
    )

    raw_parts = _SENTENCE_BOUNDARY.split(protected)

    sentences: list[str] = []
    for part in raw_parts:
        restored = part.replace(_DOT_MARKER, ".")
        cleaned = restored.strip()
        if cleaned:
            sentences.append(cleaned)

    return _merge_short(sentences)


def _merge_short(sentences: list[str], min_len: int = 5) -> list[str]:
    """将未以句末标点结尾的过短片段合并到相邻句。"""
    if not sentences:
        return []

    SENTENCE_ENDS = ("。", "！", "？", "；", ".", "!", "?")
    merged: list[str] = []
    i = 0
    while i < len(sentences):
        current = sentences[i]

        # 以句末标点结尾 → 保留，不合并
        if current.endswith(SENTENCE_ENDS):
            merged.append(current)
            i += 1
            continue

        # 长度足够 → 保留
        if len(current) >= min_len:
            merged.append(current)
            i += 1
            continue

        # 过短且无句末标点 → 合并到下一句或前驱
        if i + 1 < len(sentences):
            sentences[i + 1] = current + sentences[i + 1]
        elif merged:
            merged[-1] = merged[-1] + current
        else:
            merged.append(current)
        i += 1

    return merged


def generate_sentence_projections(
    evidence_unit_id: str | object,
    content: str,
) -> list:
    """从 EvidenceUnit 内容生成 SentenceProjection 列表。"""
    from mentora.retrieval.models import SentenceProjection

    sentences = split_sentences(content)
    return [
        SentenceProjection(
            evidence_unit_id=evidence_unit_id,
            position_index=idx,
            content=sentence,
        )
        for idx, sentence in enumerate(sentences)
    ]
