"""
任务路由器：将 task_type 映射到 Provider。

约定：
- 路由配置可运行时变更，不硬编码 Provider 实例
- 默认使用 fake provider，真实 provider 通过环境变量覆盖

@module mentora/model_gateway/router
"""

import os
from typing import Protocol

from mentora.model_gateway.providers.base import BaseProvider


class TaskRouter:
    """将 task_type 路由到对应的 Provider。

    约定：
    - 找不到映射时抛出 KeyError
    - Provider 由外部注入，路由只持有引用
    """

    def __init__(self, default_provider: BaseProvider | None = None):
        self._routes: dict[str, BaseProvider] = {}
        self._default = default_provider

    def register(self, task_type: str, provider: BaseProvider) -> None:
        """注册 task_type → provider 映射。"""
        self._routes[task_type] = provider

    def resolve(self, task_type: str) -> BaseProvider:
        """解析 task_type 对应的 provider。"""
        if task_type in self._routes:
            return self._routes[task_type]
        if self._default is not None:
            return self._default
        raise KeyError(f"No provider registered for task_type={task_type}")
