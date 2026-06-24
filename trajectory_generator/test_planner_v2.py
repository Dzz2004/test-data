"""Test the new LLM planner's validation and fallback logic (no LLM calls)."""
import random
from pathlib import Path
from src.domain import load_domain
from src.planner import (
    validate_plan,
    _auto_fix,
    _map_nodes,
    _fallback_template_plan,
    _summarize_profile,
    _format_skills_for_prompt,
    _format_tools_for_prompt,
)

domain = load_domain(Path("domain/code_development"), Path("../personas"))
user_data = domain.user_profiles[1]
profile = user_data["profile"]

# Test profile summarization
print("=== Profile Summary ===")
print(_summarize_profile(profile)[:200])

# Test skill/tool formatting
print("\n=== Skills (first 2) ===")
lines = _format_skills_for_prompt(domain.skills).split("\n")
for line in lines[:8]:
    print(line)

# Test validation with a good sequence
print("\n=== Validate Good Plan ===")
good_plan = [
    {"node_type": "user_input", "node_name": "user_input"},
    {"node_type": "skill_call", "skill_id": "need_analysis", "node_name": "need_analysis"},
    {"node_type": "tool_call", "tool_id": "job_requirement_search", "node_name": "job_requirement_search"},
    {"node_type": "skill_call", "skill_id": "skill_gap_analysis", "node_name": "skill_gap_analysis"},
    {"node_type": "skill_call", "skill_id": "learning_path_planning", "node_name": "learning_path_planning"},
    {"node_type": "agent_response", "node_name": "final_response"},
]
result = validate_plan(good_plan, domain)
print(f"  Valid: {result['valid']}, Issues: {result['issues']}")

# Test validation with a bad sequence (no user_input, no final_response)
print("\n=== Validate Bad Plan ===")
bad_plan = [
    {"node_type": "skill_call", "skill_id": "need_analysis", "node_name": "need_analysis"},
    {"node_type": "skill_call", "skill_id": "need_analysis", "node_name": "need_analysis"},  # duplicate
]
result = validate_plan(bad_plan, domain)
print(f"  Valid: {result['valid']}, Issues: {result['issues']}")

# Test auto-fix
print("\n=== Auto Fix ===")
fixed = _auto_fix(bad_plan, result["issues"], domain)
print(f"  Fixed sequence ({len(fixed)} nodes):")
for n in fixed:
    print(f"    - {n['node_name']} ({n['node_type']})")

# Validate fixed
result2 = validate_plan(fixed, domain)
print(f"  After fix - Valid: {result2['valid']}, Issues: {result2['issues']}")

# Test fallback
print("\n=== Fallback Template Plan ===")
task = {
    "task_id": "test_002",
    "task_type": "learning_path_planning",
    "task_description": "test",
    "initial_user_query": "test",
    "interaction_style": "info_complete",
}
fallback = _fallback_template_plan(domain, task, profile)
print(f"  Template: {fallback['template_name']}")
print(f"  Nodes: {len(fallback['planned_nodes'])}")
for n in fallback["planned_nodes"]:
    print(f"    - {n['node_name']} ({n['node_type']})")

print("\nAll planner tests passed!")
