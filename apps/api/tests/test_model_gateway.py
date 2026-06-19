"""
模型网关契约测试：路由、结构化校验、重试与 Fallback。

约束：
- 全部使用 FakeProvider，不需要任何外部凭证或网络，可在 CI 离线运行。

@see docs/project-management/stage-01-backlog.md P1-LWJ-01/02
"""

import pytest
from pydantic import BaseModel

from mentora.model_gateway.contracts import (
    AttemptStatus,
    ModelMessage,
    ModelRequest,
    QualityTier,
    Role,
    ToolCall,
    ToolSpec,
)
from mentora.model_gateway.contracts import StreamEventType
from mentora.model_gateway.exceptions import ProviderError, StructuredOutputError
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.providers.base import ProviderResponse, ProviderStreamChunk
from mentora.model_gateway.registry import ProviderRegistry

FAKE = "mentora.model_gateway.providers.fake.FakeProvider"


class _Shape(BaseModel):
    message: str


def _gateway(config: dict) -> ModelGateway:
    return ModelGateway(registry=ProviderRegistry(config=config))


def _request(**kwargs) -> ModelRequest:
    defaults = dict(
        task_type="test",
        messages=[ModelMessage(role=Role.USER, content="hi")],
        quality_tier=QualityTier.BALANCED,
    )
    defaults.update(kwargs)
    return ModelRequest(**defaults)


def test_text_completion_records_requested_and_actual_model():
    config = {
        "providers": {"p": {"class": FAKE, "options": {"script": ["你好"]}}},
        "routing": {"balanced": [{"provider": "p", "model": "m-balanced"}]},
    }
    response = _gateway(config).complete(_request())

    assert response.text == "你好"
    assert response.requested_model == "m-balanced"
    assert response.actual_model == "m-balanced"
    assert response.provider == "p"
    assert len(response.attempts) == 1
    assert response.attempts[0].status == AttemptStatus.SUCCEEDED


def test_structured_output_validated_before_return():
    config = {
        "providers": {
            "p": {"class": FAKE, "options": {"script": ['{"message": "ok"}']}}
        },
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
    }
    response = _gateway(config).complete(_request(structured_output_schema=_Shape))

    assert isinstance(response.structured, _Shape)
    assert response.structured.message == "ok"


def test_structured_retries_then_succeeds():
    config = {
        "providers": {
            "p": {"class": FAKE, "options": {"script": ["不是 JSON", '{"message": "ok"}']}}
        },
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
        "max_retries_per_attempt": 1,
    }
    response = _gateway(config).complete(_request(structured_output_schema=_Shape))

    assert response.structured.message == "ok"
    assert response.attempts[0].status == AttemptStatus.INVALID_OUTPUT
    assert response.attempts[1].status == AttemptStatus.SUCCEEDED


def test_structured_all_invalid_raises():
    config = {
        "providers": {
            "p": {"class": FAKE, "options": {"script": ["nope", "still nope"]}}
        },
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
        "max_retries_per_attempt": 1,
    }
    with pytest.raises(StructuredOutputError):
        _gateway(config).complete(_request(structured_output_schema=_Shape))


def test_fallback_to_secondary_on_non_transient_error():
    config = {
        "providers": {
            "primary": {
                "class": FAKE,
                "options": {"script": [ProviderError("boom", transient=False)]},
            },
            "secondary": {"class": FAKE, "options": {"script": ["来自备选"]}},
        },
        "routing": {
            "balanced": [
                {"provider": "primary", "model": "m-primary"},
                {"provider": "secondary", "model": "m-secondary"},
            ]
        },
    }
    response = _gateway(config).complete(_request())

    assert response.text == "来自备选"
    assert response.requested_model == "m-primary"
    assert response.actual_model == "m-secondary"
    assert response.attempts[0].status == AttemptStatus.PROVIDER_ERROR
    assert response.attempts[-1].status == AttemptStatus.SUCCEEDED


def test_transient_error_retried_within_same_candidate():
    config = {
        "providers": {
            "p": {
                "class": FAKE,
                "options": {
                    "script": [
                        ProviderError("临时抖动", transient=True),
                        ProviderResponse(text="恢复", model="m", finish_reason="stop"),
                    ]
                },
            }
        },
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
        "max_retries_per_attempt": 1,
    }
    response = _gateway(config).complete(_request())

    assert response.text == "恢复"
    assert len(response.attempts) == 2
    assert response.attempts[0].status == AttemptStatus.PROVIDER_ERROR
    assert response.attempts[1].status == AttemptStatus.SUCCEEDED


def test_all_candidates_fail_raises_provider_error():
    config = {
        "providers": {
            "p": {
                "class": FAKE,
                "options": {"script": [ProviderError("挂了", transient=False)]},
            }
        },
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
    }
    with pytest.raises(ProviderError):
        _gateway(config).complete(_request())


def _drain(events):
    deltas, done = [], None
    for ev in events:
        if ev.type == StreamEventType.DELTA:
            deltas.append(ev.text)
        elif ev.type == StreamEventType.DONE:
            done = ev.response
    return deltas, done


def test_stream_emits_deltas_then_done():
    config = {
        "providers": {"p": {"class": FAKE, "options": {"script": ["你好世界"]}}},
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
    }
    deltas, done = _drain(_gateway(config).stream(_request()))

    assert "".join(deltas) == "你好世界"
    assert len(deltas) == 4  # 逐字推送
    assert done is not None
    assert done.text == "你好世界"
    assert done.actual_model == "m"
    assert done.attempts[-1].status == AttemptStatus.SUCCEEDED


def test_stream_fallback_before_first_delta():
    config = {
        "providers": {
            "primary": {
                "class": FAKE,
                "options": {"script": [ProviderError("早挂", transient=False)]},
            },
            "secondary": {"class": FAKE, "options": {"script": ["备选流"]}},
        },
        "routing": {
            "balanced": [
                {"provider": "primary", "model": "m1"},
                {"provider": "secondary", "model": "m2"},
            ]
        },
    }
    deltas, done = _drain(_gateway(config).stream(_request()))

    assert "".join(deltas) == "备选流"
    assert done.actual_model == "m2"
    assert done.requested_model == "m1"


def test_stream_no_fallback_after_first_delta():
    # 首片已产出后再断流：不得切换候选，直接抛错。
    mid_break = [ProviderStreamChunk(delta="开"), ProviderError("断了", transient=False)]
    config = {
        "providers": {
            "primary": {"class": FAKE, "options": {"script": [mid_break]}},
            "secondary": {"class": FAKE, "options": {"script": ["不该用到"]}},
        },
        "routing": {
            "balanced": [
                {"provider": "primary", "model": "m1"},
                {"provider": "secondary", "model": "m2"},
            ]
        },
    }
    collected = []
    with pytest.raises(ProviderError):
        for ev in _gateway(config).stream(_request()):
            if ev.type == StreamEventType.DELTA:
                collected.append(ev.text)

    assert collected == ["开"]


def test_stream_structured_validated_at_end():
    config = {
        "providers": {
            "p": {"class": FAKE, "options": {"script": ['{"message": "ok"}']}}
        },
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
    }
    _, done = _drain(
        _gateway(config).stream(_request(structured_output_schema=_Shape))
    )

    assert done.structured.message == "ok"


def test_stream_structured_invalid_raises_after_stream():
    config = {
        "providers": {"p": {"class": FAKE, "options": {"script": ["不是 JSON"]}}},
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
    }
    with pytest.raises(StructuredOutputError):
        _drain(_gateway(config).stream(_request(structured_output_schema=_Shape)))


def test_tool_calls_forwarded_in_response():
    config = {
        "providers": {
            "p": {
                "class": FAKE,
                "options": {
                    "script": [
                        ProviderResponse(
                            text="",
                            model="m",
                            finish_reason="tool_calls",
                            tool_calls=[
                                ToolCall(
                                    id="call_1",
                                    name="search",
                                    arguments='{"query": "test"}',
                                )
                            ],
                        )
                    ]
                },
            }
        },
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
    }
    tools = (
        ToolSpec(
            name="search",
            description="检索",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        ),
    )
    response = _gateway(config).complete(_request(tools=tools))

    assert response.finish_reason == "tool_calls"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "search"
    assert response.tool_calls[0].arguments == '{"query": "test"}'


def test_assistant_tool_message_roundtrip():
    config = {
        "providers": {"p": {"class": FAKE, "options": {"script": ["收到工具结果"]}}},
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
    }
    request = _request(
        messages=[
            ModelMessage(
                role=Role.ASSISTANT,
                content="",
                tool_calls=(
                    ToolCall(id="call_1", name="search", arguments='{"query": "x"}'),
                ),
            ),
            ModelMessage(
                role=Role.TOOL,
                content='{"results": []}',
                tool_call_id="call_1",
                name="search",
            ),
            ModelMessage(role=Role.USER, content="继续"),
        ]
    )
    response = _gateway(config).complete(request)
    assert response.text == "收到工具结果"


def test_stream_tool_calls_in_done_response():
    config = {
        "providers": {
            "p": {
                "class": FAKE,
                "options": {
                    "script": [
                        ProviderResponse(
                            text="",
                            model="m",
                            finish_reason="tool_calls",
                            tool_calls=[
                                ToolCall(
                                    id="call_1",
                                    name="search",
                                    arguments='{"query": "x"}',
                                )
                            ],
                        )
                    ]
                },
            }
        },
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
    }
    tools = (
        ToolSpec(
            name="search",
            description="检索",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        ),
    )
    _, done = _drain(_gateway(config).stream(_request(tools=tools)))

    assert done is not None
    assert done.finish_reason == "tool_calls"
    assert len(done.tool_calls) == 1
    assert done.tool_calls[0].name == "search"
