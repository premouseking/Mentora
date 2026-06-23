"""Task based provider router with optional fallback candidates."""

from __future__ import annotations

from mentora.model_gateway.providers.base import BaseProvider


class TaskRouter:
    """Route a task type to one or more provider candidates."""

    def __init__(self, default_provider: BaseProvider | None = None):
        self._routes: dict[str, list[BaseProvider]] = {}
        self._default = default_provider

    def register(self, task_type: str, provider: BaseProvider) -> None:
        self.register_candidates(task_type, [provider])

    def register_candidates(self, task_type: str, providers: list[BaseProvider]) -> None:
        if not providers:
            raise ValueError("providers must not be empty")
        self._routes[task_type] = providers

    def resolve(self, task_type: str) -> BaseProvider:
        return self.resolve_candidates(task_type)[0]

    def resolve_candidates(self, task_type: str) -> list[BaseProvider]:
        if task_type in self._routes:
            return self._routes[task_type]
        if self._default is not None:
            return [self._default]
        raise KeyError(f"No provider registered for task_type={task_type}")
