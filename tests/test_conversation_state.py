"""Step E: ConversationState — 跨轮状态追踪。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "trajectory_generator"))

from src.conversation_state import ConversationState


class TestConversationState:

    def test_initial_state_empty(self):
        state = ConversationState()
        assert state.history == []
        assert state.established_facts == {}
        assert state.last_agent_response == ""

    def test_add_turn_appends_history(self):
        state = ConversationState()
        state.add_turn(user_message="帮我规划", agent_response="好的，我来分析")
        assert len(state.history) == 1
        assert state.history[0]["user"] == "帮我规划"
        assert state.history[0]["agent"] == "好的，我来分析"

    def test_last_agent_response_updated(self):
        state = ConversationState()
        state.add_turn("msg1", "response1")
        state.add_turn("msg2", "response2")
        assert state.last_agent_response == "response2"

    def test_update_fact(self):
        state = ConversationState()
        state.update_fact("time_budget", "每周15小时")
        state.update_fact("target_role", "后端架构师")
        assert state.established_facts["time_budget"] == "每周15小时"
        assert state.established_facts["target_role"] == "后端架构师"

    def test_update_fact_overwrites(self):
        state = ConversationState()
        state.update_fact("time_budget", "每周15小时")
        state.update_fact("time_budget", "每周8小时")  # 用户更新了约束
        assert state.established_facts["time_budget"] == "每周8小时"

    def test_get_context_summary_includes_history(self):
        state = ConversationState()
        state.add_turn("请帮我规划面试", "我建议你分三个阶段准备")
        summary = state.get_context_summary(max_turns=3)
        assert "请帮我规划面试" in summary
        assert "我建议你分三个阶段准备" in summary

    def test_get_context_summary_max_turns(self):
        state = ConversationState()
        for i in range(5):
            state.add_turn(f"用户消息{i}", f"agent回复{i}")
        summary = state.get_context_summary(max_turns=2)
        # 只包含最后 2 轮
        assert "用户消息4" in summary
        assert "用户消息3" in summary
        assert "用户消息0" not in summary

    def test_facts_included_in_summary(self):
        state = ConversationState()
        state.update_fact("time_budget", "每周8小时")
        summary = state.get_context_summary()
        assert "每周8小时" in summary

    def test_to_messages_format(self):
        """to_messages() 返回 OpenAI-style messages list。"""
        state = ConversationState()
        state.add_turn("你好", "你好，我来帮你")
        msgs = state.to_messages()
        assert any(m["role"] == "user"      and "你好" in m["content"] for m in msgs)
        assert any(m["role"] == "assistant" and "你来帮你" in m["content"] or
                   m["role"] == "assistant" and "我来帮你" in m["content"] for m in msgs)
