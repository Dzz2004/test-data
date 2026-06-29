"""
ConversationState - 跨轮对话状态追踪

追踪：conversation history、已确认约束/事实、上一轮 agent 输出、
      当前轮节点级状态（供 node_planner 使用）。
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ConversationState:
    history: list[dict]               = field(default_factory=list)
    established_facts: dict           = field(default_factory=dict)
    last_agent_response: str          = ""

    # ── 节点级状态（每轮内动态更新，供 node_planner 读取）──────────────────
    last_node_output: dict            = field(default_factory=dict)
    last_node_type: str               = ""
    current_turn_used_tools: list     = field(default_factory=list)

    # ── 轮次级方法 ────────────────────────────────────────────────────────────

    def add_turn(self, user_message: str, agent_response: str) -> None:
        self.history.append({"user": user_message, "agent": agent_response})
        self.last_agent_response = agent_response

    def update_fact(self, key: str, value: str) -> None:
        self.established_facts[key] = value

    def reset_turn_tools(self) -> None:
        """每轮开始时调用，清空本轮已使用工具记录。"""
        self.current_turn_used_tools = []

    # ── 节点级方法 ────────────────────────────────────────────────────────────

    def add_node(self, node: dict) -> None:
        """节点执行完成后立即调用，更新节点级状态。"""
        self.last_node_type   = node.get("node_type", "")
        self.last_node_output = node.get("output", {})
        if node.get("node_type") == "tool_call":
            tool_id = node.get("tool_id") or node.get("name", "")
            if tool_id and tool_id not in self.current_turn_used_tools:
                self.current_turn_used_tools.append(tool_id)

    # ── 规划上下文（node_planner 专用）───────────────────────────────────────

    def get_planning_context(self) -> dict:
        """
        返回结构化规划上下文，比 get_context_summary() 更精确。
        node_planner 用此方法提取相关事实，而非文本截断。
        """
        return {
            "confirmed_facts":         dict(self.established_facts),
            "last_node_type":          self.last_node_type,
            "last_node_output":        dict(self.last_node_output),
            "current_turn_used_tools": list(self.current_turn_used_tools),
            "turn_count":              len(self.history),
            "last_agent_response":     self.last_agent_response[:200] if self.last_agent_response else "",
        }

    # ── 对话历史摘要（generator 内部用）─────────────────────────────────────

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
