"""
用户注册与登录 API。

@module mentora/users/views
"""

from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.tokens import RefreshToken

from mentora.users.models import User


def _tokens_for(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "user_id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@extend_schema(
    summary="用户注册",
    description="创建新用户并返回 JWT。",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "邮箱"},
                "password": {"type": "string", "description": "密码，≥8 位"},
                "display_name": {"type": "string", "description": "显示名称"},
            },
            "required": ["email", "password"],
        },
    },
    responses={
        201: {"description": "注册成功，返回 JWT"},
        400: {"description": "参数无效或邮箱已注册"},
    },
)
@api_view(["POST"])
def register(request):
    email = (request.data.get("email") or "").strip().lower()
    password = (request.data.get("password") or "")
    display_name = (request.data.get("display_name") or "").strip()

    if not email or not password:
        return Response({"error": "email 和 password 为必填"}, status=400)
    if len(password) < 8:
        return Response({"error": "密码长度至少 8 位"}, status=400)
    if User.objects.filter(email=email).exists():
        return Response({"error": "该邮箱已注册"}, status=400)

    user = User.objects.create_user(
        email=email,
        password=password,
        display_name=display_name or email.split("@")[0],
    )
    return Response(_tokens_for(user), status=201)


@extend_schema(
    summary="用户登录",
    description="验证邮箱密码，返回 JWT。",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "邮箱"},
                "password": {"type": "string", "description": "密码"},
            },
            "required": ["email", "password"],
        },
    },
    responses={
        200: {"description": "登录成功，返回 JWT"},
        401: {"description": "邮箱或密码错误"},
    },
)
@api_view(["POST"])
def login(request):
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""

    from django.contrib.auth import authenticate

    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response({"error": "邮箱或密码错误"}, status=401)

    return Response(_tokens_for(user))


@extend_schema(
    summary="刷新 Token",
    description="用 refresh token 换取新的 access token。",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "refresh": {"type": "string", "description": "refresh token"},
            },
            "required": ["refresh"],
        },
    },
    responses={
        200: {"description": "新的 access token"},
        401: {"description": "refresh token 无效或过期"},
    },
)
@api_view(["POST"])
def refresh(request):
    refresh = (request.data.get("refresh") or "").strip()
    if not refresh:
        return Response({"error": "缺少 refresh token"}, status=400)

    try:
        token = RefreshToken(refresh)
        return Response({
            "access": str(token.access_token),
            "refresh": str(token),
        })
    except Exception:
        return Response({"error": "refresh token 无效或已过期"}, status=401)
