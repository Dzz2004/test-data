"""
Trajectory Planner - 多轮轨迹规划

策略：
1. plan_multi_turn: 按 conversation_arc 逐轮规划，每轮产生节点序列
2. 每轮可选 LLM 规划或模板规划（use_llm=False 用于测试）
3. 原有单轮 plan_with_llm 保留作内部工具
"""
from __future__ import annotations

import random
from typing import Any
from .domain import Domain, SkillSpec, ToolSpec
from .llm_client import chat_json


# ─── 主入口 ────────────────────────────────────────────────────────────────────

def plan_with_llm(
    domain: Domain,
    task: dict,
    user_profile: dict,
    max_retries: int = 2,
) -> dict:
    """
    使用 LLM 生成轨迹节点序列。
    失败时 fallback 到模板方案。
    """
    # 准备 prompt 上下文
    skill_descriptions = _format_skills_for_prompt(domain.skills)
    tool_descriptions = _format_tools_for_prompt(domain.tools)
    few_shot_examples = _select_few_shot_templates(domain, task)
    profile_summary = _summarize_profile(user_profile)

    prompt = _build_planning_prompt(
        task=task,
        profile_summary=profile_summary,
        skill_descriptions=skill_descriptions,
        tool_descriptions=tool_descriptions,
        few_shot_examples=few_shot_examples,
    )

    # 尝试 LLM 规划
    for attempt in range(max_retries):
        try:
            raw_plan = chat_json(
                [{"role": "user", "content": prompt}],
                temperature=0.7 + attempt * 0.1,  # 重试时稍微提高温度
            )

            # 解析 LLM 输出
            node_sequence = _parse_llm_plan(raw_plan)

            # 校验
            validation = validate_plan(node_sequence, domain)

            if validation["valid"]:
                # 通过校验，构建最终 plan
                planned_nodes = _map_nodes(node_sequence, domain)
                return {
                    "trajectory_id": f"traj_{task['task_id']}_{random.randint(100, 999)}",
                    "template_id": "llm_generated",
                    "template_name": "LLM 自由规划",
                    "planning_method": "llm",
                    "planned_nodes": planned_nodes,
                    "task": task,
                    "user_profile": user_profile,
                }

            # 校验不通过，尝试自动修复
            fixed = _auto_fix(node_sequence, validation["issues"], domain)
            re_validation = validate_plan(fixed, domain)

            if re_validation["valid"]:
                planned_nodes = _map_nodes(fixed, domain)
                return {
                    "trajectory_id": f"traj_{task['task_id']}_{random.randint(100, 999)}",
                    "template_id": "llm_generated_fixed",
                    "template_name": "LLM 规划(已修复)",
                    "planning_method": "llm_fixed",
                    "planned_nodes": planned_nodes,
                    "task": task,
                    "user_profile": user_profile,
                }

        except Exception as e:
            print(f"    LLM planning attempt {attempt + 1} failed: {e}")
            continue

    # Fallback 到模板方案
    print("    Falling back to template-based planning")
    return _fallback_template_plan(domain, task, user_profile)


# ─── Prompt 构建 ──────────────────────────────────────────────────────────────

def _build_planning_prompt(
    task: dict,
    profile_summary: str,
    skill_descriptions: str,
    tool_descriptions: str,
    few_shot_examples: str,
) -> str:
    return f"""你是一个 Agent 轨迹规划器。根据用户画像和任务，规划一条合理的 agent 执行轨迹。

## 可用 Skill 池
{skill_descriptions}

## 可用 Tool 池
{tool_descriptions}

## 用户画像
{profile_summary}

## 任务信息
- 任务类型: {task.get('task_type', '')}
- 任务描述: {task.get('task_description', '')}
- 用户请求: {task.get('initial_user_query', '')}
- 交互风格: {task.get('interaction_style', '信息充分型')}

## 规划规则
1. 轨迹必须以 user_input 开头，以 final_response 结尾
2. 每个节点必须是以下类型之一:
   - user_input: 用户输入（首轮请求、补充信息、修改约束等）
   - skill_call: 调用一个 skill（从 skill 池中选择）
   - tool_call: 调用一个 tool（从 tool 池中选择）
   - agent_reasoning: agent 内部推理或向用户追问
   - agent_response: 最终回复
3. skill 的 preconditions 必须被前序节点满足
4. tool_call 通常出现在需要外部数据时
5. 节点数量应在 5-14 个之间
6. 不要连续重复调用同一个 skill 或 tool
7. 根据交互风格调整:
   - 信息缺失型: 需要加入 agent_reasoning(追问) + user_input(补充)
   - 反复修改型: 需要加入 user_input(修改约束) + plan_revision
   - 质疑型: 需要加入 user_input(质疑) + agent_reasoning(解释)

## 参考示例（仅供参考，你可以自由组合）
{few_shot_examples}

## 输出格式
返回 JSON 数组，每个元素描述一个节点:
```json
[
  {{"node_type": "user_input", "node_name": "user_input", "reason": "用户发起请求"}},
  {{"node_type": "skill_call", "skill_id": "need_analysis", "node_name": "need_analysis", "reason": "解析用户需求"}},
  {{"node_type": "tool_call", "tool_id": "job_requirement_search", "node_name": "job_requirement_search", "reason": "查询目标岗位要求"}},
  ...
  {{"node_type": "agent_response", "node_name": "final_response", "reason": "综合前序分析给出最终建议"}}
]
```

请根据此用户的具体情况规划最合理的轨迹，不必拘泥于示例模板。"""


def _format_skills_for_prompt(skills: list[SkillSpec]) -> str:
    lines = []
    for s in skills:
        next_skills = ", ".join(s.possible_next_skills[:3]) if s.possible_next_skills else "无"
        lines.append(
            f"- {s.skill_id} ({s.name}): {s.description}\n"
            f"  前置条件: {', '.join(s.preconditions)}\n"
            f"  后置条件: {', '.join(s.postconditions)}\n"
            f"  可接: {next_skills}"
        )
    return "\n".join(lines)


def _format_tools_for_prompt(tools: list[ToolSpec]) -> str:
    lines = []
    for t in tools:
        inputs = ", ".join(f"{k}:{v}" for k, v in t.input_schema.items())
        lines.append(f"- {t.tool_id} ({t.name}): {t.description}\n  输入: {inputs}")
    return "\n".join(lines)


def _select_few_shot_templates(domain: Domain, task: dict) -> str:
    """选 2 个相关模板作为 few-shot 示例"""
    task_type = task.get("task_type", "")
    type_map = {
        "learning-plan": "learning_path_planning",
        "career-roadmap": "career_roadmap",
        "mock-interview": "mock_interview_prep",
        "coding-assessment": "skill_gap_diagnosis",
    }
    normalized = type_map.get(task_type, task_type)

    # 按相关性排序
    scored = []
    for t in domain.trajectory_templates:
        score = 0
        if normalized in t.get("applicable_task_types", []):
            score += 2
        if task.get("interaction_style", "") in t.get("applicable_interaction_styles", []):
            score += 1
        scored.append((t, score))

    scored.sort(key=lambda x: -x[1])
    selected = scored[:2]

    lines = []
    for tmpl, _ in selected:
        lines.append(f"### {tmpl['name']}")
        lines.append(f"节点序列: {' → '.join(tmpl['node_sequence'])}")
        lines.append("")
    return "\n".join(lines)


def _summarize_profile(profile: dict) -> str:
    parts = []
    if profile.get("currentRole"):
        parts.append(f"当前角色: {profile['currentRole']}")
    if profile.get("targetRole"):
        parts.append(f"目标角色: {profile['targetRole']}")
    if profile.get("experienceSummary"):
        parts.append(f"经验: {profile['experienceSummary'][:120]}")
    if profile.get("shortTermGoal"):
        parts.append(f"短期目标: {profile['shortTermGoal'][:80]}")
    if profile.get("constraints"):
        parts.append(f"约束: {', '.join(profile['constraints'][:3])}")
    if profile.get("weeklyTimeBudget"):
        parts.append(f"每周时间: {profile['weeklyTimeBudget']}")
    if profile.get("keyStrengths"):
        parts.append(f"优势: {', '.join(profile['keyStrengths'][:3])}")
    if profile.get("riskSignals"):
        parts.append(f"风险点: {', '.join(profile['riskSignals'][:2])}")
    return "\n".join(parts)


# ─── 解析 LLM 输出 ────────────────────────────────────────────────────────────

def _parse_llm_plan(raw: Any) -> list[dict]:
    """解析 LLM 返回的节点列表"""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        # 可能包裹在某个 key 下
        for key in ("nodes", "plan", "trajectory", "steps"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
        return [raw]
    raise ValueError(f"Unexpected LLM plan format: {type(raw)}")


# ─── 校验 ─────────────────────────────────────────────────────────────────────

def validate_plan(node_sequence: list[dict], domain: Domain) -> dict:
    """
    校验 LLM 生成的节点序列是否合理。
    返回 {"valid": bool, "issues": [...]}
    """
    issues = []
    skill_map = {s.skill_id: s for s in domain.skills}
    tool_map = {t.tool_id: t for t in domain.tools}
    valid_skill_ids = set(skill_map.keys())
    valid_tool_ids = set(tool_map.keys())

    if not node_sequence:
        return {"valid": False, "issues": ["empty_plan"]}

    # Rule 1: 必须以 user_input 开头
    first = node_sequence[0]
    if first.get("node_type") != "user_input" and first.get("node_name") != "user_input":
        issues.append("missing_start_user_input")

    # Rule 2: 必须以 final_response/agent_response 结尾
    last = node_sequence[-1]
    if last.get("node_type") not in ("agent_response",) and last.get("node_name") != "final_response":
        issues.append("missing_end_final_response")

    # Rule 3: 节点数量合理
    if len(node_sequence) < 4:
        issues.append("too_few_nodes")
    if len(node_sequence) > 20:
        issues.append("too_many_nodes")

    # Rule 4: skill_id 和 tool_id 必须存在于池中
    for i, node in enumerate(node_sequence):
        sid = node.get("skill_id")
        tid = node.get("tool_id")
        if sid and sid not in valid_skill_ids:
            issues.append(f"unknown_skill:{sid}")
        if tid and tid not in valid_tool_ids:
            issues.append(f"unknown_tool:{tid}")

    # Rule 5: 不连续重复同一节点
    for i in range(1, len(node_sequence)):
        curr_name = node_sequence[i].get("node_name") or node_sequence[i].get("skill_id") or ""
        prev_name = node_sequence[i-1].get("node_name") or node_sequence[i-1].get("skill_id") or ""
        if curr_name and curr_name == prev_name:
            issues.append(f"consecutive_repeat:{curr_name}")

    # Rule 6: 前置条件检查（宽松模式 — 只检查关键依赖）
    achieved_postconditions = set()
    for node in node_sequence:
        sid = node.get("skill_id")
        if sid and sid in skill_map:
            skill = skill_map[sid]
            # 检查 preconditions 是否被前面的 postconditions 覆盖
            for pre in skill.preconditions:
                if pre not in achieved_postconditions and len(achieved_postconditions) > 0:
                    # 宽松: 只要有前序 skill 就算部分满足
                    pass  # 严格版可以加 issues
            # 记录当前 skill 的 postconditions
            for post in skill.postconditions:
                achieved_postconditions.add(post)

    # 严重问题直接判定不合格
    critical_issues = {"empty_plan", "too_few_nodes", "missing_start_user_input", "missing_end_final_response"}
    has_critical = bool(set(issues) & critical_issues)

    return {
        "valid": not has_critical and len(issues) <= 2,  # 允许 1-2 个小问题
        "issues": issues,
    }


# ─── 自动修复 ──────────────────────────────────────────────────────────────────

def _auto_fix(node_sequence: list[dict], issues: list[str], domain: Domain) -> list[dict]:
    """尝试自动修复常见问题"""
    fixed = list(node_sequence)

    if "missing_start_user_input" in issues:
        fixed.insert(0, {"node_type": "user_input", "node_name": "user_input", "reason": "用户发起请求"})

    if "missing_end_final_response" in issues:
        fixed.append({"node_type": "agent_response", "node_name": "final_response", "reason": "生成最终回复"})

    # 移除未知的 skill/tool（替换为最接近的）
    valid_skills = {s.skill_id for s in domain.skills}
    valid_tools = {t.tool_id for t in domain.tools}

    cleaned = []
    for node in fixed:
        sid = node.get("skill_id")
        tid = node.get("tool_id")
        if sid and sid not in valid_skills:
            # 跳过未知 skill
            continue
        if tid and tid not in valid_tools:
            continue
        cleaned.append(node)

    # 移除连续重复
    deduped = [cleaned[0]] if cleaned else []
    for i in range(1, len(cleaned)):
        curr_name = cleaned[i].get("node_name") or cleaned[i].get("skill_id") or ""
        prev_name = cleaned[i-1].get("node_name") or cleaned[i-1].get("skill_id") or ""
        if curr_name != prev_name or not curr_name:
            deduped.append(cleaned[i])

    return deduped if deduped else fixed


# ─── 节点映射 ──────────────────────────────────────────────────────────────────

def _map_nodes(node_sequence: list[dict], domain: Domain) -> list[dict]:
    """将 LLM 输出的节点列表转为 generator 期望的 planned_nodes 格式"""
    skill_map = {s.skill_id: s for s in domain.skills}
    tool_map = {t.tool_id: t for t in domain.tools}

    planned = []
    for i, node in enumerate(node_sequence):
        node_type = node.get("node_type", "skill_call")
        node_name = node.get("node_name") or node.get("skill_id") or node.get("tool_id") or f"step_{i}"
        skill_id = node.get("skill_id")
        tool_id = node.get("tool_id")

        # 如果 node_name 匹配到 skill/tool 但没有显式设置 id
        if not skill_id and node_name in skill_map:
            skill_id = node_name
            node_type = "skill_call"
        if not tool_id and node_name in tool_map:
            tool_id = node_name
            node_type = "tool_call"

        planned.append({
            "node_index": i,
            "node_name": node_name,
            "node_type": node_type,
            "skill_id": skill_id,
            "tool_id": tool_id,
        })

    return planned


# ─── Fallback: 模板方案 ───────────────────────────────────────────────────────

def _fallback_template_plan(domain: Domain, task: dict, user_profile: dict) -> dict:
    """当 LLM 规划失败时，退回模板方案"""
    interaction_style = task.get("interaction_style", "信息充分型")
    template = select_template(domain, task, interaction_style)
    return plan_trajectory(domain, task, user_profile, template)


# ─── 保留原有的模板方案（作为 fallback 和参考）────────────────────────────────

def select_template(domain: Domain, task: dict, interaction_style: str) -> dict:
    """Select the best trajectory template based on task type and interaction style."""
    candidates = []
    task_type = task["task_type"]

    type_map = {
        "learning-plan": "learning_path_planning",
        "career-roadmap": "career_roadmap",
        "mock-interview": "mock_interview_prep",
        "coding-assessment": "skill_gap_diagnosis",
    }
    normalized_type = type_map.get(task_type, task_type)

    for template in domain.trajectory_templates:
        if normalized_type in template.get("applicable_task_types", []):
            styles = template.get("applicable_interaction_styles", [])
            if interaction_style in styles:
                candidates.append((template, 2))
            else:
                candidates.append((template, 1))

    if not candidates:
        return domain.trajectory_templates[0]

    templates, weights = zip(*candidates)
    return random.choices(templates, weights=weights, k=1)[0]


def plan_trajectory(
    domain: Domain,
    task: dict,
    user_profile: dict,
    template: dict,
) -> dict:
    """模板驱动的轨迹规划（保留作为 fallback）"""
    node_sequence = template["node_sequence"]
    skill_map = {s.skill_id: s for s in domain.skills}
    tool_map = {t.tool_id: t for t in domain.tools}
    skill_name_map = {s.name: s for s in domain.skills}
    tool_name_map = {t.name: t for t in domain.tools}

    planned_nodes = []
    for i, node_name in enumerate(node_sequence):
        node_plan = {
            "node_index": i,
            "node_name": node_name,
            "node_type": _classify_node_type(node_name, skill_map, tool_map),
            "skill_id": None,
            "tool_id": None,
        }

        if node_name in skill_map:
            node_plan["skill_id"] = node_name
            node_plan["node_type"] = "skill_call"
        elif node_name in skill_name_map:
            node_plan["skill_id"] = skill_name_map[node_name].skill_id
            node_plan["node_type"] = "skill_call"

        if node_name in tool_map:
            node_plan["tool_id"] = node_name
            node_plan["node_type"] = "tool_call"
        elif node_name in tool_name_map:
            node_plan["tool_id"] = tool_name_map[node_name].tool_id
            node_plan["node_type"] = "tool_call"

        if node_name in ("user_input", "user_followup", "user_constraint_update"):
            node_plan["node_type"] = "user_input"
        elif node_name in ("final_response",):
            node_plan["node_type"] = "agent_response"
        elif node_name in ("agent_clarification",):
            node_plan["node_type"] = "agent_reasoning"

        planned_nodes.append(node_plan)

    return {
        "trajectory_id": f"traj_{task['task_id']}_{random.randint(100, 999)}",
        "template_id": template["template_id"],
        "template_name": template["name"],
        "planning_method": "template",
        "planned_nodes": planned_nodes,
        "task": task,
        "user_profile": user_profile,
    }


def _classify_node_type(node_name: str, skill_map: dict, tool_map: dict) -> str:
    if node_name in skill_map:
        return "skill_call"
    if node_name in tool_map:
        return "tool_call"
    if "user" in node_name and ("input" in node_name or "followup" in node_name or "update" in node_name):
        return "user_input"
    if "search" in node_name or "query" in node_name:
        return "tool_call"
    if "final" in node_name or "response" in node_name:
        return "agent_response"
    if "clarification" in node_name:
        return "agent_reasoning"
    return "skill_call"


# ══════════════════════════════════════════════════════════════════════════════
# Multi-turn Planner
# ══════════════════════════════════════════════════════════════════════════════

# 每种 trigger 对应的默认节点序列（不含 user_input，结尾固定 agent_response）
_TRIGGER_TEMPLATES: dict[str, dict[str, list[dict]]] = {
    # ── 第一轮模板（按任务类型细分）──────────────────────────────────────────
    "initial_request": {
        "mock-interview": [
            {"node_type": "skill_call", "skill_id": "need_analysis",        "node_name": "need_analysis"},
            {"node_type": "tool_call",  "tool_id":  "job_requirement_search","node_name": "job_requirement_search"},
            {"node_type": "skill_call", "skill_id": "level_diagnosis",       "node_name": "level_diagnosis"},
            {"node_type": "skill_call", "skill_id": "interview_prep_planning","node_name": "interview_prep_planning"},
            {"node_type": "tool_call",  "tool_id":  "interview_question_search","node_name": "interview_question_search"},
            {"node_type": "skill_call", "skill_id": "feasibility_check",     "node_name": "feasibility_check"},
            {"node_type": "agent_response", "node_name": "agent_response"},
        ],
        "mock_interview_prep": [
            {"node_type": "skill_call", "skill_id": "need_analysis",         "node_name": "need_analysis"},
            {"node_type": "tool_call",  "tool_id":  "job_requirement_search", "node_name": "job_requirement_search"},
            {"node_type": "skill_call", "skill_id": "level_diagnosis",        "node_name": "level_diagnosis"},
            {"node_type": "skill_call", "skill_id": "interview_prep_planning","node_name": "interview_prep_planning"},
            {"node_type": "agent_response", "node_name": "agent_response"},
        ],
        "learning-plan": [
            {"node_type": "skill_call", "skill_id": "need_analysis",          "node_name": "need_analysis"},
            {"node_type": "skill_call", "skill_id": "level_diagnosis",         "node_name": "level_diagnosis"},
            {"node_type": "tool_call",  "tool_id":  "knowledge_graph_query",   "node_name": "knowledge_graph_query"},
            {"node_type": "skill_call", "skill_id": "skill_gap_analysis",      "node_name": "skill_gap_analysis"},
            {"node_type": "skill_call", "skill_id": "learning_path_planning",  "node_name": "learning_path_planning"},
            {"node_type": "agent_response", "node_name": "agent_response"},
        ],
        "career-roadmap": [
            {"node_type": "skill_call", "skill_id": "need_analysis",          "node_name": "need_analysis"},
            {"node_type": "tool_call",  "tool_id":  "job_requirement_search",  "node_name": "job_requirement_search"},
            {"node_type": "skill_call", "skill_id": "career_path_analysis",    "node_name": "career_path_analysis"},
            {"node_type": "skill_call", "skill_id": "skill_gap_analysis",      "node_name": "skill_gap_analysis"},
            {"node_type": "agent_response", "node_name": "agent_response"},
        ],
        "_default": [
            {"node_type": "skill_call", "skill_id": "need_analysis",          "node_name": "need_analysis"},
            {"node_type": "skill_call", "skill_id": "level_diagnosis",         "node_name": "level_diagnosis"},
            {"node_type": "skill_call", "skill_id": "skill_gap_analysis",      "node_name": "skill_gap_analysis"},
            {"node_type": "agent_response", "node_name": "agent_response"},
        ],
    },
    # ── 后续轮次模板 ──────────────────────────────────────────────────────────
    "constraint_update": {
        "_default": [
            {"node_type": "skill_call", "skill_id": "feasibility_check",  "node_name": "feasibility_check"},
            {"node_type": "skill_call", "skill_id": "plan_revision",       "node_name": "plan_revision"},
            {"node_type": "skill_call", "skill_id": "learning_path_planning","node_name": "learning_path_planning"},
            {"node_type": "agent_response", "node_name": "agent_response"},
        ],
    },
    "clarification": {
        "_default": [
            {"node_type": "skill_call", "skill_id": "need_analysis",       "node_name": "need_analysis"},
            {"node_type": "skill_call", "skill_id": "resource_recommendation","node_name": "resource_recommendation"},
            {"node_type": "agent_response", "node_name": "agent_response"},
        ],
    },
    "plan_revision": {
        "_default": [
            {"node_type": "skill_call", "skill_id": "plan_revision",       "node_name": "plan_revision"},
            {"node_type": "skill_call", "skill_id": "feasibility_check",   "node_name": "feasibility_check"},
            {"node_type": "agent_response", "node_name": "agent_response"},
        ],
    },
    "pushback": {
        "_default": [
            {"node_type": "skill_call", "skill_id": "need_analysis",       "node_name": "need_analysis"},
            {"node_type": "skill_call", "skill_id": "career_path_analysis", "node_name": "career_path_analysis"},
            {"node_type": "agent_response", "node_name": "agent_response"},
        ],
    },
}


def plan_multi_turn(
    domain: "Domain",
    blueprint: Any,
    user_profile: dict,
    use_llm: bool = True,
) -> dict:
    """
    Plan a multi-turn trajectory from a Blueprint.
    Returns a dict with 'turns_plan': list of per-turn planned node sequences.

    Each turn_plan:
        {"turn_id": int, "trigger": str, "planned_nodes": [node_dict, ...]}

    Node dicts do NOT include user_input (handled by generator).
    Every turn ends with an agent_response node.
    """
    import random as _random

    turns_plan = []
    task_type = blueprint.task_type

    for arc_turn in blueprint.conversation_arc:
        if use_llm:
            nodes = _plan_turn_with_llm(domain, blueprint, user_profile, arc_turn, turns_plan)
        else:
            nodes = _plan_turn_from_template(task_type, arc_turn.trigger)

        turns_plan.append({
            "turn_id":       arc_turn.turn,
            "trigger":       arc_turn.trigger,
            "arc_description": arc_turn.description,
            "planned_nodes": nodes,
        })

    return {
        "trajectory_id": f"traj_{blueprint.task_id}_{_random.randint(100, 999)}",
        "blueprint":     blueprint,
        "user_profile":  user_profile,
        "turns_plan":    turns_plan,
    }


def _plan_turn_from_template(task_type: str, trigger: str) -> list[dict]:
    """Select node sequence from static templates, copy to avoid mutation."""
    trigger_map = _TRIGGER_TEMPLATES.get(trigger, _TRIGGER_TEMPLATES.get("clarification", {}))
    nodes = trigger_map.get(task_type) or trigger_map.get("_default", [])
    return [dict(n) for n in nodes]


def _plan_turn_with_llm(
    domain: "Domain",
    blueprint: Any,
    user_profile: dict,
    arc_turn: Any,
    previous_turns: list[dict],
) -> list[dict]:
    """LLM plans nodes for one turn; falls back to template on failure."""
    skill_descriptions = _format_skills_for_prompt(domain.skills)
    tool_descriptions  = _format_tools_for_prompt(domain.tools)

    prev_summary = ""
    if previous_turns:
        lines = []
        for tp in previous_turns[-2:]:
            skill_ids = [n.get("skill_id") or n.get("tool_id", "") for n in tp["planned_nodes"]]
            lines.append(f"  Turn {tp['turn_id']} ({tp['trigger']}): {', '.join(filter(None, skill_ids))}")
        prev_summary = "\n".join(lines)

    prompt = f"""你是 Agent 轨迹规划器，正在规划多轮对话中第 {arc_turn.turn} 轮的节点序列。

## 用户画像
- 当前角色: {user_profile.get('currentRole', '')}
- 目标角色: {user_profile.get('targetRole', '')}
- 约束: {', '.join(user_profile.get('constraints', [])[:3])}

## 任务
- 类型: {blueprint.task_type}
- 本轮触发: {arc_turn.trigger}
- 本轮描述: {arc_turn.description}

## 前序轮次
{prev_summary or "（第一轮）"}

## 可用 Skill 池
{skill_descriptions}

## 可用 Tool 池
{tool_descriptions}

## 规划规则
1. 只规划本轮 agent 内部处理节点，不包含 user_input
2. 最后一个节点必须是 agent_response
3. 节点数量 2-6 个
4. 不重复使用前序轮次已用过的 tool（skill 可复用）
5. 根据本轮 trigger 类型选择合适的 skill/tool:
   - initial_request: 完整分析流程
   - constraint_update: 必须包含 feasibility_check 或 plan_revision
   - clarification: 针对用户追问的具体回答
   - plan_revision: 重新规划
   - pushback: 解释和说明

返回 JSON 数组（只包含节点，不包含 user_input）:
[
  {{"node_type": "skill_call", "skill_id": "need_analysis",    "node_name": "need_analysis"}},
  {{"node_type": "tool_call",  "tool_id":  "job_requirement_search", "node_name": "job_requirement_search"}},
  ...
  {{"node_type": "agent_response", "node_name": "agent_response"}}
]"""

    try:
        raw = chat_json([{"role": "user", "content": prompt}], temperature=0.6)
        nodes = _parse_llm_plan(raw) if isinstance(raw, list) else _parse_llm_plan(raw)
        # 确保结尾是 agent_response
        if not nodes or nodes[-1].get("node_type") != "agent_response":
            nodes.append({"node_type": "agent_response", "node_name": "agent_response"})
        # 过滤掉 unknown skill/tool
        valid_skills = {s.skill_id for s in domain.skills}
        valid_tools  = {t.tool_id  for t in domain.tools}
        cleaned = []
        for n in nodes:
            sid = n.get("skill_id")
            tid = n.get("tool_id")
            if sid and sid not in valid_skills:
                continue
            if tid and tid not in valid_tools:
                continue
            cleaned.append(n)
        if not cleaned or cleaned[-1].get("node_type") != "agent_response":
            cleaned.append({"node_type": "agent_response", "node_name": "agent_response"})
        return [dict(n) for n in cleaned]
    except Exception as e:
        print(f"    LLM turn planning failed (turn {arc_turn.turn}): {e}, using template")
        return _plan_turn_from_template(blueprint.task_type, arc_turn.trigger)
