"""Quick test - verify planner works without LLM calls."""
import json
import random
from pathlib import Path
from src.domain import load_domain
from src.planner import select_template, plan_trajectory
from src.task_generator import infer_interaction_style
from src.mock_tools import mock_tool_call

domain = load_domain(Path("domain/code_development"), Path("../personas"))
user_data = domain.user_profiles[0]
profile = user_data["profile"]
meta = user_data.get("_meta", {})

style = infer_interaction_style(profile)
print(f"Persona: {meta.get('personaId', '?')}")
print(f"Interaction style: {style}")

# Mock a task
task = {
    "task_id": "test_001",
    "domain": "code_development",
    "task_type": "learning_path_planning",
    "user_id": meta.get("personaId", "test"),
    "task_description": "test task",
    "initial_user_query": "I want to learn React in 3 months",
    "interaction_style": style,
    "expected_skills": meta.get("expectedSkills", []),
}

template = select_template(domain, task, style)
print(f"Selected template: {template['name']}")

plan = plan_trajectory(domain, task, profile, template)
print(f"Planned nodes: {len(plan['planned_nodes'])}")
for n in plan["planned_nodes"]:
    print(f"  - {n['node_name']} ({n['node_type']})")

# Test mock tool
print("\nMock tool test:")
result = mock_tool_call("job_requirement_search", {"job_title": "前端开发工程师"})
print(f"  Required skills: {result.get('required_skills', [])}")

print("\nAll tests passed!")
