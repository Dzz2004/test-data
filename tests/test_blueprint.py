"""Step C: Blueprint Generator — 生成含 conversation_arc 的任务蓝图。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "trajectory_generator"))

import pytest
from src.schema import ArcTurn, Blueprint, VALID_TRIGGERS


def _load_domain():
    from src.domain import load_domain
    base = Path(__file__).parent.parent
    return load_domain(
        base / "trajectory_generator/domain/code_development",
        base / "personas",
    )


def _load_persona(name="senior-backend-job-hopping"):
    import json
    p = Path(__file__).parent.parent / "personas" / f"{name}.json"
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ── 不调 LLM 的结构性测试 ──────────────────────────────────────────────────────

class TestBlueprintStructure:
    """不依赖 LLM，只验证蓝图数据结构的规约。"""

    def test_arc_first_turn_is_initial_request(self, sample_arc):
        assert sample_arc[0].trigger == "initial_request"

    def test_arc_turns_numbered_sequentially(self, sample_arc):
        for i, t in enumerate(sample_arc, start=1):
            assert t.turn == i

    def test_all_triggers_valid(self, sample_arc):
        for t in sample_arc:
            assert t.trigger in VALID_TRIGGERS

    def test_blueprint_rejects_empty_arc(self):
        with pytest.raises((ValueError, AssertionError)):
            Blueprint(
                task_id="x", domain="x", task_type="x", user_id="x",
                task_description="x", initial_user_query="x",
                interaction_style="x", expected_skills=[],
                goal="x", conversation_arc=[],
            )

    def test_blueprint_rejects_wrong_first_trigger(self):
        with pytest.raises((ValueError, AssertionError)):
            Blueprint(
                task_id="x", domain="x", task_type="x", user_id="x",
                task_description="x", initial_user_query="x",
                interaction_style="x", expected_skills=[],
                goal="x",
                conversation_arc=[ArcTurn(1, "constraint_update", "不该是第一轮")],
            )

    def test_blueprint_to_dict_contains_arc(self):
        bp = Blueprint(
            task_id="t1", domain="d", task_type="mock-interview", user_id="u",
            task_description="desc", initial_user_query="query",
            interaction_style="信息充分型", expected_skills=["系统设计"],
            goal="完成面试规划",
            conversation_arc=[
                ArcTurn(1, "initial_request",    "初始请求"),
                ArcTurn(2, "constraint_update",  "改时间"),
            ],
        )
        d = bp.to_dict()
        assert len(d["conversation_arc"]) == 2
        assert d["conversation_arc"][0]["trigger"] == "initial_request"


# ── 依赖 LLM 的生成测试（需要真实 API key）────────────────────────────────────

@pytest.mark.llm
class TestBlueprintGenerator:
    """需要 ANTHROPIC_API_KEY，用 pytest -m llm 单独运行。"""

    def test_generate_blueprint_returns_blueprint(self):
        from src.task_generator import generate_blueprint
        domain = _load_domain()
        persona = _load_persona("senior-backend-job-hopping")
        bp = generate_blueprint(domain, persona)

        assert isinstance(bp, Blueprint)
        assert bp.task_id
        assert bp.initial_user_query
        assert len(bp.conversation_arc) >= 2
        assert bp.conversation_arc[0].trigger == "initial_request"

    def test_arc_triggers_are_valid(self):
        from src.task_generator import generate_blueprint
        domain = _load_domain()
        persona = _load_persona("junior-frontend-graduate")
        bp = generate_blueprint(domain, persona)

        for arc_turn in bp.conversation_arc:
            assert arc_turn.trigger in VALID_TRIGGERS, \
                f"Invalid trigger: {arc_turn.trigger}"

    def test_arc_length_2_to_4(self):
        from src.task_generator import generate_blueprint
        domain = _load_domain()
        persona = _load_persona("career-switcher-to-backend")
        bp = generate_blueprint(domain, persona)

        assert 2 <= len(bp.conversation_arc) <= 4, \
            f"Arc length {len(bp.conversation_arc)} out of range [2,4]"

    def test_interaction_style_affects_arc(self):
        """偏好强烈型用户的 arc 应包含 constraint 或 pushback 类型轮次。"""
        from src.task_generator import generate_blueprint
        domain = _load_domain()
        persona = _load_persona("senior-backend-job-hopping")  # 偏好强烈型
        bp = generate_blueprint(domain, persona)

        non_initial = [t.trigger for t in bp.conversation_arc[1:]]
        assert any(t in ("constraint_update", "pushback", "plan_revision") for t in non_initial), \
            f"Expected constraint/pushback/revision in arc, got: {non_initial}"

    def test_goal_is_nonempty(self):
        from src.task_generator import generate_blueprint
        domain = _load_domain()
        persona = _load_persona("mid-level-fullstack-promotion")
        bp = generate_blueprint(domain, persona)

        assert bp.goal and len(bp.goal) > 5
