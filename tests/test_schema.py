"""Step A: 验证新 Schema 数据结构。"""
import pytest
from dataclasses import asdict


# ── 导入 ───────────────────────────────────────────────────────────────────────
def _import():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "trajectory_generator"))
    from src.schema import (
        ArcTurn, Blueprint, ConversationTurn, MultiTurnTrajectory,
        VALID_TRIGGERS,
    )
    return ArcTurn, Blueprint, ConversationTurn, MultiTurnTrajectory, VALID_TRIGGERS


# ── ArcTurn ────────────────────────────────────────────────────────────────────

class TestArcTurn:
    def test_fields(self):
        ArcTurn, *_ = _import()
        arc = ArcTurn(turn=1, trigger="initial_request", description="用户发起请求")
        assert arc.turn == 1
        assert arc.trigger == "initial_request"
        assert arc.description == "用户发起请求"

    def test_valid_triggers(self):
        _, _, _, _, VALID_TRIGGERS = _import()
        assert "initial_request"   in VALID_TRIGGERS
        assert "constraint_update" in VALID_TRIGGERS
        assert "clarification"     in VALID_TRIGGERS
        assert "plan_revision"     in VALID_TRIGGERS
        assert "pushback"          in VALID_TRIGGERS

    def test_to_dict(self):
        ArcTurn, *_ = _import()
        d = asdict(ArcTurn(turn=2, trigger="constraint_update", description="改约束"))
        assert set(d.keys()) == {"turn", "trigger", "description"}


# ── Blueprint ──────────────────────────────────────────────────────────────────

class TestBlueprint:
    def _make(self):
        ArcTurn, Blueprint, *_ = _import()
        return Blueprint(
            task_id="task_001",
            domain="code_development",
            task_type="mock-interview",
            user_id="senior-backend-job-hopping",
            task_description="为资深后端工程师规划面试准备",
            initial_user_query="帮我规划两个月的面试准备计划",
            interaction_style="偏好强烈型",
            expected_skills=["系统设计", "行为面试"],
            goal="用户拿到一份调整后的面试计划",
            conversation_arc=[
                ArcTurn(1, "initial_request",   "用户发起请求"),
                ArcTurn(2, "constraint_update", "时间改为8h/周"),
            ],
        )

    def test_fields(self):
        bp = self._make()
        assert bp.task_id == "task_001"
        assert len(bp.conversation_arc) == 2
        assert bp.conversation_arc[0].trigger == "initial_request"

    def test_arc_starts_with_initial_request(self):
        bp = self._make()
        assert bp.conversation_arc[0].trigger == "initial_request"

    def test_arc_min_length(self):
        ArcTurn, Blueprint, *_ = _import()
        with pytest.raises((ValueError, AssertionError)):
            Blueprint(
                task_id="x", domain="x", task_type="x", user_id="x",
                task_description="x", initial_user_query="x",
                interaction_style="x", expected_skills=[],
                goal="x",
                conversation_arc=[],  # 空 arc 应该报错
            )

    def test_to_dict_serializable(self):
        import json
        bp = self._make()
        d = bp.to_dict()
        json.dumps(d, ensure_ascii=False)  # 不应抛出异常
        assert "conversation_arc" in d
        assert isinstance(d["conversation_arc"], list)


# ── ConversationTurn ───────────────────────────────────────────────────────────

class TestConversationTurn:
    def test_fields(self):
        _, _, ConversationTurn, *_ = _import()
        turn = ConversationTurn(
            turn_id=1,
            trigger="initial_request",
            user_message="帮我规划面试",
            processing_nodes=[{"node_type": "skill_call", "name": "need_analysis"}],
            agent_response="好的，根据你的情况...",
        )
        assert turn.turn_id == 1
        assert len(turn.processing_nodes) == 1
        assert turn.agent_response.startswith("好的")

    def test_to_dict(self):
        _, _, ConversationTurn, *_ = _import()
        turn = ConversationTurn(
            turn_id=2, trigger="constraint_update",
            user_message="我时间只有8小时", processing_nodes=[],
            agent_response="已调整计划",
        )
        d = turn.to_dict()
        assert d["turn_id"] == 2
        assert "processing_nodes" in d
        assert "agent_response" in d


# ── MultiTurnTrajectory ────────────────────────────────────────────────────────

class TestMultiTurnTrajectory:
    def _make(self):
        ArcTurn, Blueprint, ConversationTurn, MultiTurnTrajectory, _ = _import()
        bp = Blueprint(
            task_id="t1", domain="code_development", task_type="mock-interview",
            user_id="u1", task_description="desc", initial_user_query="query",
            interaction_style="信息充分型", expected_skills=[],
            goal="goal",
            conversation_arc=[ArcTurn(1, "initial_request", "初始请求")],
        )
        turns = [
            ConversationTurn(1, "initial_request", "帮我规划", [], "好的"),
        ]
        return MultiTurnTrajectory(
            trajectory_id="traj_001",
            domain="code_development",
            template_used="llm_generated",
            user_profile={"currentRole": "P7"},
            task=bp,
            turns=turns,
        )

    def test_fields(self):
        traj = self._make()
        assert traj.trajectory_id == "traj_001"
        assert len(traj.turns) == 1
        assert traj.evaluation is None

    def test_to_dict_json_serializable(self):
        import json
        traj = self._make()
        d = traj.to_dict()
        s = json.dumps(d, ensure_ascii=False)
        assert "turns" in d
        assert "task" in d
        assert len(d["turns"]) == 1

    def test_turn_count_matches_arc(self):
        traj = self._make()
        assert len(traj.turns) == len(traj.task.conversation_arc)
