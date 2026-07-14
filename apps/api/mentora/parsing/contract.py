"""ParsedBundle API 契约序列化。"""

from __future__ import annotations

from mentora.parsing.schemas import ParsedBundle


def serialize_parsed_bundle(bundle_data: dict | ParsedBundle | None) -> dict | None:
    """将 ParsedBundle 归一化为稳定的 JSON 契约（含 page_count / element_count）。"""
    if bundle_data is None:
        return None
    if isinstance(bundle_data, ParsedBundle):
        return bundle_data.model_dump(mode="json")
    try:
        return ParsedBundle.model_validate(bundle_data).model_dump(mode="json")
    except Exception:
        pages = bundle_data.get("pages") or []
        return {
            **bundle_data,
            "page_count": bundle_data.get("page_count", len(pages)),
            "element_count": bundle_data.get(
                "element_count",
                sum(len((page or {}).get("elements") or []) for page in pages),
            ),
        }
