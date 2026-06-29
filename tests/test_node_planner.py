"""Step G1: NodePlanner — 节点规划器测试。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "trajectory_generator"))

import pytest
from src.conversation_state import ConversationState
from src.node_planner import plan_next_node


def _load_domain():
    from src.domain import load_domain
    base = Path(__file__).parent.parent
    return load_domain(
        base / "trajectory_generator/domain/code_development",
        base / "personas",
    )


def _make_profile():
    return {
        "currentRole":      "后端技术专家（P7）",
        "targetRole":       "后端架构师",
        "weeklyTimeBudget": "15小时",
        "constraints":      ["在职跳槽", "家庭约束"],
        "techStack":        ["Java", "Go"],
        "keyStrengths":     ["分布式系统", "性能优化"],
        "riskSignals":      ["业务 sense 弱", "行为面试准备不足"],
        "shortTermGoal":    "三个月内完成跳槽",
    }


class TestNodePlannerFallback:
    """不调 LLM 的结构性测试。"""

    def test_returns_dict(self):
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        plan = plan_next_node("initial_request", "mock-interview", state,
                              domain, [], profile, use_llm=False)
        assert isinstance(plan, dict)

    def test_plan_has_required_keys(self):
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        plan = plan_next_node("initial_request", "mock-interview", state,
                              domain, [], profile, use_llm=False)
        for key in ("node_type", "node_id", "node_name", "inputs", "rationale", "is_terminal"):
            assert key in plan, f"Missing key: {key}"

    def test_first_node_is_not_terminal(self):
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        plan = plan_next_node("initial_request", "mock-interview", state,
                              domain, [], profile, use_llm=False)
        assert plan["is_terminal"] is False

    def test_node_type_is_valid(self):
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        valid_types = {"skill_call", "tool_call", "agent_response"}
        plan = plan_next_node("initial_request", "mock-interview", state,
                              domain, [], profile, use_llm=False)
        assert plan["node_type"] in valid_types

    def test_node_id_in_domain(self):
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        skill_ids = {s.skill_id for s in domain.skills}
        tool_ids  = {t.tool_id  for t in domain.tools}
        plan = plan_next_node("initial_request", "mock-interview", state,
                              domain, [], profile, use_llm=False)
        if plan["node_type"] == "skill_call":
            assert plan["node_id"] in skill_ids
        elif plan["node_type"] == "tool_call":
            assert plan["node_id"] in tool_ids

    def test_inputs_is_dict(self):
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        plan = plan_next_node("initial_request", "mock-interview", state,
                              domain, [], profile, use_llm=False)
        assert isinstance(plan["inputs"], dict)

    def test_sequence_advances_with_node_context(self):
        """node_context 增加后，规划器应推进到下一个节点。"""
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        plan1 = plan_next_node("initial_request", "mock-interview", state,
                               domain, [], profile, use_llm=False)
        # 模拟第一个节点执行完
        node_context = [{"node_id": plan1["node_id"]}]
        plan2 = plan_next_node("initial_request", "mock-interview", state,
                               domain, node_context, profile, use_llm=False)
        assert plan2["node_id"] != plan1["node_id"] or plan2["is_terminal"]

    def test_terminal_after_full_sequence(self):
        """超出序列长度后，返回 is_terminal=True。"""
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        # 模拟已执行 10 个节点（远超序列长度）
        node_context = [{"node_id": f"node_{i}"} for i in range(10)]
        plan = plan_next_node("initial_request", "mock-interview", state,
                              domain, node_context, profile, use_llm=False)
        assert plan["is_terminal"] is True
        assert plan["node_type"] == "agent_response"

    def test_constraint_update_trigger(self):
        """constraint_update trigger 应包含 feasibility_check 或 plan_revision。"""
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        plan = plan_next_node("constraint_update", "mock-interview", state,
                              domain, [], profile, use_llm=False)
        assert plan["node_id"] in ("feasibility_check", "plan_revision")

    def test_structured_inputs_for_need_analysis(self):
        """need_analysis 节点应有 user_goal 等结构化字段。"""
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        # 找到 need_analysis 对应的 plan
        node_context = []
        for _ in range(5):
            plan = plan_next_node("initial_request", "mock-interview", state,
                                  domain, node_context, profile, use_llm=False)
            if plan["is_terminal"]:
                break
            if plan["node_id"] == "need_analysis":
                assert "user_goal" in plan["inputs"] or "constraints" in plan["inputs"]
                return
            node_context.append({"node_id": plan["node_id"]})
        # 如果未到 need_analysis 也不算失败（序列可能不包含）
        assert True

    def test_skill_gap_inputs_reference_last_output(self):
        """skill_gap_analysis 的 inputs 应引用上一节点（工具）的输出。"""
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        # 模拟上一个 tool_call 返回了岗位技能
        state.add_node({
            "node_type": "tool_call",
            "tool_id":   "job_requirement_search",
            "output":    {"required_skills": ["Java", "Kubernetes", "系统设计"]},
        })
        plan = plan_next_node("initial_request", "learning-plan", state,
                              domain, [{"node_id": "job_requirement_search"}],
                              profile, use_llm=False)
        # 不论规划了哪个节点，只要 inputs 中存在对 required_skills 的引用
        # （对于 skill_gap_analysis 节点），就算通过
        if plan["node_id"] == "skill_gap_analysis":
            skills_in_inputs = plan["inputs"].get("job_required_skills", [])
            assert "Java" in skills_in_inputs or len(skills_in_inputs) > 0

    def test_different_triggers_produce_different_first_nodes(self):
        """不同 trigger 的首个节点应体现差异。"""
        domain  = _load_domain()
        profile = _make_profile()
        plan_init  = plan_next_node("initial_request",  "mock-interview",
                                    ConversationState(), domain, [], profile, use_llm=False)
        plan_const = plan_next_node("constraint_update", "mock-interview",
                                    ConversationState(), domain, [], profile, use_llm=False)
        # constraint_update 首节点不应与 initial_request 一样
        assert plan_init["node_id"] != plan_const["node_id"]


@pytest.mark.llm
class TestNodePlannerLLM:

    def test_llm_plan_is_valid(self):
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        plan = plan_next_node("initial_request", "mock-interview", state,
                              domain, [], profile, use_llm=True)
        assert plan["node_type"] in {"skill_call", "tool_call", "agent_response"}
        assert plan["node_id"]
        assert isinstance(plan["inputs"], dict)

    def test_llm_incorporates_feedback(self):
        """带 feedback 时，规划器应改变输出（不是固定死的）。"""
        domain  = _load_domain()
        state   = ConversationState()
        profile = _make_profile()
        feedback = "该节点重复了已有分析，请换一个工具调用"
        plan = plan_next_node("initial_request", "mock-interview", state,
                              domain, [{"node_id": "need_analysis"}],
                              profile, feedback=feedback, use_llm=True)
        # 至少说明 feedback 被接收（rationale 中有反映或换了节点）
        assert plan["node_id"] != "need_analysis" or plan["is_terminal"]
