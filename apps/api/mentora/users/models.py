"""
用户认证模型。

约定：
- email 为唯一登录标识
- JWT 通过 djangorestframework-simplejwt 签发

@module mentora/auth/models
"""

import uuid

from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("email 不能为空")
        email = self.normalize_email(email)
        user = self.model(email=email, username="", **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Mentora 用户。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True, verbose_name="邮箱")
    display_name = models.CharField(max_length=128, blank=True, default="", verbose_name="显示名称")

    # 禁用默认 username 字段
    username = models.CharField(max_length=150, blank=True, default="", editable=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]
    objects = UserManager()

    class Meta:
        db_table = "auth_user"
        verbose_name = "用户"
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        return f"{self.display_name or self.email}"
