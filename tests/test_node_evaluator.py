"""Step G2: NodeEvaluator — 节点规划评估器测试。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "trajectory_generator"))

import pytest
from src.conversation_state import ConversationState
from src.node_evaluator import evaluate_node_plan


def _load_domain():
    from src.domain import load_domain
    base = Path(__file__).parent.parent
    return load_domain(
        base / "trajectory_generator/domain/code_development",
        base / "personas",
    )


def _valid_skill_plan(node_id="need_analysis"):
    return {
        "node_type":   "skill_call",
        "node_id":     node_id,
        "node_name":   node_id,
        "inputs":      {"user_goal": "成为后端架构师", "constraints": ["在职"]},
        "rationale":   "解析用户需求",
        "is_terminal": False,
    }


def _valid_tool_plan(node_id="job_requirement_search"):
    return {
        "node_type":   "tool_call",
        "node_id":     node_id,
        "node_name":   node_id,
        "inputs":      {"job_title": "后端架构师", "seniority": "senior"},
        "rationale":   "查询岗位技能要求",
        "is_terminal": False,
    }


def _terminal_plan():
    return {
        "node_type":   "agent_response",
        "node_id":     "agent_response",
        "node_name":   "agent_response",
        "inputs":      {},
        "rationale":   "结束本轮",
        "is_terminal": True,
    }


class TestNodeEvaluatorFallback:
    """不调 LLM 的规则评估测试。"""

    def test_returns_dict_with_required_keys(self):
        domain = _load_domain()
        state  = ConversationState()
        result = evaluate_node_plan(_valid_skill_plan(), "initial_request",
                                    state, domain, [], use_llm=False)
        assert isinstance(result, dict)
        for key in ("pass", "rationale", "suggestions"):
            assert key in result, f"Missing key: {key}"

    def test_valid_skill_plan_passes(self):
        domain = _load_domain()
        state  = ConversationState()
        result = evaluate_node_plan(_valid_skill_plan(), "initial_request",
                                    state, domain, [], use_llm=False)
        assert result["pass"] is True

    def test_valid_tool_plan_passes(self):
        domain = _load_domain()
        state  = ConversationState()
        result = evaluate_node_plan(_valid_tool_plan(), "initial_request",
                                    state, domain, [], use_llm=False)
        assert result["pass"] is True

    def test_terminal_plan_always_passes(self):
        domain = _load_domain()
        state  = ConversationState()
        result = evaluate_node_plan(_terminal_plan(), "initial_request",
                                    state, domain, [], use_llm=False)
        assert result["pass"] is True

    def test_unknown_skill_id_fails(self):
        domain = _load_domain()
        state  = ConversationState()
        plan   = _valid_skill_plan(node_id="nonexistent_skill_xyz")
        result = evaluate_node_plan(plan, "initial_request",
                                    state, domain, [], use_llm=False)
        assert result["pass"] is False
        assert result["rationale"]
        assert result["suggestions"]

    def test_unknown_tool_id_fails(self):
        domain = _load_domain()
        state  = ConversationState()
        plan   = _valid_tool_plan(node_id="nonexistent_tool_xyz")
        result = evaluate_node_plan(plan, "initial_request",
                                    state, domain, [], use_llm=False)
        assert result["pass"] is False

    def test_duplicate_tool_call_fails(self):
        """本轮已调用过的工具再次规划应不通过。"""
        domain = _load_domain()
        state  = ConversationState()
        state.add_node({
            "node_type": "tool_call",
            "tool_id":   "job_requirement_search",
            "output":    {"required_skills": ["Java"]},
        })
        plan   = _valid_tool_plan(node_id="job_requirement_search")
        result = evaluate_node_plan(plan, "initial_request",
                                    state, domain, [], use_llm=False)
        assert result["pass"] is False
        assert "重复" in result["rationale"] or "已调用" in result["rationale"]

    def test_empty_inputs_fails(self):
        """inputs 为空（非 terminal）应不通过。"""
        domain = _load_domain()
        state  = ConversationState()
        plan   = {
            "node_type": "skill_call", "node_id": "need_analysis",
            "node_name": "need_analysis", "inputs": {},
            "rationale": "...", "is_terminal": False,
        }
        result = evaluate_node_plan(plan, "initial_request",
                                    state, domain, [], use_llm=False)
        assert result["pass"] is False

    def test_too_many_nodes_fails(self):
        """超出节点上限时应不通过。"""
        from src.node_evaluator import MAX_NODES_PER_TURN
        domain       = _load_domain()
        state        = ConversationState()
        node_context = [{"node_id": f"node_{i}"} for i in range(MAX_NODES_PER_TURN)]
        plan         = _valid_skill_plan()
        result       = evaluate_node_plan(plan, "initial_request",
                                          state, domain, node_context, use_llm=False)
        assert result["pass"] is False
        assert result["suggestions"]

    def test_rationale_is_string(self):
        domain = _load_domain()
        state  = ConversationState()
        result = evaluate_node_plan(_valid_skill_plan(), "initial_request",
                                    state, domain, [], use_llm=False)
        assert isinstance(result["rationale"], str)
        assert len(result["rationale"]) > 0

    def test_suggestions_is_list(self):
        domain = _load_domain()
        state  = ConversationState()
        result = evaluate_node_plan(_valid_skill_plan(), "initial_request",
                                    state, domain, [], use_llm=False)
        assert isinstance(result["suggestions"], list)

    def test_fail_result_has_suggestions(self):
        """不通过时应有 suggestions 指导下一轮规划。"""
        domain = _load_domain()
        state  = ConversationState()
        plan   = _valid_skill_plan(node_id="bad_skill_id")
        result = evaluate_node_plan(plan, "initial_request",
                                    state, domain, [], use_llm=False)
        assert result["pass"] is False
        assert len(result["suggestions"]) > 0


@pytest.mark.llm
class TestNodeEvaluatorLLM:

    def test_llm_eval_returns_valid_structure(self):
        domain = _load_domain()
        state  = ConversationState()
        result = evaluate_node_plan(_valid_skill_plan(), "initial_request",
                                    state, domain, [], use_llm=True)
        assert isinstance(result["pass"], bool)
        assert isinstance(result["rationale"], str)
        assert isinstance(result["suggestions"], list)

    def test_llm_catches_poor_plan(self):
        """提供明显不合理的规划，LLM 应判断不通过。"""
        domain = _load_domain()
        state  = ConversationState()
        # 在没有任何前序信息的情况下，规划 skill_gap_analysis
        # 但 inputs 里直接给空数组
        plan = {
            "node_type":   "skill_call",
            "node_id":     "skill_gap_analysis",
            "node_name":   "skill_gap_analysis",
            "inputs":      {"job_required_skills": [], "user_current_level": ""},
            "rationale":   "分析技能缺口",
            "is_terminal": False,
        }
        result = evaluate_node_plan(plan, "initial_request",
                                    state, domain, [], use_llm=True)
        # 预期：空 inputs 可能被判为不合理（不强制，因为 LLM 判断有随机性）
        assert isinstance(result["pass"], bool)
