import json
import uuid

import pytest

from nora_lib.impl.interactions.models import (
    CostDetail,
    LangChainRun,
    LLMCost,
    LLMTokenBreakdown,
    ServiceCost,
    unify_llm_cost_details,
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


def test_unify_llm_cost_details():
    # Test case 1: Successfully unifying LLMCost with matching LLMTokenBreakdown
    details = [
        LLMCost(model_name="gpt-4", token_count=100),
        LLMTokenBreakdown(prompt_tokens=70, completion_tokens=30),
        LangChainRun(run_id=uuid.uuid4(), run_name="test-run"),
    ]

    unified = unify_llm_cost_details(details)
    assert len(unified) == 2  # LLMCost (with breakdown embedded) + LangChainRun
    assert isinstance(unified[0], LLMCost)
    assert unified[0].model_name == "gpt-4"
    assert unified[0].token_count == 100
    assert unified[0].token_breakdown is not None
    assert unified[0].token_breakdown.prompt_tokens == 70
    assert unified[0].token_breakdown.completion_tokens == 30
    assert isinstance(unified[1], LangChainRun)

    # Test case 2: Multiple matching pairs
    details = [
        LLMCost(model_name="gpt-4", token_count=100),
        LLMTokenBreakdown(prompt_tokens=70, completion_tokens=30),
        LLMCost(model_name="claude-3", token_count=200),
        LLMTokenBreakdown(prompt_tokens=150, completion_tokens=50),
        LangChainRun(run_id=uuid.uuid4(), run_name="test-run"),
    ]

    unified = unify_llm_cost_details(details)
    assert len(unified) == 3  # 2 LLMCosts (with breakdowns) + LangChainRun

    # Test case 3: No token breakdowns
    details = [
        LLMCost(model_name="gpt-4", token_count=100),
        LangChainRun(run_id=uuid.uuid4(), run_name="test-run"),
    ]

    unified = unify_llm_cost_details(details)
    assert len(unified) == 2  # Should return original list
    assert unified[0].token_breakdown is None
    
    # Test case 3.5: Already unified list
    breakdown = LLMTokenBreakdown(prompt_tokens=70, completion_tokens=30)
    details = [
        LLMCost(model_name="gpt-4", token_count=100, token_breakdown=breakdown),
        LangChainRun(run_id=uuid.uuid4(), run_name="test-run"),
    ]
    
    unified = unify_llm_cost_details(details)
    assert len(unified) == 2  # Should return original list
    assert unified[0].token_breakdown is not None
    assert unified[0].token_breakdown.prompt_tokens == 70

    # Test case 4: Error - mismatched counts
    details = [
        LLMCost(model_name="gpt-4", token_count=100),
        LLMCost(model_name="claude-3", token_count=200),
        LLMTokenBreakdown(prompt_tokens=70, completion_tokens=30),
    ]

    with pytest.raises(ValueError):
        unify_llm_cost_details(details)

    # Test case 5: Error - token count doesn't match
    details = [
        LLMCost(model_name="gpt-4", token_count=100),
        LLMTokenBreakdown(prompt_tokens=60, completion_tokens=30),  # Total 90, not 100
    ]

    with pytest.raises(ValueError):
        unify_llm_cost_details(details)

    # Test case 6: Error - ambiguous matching (multiple breakdowns with same total token count)
    details = [
        LLMCost(model_name="gpt-4", token_count=100),
        LLMTokenBreakdown(prompt_tokens=70, completion_tokens=30),  # Total 100
        LLMTokenBreakdown(prompt_tokens=60, completion_tokens=40),  # Also total 100
    ]

    with pytest.raises(ValueError):
        unify_llm_cost_details(details)


def test_service_cost_with_unified_llm_costs(step_cost_event_json):
    # Create a ServiceCost from the test fixture JSON
    svc_cost = ServiceCost.model_validate_json(step_cost_event_json)

    # The original ServiceCost should have separate LLMCost and LLMTokenBreakdown details
    cost_details = [d for d in svc_cost.details if isinstance(d, LLMCost)]
    breakdown_details = [
        d for d in svc_cost.details if isinstance(d, LLMTokenBreakdown)
    ]
    langchain_details = [d for d in svc_cost.details if isinstance(d, LangChainRun)]

    assert len(cost_details) == 2
    assert len(breakdown_details) == 2
    assert len(langchain_details) == 2

    # Create a unified ServiceCost
    unified_cost = svc_cost.with_unified_llm_costs()

    # Check that the non-details fields were preserved
    assert unified_cost.dollar_cost == svc_cost.dollar_cost
    assert unified_cost.service_provider == svc_cost.service_provider
    assert unified_cost.description == svc_cost.description
    assert unified_cost.tool_name == svc_cost.tool_name

    # The unified ServiceCost should have LLMCost objects with token_breakdown fields set
    new_cost_details = [d for d in unified_cost.details if isinstance(d, LLMCost)]
    new_breakdown_details = [
        d for d in unified_cost.details if isinstance(d, LLMTokenBreakdown)
    ]
    new_langchain_details = [
        d for d in unified_cost.details if isinstance(d, LangChainRun)
    ]

    assert len(new_cost_details) == 2
    assert len(new_breakdown_details) == 0  # No standalone breakdowns anymore
    assert len(new_langchain_details) == 2  # LangChain details preserved

    # Verify that the token breakdowns were incorporated into the LLMCost objects
    for cost in new_cost_details:
        assert cost.token_breakdown is not None
        assert (
            cost.token_breakdown.prompt_tokens + cost.token_breakdown.completion_tokens
            == cost.token_count
        )
            
    # Test case: calling with_unified_llm_costs on an already unified ServiceCost
    # The method should return a new instance without modifying the details
    already_unified_cost = unified_cost.with_unified_llm_costs()
    
    # Verify it's a new instance but has the same data
    assert already_unified_cost is not unified_cost
    assert already_unified_cost.dollar_cost == unified_cost.dollar_cost
    assert already_unified_cost.service_provider == unified_cost.service_provider
    
    # Check that all the details are preserved
    unified_details = [d for d in already_unified_cost.details]
    assert len(unified_details) == 4  # 2 LLMCosts and 2 LangChainRuns
    
    # Check that the LLMCost token breakdowns are still there
    unified_cost_details = [d for d in already_unified_cost.details if isinstance(d, LLMCost)]
    for cost in unified_cost_details:
        assert cost.token_breakdown is not None
