"""知识库领域服务。"""


def get_completed_source_versions() -> list[str]:
    """返回所有已完成解析的 SourceVersion ID 列表。"""
    from mentora.knowledge.models import SourceVersion

    return [
        str(sv.id)
        for sv in SourceVersion.objects.filter(
            processing_status="completed",
        ).values_list("id", flat=True)
    ]
