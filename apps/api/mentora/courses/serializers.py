"""
建课会话 DRF Serializer。

约定：
- 使用 DRF ModelSerializer 确保与模型字段同步
- inquiry_history 不做对象嵌套校验（存储时信任调用方）
- 响应字段名使用 camelCase，与前端对齐

约束：
- goal 创建时必填，更新时可选

@module mentora/courses/serializers
"""

from rest_framework import serializers

from mentora.courses.models import CourseCreationSession


class SessionCreateSerializer(serializers.ModelSerializer):
    """创建会话。"""

    goal = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = CourseCreationSession
        fields = ["id", "goal", "status"]
        read_only_fields = ["id", "status"]


class SessionUpdateSerializer(serializers.ModelSerializer):
    """更新会话基础信息。"""

    class Meta:
        model = CourseCreationSession
        fields = ["level", "pace", "school", "status"]


class SessionDetailSerializer(serializers.ModelSerializer):
    """会话详情。"""

    class Meta:
        model = CourseCreationSession
        fields = [
            "id",
            "goal",
            "title",
            "level",
            "pace",
            "school",
            "inquiry_history",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
