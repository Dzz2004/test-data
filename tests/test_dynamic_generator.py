"""Step G3: Dynamic Generator — 动态规划-评估-执行循环测试。

验证新版 generate_multi_turn_trajectory 的动态节点选择机制，
不依赖 LLM（use_llm=False 模式）。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "trajectory_generator"))

import pytest
from src.schema import ArcTurn, Blueprint, MultiTurnTrajectory
from src.planner import plan_multi_turn
from src.generator import generate_multi_turn_trajectory, MAX_NODES_PER_TURN


def _load_domain():
    from src.domain import load_domain
    base = Path(__file__).parent.parent
    return load_domain(
        base / "trajectory_generator/domain/code_development",
        base / "personas",
    )


def _make_blueprint(task_type="mock-interview", arc=None):
    if arc is None:
        arc = [
            ArcTurn(1, "initial_request",   "用户发起面试规划请求"),
            ArcTurn(2, "constraint_update",  "用户将每周时间从15h改为8h"),
            ArcTurn(3, "clarification",      "用户追问系统设计练习方式"),
        ]
    return Blueprint(
        task_id="t_dyn_1", domain="code_development",
        task_type=task_type, user_id="senior-backend-job-hopping",
        task_description="为资深后端工程师规划面试准备",
        initial_user_query="帮我规划两个月的面试准备计划",
        interaction_style="偏好强烈型",
        expected_skills=["系统设计", "行为面试"],
        goal="用户拿到一份调整后的面试计划",
        conversation_arc=arc,
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


def _make_plan(domain, task_type="mock-interview", arc=None):
    bp      = _make_blueprint(task_type, arc)
    profile = _make_profile()
    return plan_multi_turn(domain, bp, profile, use_llm=False)


class TestDynamicGeneratorStructure:
    """结构完整性测试：动态版应产出与固定版相同的外层结构。"""

    def test_returns_multi_turn_trajectory(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        assert isinstance(traj, MultiTurnTrajectory)

    def test_template_used_reflects_dynamic_mode(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        assert "dynamic" in traj.template_used

    def test_turns_count_matches_arc(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        assert len(traj.turns) == 3

    def test_first_turn_user_message_is_initial_query(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        assert traj.turns[0].user_message == plan["blueprint"].initial_user_query

    def test_each_turn_has_agent_response(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            assert turn.agent_response, f"Turn {turn.turn_id} has empty agent_response"

    def test_each_turn_has_processing_nodes(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            assert len(turn.processing_nodes) >= 1, \
                f"Turn {turn.turn_id} has no processing_nodes"

    def test_nodes_do_not_exceed_max_per_turn(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            assert len(turn.processing_nodes) <= MAX_NODES_PER_TURN, \
                f"Turn {turn.turn_id} exceeds MAX_NODES_PER_TURN: {len(turn.processing_nodes)}"

    def test_serializable_to_dict(self):
        import json
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        d      = traj.to_dict()
        json.dumps(d, ensure_ascii=False)  # should not raise


class TestDynamicPlannerIntegration:
    """验证动态规划器与生成器的集成行为。"""

    def test_tool_nodes_have_structured_input_and_output(self):
        """v2 tool_call 应有 input/output 字段。"""
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                if node.get("node_type") == "tool_call":
                    assert "input"  in node, f"tool_call missing input: {node}"
                    assert "output" in node, f"tool_call missing output: {node}"

    def test_skill_nodes_have_structured_input(self):
        """v2 skill_call 的 input 应是结构化 dict（而非空）。"""
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                if node.get("node_type") == "skill_call":
                    assert isinstance(node.get("input"), dict), \
                        f"skill_call input is not dict: {node}"

    def test_no_duplicate_tool_calls_in_same_turn(self):
        """同一轮内不应调用同一个工具两次。"""
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            tool_ids = [n.get("tool_id") for n in turn.processing_nodes
                        if n.get("node_type") == "tool_call"]
            assert len(tool_ids) == len(set(tool_ids)), \
                f"Turn {turn.turn_id} has duplicate tool calls: {tool_ids}"

    def test_node_rationale_is_nonempty(self):
        """每个节点应有非空 rationale。"""
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                assert node.get("rationale"), \
                    f"Node in turn {turn.turn_id} has empty rationale: {node}"

    def test_state_updated_between_turns(self):
        """第2轮应能读到第1轮的状态（用 ConversationState 跨轮传递）。"""
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        # 至少有2轮
        assert len(traj.turns) >= 2
        # 第2轮的 user_message 不等于第1轮（说明 followup 是新生成的，不是复制）
        assert traj.turns[1].user_message != traj.turns[0].user_message

    def test_different_task_types_produce_different_first_nodes(self):
        """不同任务类型的第一轮第一个节点应不同（体现动态选择）。"""
        domain   = _load_domain()
        arc_2    = [ArcTurn(1, "initial_request", "初始请求")]
        plan_mi  = _make_plan(domain, "mock-interview",
                              [ArcTurn(1, "initial_request", "面试规划请求")])
        plan_lp  = _make_plan(domain, "learning-plan",
                              [ArcTurn(1, "initial_request", "学习路径请求")])

        traj_mi = generate_multi_turn_trajectory(plan_mi, domain, use_llm=False)
        traj_lp = generate_multi_turn_trajectory(plan_lp, domain, use_llm=False)

        # 两条轨迹的节点序列不应完全相同
        nodes_mi = [n.get("name") for n in traj_mi.turns[0].processing_nodes]
        nodes_lp = [n.get("name") for n in traj_lp.turns[0].processing_nodes]
        # 至少有一处不同
        assert nodes_mi != nodes_lp or len(nodes_mi) != len(nodes_lp)

    def test_constraint_update_turn_contains_revision_skill(self):
        """constraint_update 轮应至少包含一个 plan_revision/feasibility_check 节点。"""
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        turn2  = traj.turns[1]  # trigger = constraint_update
        assert turn2.trigger == "constraint_update"
        skill_ids = [n.get("skill_id") or n.get("name", "") for n in turn2.processing_nodes]
        revision_skills = {"feasibility_check", "plan_revision", "learning_path_planning"}
        assert any(s in revision_skills for s in skill_ids), \
            f"constraint_update turn missing revision skill, got: {skill_ids}"


class TestPlanningTrace:
    """验证 planning_trace 在节点中正确存储。"""

    def test_each_node_has_planning_trace(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                assert "planning_trace" in node, \
                    f"Node {node.get('name')} missing planning_trace"

    def test_planning_trace_is_list(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                assert isinstance(node["planning_trace"], list)
                assert len(node["planning_trace"]) >= 1

    def test_planning_trace_entry_has_required_keys(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                for entry in node["planning_trace"]:
                    for key in ("attempt", "plan", "eval", "accepted"):
                        assert key in entry, \
                            f"planning_trace entry missing key '{key}': {entry}"

    def test_planning_trace_plan_has_required_keys(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                for entry in node["planning_trace"]:
                    p = entry["plan"]
                    for key in ("node_type", "node_id", "inputs", "rationale"):
                        assert key in p, \
                            f"planning_trace.plan missing key '{key}': {p}"

    def test_planning_trace_eval_has_required_keys(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                for entry in node["planning_trace"]:
                    ev = entry["eval"]
                    for key in ("pass", "rationale", "suggestions"):
                        assert key in ev, \
                            f"planning_trace.eval missing key '{key}': {ev}"

    def test_planning_trace_attempt_increments(self):
        """attempt 字段从 1 开始且单调递增。"""
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                attempts = [e["attempt"] for e in node["planning_trace"]]
                assert attempts[0] == 1
                assert attempts == list(range(1, len(attempts) + 1))

    def test_last_trace_entry_is_accepted(self):
        """最终被执行的规划条目 accepted=True。"""
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                last_entry = node["planning_trace"][-1]
                assert last_entry["accepted"] is True, \
                    f"Last planning_trace entry should be accepted: {last_entry}"

    def test_planning_trace_plan_matches_node(self):
        """trace 里记录的 node_id 应与节点实际执行的一致。"""
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                executed_id = node.get("skill_id") or node.get("tool_id") or node.get("name")
                last_plan   = node["planning_trace"][-1]["plan"]
                assert last_plan["node_id"] == executed_id, \
                    f"planning_trace node_id {last_plan['node_id']} != executed {executed_id}"

    def test_planning_trace_serializable(self):
        """planning_trace 必须可以 JSON 序列化。"""
        import json
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=False)
        d      = traj.to_dict()
        json.dumps(d, ensure_ascii=False)  # should not raise

    def test_existing_backfilled_files_have_planning_trace(self):
        """已回填的旧数据文件中每个节点都有 planning_trace。"""
        import json
        from pathlib import Path
        individual_dir = Path(__file__).parent.parent / "trajectory_generator/output_2/individual"
        for fpath in sorted(individual_dir.glob("*.json")):
            data = json.loads(fpath.read_text(encoding="utf-8"))
            for turn in data.get("turns", []):
                for node in turn.get("processing_nodes", []):
                    assert "planning_trace" in node, \
                        f"{fpath.name}: node missing planning_trace: {node.get('name')}"
                    trace = node["planning_trace"]
                    assert isinstance(trace, list) and len(trace) >= 1
                    for entry in trace:
                        assert "attempt" in entry and "plan" in entry and "eval" in entry


@pytest.mark.llm
class TestDynamicGeneratorLLM:

    def test_skill_outputs_are_structured_dicts(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=True)
        for turn in traj.turns:
            for node in turn.processing_nodes:
                if node.get("node_type") == "skill_call":
                    assert isinstance(node.get("output"), dict), \
                        f"skill_call output should be dict, got {type(node.get('output'))}"

    def test_agent_response_is_substantial(self):
        domain = _load_domain()
        plan   = _make_plan(domain)
        traj   = generate_multi_turn_trajectory(plan, domain, use_llm=True)
        for turn in traj.turns:
            assert len(turn.agent_response) > 50, \
                f"Turn {turn.turn_id} agent_response too short"
