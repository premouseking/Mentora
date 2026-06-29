"""
用户认证模型。

约定：
- email 为唯一登录标识
- JWT 通过 djangorestframework-simplejwt 签发

@module mentora/auth/models
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Mentora 用户。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True, verbose_name="邮箱")
    display_name = models.CharField(max_length=128, blank=True, default="", verbose_name="显示名称")

    # 禁用默认 username 字段
    username = models.CharField(max_length=150, blank=True, default="", editable=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        db_table = "auth_user"
        verbose_name = "用户"
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        return f"{self.display_name or self.email}"
