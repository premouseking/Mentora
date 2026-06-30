"""Agent 运行时异常。"""


class AgentRuntimeError(Exception):
    """Agent 运行时基础异常。"""


class MaxIterationsError(AgentRuntimeError):
    """tool-loop 达到迭代上限。"""


class ContextBudgetExceeded(AgentRuntimeError):
    """上下文超过当前 token 预算，且尚未接入压缩策略。"""
