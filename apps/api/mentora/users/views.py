"""
用户注册与登录 API。

@module mentora/users/views
"""

from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
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
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
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


@extend_schema(
    summary="获取用户资料",
    description="返回当前登录用户的资料。",
    responses={200: {"description": "用户资料"}},
)
@api_view(["GET"])
def profile(request):
    user = request.user
    return Response({
        "user_id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "date_joined": user.date_joined.isoformat(),
    })


@extend_schema(
    summary="更新用户资料",
    description="修改当前用户的显示名称。",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "display_name": {"type": "string", "description": "新显示名称"},
            },
            "required": ["display_name"],
        },
    },
    responses={200: {"description": "更新成功"}},
)
@api_view(["PATCH"])
def update_profile(request):
    display_name = (request.data.get("display_name") or "").strip()
    if not display_name:
        return Response({"error": "display_name 不能为空"}, status=400)

    user = request.user
    user.display_name = display_name
    user.save(update_fields=["display_name"])
    return Response({
        "user_id": str(user.id),
        "display_name": user.display_name,
    })


@extend_schema(
    summary="修改密码",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "old_password": {"type": "string"},
                "new_password": {"type": "string", "description": "新密码，≥8 位"},
            },
            "required": ["old_password", "new_password"],
        },
    },
    responses={200: {"description": "修改成功"}, 400: {"description": "原密码错误或新密码太短"}},
)
@api_view(["POST"])
def change_password(request):
    user = request.user
    old_password = request.data.get("old_password") or ""
    new_password = request.data.get("new_password") or ""

    if not user.check_password(old_password):
        return Response({"error": "原密码错误"}, status=400)
    if len(new_password) < 8:
        return Response({"error": "新密码至少 8 位"}, status=400)

    user.set_password(new_password)
    user.save(update_fields=["password"])
    return Response({"status": "密码已修改"})


@extend_schema(
    summary="登出",
    description="将当前 refresh token 加入黑名单。",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "refresh": {"type": "string", "description": "refresh token"},
            },
            "required": ["refresh"],
        },
    },
    responses={200: {"description": "登出成功"}},
)
@api_view(["POST"])
def logout(request):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = (request.data.get("refresh") or "").strip()
    if refresh:
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except Exception:
            pass
    return Response({"status": "已登出"})
