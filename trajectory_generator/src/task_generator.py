"""
Task Generator - 基于用户画像和领域生成任务
"""
import random
from typing import Any
from .domain import Domain
from .llm_client import chat_json


# 交互风格映射（从画像特征推断）
def infer_interaction_style(profile: dict) -> str:
    """从用户画像推断交互风格"""
    constraints = profile.get("constraints", [])
    risk_signals = profile.get("riskSignals", [])

    # 信息缺失型：约束少、目标模糊
    if not profile.get("shortTermGoal") or len(profile.get("shortTermGoal", "")) < 20:
        return "信息缺失型"

    # 反复修改型：风险信号中提到焦虑或反复
    for signal in risk_signals:
        if any(w in signal for w in ["焦虑", "反复", "变更", "切换"]):
            return "反复修改型"

    # 偏好强烈型：工作偏好和约束条件多
    if len(profile.get("workPreferences", [])) >= 4 or len(constraints) >= 4:
        return "偏好强烈型"

    # 默认：信息充分型
    return "信息充分型"


def generate_task(domain: Domain, user_data: dict) -> dict:
    """
    Generate a task based on user profile and domain configuration.
    Uses LLM to generate a natural user query.
    """
    profile = user_data["profile"]
    meta = user_data.get("_meta", {})
    persona_id = meta.get("personaId", "unknown")
    interaction_style = infer_interaction_style(profile)

    # Pick task type based on test scenarios in meta
    test_scenarios = meta.get("testScenarios", domain.spec.task_types)
    task_type = random.choice(test_scenarios) if test_scenarios else random.choice(domain.spec.task_types)

    # Map task type to Chinese description for prompt
    task_type_labels = {
        "learning-plan": "学习路径规划",
        "learning_path_planning": "学习路径规划",
        "career-roadmap": "职业路线规划",
        "career_roadmap": "职业路线规划",
        "mock-interview": "面试准备",
        "mock_interview_prep": "面试准备",
        "coding-assessment": "技能评估",
        "skill_gap_diagnosis": "技能缺口诊断",
        "project_recommendation": "项目推荐",
        "tech_stack_selection": "技术栈选择",
    }
    task_label = task_type_labels.get(task_type, task_type)

    # Generate user query via LLM
    messages = [{
        "role": "user",
        "content": f"""基于以下用户画像，生成一个该用户可能向职业规划 AI 助手提出的自然语言请求。

用户画像:
- 当前角色: {profile.get('currentRole', '')}
- 目标角色: {profile.get('targetRole', '')}
- 经验概述: {profile.get('experienceSummary', '')}
- 短期目标: {profile.get('shortTermGoal', '')}
- 约束条件: {', '.join(profile.get('constraints', []))}
- 每周时间: {profile.get('weeklyTimeBudget', '')}

任务类型: {task_label}
交互风格: {interaction_style}

交互风格说明:
- 信息充分型: 用户一次性提供较完整的背景、目标和约束
- 信息缺失型: 用户只说了一个模糊的方向，没有提供基础、时间等细节
- 偏好强烈型: 用户有明确偏好和限制条件
- 反复修改型: 用户中途可能修改需求

请直接输出用户会说的话（一段自然语言，不要加引号或标记），语言与画像的 locale 一致。字数在 30-120 字之间。"""
    }]

    try:
        user_query = chat_json(messages)  # will fail since this isn't JSON
    except Exception:
        # Fallback: use plain chat
        from .llm_client import chat
        user_query = chat(messages, temperature=0.8, max_tokens=200).strip().strip('"').strip("'")

    return {
        "task_id": f"task_{persona_id}_{random.randint(1000, 9999)}",
        "domain": domain.spec.domain_id,
        "task_type": task_type,
        "user_id": persona_id,
        "task_description": f"为 {profile.get('currentRole', '用户')} 生成{task_label}",
        "initial_user_query": user_query,
        "interaction_style": interaction_style,
        "expected_skills": meta.get("expectedSkills", []),
    }
