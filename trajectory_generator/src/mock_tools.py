"""
Mock Tool Executor - 模拟工具调用返回结果

在轨迹生成阶段，工具调用由 LLM 模拟生成合理的返回结果，
而不是真正调用外部 API。
"""
from __future__ import annotations

from typing import Any


# 预定义的 mock 数据，用于不调用 LLM 时的快速返回
MOCK_RESPONSES: dict[str, dict[str, Any]] = {
    "job_requirement_search": {
        "前端开发工程师": {
            "required_skills": ["JavaScript", "React/Vue", "TypeScript", "HTML/CSS", "HTTP协议", "Git"],
            "preferred_skills": ["Node.js", "Webpack/Vite", "性能优化", "CI/CD"],
            "experience_years": "1-3年",
            "typical_projects": ["SPA应用开发", "组件库建设", "性能优化", "移动端适配"],
        },
        "Python后端开发工程师": {
            "required_skills": ["Python", "Django/FastAPI", "SQL", "Linux", "Git", "HTTP/REST"],
            "preferred_skills": ["Docker", "Redis", "消息队列", "微服务"],
            "experience_years": "1-3年",
            "typical_projects": ["RESTful API开发", "数据库设计", "后台管理系统", "自动化脚本"],
        },
        "全栈开发工程师": {
            "required_skills": ["JavaScript/TypeScript", "React/Vue", "Node.js", "SQL", "Git", "Docker"],
            "preferred_skills": ["Go/Python", "Redis", "CI/CD", "云服务", "系统设计"],
            "experience_years": "3-5年",
            "typical_projects": ["全链路产品开发", "微服务架构", "性能优化", "团队协作"],
        },
        "后端架构师": {
            "required_skills": ["Java/Go", "分布式系统", "微服务架构", "数据库设计", "系统设计", "Kubernetes"],
            "preferred_skills": ["性能调优", "容量规划", "技术选型", "团队管理"],
            "experience_years": "7-10年",
            "typical_projects": ["系统架构设计", "中间件开发", "高可用方案", "技术评审"],
        },
        "Rust Systems Engineer": {
            "required_skills": ["Rust", "系统编程", "并发编程", "Linux", "性能优化"],
            "preferred_skills": ["C/C++", "WebAssembly", "分布式系统", "开源贡献"],
            "experience_years": "5-8年",
            "typical_projects": ["数据库引擎", "运行时开发", "网络框架", "嵌入式系统"],
        },
    },
    "tech_trend_search": {
        "React": {
            "trend_summary": "React 仍然是前端框架第一选择，2025年 React Server Components 成为主流",
            "market_demand": "高",
            "salary_range": "15K-45K (视城市和级别)",
            "growth_outlook": "稳定增长，生态成熟",
        },
        "Rust": {
            "trend_summary": "Rust 在系统编程、WebAssembly、区块链领域增长迅速，但岗位总量仍小于 Go/Java",
            "market_demand": "中等偏高，海外远程岗位较多",
            "salary_range": "30K-80K (国内少，海外 $150K-$250K)",
            "growth_outlook": "快速增长，被 Linux 内核采纳是里程碑",
        },
        "Go": {
            "trend_summary": "Go 在云原生和微服务领域占主导地位",
            "market_demand": "高",
            "salary_range": "20K-50K",
            "growth_outlook": "稳定，是后端开发主流选择之一",
        },
    },
    "course_resource_search": {
        "_default": {
            "resources": [
                {"name": "官方文档", "type": "text", "difficulty": "varies", "estimated_hours": 20, "rating": 4.5},
                {"name": "实战课程", "type": "video", "difficulty": "intermediate", "estimated_hours": 40, "rating": 4.3},
                {"name": "开源项目源码", "type": "code", "difficulty": "advanced", "estimated_hours": 60, "rating": 4.7},
            ]
        }
    },
    "project_repository_search": {
        "_default": {
            "projects": [
                {"name": "Todo App", "difficulty": "beginner", "estimated_hours": 10, "learning_outcomes": ["基础CRUD", "状态管理"]},
                {"name": "Blog System", "difficulty": "intermediate", "estimated_hours": 30, "learning_outcomes": ["认证授权", "数据库设计", "部署"]},
                {"name": "Real-time Chat", "difficulty": "intermediate", "estimated_hours": 40, "learning_outcomes": ["WebSocket", "并发处理", "消息存储"]},
            ]
        }
    },
    "interview_question_search": {
        "_default": {
            "questions": [
                {"question": "请描述一次你解决复杂技术问题的经历", "category": "behavioral", "difficulty": "medium", "frequency": "high"},
                {"question": "设计一个短链接系统", "category": "system_design", "difficulty": "medium", "frequency": "high"},
                {"question": "LRU Cache 实现", "category": "algorithm", "difficulty": "medium", "frequency": "high"},
            ],
            "preparation_tips": ["STAR 格式组织行为面试回答", "系统设计先澄清需求再画架构", "算法题先说思路再写代码"]
        }
    },
    "salary_benchmark_search": {
        "_default": {
            "salary_range": {"min": 15000, "median": 25000, "max": 50000},
            "currency": "CNY",
            "data_source": "aggregated from major job platforms 2025",
        }
    },
    "knowledge_graph_query": {
        "_default": {
            "dependencies": [
                {"skill": "基础语法", "relation": "prerequisite", "is_required": True},
                {"skill": "数据结构", "relation": "prerequisite", "is_required": True},
                {"skill": "项目实践", "relation": "application", "is_required": False},
            ],
            "learning_order": ["基础语法", "数据结构", "框架入门", "项目实践", "进阶优化"]
        }
    },
}


def mock_tool_call(tool_id: str, input_params: dict[str, Any]) -> dict[str, Any]:
    """
    Return mock data for a tool call.
    First tries exact match by key fields, then falls back to _default.
    """
    tool_data = MOCK_RESPONSES.get(tool_id, {})

    # Try matching by primary input field
    for key, value in input_params.items():
        if isinstance(value, str) and value in tool_data:
            return tool_data[value]

    # Fallback to _default
    if "_default" in tool_data:
        return tool_data["_default"]

    # Generic fallback
    return {"result": "mock data not available", "tool_id": tool_id, "input": input_params}
