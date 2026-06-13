"""
jieba 分词器，加载自定义词典，构建 PostgreSQL tsquery。

约定：
- 分词在查询侧执行，不修改存储侧 Evidence 文本
- 自定义词典位于 jieba_dict.txt，随模块加载
- 英文术语保留原样（不转换大小写），中文按词典切分

约束：
- tsquery 使用 simple 配置，避免 PG 自带词典干扰自定义词典效果
- 空查询返回 None，调用方应提前校验

@module mentora/retrieval/tokenizer
"""

import os

import jieba

# 加载自定义词典
_DICT_PATH = os.path.join(os.path.dirname(__file__), "jieba_dict.txt")
if os.path.exists(_DICT_PATH):
    jieba.load_userdict(_DICT_PATH)


def segment(text: str) -> list[str]:
    """
    jieba 精确模式分词。

    返回去重、去空的词条列表，保留英文术语原样。
    """
    words: list[str] = []
    seen: set[str] = set()
    for word in jieba.cut(text, cut_all=False):
        word = word.strip()
        if not word:
            continue
        # 英文术语保留原样
        normalized = word.lower() if _is_pure_cjk(word) else word
        if normalized not in seen:
            seen.add(normalized)
            words.append(normalized)
    return words


def build_fts_query(text: str) -> str | None:
    """
    将用户查询转换为 PostgreSQL plainto_tsquery('simple', ...) 的输入。

    返回 None 表示无有效词条。
    """
    words = segment(text)
    if not words:
        return None
    return " & ".join(words)


def build_trgm_query(text: str) -> str | None:
    """
    将用户查询转换为 pg_trgm similarity 的输入（直接使用原始文本）。
    """
    stripped = text.strip()
    return stripped if stripped else None


def _is_pure_cjk(word: str) -> bool:
    """判断是否纯中日韩字符（无英文/数字）。"""
    for ch in word:
        if ch.isascii():
            return False
    return True
