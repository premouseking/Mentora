"""
主题领域服务：主题树构建、查询与证据关联。

约定：
- parent_index 为输入数组中的序号，-1/null 表示根节点
- link_evidence 批量写入后更新 Topic.evidence_count

@module mentora/topics/services
"""

from django.db import transaction

from mentora.topics.models import Topic, TopicEvidence


@transaction.atomic
def build_topic_tree(course_id: str, topics_data: list[dict]) -> dict:
    """从结构化数据创建主题树。

    topics_data: [
        {"name": str, "level": int, "parent_index": int, "position": int, "estimated_minutes": int},
        ...
    ]
    parent_index: topics_data 数组中的序号，-1 或 None 表示根节点

    返回: {topic_count: int, root_ids: [...]}
    """
    # 清空旧主题树
    Topic.objects.filter(course_id=course_id).delete()

    created: list[Topic] = []
    for data in topics_data:
        topic = Topic.objects.create(
            course_id=course_id,
            name=data["name"],
            level=data.get("level", 0),
            position=data.get("position", 0),
            estimated_minutes=data.get("estimated_minutes", 0),
        )
        created.append(topic)

    # 设置 parent 关联（两遍：第一遍创建，第二遍设 parent）
    for i, data in enumerate(topics_data):
        parent_index = data.get("parent_index")
        if parent_index is not None and parent_index >= 0 and parent_index < len(created):
            topic = created[i]
            topic.parent = created[parent_index]
            topic.save(update_fields=["parent"])

    return {
        "topic_count": len(created),
        "root_ids": [str(t.id) for t in created if t.parent_id is None],
    }


def get_topic_tree(course_id: str) -> list[dict]:
    """获取课程的主题树（嵌套结构）。"""
    topics = Topic.objects.filter(course_id=course_id).order_by("level", "position")

    # 构建 id→node 映射
    node_map: dict[str, dict] = {}
    for t in topics:
        node_map[str(t.id)] = {
            "id": str(t.id),
            "name": t.name,
            "level": t.level,
            "position": t.position,
            "evidence_count": t.evidence_count,
            "estimated_minutes": t.estimated_minutes,
            "parent_id": str(t.parent_id) if t.parent_id else None,
            "children": [],
        }

    # 嵌套组装
    roots = []
    for t in topics:
        node = node_map[str(t.id)]
        if node["parent_id"]:
            parent = node_map.get(node["parent_id"])
            if parent:
                parent["children"].append(node)
        else:
            roots.append(node)

    return roots


@transaction.atomic
def link_evidence(topic_id: str, evidence_unit_ids: list[str]) -> dict:
    """批量关联证据到主题。已存在的关联跳过（幂等）。"""
    topic = Topic.objects.get(id=topic_id)
    linked = 0

    for eid in evidence_unit_ids:
        _, created = TopicEvidence.objects.get_or_create(
            topic=topic,
            evidence_unit_id=str(eid),
        )
        if created:
            linked += 1

    if linked > 0:
        topic.evidence_count = TopicEvidence.objects.filter(topic=topic).count()
        topic.save(update_fields=["evidence_count"])

    return {
        "topic_id": topic_id,
        "linked": linked,
        "total_evidence": topic.evidence_count,
    }
