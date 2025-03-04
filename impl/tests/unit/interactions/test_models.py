import json
import uuid

import pytest

from nora_lib.impl.interactions.models import (
    CostDetail,
    LangChainRun,
    LLMCost,
    LLMTokenBreakdown,
    ServiceCost,
)


@pytest.fixture
def step_cost_event_json():
    # Event 4319806 from istore
    return """
        {
          "env": "production",
          "details": [
            {
              "detail_type": "llm_token_breakdown",
              "prompt_tokens": 8896,
              "completion_tokens": 49
            },
            {
              "model_name": "gpt-4-turbo-2024-04-09",
              "detail_type": "llm_cost",
              "token_count": 8945
            },
            {
              "detail_type": "llm_token_breakdown",
              "prompt_tokens": 9054,
              "completion_tokens": 34
            },
            {
              "model_name": "gpt-4-turbo-2024-04-09",
              "detail_type": "llm_cost",
              "token_count": 9088
            },
            {
              "run_id": "4916026d-555b-4631-9d69-751b25695d4d",
              "run_name": "corpus_qa",
              "trace_id": "4916026d-555b-4631-9d69-751b25695d4d",
              "session_id": "None",
              "detail_type": "langchain_run",
              "session_name": ""
            },
            {
              "run_id": "73e914ea-2fc3-474e-93a0-0bab49a426a6",
              "run_name": "LangGraph",
              "trace_id": "73e914ea-2fc3-474e-93a0-0bab49a426a6",
              "session_id": "None",
              "detail_type": "langchain_run",
              "session_name": ""
            }
          ],
          "git_sha": "not_set",
          "task_id": null,
          "tool_name": "Handler",
          "description": "Langgraph step",
          "dollar_cost": 0.18199,
          "tool_call_id": null,
          "service_provider": "Langgraph"
        }
    """


def test_step_cost_deserialization(step_cost_event_json):
    svc_cost = ServiceCost.model_validate_json(step_cost_event_json)
    assert svc_cost.tool_name == "Handler"
    assert svc_cost.description == "Langgraph step"
    assert abs(svc_cost.dollar_cost - 0.18199) < 1e-6
    assert svc_cost.service_provider == "Langgraph"

    assert svc_cost.git_sha == "not_set"
    assert svc_cost.task_id is None
    assert svc_cost.tool_call_id is None
    assert len(svc_cost.details) == 6

    assert isinstance(svc_cost.details[0], LLMTokenBreakdown)
    assert svc_cost.details[0].prompt_tokens == 8896
    assert svc_cost.details[0].completion_tokens == 49

    assert isinstance(svc_cost.details[1], LLMCost)
    assert svc_cost.details[1].model_name == "gpt-4-turbo-2024-04-09"
    assert svc_cost.details[1].token_count == 8945

    assert isinstance(svc_cost.details[2], LLMTokenBreakdown)
    assert svc_cost.details[2].prompt_tokens == 9054
    assert svc_cost.details[2].completion_tokens == 34

    assert isinstance(svc_cost.details[3], LLMCost)
    assert svc_cost.details[3].model_name == "gpt-4-turbo-2024-04-09"
    assert svc_cost.details[3].token_count == 9088

    assert isinstance(svc_cost.details[4], LangChainRun)
    assert svc_cost.details[4].run_id == uuid.UUID(
        "4916026d-555b-4631-9d69-751b25695d4d"
    )
    assert svc_cost.details[4].run_name == "corpus_qa"
    assert svc_cost.details[4].trace_id == uuid.UUID(
        "4916026d-555b-4631-9d69-751b25695d4d"
    )
    assert svc_cost.details[4].session_id is None
    assert svc_cost.details[4].session_name == ""

    assert isinstance(svc_cost.details[5], LangChainRun)
    assert svc_cost.details[5].run_id == uuid.UUID(
        "73e914ea-2fc3-474e-93a0-0bab49a426a6"
    )
    assert svc_cost.details[5].run_name == "LangGraph"
    assert svc_cost.details[5].trace_id == uuid.UUID(
        "73e914ea-2fc3-474e-93a0-0bab49a426a6"
    )
    assert svc_cost.details[5].session_id is None
    assert svc_cost.details[5].session_name == ""

    # Make sure it works for dict deserialization as well
    assert ServiceCost.model_validate(json.loads(step_cost_event_json)) == svc_cost


def test_step_cost_legacy_deserialization(step_cost_event_json):
    # If detail_type is missing (as is the case for legacy blobs), we should
    # fall back to an empty CostDetail rather than crashing
    d = json.loads(step_cost_event_json)
    for detail in d["details"]:
        del detail["detail_type"]

    svc_cost = ServiceCost.model_validate(d)
    for detail in svc_cost.details:
        assert type(detail) == CostDetail


def test_step_cost_serialization(step_cost_event_json):
    svc_cost = ServiceCost.model_validate_json(step_cost_event_json)
    assert svc_cost == ServiceCost.model_validate_json(svc_cost.model_dump_json())
