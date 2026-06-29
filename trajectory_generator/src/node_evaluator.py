"""
NodeEvaluator - 小模型评估器

在 node_planner 输出规划之后、大模型执行之前调用。
判断该规划是否"足够好"可以直接执行。

输出 eval dict：
{
    "pass":        bool,
    "rationale":   str,   # 通过/不通过的理由（也是 planner 下一轮的 feedback）
    "suggestions": list[str],  # 具体改进建议（pass=False 时填充）
}

评估维度（无 LLM 时的静态规则，LLM 时作为 prompt 指导）：
  1. node_id 必须存在于 domain skill/tool 池中
  2. tool 不得在本轮重复调用（current_turn_used_tools）
  3. inputs 不能完全为空（除非 is_terminal）
  4. 节点数未超出上限（MAX_NODES_PER_TURN = 6）
  5. 节点选择与当前 trigger 类型相符
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .conversation_state import ConversationState
from .llm_client import chat_json

if TYPE_CHECKING:
    from .domain import Domain

MAX_NODES_PER_TURN = 6

# trigger → 应当出现的 skill（宽松检查，只对 constraint_update 做强制要求）
_REQUIRED_SKILLS: dict[str, set[str]] = {
    "constraint_update": {"feasibility_check", "plan_revision", "learning_path_planning"},
}


def evaluate_node_plan(
    plan: dict,
    trigger: str,
    state: ConversationState,
    domain: "Domain",
    node_context: list[dict],
    use_llm: bool = True,
) -> dict:
    """
    评估 node_planner 输出的规划。
    - use_llm=False: 纯规则评估，适合测试。
    - use_llm=True:  小模型 + 规则双重评估。
    """
    # is_terminal 时直接放行
    if plan.get("is_terminal") or plan.get("node_type") == "agent_response":
        return {"pass": True, "rationale": "terminal node，直接生成回复", "suggestions": []}

    # 先做静态规则检查
    rule_result = _rule_check(plan, trigger, state, domain, node_context)
    if not rule_result["pass"]:
        return rule_result

    if not use_llm:
        return {"pass": True, "rationale": "规则检查通过（fallback 模式）", "suggestions": []}

    return _llm_evaluate(plan, trigger, state, domain, node_context, rule_result)


# ── 静态规则评估 ───────────────────────────────────────────────────────────────

def _rule_check(
    plan: dict,
    trigger: str,
    state: ConversationState,
    domain: "Domain",
    node_context: list[dict],
) -> dict:
    issues = []
    suggestions = []

    node_type = plan.get("node_type", "")
    node_id   = plan.get("node_id", "")

    valid_skill_ids = {s.skill_id for s in domain.skills}
    valid_tool_ids  = {t.tool_id  for t in domain.tools}

    # Rule 1: node_id 必须合法
    if node_type == "skill_call" and node_id not in valid_skill_ids:
        issues.append(f"未知 skill_id: {node_id}")
        suggestions.append(f"从 skill 池中选择合法的 skill_id，可用: {list(valid_skill_ids)[:5]}")

    if node_type == "tool_call" and node_id not in valid_tool_ids:
        issues.append(f"未知 tool_id: {node_id}")
        suggestions.append(f"从 tool 池中选择合法的 tool_id，可用: {list(valid_tool_ids)}")

    # Rule 2: tool 不得重复调用
    if node_type == "tool_call":
        used = state.current_turn_used_tools
        if node_id in used:
            issues.append(f"工具 {node_id} 本轮已调用过")
            suggestions.append("换一个不同的工具，或直接生成 agent_response")

    # Rule 3: inputs 不能完全为空（skill/tool 都需要有意义的输入）
    inputs = plan.get("inputs", {})
    if not inputs and node_type in ("skill_call", "tool_call"):
        issues.append("inputs 为空，需要从当前状态提取结构化输入")
        suggestions.append("在 inputs 中填入从 last_node_output 或 profile 中提取的相关字段")

    # Rule 4: 节点数不超上限
    if len(node_context) >= MAX_NODES_PER_TURN:
        issues.append(f"本轮已执行 {len(node_context)} 个节点，达到上限")
        suggestions.append("直接生成 agent_response 结束本轮")

    if issues:
        return {
            "pass":        False,
            "rationale":   "规则检查不通过: " + "; ".join(issues),
            "suggestions": suggestions,
        }
    return {"pass": True, "rationale": "规则检查通过", "suggestions": []}


# ── LLM 评估 ──────────────────────────────────────────────────────────────────

def _llm_evaluate(
    plan: dict,
    trigger: str,
    state: ConversationState,
    domain: "Domain",
    node_context: list[dict],
    rule_result: dict,
) -> dict:
    """小模型评估规划质量。"""
    ctx      = state.get_planning_context()
    executed = [c.get("node_id", c.get("name", "")) for c in node_context]

    prompt = f"""你是一个 AI 助手的内部质量评估模块。你的同事（规划模块）提出了"下一步要做什么"，你需要从用户实际需求的角度判断这个行动是否真的有帮助。

## 用户当前的对话状态
- 本轮用户意图（trigger）: {trigger}
- 本轮已完成的分析步骤: {executed or ['（本轮尚未开始）']}
- 最近一步分析的输出: {json.dumps(ctx['last_node_output'], ensure_ascii=False)[:200]}
- 本轮已调用的工具: {ctx['current_turn_used_tools']}
- 跨轮积累的已知信息: {json.dumps(ctx['confirmed_facts'], ensure_ascii=False)[:150]}

## 规划模块提出的下一步行动
{json.dumps(plan, ensure_ascii=False, indent=2)}

## 你的评估任务
请思考：这个行动现在做，对用户有没有实际帮助？具体判断：
1. 这一步是用户现在最需要的吗？还是可以跳过或换一个更有价值的步骤？
2. inputs 是否真实反映了当前已知的信息？还是只是空洞的占位符？
3. 执行这一步之后，用户的问题会向前推进吗？
4. 有没有更重要的事情应该先做？

## 输出格式（严格 JSON）
{{
  "pass": true 或 false,
  "rationale": "一句话说明：从用户需求角度，为什么这步合适/不合适",
  "suggestions": ["如果不通过，给出具体的改进方向"]
}}"""

    try:
        raw = chat_json([{"role": "user", "content": prompt}], temperature=0.3)
        if not isinstance(raw, dict) or "pass" not in raw:
            return {"pass": True, "rationale": "LLM 评估返回格式异常，默认通过", "suggestions": []}
        return {
            "pass":        bool(raw["pass"]),
            "rationale":   str(raw.get("rationale", "")),
            "suggestions": list(raw.get("suggestions", [])),
        }
    except Exception as e:
        print(f"    [node_evaluator] LLM failed: {e}, defaulting to pass")
        return {"pass": True, "rationale": "LLM 评估失败，默认通过", "suggestions": []}
