"""
模型网关异常层级。

约定：
- transient 为 True 的错误才允许网关在同一 provider 上重试或触发 Fallback。
- 异常信息中禁止包含密钥、完整资料正文或隐藏答案。

@module mentora/model_gateway/exceptions
"""

from __future__ import annotations


class GatewayError(Exception):
    """网关层通用错误基类。"""


class NoRouteError(GatewayError):
    """没有可用的路由（质量档未配置或 provider 未注册）。"""


class ProviderError(GatewayError):
    """provider 物理调用失败。transient 决定是否可重试/Fallback。"""

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


class ProviderTimeout(ProviderError):
    def __init__(self, message: str = "provider 调用超时") -> None:
        super().__init__(message, transient=True)


class StructuredOutputError(GatewayError):
    """模型输出无法解析或未通过 Pydantic schema 校验。"""


class NoHealthyProviderError(GatewayError):
    """所有 Provider 均不健康（连续失败超过阈值，处于冷却期）。"""
