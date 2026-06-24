"""
Domain Manager - 加载领域配置
"""
from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DomainSpec:
    domain_id: str
    domain_name: str
    description: str
    task_types: list[str]
    supported_interaction_modes: list[str]


@dataclass
class SkillSpec:
    skill_id: str
    name: str
    type: str
    description: str
    inputs: list[str]
    outputs: list[str]
    preconditions: list[str]
    postconditions: list[str]
    possible_next_skills: list[str]


@dataclass
class ToolSpec:
    tool_id: str
    name: str
    description: str
    input_schema: dict[str, str]
    output_schema: dict[str, Any]
    failure_modes: list[str]


@dataclass
class Domain:
    spec: DomainSpec
    skills: list[SkillSpec]
    tools: list[ToolSpec]
    knowledge_base: dict[str, Any]
    trajectory_templates: list[dict]
    user_profiles: list[dict]


def load_domain(domain_dir: Path, personas_dir: Path) -> Domain:
    """Load all domain configuration from directory."""

    # Domain spec
    with open(domain_dir / "domain_spec.json", "r", encoding="utf-8") as f:
        spec_data = json.load(f)
    spec = DomainSpec(**spec_data)

    # Skills
    with open(domain_dir / "skills.json", "r", encoding="utf-8") as f:
        skills_data = json.load(f)
    skills = [SkillSpec(**s) for s in skills_data]

    # Tools
    with open(domain_dir / "tools.json", "r", encoding="utf-8") as f:
        tools_data = json.load(f)
    tools = [ToolSpec(**t) for t in tools_data]

    # Knowledge base
    with open(domain_dir / "knowledge_base.json", "r", encoding="utf-8") as f:
        knowledge_base = json.load(f)

    # Trajectory templates
    with open(domain_dir / "trajectory_templates.json", "r", encoding="utf-8") as f:
        trajectory_templates = json.load(f)

    # User profiles from personas directory
    user_profiles = []
    if personas_dir.exists():
        for p in sorted(personas_dir.glob("*.json")):
            with open(p, "r", encoding="utf-8") as f:
                user_profiles.append(json.load(f))

    return Domain(
        spec=spec,
        skills=skills,
        tools=tools,
        knowledge_base=knowledge_base,
        trajectory_templates=trajectory_templates,
        user_profiles=user_profiles,
    )
