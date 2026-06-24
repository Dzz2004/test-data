"""
Blueprint Generator - 基于用户画像生成含对话弧线的任务蓝图
"""
from __future__ import annotations

import random
from typing import Any
from .domain import Domain
from .llm_client import chat, chat_json
from .schema import ArcTurn, Blueprint, VALID_TRIGGERS


# ── 交互风格推断 ───────────────────────────────────────────────────────────────

def infer_interaction_style(profile: dict) -> str:
    constraints   = profile.get("constraints", [])
    risk_signals  = profile.get("riskSignals", [])

    if not profile.get("shortTermGoal") or len(profile.get("shortTermGoal", "")) < 20:
        return "信息缺失型"
    for signal in risk_signals:
        if any(w in signal for w in ["焦虑", "反复", "变更", "切换"]):
            return "反复修改型"
    if len(profile.get("workPreferences", [])) >= 4 or len(constraints) >= 4:
        return "偏好强烈型"
    return "信息充分型"


# ── 主入口 ─────────────────────────────────────────────────────────────────────

def generate_blueprint(domain: Domain, user_data: dict) -> Blueprint:
    """
    Generate a multi-turn task blueprint from a user persona.
    Returns a Blueprint with conversation_arc describing the full dialogue plan.
    """
    profile           = user_data["profile"]
    meta              = user_data.get("_meta", {})
    persona_id        = meta.get("personaId", "unknown")
    interaction_style = infer_interaction_style(profile)

    test_scenarios = meta.get("testScenarios", domain.spec.task_types)
    task_type      = random.choice(test_scenarios) if test_scenarios else random.choice(domain.spec.task_types)

    task_type_labels = {
        "learning-plan":         "学习路径规划",
        "learning_path_planning":"学习路径规划",
        "career-roadmap":        "职业路线规划",
        "career_roadmap":        "职业路线规划",
        "mock-interview":        "面试准备",
        "mock_interview_prep":   "面试准备",
        "coding-assessment":     "技能评估",
        "skill_gap_diagnosis":   "技能缺口诊断",
        "project_recommendation":"项目推荐",
        "tech_stack_selection":  "技术栈选择",
    }
    task_label = task_type_labels.get(task_type, task_type)

    # ── Step 1: 生成初始用户请求 ───────────────────────────────────────────────
    initial_query = _generate_initial_query(profile, task_label, interaction_style)

    # ── Step 2: 生成对话弧线 ───────────────────────────────────────────────────
    arc = _generate_conversation_arc(profile, task_label, interaction_style, initial_query)

    # ── Step 3: 生成任务目标 ───────────────────────────────────────────────────
    goal = _infer_goal(profile, task_label, arc)

    return Blueprint(
        task_id           = f"task_{persona_id}_{random.randint(1000, 9999)}",
        domain            = domain.spec.domain_id,
        task_type         = task_type,
        user_id           = persona_id,
        task_description  = f"为 {profile.get('currentRole', '用户')} 生成{task_label}",
        initial_user_query= initial_query,
        interaction_style = interaction_style,
        expected_skills   = meta.get("expectedSkills", []),
        goal              = goal,
        conversation_arc  = arc,
    )


# ── 内部生成函数 ───────────────────────────────────────────────────────────────

def _generate_initial_query(profile: dict, task_label: str, interaction_style: str) -> str:
    prompt = f"""基于以下用户画像，生成一个该用户会向职业规划 AI 助手提出的自然语言请求。

用户画像:
- 当前角色: {profile.get('currentRole', '')}
- 目标角色: {profile.get('targetRole', '')}
- 经验概述: {profile.get('experienceSummary', '')[:120]}
- 短期目标: {profile.get('shortTermGoal', '')}
- 约束条件: {', '.join(profile.get('constraints', [])[:3])}
- 每周时间: {profile.get('weeklyTimeBudget', '')}

任务类型: {task_label}
交互风格: {interaction_style}

交互风格说明:
- 信息充分型: 用户一次性提供较完整的背景、目标和约束（30-120字）
- 信息缺失型: 用户只说了一个模糊的方向，细节不足（15-40字）
- 偏好强烈型: 用户有明确偏好和限制条件（40-120字）
- 反复修改型: 用户初始请求正常，后续会修改需求

请直接输出用户会说的话（自然语言，不加引号或标记），语言与画像的 locale 一致。"""

    try:
        return chat([{"role": "user", "content": prompt}], temperature=0.8, max_tokens=200).strip().strip('"\'')
    except Exception:
        return f"请帮我制定{task_label}计划，我是{profile.get('currentRole', '开发工程师')}，目标是{profile.get('targetRole', '更高级职位')}。"


def _generate_conversation_arc(
    profile: dict,
    task_label: str,
    interaction_style: str,
    initial_query: str,
) -> list[ArcTurn]:
    """
    LLM 生成 2-4 轮对话弧线。第一轮固定为 initial_request，
    后续轮次根据交互风格选择合适的 trigger 类型。
    """
    style_hints = {
        "信息充分型": "用户信息充足，可能在第2轮追问某个具体细节（clarification）或要求调整（plan_revision）",
        "信息缺失型": "用户第1轮信息不足，agent 会追问，用户第2轮会补充信息（trigger: clarification，用户回答补充）",
        "偏好强烈型": "用户有强约束，第2轮可能修改约束（constraint_update）或质疑建议（pushback）",
        "反复修改型": "用户第2轮会修改时间/目标等约束（constraint_update），第3轮可能再次调整",
    }

    trigger_options = [t for t in VALID_TRIGGERS if t != "initial_request"]

    prompt = f"""你是一个对话设计师，需要为以下用户设计一段多轮对话的弧线（arc）。

用户画像:
- 当前角色: {profile.get('currentRole', '')}
- 目标角色: {profile.get('targetRole', '')}
- 短期目标: {profile.get('shortTermGoal', '')}
- 约束条件: {', '.join(profile.get('constraints', [])[:3])}
- 交互风格: {interaction_style}

任务类型: {task_label}
用户初始请求: {initial_query}

交互风格指导: {style_hints.get(interaction_style, '')}

可用的 trigger 类型（除第一轮外）:
- constraint_update: 用户修改约束（时间、预算、技术栈偏好等）
- clarification: 用户追问某个具体点，或回答 agent 的追问
- plan_revision: 用户要求重新规划或调整方向
- pushback: 用户质疑 agent 的建议，要求解释

请设计 2-4 轮对话弧线。规则：
1. 第一轮固定为 initial_request，描述用户发起的初始请求
2. 后续 1-3 轮，根据用户特征选择合适的 trigger
3. 每轮的 description 要具体，说明用户在这轮"会做什么"或"会说什么方向的话"
4. description 用中文，15-40字

返回 JSON 数组:
[
  {{"turn": 1, "trigger": "initial_request", "description": "..."}},
  {{"turn": 2, "trigger": "...", "description": "..."}},
  ...
]"""

    try:
        raw = chat_json([{"role": "user", "content": prompt}], temperature=0.7)
        return _parse_arc(raw, profile, interaction_style)
    except Exception:
        return _fallback_arc(interaction_style, profile)


def _parse_arc(raw: Any, profile: dict, interaction_style: str) -> list[ArcTurn]:
    """Parse and validate LLM arc output, fix issues if needed."""
    if not isinstance(raw, list):
        raw = raw.get("arc", raw.get("turns", [raw])) if isinstance(raw, dict) else []

    arc = []
    for i, item in enumerate(raw[:4], start=1):
        if not isinstance(item, dict):
            continue
        trigger = item.get("trigger", "")
        if trigger not in VALID_TRIGGERS:
            trigger = "clarification"
        desc = item.get("description", f"第{i}轮用户操作")
        arc.append(ArcTurn(turn=i, trigger=trigger, description=desc))

    # 修复第一轮必须是 initial_request
    if arc and arc[0].trigger != "initial_request":
        arc[0] = ArcTurn(turn=1, trigger="initial_request", description=arc[0].description)

    # 至少 2 轮
    if len(arc) < 2:
        fallback = _fallback_arc(interaction_style, profile)
        arc = arc + fallback[len(arc):]

    # 重新编号
    arc = [ArcTurn(turn=i+1, trigger=t.trigger, description=t.description) for i, t in enumerate(arc)]

    return arc


def _fallback_arc(interaction_style: str, profile: dict) -> list[ArcTurn]:
    """Deterministic fallback arc based on interaction style."""
    constraints = profile.get("constraints", [])
    constraint_desc = constraints[0] if constraints else "时间约束"

    arcs = {
        "信息充分型": [
            ArcTurn(1, "initial_request",  "用户提供完整背景发起请求"),
            ArcTurn(2, "clarification",    "用户追问某个具体执行步骤"),
        ],
        "信息缺失型": [
            ArcTurn(1, "initial_request",  "用户发出模糊请求"),
            ArcTurn(2, "clarification",    "用户回答 agent 追问，补充基础和目标"),
        ],
        "偏好强烈型": [
            ArcTurn(1, "initial_request",  "用户带有明确约束地发起请求"),
            ArcTurn(2, "constraint_update", f"用户补充或调整约束：{constraint_desc}"),
            ArcTurn(3, "pushback",          "用户质疑某项建议，要求解释"),
        ],
        "反复修改型": [
            ArcTurn(1, "initial_request",  "用户发起初始请求"),
            ArcTurn(2, "constraint_update", f"用户修改约束：{constraint_desc}"),
            ArcTurn(3, "plan_revision",     "用户要求根据新约束重新规划"),
        ],
    }
    return arcs.get(interaction_style, arcs["信息充分型"])


def _infer_goal(profile: dict, task_label: str, arc: list[ArcTurn]) -> str:
    target = profile.get("targetRole", "目标职位")
    short  = profile.get("shortTermGoal", "")
    n_turns = len(arc)
    return f"用户经过 {n_turns} 轮交互，最终获得一份针对{target}的{task_label}方案" + (f"，满足：{short[:40]}" if short else "")


# ── 向后兼容：保留旧接口 ───────────────────────────────────────────────────────

def generate_task(domain: Domain, user_data: dict) -> dict:
    """Deprecated: use generate_blueprint() instead."""
    bp = generate_blueprint(domain, user_data)
    return bp.to_dict()
