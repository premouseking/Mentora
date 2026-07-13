"""
知识主题 HTTP 视图。

@module mentora/topics/views
"""

import json

from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema

from mentora.topics.models import Topic, TopicEdge
from mentora.topics.services import build_topic_tree, get_topic_tree, link_evidence


def _parse_json(request) -> dict:
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


@extend_schema(
    summary="创建/更新主题树",
    description="从结构化数据批量创建课程主题树。已存在的主题会被清空重建。",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "主题名称"},
                            "level": {"type": "integer", "description": "层级"},
                            "parent_index": {"type": "integer", "description": "父主题在数组中的序号，-1 为根"},
                            "position": {"type": "integer", "description": "排序"},
                            "estimated_minutes": {"type": "integer", "description": "预估时长"},
                        },
                    },
                },
            },
            "required": ["topics"],
        },
    },
    responses={201: {"description": "创建成功"}},
)
@api_view(["POST"])
def topic_create_tree(request, course_id):
    try:
        body = _parse_json(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)

    topics_data = body.get("topics", [])
    if not topics_data:
        return Response({"error": "缺少 topics 参数"}, status=400)

    result = build_topic_tree(course_id, topics_data)
    return Response(result, status=201)


@extend_schema(
    summary="获取主题树",
    description="返回课程主题的嵌套树结构。",
    responses={200: {"description": "主题树"}},
)
@api_view(["GET"])
def topic_get_tree(request, course_id):
    return Response(get_topic_tree(course_id))


@extend_schema(
    summary="编辑主题",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "新名称"},
                "position": {"type": "integer", "description": "新排序"},
                "estimated_minutes": {"type": "integer", "description": "预估时长"},
            },
        },
    },
    responses={200: {"description": "编辑成功"}, 404: {"description": "主题不存在"}},
)
@api_view(["PATCH"])
def topic_update(request, topic_id):
    try:
        topic = Topic.objects.get(id=topic_id)
    except Topic.DoesNotExist:
        return Response({"error": "主题不存在"}, status=404)

    try:
        body = _parse_json(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)

    for field in ("name", "position", "estimated_minutes"):
        if field in body:
            setattr(topic, field, body[field])
    topic.save(update_fields=[f for f in ("name", "position", "estimated_minutes") if f in body])
    return Response({"id": str(topic.id), "name": topic.name, "position": topic.position})


@extend_schema(
    summary="删除主题",
    description="删除主题及 CASCADE 子节点、边和证据关联。",
    responses={200: {"description": "删除成功"}, 404: {"description": "主题不存在"}},
)
@api_view(["DELETE"])
def topic_delete(request, topic_id):
    try:
        topic = Topic.objects.get(id=topic_id)
    except Topic.DoesNotExist:
        return Response({"error": "主题不存在"}, status=404)
    topic.delete()
    return Response({"status": "deleted"})


@extend_schema(
    summary="添加前置关系",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "target_id": {"type": "string", "description": "前置主题 ID"},
                "relation": {"type": "string", "description": "requires 或 suggests"},
            },
            "required": ["target_id"],
        },
    },
    responses={201: {"description": "关系创建成功"}, 404: {"description": "主题不存在"}},
)
@api_view(["POST"])
def topic_add_edge(request, topic_id):
    try:
        source = Topic.objects.get(id=topic_id)
    except Topic.DoesNotExist:
        return Response({"error": "主题不存在"}, status=404)

    try:
        body = _parse_json(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)

    target_id = body.get("target_id")
    if not target_id:
        return Response({"error": "缺少 target_id"}, status=400)

    try:
        target = Topic.objects.get(id=target_id)
    except Topic.DoesNotExist:
        return Response({"error": "前置主题不存在"}, status=404)

    relation = body.get("relation", "requires")
    edge, created = TopicEdge.objects.get_or_create(
        source=source, target=target,
        defaults={"relation": relation},
    )
    return Response({
        "id": str(edge.id),
        "source_id": str(edge.source_id),
        "target_id": str(edge.target_id),
        "relation": edge.relation,
    }, status=201 if created else 200)


@extend_schema(
    summary="关联证据",
    description="批量关联 EvidenceUnit 到主题。",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "evidence_unit_ids": {
                    "type": "array", "items": {"type": "string"},
                    "description": "EvidenceUnit ID 列表",
                },
            },
            "required": ["evidence_unit_ids"],
        },
    },
    responses={200: {"description": "关联成功"}, 404: {"description": "主题不存在"}},
)
@api_view(["POST"])
def topic_link_evidence(request, topic_id):
    try:
        Topic.objects.get(id=topic_id)
    except Topic.DoesNotExist:
        return Response({"error": "主题不存在"}, status=404)

    try:
        body = _parse_json(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)

    eids = body.get("evidence_unit_ids", [])
    if not eids:
        return Response({"error": "缺少 evidence_unit_ids"}, status=400)

    result = link_evidence(topic_id, eids)
    return Response(result)
