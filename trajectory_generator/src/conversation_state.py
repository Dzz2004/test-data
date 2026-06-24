"""
ConversationState - 跨轮对话状态追踪

追踪：conversation history、已确认约束/事实、上一轮 agent 输出。
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ConversationState:
    history: list[dict]        = field(default_factory=list)
    established_facts: dict    = field(default_factory=dict)
    last_agent_response: str   = ""

    def add_turn(self, user_message: str, agent_response: str) -> None:
        self.history.append({"user": user_message, "agent": agent_response})
        self.last_agent_response = agent_response

    def update_fact(self, key: str, value: str) -> None:
        self.established_facts[key] = value

    def get_context_summary(self, max_turns: int = 3) -> str:
        lines = []
        if self.established_facts:
            facts = "; ".join(f"{k}={v}" for k, v in self.established_facts.items())
            lines.append(f"[已确认信息] {facts}")
        recent = self.history[-max_turns:]
        for i, turn in enumerate(recent, start=max(1, len(self.history) - max_turns + 1)):
            lines.append(f"[第{i}轮] 用户: {turn['user'][:80]}")
            lines.append(f"       Agent: {turn['agent'][:120]}")
        return "\n".join(lines)

    def to_messages(self) -> list[dict]:
        msgs = []
        for turn in self.history:
            msgs.append({"role": "user",      "content": turn["user"]})
            msgs.append({"role": "assistant", "content": turn["agent"]})
        return msgs
