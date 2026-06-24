"""
Multi-turn trajectory data structures.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

VALID_TRIGGERS = {
    "initial_request",   # 用户发起初始请求
    "constraint_update", # 用户修改约束（时间、预算、偏好等）
    "clarification",     # 用户追问某个具体点
    "plan_revision",     # 用户要求重新规划
    "pushback",          # 用户质疑 agent 的建议
}


@dataclass
class ArcTurn:
    turn: int
    trigger: str
    description: str


@dataclass
class Blueprint:
    task_id: str
    domain: str
    task_type: str
    user_id: str
    task_description: str
    initial_user_query: str
    interaction_style: str
    expected_skills: list[str]
    goal: str
    conversation_arc: list[ArcTurn]

    def __post_init__(self):
        if not self.conversation_arc:
            raise ValueError("conversation_arc must have at least one turn")
        if self.conversation_arc[0].trigger != "initial_request":
            raise ValueError("conversation_arc must start with trigger='initial_request'")

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class ConversationTurn:
    turn_id: int
    trigger: str
    user_message: str
    processing_nodes: list[dict]
    agent_response: str

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "trigger": self.trigger,
            "user_message": self.user_message,
            "processing_nodes": self.processing_nodes,
            "agent_response": self.agent_response,
        }


@dataclass
class MultiTurnTrajectory:
    trajectory_id: str
    domain: str
    template_used: str
    user_profile: dict
    task: Blueprint
    turns: list[ConversationTurn]
    evaluation: dict[str, Any] | None = field(default=None)

    def to_dict(self) -> dict:
        return {
            "trajectory_id": self.trajectory_id,
            "domain": self.domain,
            "template_used": self.template_used,
            "user_profile": self.user_profile,
            "task": self.task.to_dict(),
            "turns": [t.to_dict() for t in self.turns],
            "evaluation": self.evaluation,
        }
