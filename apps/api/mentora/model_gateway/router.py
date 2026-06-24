"""任务路由 + Provider 健康状态 + Fallback 策略。"""

from __future__ import annotations

import time

from mentora.model_gateway.exceptions import NoHealthyProviderError
from mentora.model_gateway.providers.base import BaseProvider


class TaskRouter:
    """
    按 task_type 路由到 Provider，支持健康检查与自动 Fallback。

    约定：
    - 连续失败 >= max_failures 后标记为不健康，cooldown_seconds 后自动恢复
    - candidates 列表按优先级排序，第一个为 Primary

    约束：
    - 健康状态在内存中（进程重启重置），生产环境可迁移到 Redis
    """

    def __init__(
        self,
        default_provider: BaseProvider | None = None,
        *,
        max_failures: int = 3,
        cooldown_seconds: int = 60,
    ):
        self._routes: dict[str, list[BaseProvider]] = {}
        self._default = default_provider
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        self._failures: dict[str, int] = {}
        self._cooldown_until: dict[str, float] = {}

    def register(self, task_type: str, provider: BaseProvider) -> None:
        self.register_candidates(task_type, [provider])

    def register_candidates(self, task_type: str, providers: list[BaseProvider]) -> None:
        if not providers:
            raise ValueError("providers must not be empty")
        self._routes[task_type] = providers

    def resolve_candidates(self, task_type: str) -> list[BaseProvider]:
        if task_type in self._routes:
            return self._routes[task_type]
        if self._default is not None:
            return [self._default]
        raise KeyError(f"No provider registered for task_type={task_type}")

    def resolve(self, task_type: str) -> BaseProvider:
        candidates = self.resolve_candidates(task_type)
        for p in candidates:
            if self._is_healthy(p.name):
                return p
        raise NoHealthyProviderError(
            f"All providers unhealthy for task_type={task_type}"
        )

    def mark_success(self, provider_name: str) -> None:
        self._failures[provider_name] = 0

    def mark_failure(self, provider_name: str) -> None:
        self._failures[provider_name] = self._failures.get(provider_name, 0) + 1
        if self._failures[provider_name] >= self.max_failures:
            self._cooldown_until[provider_name] = time.time() + self.cooldown_seconds

    def _is_healthy(self, provider_name: str) -> bool:
        cooldown = self._cooldown_until.get(provider_name, 0)
        if cooldown > 0 and time.time() < cooldown:
            return False
        if cooldown > 0 and time.time() >= cooldown:
            del self._cooldown_until[provider_name]
            self._failures[provider_name] = 0
        return True

    def health_status(self) -> dict:
        """返回所有已知 Provider 的健康状态。"""
        return {
            name: {
                "healthy": self._is_healthy(name),
                "failures": self._failures.get(name, 0),
                "cooldown_until": self._cooldown_until.get(name),
            }
            for name in self._failures
        }
