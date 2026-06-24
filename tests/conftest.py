"""Shared fixtures for all tests."""
import pytest
from pathlib import Path

DOMAIN_DIR = Path(__file__).parent.parent / "trajectory_generator" / "domain" / "code_development"
PERSONAS_DIR = Path(__file__).parent.parent / "personas"


@pytest.fixture(scope="session")
def domain():
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "trajectory_generator"))
    from src.domain import load_domain
    return load_domain(DOMAIN_DIR, PERSONAS_DIR)


@pytest.fixture
def sample_persona():
    import json
    p = PERSONAS_DIR / "senior-backend-job-hopping.json"
    with open(p, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_arc():
    from trajectory_generator.src.schema import ArcTurn
    return [
        ArcTurn(turn=1, trigger="initial_request",    description="用户发起面试规划请求"),
        ArcTurn(turn=2, trigger="constraint_update",  description="用户将每周时间从15h改为8h"),
        ArcTurn(turn=3, trigger="clarification",      description="用户追问系统设计如何练习"),
    ]
