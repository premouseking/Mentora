"""
Provider 注册表与路由解析。

约定：
- provider 实例从 settings.MODEL_GATEWAY 懒构造并缓存：缺少 api_key 不阻塞 Django 启动，
  只有真正调用时才报错。
- 路由表按 QualityTier 给出「主选 + Fallback」候选序列；网关按序尝试。

约束：
- 新增厂商只需在 settings 增加 provider 与 routing 条目，无需改本文件。

@module mentora/model_gateway/registry
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string

from .contracts import QualityTier
from .exceptions import GatewayError, NoRouteError
from .providers.base import LlmProvider


@dataclass(frozen=True)
class RouteTarget:
    """一个候选目标：用哪个 provider 的哪个模型。"""

    provider: str
    model: str


class ProviderRegistry:
    def __init__(self, config: dict | None = None) -> None:
        self._config = config if config is not None else getattr(settings, "MODEL_GATEWAY", {})
        self._instances: dict[str, LlmProvider] = {}

    def get_provider(self, name: str) -> LlmProvider:
        if name in self._instances:
            return self._instances[name]

        providers_cfg = self._config.get("providers", {})
        if name not in providers_cfg:
            raise NoRouteError(f"provider 未注册: {name}")

        entry = providers_cfg[name]
        dotted_path = entry.get("class")
        if not dotted_path:
            raise GatewayError(f"provider {name} 缺少 class 配置")

        provider_cls = import_string(dotted_path)
        options = dict(entry.get("options", {}))
        options.setdefault("name", name)
        instance = provider_cls(**options)
        self._instances[name] = instance
        return instance

    def resolve_route(self, tier: QualityTier) -> list[RouteTarget]:
        routing = self._config.get("routing", {})
        raw = routing.get(tier.value)
        if not raw:
            raise NoRouteError(f"质量档未配置路由: {tier.value}")

        targets = [RouteTarget(provider=item["provider"], model=item["model"]) for item in raw]
        if not targets:
            raise NoRouteError(f"质量档路由为空: {tier.value}")
        return targets

    @property
    def max_retries_per_attempt(self) -> int:
        return int(self._config.get("max_retries_per_attempt", 1))

    @property
    def timeout_s(self) -> float:
        return float(self._config.get("timeout_s", 60.0))
