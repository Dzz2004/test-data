"""Step D: Multi-turn Planner — 按轮次分别规划节点序列。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "trajectory_generator"))

import pytest
from src.schema import ArcTurn, Blueprint


def _load_domain():
    from src.domain import load_domain
    base = Path(__file__).parent.parent
    return load_domain(
        base / "trajectory_generator/domain/code_development",
        base / "personas",
    )


def _make_blueprint(arc=None):
    if arc is None:
        arc = [
            ArcTurn(1, "initial_request",   "用户发起面试规划请求"),
            ArcTurn(2, "constraint_update",  "用户将每周时间从15h改为8h"),
            ArcTurn(3, "clarification",      "用户追问系统设计练习方式"),
        ]
    return Blueprint(
        task_id="t1", domain="code_development",
        task_type="mock-interview", user_id="senior-backend-job-hopping",
        task_description="为资深后端工程师规划面试准备",
        initial_user_query="帮我规划两个月的面试准备计划",
        interaction_style="偏好强烈型",
        expected_skills=["系统设计", "行为面试"],
        goal="用户拿到一份调整后的面试计划",
        conversation_arc=arc,
    )


def _make_profile():
    return {
        "currentRole": "后端技术专家（P7）",
        "targetRole": "后端架构师",
        "weeklyTimeBudget": "15小时",
        "constraints": ["在职跳槽", "家庭约束"],
    }


# ── 不调 LLM 的结构性测试 ──────────────────────────────────────────────────────

class TestMultiTurnPlanStructure:

    def test_plan_has_turns_key(self):
        from src.planner import plan_multi_turn
        domain = _load_domain()
        bp = _make_blueprint()
        plan = plan_multi_turn(domain, bp, _make_profile(), use_llm=False)
        assert "turns_plan" in plan

    def test_turns_count_matches_arc(self):
        from src.planner import plan_multi_turn
        domain = _load_domain()
        bp = _make_blueprint()
        plan = plan_multi_turn(domain, bp, _make_profile(), use_llm=False)
        assert len(plan["turns_plan"]) == len(bp.conversation_arc)

    def test_each_turn_has_required_keys(self):
        from src.planner import plan_multi_turn
        domain = _load_domain()
        bp = _make_blueprint()
        plan = plan_multi_turn(domain, bp, _make_profile(), use_llm=False)
        for turn_plan in plan["turns_plan"]:
            assert "turn_id"       in turn_plan
            assert "trigger"       in turn_plan
            assert "planned_nodes" in turn_plan
            assert isinstance(turn_plan["planned_nodes"], list)

    def test_each_turn_nodes_nonempty(self):
        from src.planner import plan_multi_turn
        domain = _load_domain()
        bp = _make_blueprint()
        plan = plan_multi_turn(domain, bp, _make_profile(), use_llm=False)
        for turn_plan in plan["turns_plan"]:
            assert len(turn_plan["planned_nodes"]) >= 1, \
                f"Turn {turn_plan['turn_id']} has no nodes"

    def test_node_types_are_valid(self):
        from src.planner import plan_multi_turn
        valid_types = {"skill_call", "tool_call", "agent_reasoning", "agent_response"}
        domain = _load_domain()
        bp = _make_blueprint()
        plan = plan_multi_turn(domain, bp, _make_profile(), use_llm=False)
        for turn_plan in plan["turns_plan"]:
            for node in turn_plan["planned_nodes"]:
                assert node["node_type"] in valid_types, \
                    f"Invalid node_type: {node['node_type']}"

    def test_each_turn_ends_with_agent_response(self):
        from src.planner import plan_multi_turn
        domain = _load_domain()
        bp = _make_blueprint()
        plan = plan_multi_turn(domain, bp, _make_profile(), use_llm=False)
        for turn_plan in plan["turns_plan"]:
            last_node = turn_plan["planned_nodes"][-1]
            assert last_node["node_type"] == "agent_response", \
                f"Turn {turn_plan['turn_id']} last node is {last_node['node_type']}, not agent_response"

    def test_first_turn_uses_domain_skills_or_tools(self):
        """第一轮应该包含至少一个 skill_call 或 tool_call。"""
        from src.planner import plan_multi_turn
        domain = _load_domain()
        bp = _make_blueprint()
        plan = plan_multi_turn(domain, bp, _make_profile(), use_llm=False)
        first_turn = plan["turns_plan"][0]
        non_response = [n for n in first_turn["planned_nodes"] if n["node_type"] != "agent_response"]
        assert len(non_response) >= 1

    def test_constraint_update_turn_includes_relevant_skill(self):
        """constraint_update 轮应包含 feasibility_check 或 plan_revision。"""
        from src.planner import plan_multi_turn
        domain = _load_domain()
        arc = [
            ArcTurn(1, "initial_request",   "初始请求"),
            ArcTurn(2, "constraint_update", "时间从15h改为8h"),
        ]
        bp = _make_blueprint(arc)
        plan = plan_multi_turn(domain, bp, _make_profile(), use_llm=False)
        turn2_nodes = plan["turns_plan"][1]["planned_nodes"]
        skill_ids = [n.get("skill_id") for n in turn2_nodes]
        assert any(s in ("feasibility_check", "plan_revision", "learning_path_planning")
                   for s in skill_ids), \
            f"constraint_update turn should handle replanning, got skills: {skill_ids}"


# ── 依赖 LLM 的测试 ────────────────────────────────────────────────────────────

@pytest.mark.llm
class TestMultiTurnPlannerLLM:

    def test_llm_plan_structure(self):
        from src.planner import plan_multi_turn
        domain = _load_domain()
        bp = _make_blueprint()
        plan = plan_multi_turn(domain, bp, _make_profile(), use_llm=True)
        assert len(plan["turns_plan"]) == 3
        for tp in plan["turns_plan"]:
            assert len(tp["planned_nodes"]) >= 2

    def test_no_cross_turn_duplicate_tools(self):
        """同一工具不应在相邻两轮都出现（冗余调用）。"""
        from src.planner import plan_multi_turn
        domain = _load_domain()
        bp = _make_blueprint()
        plan = plan_multi_turn(domain, bp, _make_profile(), use_llm=True)
        turns = plan["turns_plan"]
        for i in range(1, len(turns)):
            prev_tools = {n.get("tool_id") for n in turns[i-1]["planned_nodes"] if n.get("tool_id")}
            curr_tools = {n.get("tool_id") for n in turns[i]["planned_nodes"]   if n.get("tool_id")}
            overlap = prev_tools & curr_tools
            assert not overlap, f"Tool(s) {overlap} repeated in consecutive turns {i} and {i+1}"
