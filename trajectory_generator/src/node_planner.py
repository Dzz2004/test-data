"""
NodePlanner - 小模型规划器

在每个节点执行之前被调用，完成两件事：
  1. 消化上一个节点的输出，更新对当前状态的理解
  2. 决定下一个节点（类型 + ID）及其结构化输入

输出 plan dict：
{
    "node_type":   "skill_call" | "tool_call" | "agent_response",
    "node_id":     str,       # skill_id 或 tool_id，agent_response 时为 "agent_response"
    "node_name":   str,
    "inputs":      dict,      # 结构化输入（由规划器从状态中提取，而非通用摘要）
    "rationale":   str,       # 本轮规划的推理依据
    "is_terminal": bool,      # True → 本轮应生成 agent_response，结束节点循环
}
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .conversation_state import ConversationState
from .llm_client import chat_json

if TYPE_CHECKING:
    from .domain import Domain

# ── use_llm=False 时的静态 fallback 序列（按 trigger 分类）─────────────────────

_FALLBACK_SEQUENCES: dict[str, dict[str, list[dict]]] = {
    "initial_request": {
        "mock-interview": [
            {"node_type": "skill_call", "node_id": "need_analysis"},
            {"node_type": "tool_call",  "node_id": "job_requirement_search"},
            {"node_type": "skill_call", "node_id": "level_diagnosis"},
            {"node_type": "skill_call", "node_id": "interview_prep_planning"},
        ],
        "learning-plan": [
            {"node_type": "skill_call", "node_id": "need_analysis"},
            {"node_type": "skill_call", "node_id": "level_diagnosis"},
            {"node_type": "tool_call",  "node_id": "knowledge_graph_query"},
            {"node_type": "skill_call", "node_id": "skill_gap_analysis"},
            {"node_type": "skill_call", "node_id": "learning_path_planning"},
        ],
        "career-roadmap": [
            {"node_type": "skill_call", "node_id": "need_analysis"},
            {"node_type": "tool_call",  "node_id": "job_requirement_search"},
            {"node_type": "skill_call", "node_id": "career_path_analysis"},
            {"node_type": "skill_call", "node_id": "skill_gap_analysis"},
        ],
        "_default": [
            {"node_type": "skill_call", "node_id": "need_analysis"},
            {"node_type": "skill_call", "node_id": "level_diagnosis"},
            {"node_type": "skill_call", "node_id": "skill_gap_analysis"},
        ],
    },
    "constraint_update": {
        "_default": [
            {"node_type": "skill_call", "node_id": "feasibility_check"},
            {"node_type": "skill_call", "node_id": "plan_revision"},
            {"node_type": "skill_call", "node_id": "learning_path_planning"},
        ],
    },
    "clarification": {
        "_default": [
            {"node_type": "skill_call", "node_id": "need_analysis"},
            {"node_type": "skill_call", "node_id": "resource_recommendation"},
        ],
    },
    "plan_revision": {
        "_default": [
            {"node_type": "skill_call", "node_id": "plan_revision"},
            {"node_type": "skill_call", "node_id": "feasibility_check"},
        ],
    },
    "pushback": {
        "_default": [
            {"node_type": "skill_call", "node_id": "need_analysis"},
            {"node_type": "skill_call", "node_id": "career_path_analysis"},
        ],
    },
}


def _get_fallback_sequence(trigger: str, task_type: str) -> list[dict]:
    trigger_map  = _FALLBACK_SEQUENCES.get(trigger, _FALLBACK_SEQUENCES.get("clarification", {}))
    return trigger_map.get(task_type) or trigger_map.get("_default", [
        {"node_type": "skill_call", "node_id": "need_analysis"},
    ])


def _infer_structured_inputs(
    node_type: str,
    node_id: str,
    state: ConversationState,
    profile: dict,
) -> dict:
    """
    从规划上下文中提取该节点真正需要的结构化输入，
    而不是直接传递通用文本摘要。
    """
    ctx = state.get_planning_context()
    last_output = ctx["last_node_output"]

    if node_type == "skill_call":
        if node_id == "need_analysis":
            return {
                "user_goal":    profile.get("shortTermGoal", ""),
                "user_level":   profile.get("currentRole", ""),
                "constraints":  profile.get("constraints", [])[:3],
                "prior_facts":  ctx["confirmed_facts"],
            }
        if node_id == "level_diagnosis":
            return {
                "current_role":        profile.get("currentRole", ""),
                "experience_summary":  profile.get("experienceSummary", "")[:120],
                "key_strengths":       profile.get("keyStrengths", [])[:3],
                "risk_signals":        profile.get("riskSignals", [])[:2],
            }
        if node_id == "skill_gap_analysis":
            return {
                "job_required_skills": last_output.get("required_skills", [])
                                       or last_output.get("skills", []),
                "user_current_level":  profile.get("currentRole", ""),
                "tech_stack":          profile.get("techStack", []),
            }
        if node_id == "learning_path_planning":
            return {
                "skill_gaps":    last_output.get("skill_gaps", [])
                                 or last_output.get("gaps", []),
                "time_budget":   profile.get("weeklyTimeBudget", "")
                                 or ctx["confirmed_facts"].get("time_budget", ""),
                "target_role":   profile.get("targetRole", ""),
            }
        if node_id in ("feasibility_check", "plan_revision"):
            return {
                "current_plan":   last_output,
                "updated_constraint": ctx["confirmed_facts"],
                "time_budget":    ctx["confirmed_facts"].get("time_budget",
                                  profile.get("weeklyTimeBudget", "")),
            }
        if node_id == "interview_prep_planning":
            return {
                "target_role":         profile.get("targetRole", ""),
                "time_budget":         profile.get("weeklyTimeBudget", ""),
                "job_required_skills": last_output.get("required_skills", []),
                "risk_signals":        profile.get("riskSignals", [])[:3],
            }
        if node_id == "career_path_analysis":
            return {
                "current_role":  profile.get("currentRole", ""),
                "target_role":   profile.get("targetRole", ""),
                "target_industries": profile.get("targetIndustries", [])[:3],
                "risk_signals":  profile.get("riskSignals", [])[:2],
            }
        if node_id == "resource_recommendation":
            return {
                "skill_gaps":   last_output.get("skill_gaps", []),
                "preferences":  profile.get("learningPreferences", [])[:3],
                "constraints":  profile.get("constraints", [])[:2],
            }
        # 通用 fallback
        return {
            "context_summary": state.get_context_summary(2),
            "profile_role":    profile.get("currentRole", ""),
        }

    if node_type == "tool_call":
        if node_id == "job_requirement_search":
            return {
                "job_title":  profile.get("targetRole", "开发工程师"),
                "seniority":  _infer_seniority(profile),
                "region":     profile.get("locationRegion", ""),
            }
        if node_id == "knowledge_graph_query":
            tech = (profile.get("techStack") or [profile.get("currentRole", "Java")])[0]
            return {"target_skill": tech, "depth": 2}
        if node_id == "interview_question_search":
            return {
                "role":       profile.get("targetRole", ""),
                "category":   "system_design",
                "difficulty": "hard" if _infer_seniority(profile) == "senior" else "medium",
            }
        if node_id == "salary_benchmark_search":
            return {
                "role":      profile.get("targetRole", ""),
                "seniority": _infer_seniority(profile),
                "region":    profile.get("locationRegion", "北京"),
            }
        if node_id == "tech_trend_search":
            techs = profile.get("techStack", [profile.get("currentRole", "Java")])
            return {"technology": techs[0] if techs else "Java", "aspect": "demand"}
        if node_id == "course_resource_search":
            return {"skill_name": profile.get("targetRole", "开发"), "difficulty": "advanced"}
        if node_id == "project_repository_search":
            return {"tech_stack": profile.get("techStack", [])[:3], "difficulty": "intermediate"}
        return {"query": profile.get("shortTermGoal", "")}

    return {}


def _infer_seniority(profile: dict) -> str:
    role = profile.get("currentRole", "").lower()
    if any(w in role for w in ["应届", "毕业", "实习", "junior", "entry"]):
        return "junior"
    if any(w in role for w in ["专家", "架构", "senior", "staff", "p7", "p8"]):
        return "senior"
    return "mid"


# ── 主接口 ─────────────────────────────────────────────────────────────────────

def plan_next_node(
    trigger: str,
    task_type: str,
    state: ConversationState,
    domain: "Domain",
    node_context: list[dict],
    profile: dict,
    feedback: str = "",
    arc_description: str = "",
    use_llm: bool = True,
) -> dict:
    """
    规划下一个节点。
    - use_llm=False: 按静态序列 fallback，适合测试。
    - use_llm=True:  小模型动态规划，从用户需求视角决策。

    返回 plan dict，见模块 docstring。
    """
    if not use_llm:
        return _fallback_plan(trigger, task_type, state, domain, node_context, profile)

    return _llm_plan(trigger, task_type, state, domain, node_context, profile,
                     feedback, arc_description)


# ── fallback（无 LLM）─────────────────────────────────────────────────────────

def _fallback_plan(
    trigger: str, task_type: str,
    state: ConversationState, domain: "Domain",
    node_context: list[dict], profile: dict,
) -> dict:
    """按静态序列推进，index = 已执行节点数。"""
    seq    = _get_fallback_sequence(trigger, task_type)
    index  = len(node_context)

    if index >= len(seq):
        return {
            "node_type":   "agent_response",
            "node_id":     "agent_response",
            "node_name":   "agent_response",
            "inputs":      {},
            "rationale":   "已完成本轮所有分析节点，生成 agent 回复",
            "is_terminal": True,
        }

    step = seq[index]
    node_id   = step["node_id"]
    node_type = step["node_type"]

    return {
        "node_type":   node_type,
        "node_id":     node_id,
        "node_name":   node_id,
        "inputs":      _infer_structured_inputs(node_type, node_id, state, profile),
        "rationale":   f"[fallback] 执行第{index+1}步：{node_id}",
        "is_terminal": False,
    }


# ── LLM 规划 ──────────────────────────────────────────────────────────────────

def _llm_plan(
    trigger: str, task_type: str,
    state: ConversationState, domain: "Domain",
    node_context: list[dict], profile: dict,
    feedback: str,
    arc_description: str = "",
) -> dict:
    """小模型规划下一节点。失败时 fallback。"""
    valid_skills = {s.skill_id: s.name for s in domain.skills}
    valid_tools  = {t.tool_id:  t.name for t in domain.tools}

    ctx = state.get_planning_context()
    executed = [c.get("node_id", c.get("name", "")) for c in node_context]

    nodes_this_turn = len(executed)
    feedback_section = (
        f"\n## ⚠️ 上一次规划被评估器拒绝，请务必调整后重新规划\n{feedback}\n"
        if feedback else ""
    )

    prompt = f"""你是一个 AI 职业规划助手的内部决策模块，现在需要决定下一步应该做什么来帮助用户。
{feedback_section}
## 用户情况
- 用户角色: {profile.get('currentRole', '')}
- 用户目标: {profile.get('targetRole', '')}
- 短期目标: {profile.get('shortTermGoal', '')}
- 约束: {', '.join(profile.get('constraints', [])[:3])}

## 本轮对话状态
- 用户本轮意图（trigger）: {trigger}
- 用户本轮要做的事: {arc_description or trigger}
- 用户上一轮收到的回复（若有）: {ctx['last_agent_response'][:150] or '（第一轮，尚无历史回复）'}
- 跨轮已了解的信息: {json.dumps(ctx['confirmed_facts'], ensure_ascii=False)[:200] or '（暂无）'}

## 本轮已完成的分析
- 已执行步骤数: {nodes_this_turn}（为 0 表示本轮刚开始，必须先执行至少一步再考虑结束）
- 已执行步骤: {executed or ['（本轮尚未开始任何分析）']}
- 最近一步的输出: {json.dumps(ctx['last_node_output'], ensure_ascii=False)[:200] or '（暂无）'}
- 本轮已调用的工具: {ctx['current_turn_used_tools'] or '（本轮尚未调用工具）'}

## 你可以使用的分析能力（Skill）
{chr(10).join(f"- {sid}: {name}" for sid, name in valid_skills.items())}

## 你可以调用的外部工具（Tool）
{chr(10).join(f"- {tid}: {name}" for tid, name in valid_tools.items())}

## 决策要求
请从"如何真正帮助这位用户"的角度思考：
1. 用户现在最需要什么信息或分析？
2. 已有的分析是否足以回答用户的问题或需求？
3. 下一步做什么能让用户的问题向前推进？

注意：
- 本轮已执行 {nodes_this_turn} 步。若为 0，当前尚未开始，不能立即结束
- 不重复调用本轮已用过的工具
- inputs 要提取当前状态中真正相关的字段，而非空占位符
- 每轮不超过 6 步

## 输出格式（严格 JSON，不含注释）
{{
  "node_type":   "skill_call" | "tool_call" | "agent_response",
  "node_id":     "<skill_id 或 tool_id 或 agent_response>",
  "node_name":   "<同 node_id>",
  "inputs":      {{ ... }},
  "rationale":   "一句话说明：依赖了什么前序信息，为什么选这个节点",
  "is_terminal": false
}}

若直接结束本轮:
{{
  "node_type": "agent_response", "node_id": "agent_response",
  "node_name": "agent_response", "inputs": {{}},
  "rationale": "已完成分析，生成回复", "is_terminal": true
}}"""

    try:
        raw = chat_json([{"role": "user", "content": prompt}], temperature=0.4)
        return _validate_and_fix_plan(raw, valid_skills, valid_tools, trigger, task_type,
                                       state, domain, node_context, profile)
    except Exception as e:
        print(f"    [node_planner] LLM failed: {e}, using fallback")
        return _fallback_plan(trigger, task_type, state, domain, node_context, profile)


def _validate_and_fix_plan(
    raw: dict,
    valid_skills: dict, valid_tools: dict,
    trigger: str, task_type: str,
    state: "ConversationState", domain: "Domain",
    node_context: list[dict], profile: dict,
) -> dict:
    """校验 LLM 规划输出，必要时 fallback。"""
    if not isinstance(raw, dict):
        return _fallback_plan(trigger, task_type, state, domain, node_context, profile)

    node_type   = raw.get("node_type", "")
    node_id     = raw.get("node_id", "")
    is_terminal = raw.get("is_terminal", False)

    if is_terminal or node_type == "agent_response":
        return {
            "node_type": "agent_response", "node_id": "agent_response",
            "node_name": "agent_response", "inputs": {},
            "rationale": raw.get("rationale", "结束本轮"), "is_terminal": True,
        }

    # 校验 node_id 合法性
    if node_type == "skill_call" and node_id not in valid_skills:
        return _fallback_plan(trigger, task_type, state, domain, node_context, profile)
    if node_type == "tool_call" and node_id not in valid_tools:
        return _fallback_plan(trigger, task_type, state, domain, node_context, profile)

    # 如果 inputs 是空的，用结构化推断填充
    inputs = raw.get("inputs") or {}
    if not inputs:
        inputs = _infer_structured_inputs(node_type, node_id, state, profile)

    return {
        "node_type":   node_type,
        "node_id":     node_id,
        "node_name":   raw.get("node_name", node_id),
        "inputs":      inputs,
        "rationale":   raw.get("rationale", f"执行 {node_id}"),
        "is_terminal": False,
    }
