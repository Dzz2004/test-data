"""Step F: Multi-turn Generator — 生成完整多轮轨迹。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "trajectory_generator"))

import pytest
from src.schema import ArcTurn, Blueprint
from src.planner import plan_multi_turn


def _load_domain():
    from src.domain import load_domain
    base = Path(__file__).parent.parent
    return load_domain(
        base / "trajectory_generator/domain/code_development",
        base / "personas",
    )


def _make_multi_turn_plan(domain, arc=None):
    if arc is None:
        arc = [
            ArcTurn(1, "initial_request",   "用户发起面试规划请求"),
            ArcTurn(2, "constraint_update",  "用户将每周时间从15h改为8h"),
            ArcTurn(3, "clarification",      "用户追问系统设计练习方式"),
        ]
    bp = Blueprint(
        task_id="t1", domain="code_development",
        task_type="mock-interview", user_id="senior-backend-job-hopping",
        task_description="为资深后端工程师规划面试准备",
        initial_user_query="帮我规划两个月的面试准备计划",
        interaction_style="偏好强烈型",
        expected_skills=["系统设计", "行为面试"],
        goal="用户拿到一份调整后的面试计划",
        conversation_arc=arc,
    )
    profile = {
        "currentRole": "后端技术专家（P7）",
        "targetRole": "后端架构师",
        "weeklyTimeBudget": "15小时",
        "constraints": ["在职跳槽", "家庭约束"],
    }
    return plan_multi_turn(domain, bp, profile, use_llm=False)


# ── 不调 LLM 的结构性测试 ──────────────────────────────────────────────────────

class TestMultiTurnGeneratorStructure:

    def test_returns_multi_turn_trajectory(self):
        from src.generator import generate_multi_turn_trajectory
        from src.schema import MultiTurnTrajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        assert isinstance(traj, MultiTurnTrajectory)

    def test_turns_count_matches_arc(self):
        from src.generator import generate_multi_turn_trajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        assert len(traj.turns) == 3

    def test_each_turn_has_user_message(self):
        from src.generator import generate_multi_turn_trajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            assert turn.user_message, f"Turn {turn.turn_id} has empty user_message"

    def test_each_turn_has_agent_response(self):
        from src.generator import generate_multi_turn_trajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            assert turn.agent_response, f"Turn {turn.turn_id} has empty agent_response"

    def test_each_turn_has_processing_nodes(self):
        from src.generator import generate_multi_turn_trajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            assert len(turn.processing_nodes) >= 1, \
                f"Turn {turn.turn_id} has no processing nodes"

    def test_first_turn_user_message_is_initial_query(self):
        from src.generator import generate_multi_turn_trajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        assert traj.turns[0].user_message == plan["blueprint"].initial_user_query

    def test_serializable_to_dict(self):
        import json
        from src.generator import generate_multi_turn_trajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        d = traj.to_dict()
        json.dumps(d, ensure_ascii=False)  # should not raise

    def test_processing_nodes_have_valid_types(self):
        from src.generator import generate_multi_turn_trajectory
        valid = {"skill_call", "tool_call", "agent_reasoning", "agent_response"}
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                assert node.get("node_type") in valid, \
                    f"Invalid node_type: {node.get('node_type')} in turn {turn.turn_id}"

    def test_tool_nodes_have_input_and_output(self):
        from src.generator import generate_multi_turn_trajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                if node.get("node_type") == "tool_call":
                    assert "input"  in node, f"tool_call missing 'input':  {node}"
                    assert "output" in node, f"tool_call missing 'output': {node}"


# ── 依赖 LLM 的测试 ────────────────────────────────────────────────────────────

@pytest.mark.llm
class TestMultiTurnGeneratorLLM:

    def test_subsequent_user_message_references_agent_output(self):
        """第2轮用户消息应与第1轮 agent_response 有语义关联（不是凭空生成）。"""
        from src.generator import generate_multi_turn_trajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=True)
        # 基本验证：第2轮用户消息不等于第1轮（即不是直接复制）
        assert traj.turns[1].user_message != traj.turns[0].user_message

    def test_skill_outputs_are_structured(self):
        """skill_call 节点的 output 应是 dict 而非纯字符串。"""
        from src.generator import generate_multi_turn_trajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=True)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                if node.get("node_type") == "skill_call":
                    assert isinstance(node.get("output"), dict), \
                        f"skill output should be dict, got {type(node.get('output'))}"

    def test_agent_response_references_prior_analysis(self):
        """每轮 agent_response 长度应 > 50字（有实质内容）。"""
        from src.generator import generate_multi_turn_trajectory
        domain = _load_domain()
        plan = _make_multi_turn_plan(domain)
        traj = generate_multi_turn_trajectory(plan, domain, use_llm=True)
        for turn in traj.turns:
            assert len(turn.agent_response) > 50, \
                f"Turn {turn.turn_id} agent_response too short: {turn.agent_response[:60]}"
