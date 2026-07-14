from django.conf import settings
from rest_framework.authentication import BaseAuthentication


class DevelopmentUserAuthentication(BaseAuthentication):
    """开发旁路也注入真实 User，避免业务层出现匿名身份分支。"""

    def authenticate(self, request):
        if not settings.MENTORA_DEV_AUTH_BYPASS:
            return None

        return get_development_user(), None


def get_development_user():
    from mentora.users.models import User

    user, created = User.objects.get_or_create(
        email=settings.DEV_USER_EMAIL,
        defaults={"display_name": "Mentora Dev"},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user
