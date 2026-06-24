"""Step B: mock_tools 应根据输入参数返回不同内容。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "trajectory_generator"))

from src.mock_tools import mock_tool_call


class TestJobRequirementSearch:
    def test_returns_expected_keys(self):
        r = mock_tool_call("job_requirement_search", {"job_title": "后端工程师", "seniority": "senior"})
        assert "required_skills" in r
        assert "experience_years" in r
        assert isinstance(r["required_skills"], list)

    def test_senior_vs_junior_differ(self):
        senior = mock_tool_call("job_requirement_search", {"job_title": "后端工程师", "seniority": "senior"})
        junior = mock_tool_call("job_requirement_search", {"job_title": "后端工程师", "seniority": "junior"})
        assert senior["required_skills"] != junior["required_skills"]


class TestInterviewQuestionSearch:
    def test_returns_expected_keys(self):
        r = mock_tool_call("interview_question_search", {"role": "后端", "category": "system_design", "difficulty": "medium"})
        assert "questions" in r
        assert "preparation_tips" in r
        assert isinstance(r["questions"], list)

    def test_different_categories_return_different_questions(self):
        r1 = mock_tool_call("interview_question_search", {"role": "后端", "category": "system_design",  "difficulty": "medium"})
        r2 = mock_tool_call("interview_question_search", {"role": "后端", "category": "behavioral",     "difficulty": "medium"})
        r3 = mock_tool_call("interview_question_search", {"role": "后端", "category": "algorithm",      "difficulty": "medium"})
        # 三种类别的题目内容不同
        assert r1["questions"] != r2["questions"]
        assert r1["questions"] != r3["questions"]

    def test_difficulty_affects_output(self):
        easy   = mock_tool_call("interview_question_search", {"role": "后端", "category": "algorithm", "difficulty": "easy"})
        hard   = mock_tool_call("interview_question_search", {"role": "后端", "category": "algorithm", "difficulty": "hard"})
        assert easy["questions"] != hard["questions"]


class TestSalaryBenchmarkSearch:
    def test_returns_expected_keys(self):
        r = mock_tool_call("salary_benchmark_search", {"role": "后端工程师", "seniority": "senior", "region": "北京"})
        assert "salary_range" in r
        assert "median" in r["salary_range"]

    def test_senior_higher_than_junior(self):
        senior = mock_tool_call("salary_benchmark_search", {"role": "后端工程师", "seniority": "senior", "region": "北京"})
        junior = mock_tool_call("salary_benchmark_search", {"role": "后端工程师", "seniority": "junior", "region": "北京"})
        assert senior["salary_range"]["median"] > junior["salary_range"]["median"]


class TestTechTrendSearch:
    def test_returns_expected_keys(self):
        r = mock_tool_call("tech_trend_search", {"technology": "Rust", "aspect": "demand"})
        assert "trend_summary" in r
        assert "market_demand" in r

    def test_different_technologies_differ(self):
        rust = mock_tool_call("tech_trend_search", {"technology": "Rust",   "aspect": "demand"})
        java = mock_tool_call("tech_trend_search", {"technology": "Java",   "aspect": "demand"})
        assert rust["trend_summary"] != java["trend_summary"]


class TestUnknownTool:
    def test_returns_error_key(self):
        r = mock_tool_call("nonexistent_tool", {})
        assert "error" in r
