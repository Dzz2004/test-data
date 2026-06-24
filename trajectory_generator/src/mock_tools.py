"""
Mock Tool Executor - 参数敏感的工具调用模拟

输出随关键输入参数变化，保证同一工具不同参数返回不同结果。
"""
from __future__ import annotations
from typing import Any


# ── job_requirement_search ─────────────────────────────────────────────────────

_JOB_BY_SENIORITY = {
    "junior": {
        "required_skills": ["编程语言基础", "数据结构与算法", "Git", "SQL基础", "HTTP/REST"],
        "preferred_skills": ["Docker入门", "单元测试", "Linux基础"],
        "experience_years": "0-2年",
        "typical_projects": ["CRUD应用", "个人项目", "开源贡献"],
    },
    "mid": {
        "required_skills": ["主流语言熟练(Java/Go/Python)", "数据库设计", "微服务基础", "Docker", "系统设计基础"],
        "preferred_skills": ["Redis", "消息队列", "CI/CD", "性能优化"],
        "experience_years": "3-5年",
        "typical_projects": ["业务系统开发", "接口性能优化", "模块架构设计"],
    },
    "senior": {
        "required_skills": ["分布式系统", "微服务架构", "高可用设计", "Kubernetes", "数据库调优", "系统设计"],
        "preferred_skills": ["性能容量规划", "技术选型", "团队技术 review", "跨团队协作"],
        "experience_years": "7年以上",
        "typical_projects": ["系统架构设计", "中间件开发", "高可用改造", "技术规范制定"],
    },
}

# ── interview_question_search ──────────────────────────────────────────────────

_INTERVIEW_QUESTIONS = {
    "system_design": {
        "easy":   [{"question": "设计一个 URL 短链接服务",           "category": "system_design", "difficulty": "easy",   "frequency": "high"}],
        "medium": [{"question": "设计一个支持百万 QPS 的消息推送系统", "category": "system_design", "difficulty": "medium", "frequency": "high"},
                   {"question": "设计分布式限流器",                   "category": "system_design", "difficulty": "medium", "frequency": "medium"}],
        "hard":   [{"question": "设计 Google Spanner 的事务模型",     "category": "system_design", "difficulty": "hard",   "frequency": "low"},
                   {"question": "设计支持全球一致性的分布式 KV 存储",  "category": "system_design", "difficulty": "hard",   "frequency": "medium"}],
    },
    "behavioral": {
        "easy":   [{"question": "介绍一个你做过的项目",               "category": "behavioral", "difficulty": "easy",   "frequency": "high"}],
        "medium": [{"question": "描述一次与团队产生分歧并最终解决的经历", "category": "behavioral", "difficulty": "medium", "frequency": "high"},
                   {"question": "讲述一次项目 deadline 紧张下的应对",   "category": "behavioral", "difficulty": "medium", "frequency": "high"}],
        "hard":   [{"question": "描述一次你推动了重大技术决策并带来业务影响的经历", "category": "behavioral", "difficulty": "hard", "frequency": "medium"}],
    },
    "algorithm": {
        "easy":   [{"question": "反转链表",           "category": "algorithm", "difficulty": "easy",   "frequency": "high"},
                   {"question": "二叉树层序遍历",      "category": "algorithm", "difficulty": "easy",   "frequency": "high"}],
        "medium": [{"question": "LRU Cache 实现",      "category": "algorithm", "difficulty": "medium", "frequency": "high"},
                   {"question": "最长公共子序列",       "category": "algorithm", "difficulty": "medium", "frequency": "medium"}],
        "hard":   [{"question": "正则表达式匹配",      "category": "algorithm", "difficulty": "hard",   "frequency": "medium"},
                   {"question": "接雨水（二维扩展）",   "category": "algorithm", "difficulty": "hard",   "frequency": "low"}],
    },
    "domain_specific": {
        "easy":   [{"question": "解释 HTTP 和 HTTPS 的区别",       "category": "domain_specific", "difficulty": "easy",   "frequency": "high"}],
        "medium": [{"question": "JVM 的 GC 算法有哪些，如何调优",   "category": "domain_specific", "difficulty": "medium", "frequency": "high"},
                   {"question": "解释 CAP 定理并举例",              "category": "domain_specific", "difficulty": "medium", "frequency": "high"}],
        "hard":   [{"question": "描述 Raft 一致性协议的 leader election 过程", "category": "domain_specific", "difficulty": "hard", "frequency": "medium"}],
    },
}

_INTERVIEW_TIPS = {
    "system_design":   ["先澄清规模和约束", "从高层设计到细节", "主动讨论 trade-off"],
    "behavioral":      ["用 STAR 格式组织回答", "关注自身贡献而非团队", "提前准备 3-5 个核心故事"],
    "algorithm":       ["先说思路再写代码", "考虑边界情况", "分析时间空间复杂度"],
    "domain_specific": ["结合实际项目经验回答", "承认不确定的部分", "展示持续学习的意识"],
}

# ── salary_benchmark_search ────────────────────────────────────────────────────

_SALARY_BY_SENIORITY = {
    "junior": {"min": 8000,  "median": 14000, "max": 22000},
    "mid":    {"min": 18000, "median": 30000, "max": 45000},
    "senior": {"min": 35000, "median": 55000, "max": 90000},
}

# ── tech_trend_search ──────────────────────────────────────────────────────────

_TECH_TRENDS = {
    "Rust": {
        "trend_summary":  "Rust 在系统编程和 WebAssembly 领域增长迅速，被 Linux 内核和 Android 采纳，海外远程岗位多",
        "market_demand":  "中等偏高，海外需求显著大于国内",
        "salary_range":   "国内 30K-70K，海外远程 $150K-$250K",
        "growth_outlook": "快速增长，未来五年将进入主流",
    },
    "Java": {
        "trend_summary":  "Java 是国内后端开发第一大语言，大厂和金融行业需求稳定",
        "market_demand":  "极高",
        "salary_range":   "15K-60K（视城市和级别）",
        "growth_outlook": "稳定，Spring 生态持续演进",
    },
    "Go": {
        "trend_summary":  "Go 在云原生和微服务领域占主导，字节、腾讯等大厂大量使用",
        "market_demand":  "高",
        "salary_range":   "20K-55K",
        "growth_outlook": "稳定增长，K8s/Docker 生态加持",
    },
    "Python": {
        "trend_summary":  "Python 受 AI/ML 爆发驱动需求大增，数据工程和 LLM 应用开发热门",
        "market_demand":  "极高",
        "salary_range":   "15K-50K（AI 方向溢价 20-40%）",
        "growth_outlook": "持续增长，AI 方向尤为强劲",
    },
    "TypeScript": {
        "trend_summary":  "TypeScript 已成为前端开发标配，全栈项目采用率超过 70%",
        "market_demand":  "高",
        "salary_range":   "15K-45K",
        "growth_outlook": "稳定，React/Next.js 生态推动",
    },
}

_TECH_TRENDS_DEFAULT = {
    "trend_summary":  "该技术正处于活跃发展阶段，市场关注度上升",
    "market_demand":  "中等",
    "salary_range":   "视具体岗位和地区而定",
    "growth_outlook": "数据不足，建议关注社区动态",
}

# ── knowledge_graph_query ──────────────────────────────────────────────────────

_KNOWLEDGE_GRAPH_DEFAULT = {
    "dependencies": [
        {"skill": "编程基础",   "relation": "prerequisite", "is_required": True},
        {"skill": "数据结构",   "relation": "prerequisite", "is_required": True},
        {"skill": "项目实践",   "relation": "application",  "is_required": False},
    ],
    "learning_order": ["编程基础", "数据结构与算法", "框架入门", "项目实践", "进阶优化"],
}

# ── 主入口 ─────────────────────────────────────────────────────────────────────

def mock_tool_call(tool_id: str, input_params: dict[str, Any]) -> dict[str, Any]:
    """Return parameter-sensitive mock data for a tool call."""

    if tool_id == "job_requirement_search":
        seniority = input_params.get("seniority", "mid").lower()
        data = _JOB_BY_SENIORITY.get(seniority, _JOB_BY_SENIORITY["mid"]).copy()
        job_title = input_params.get("job_title", "")
        if job_title:
            data["job_title"] = job_title
        return data

    if tool_id == "interview_question_search":
        category  = input_params.get("category", "system_design")
        difficulty = input_params.get("difficulty", "medium")
        cat_data   = _INTERVIEW_QUESTIONS.get(category, _INTERVIEW_QUESTIONS["system_design"])
        questions  = cat_data.get(difficulty, cat_data.get("medium", []))
        tips       = _INTERVIEW_TIPS.get(category, _INTERVIEW_TIPS["system_design"])
        return {"questions": questions, "preparation_tips": tips}

    if tool_id == "salary_benchmark_search":
        seniority = input_params.get("seniority", "mid").lower()
        salary    = _SALARY_BY_SENIORITY.get(seniority, _SALARY_BY_SENIORITY["mid"])
        return {
            "salary_range": salary,
            "currency": "CNY",
            "data_source": "aggregated from major job platforms 2025",
        }

    if tool_id == "tech_trend_search":
        tech = input_params.get("technology", "")
        return _TECH_TRENDS.get(tech, _TECH_TRENDS_DEFAULT).copy()

    if tool_id == "course_resource_search":
        skill = input_params.get("skill_name", "通用技能")
        diff  = input_params.get("difficulty", "intermediate")
        return {
            "resources": [
                {"name": f"{skill} 官方文档",    "type": "text",  "difficulty": diff,            "estimated_hours": 15, "rating": 4.5},
                {"name": f"{skill} 视频课程",    "type": "video", "difficulty": diff,            "estimated_hours": 30, "rating": 4.3},
                {"name": f"{skill} 实战项目示例", "type": "code",  "difficulty": "advanced",      "estimated_hours": 20, "rating": 4.6},
            ]
        }

    if tool_id == "project_repository_search":
        stack = input_params.get("tech_stack", [])
        stack_label = "/".join(stack[:2]) if stack else "通用"
        return {
            "projects": [
                {"name": f"{stack_label} CRUD 应用",  "difficulty": "beginner",     "estimated_hours": 10, "learning_outcomes": ["基础增删改查", "路由设计"]},
                {"name": f"{stack_label} 博客系统",   "difficulty": "intermediate", "estimated_hours": 25, "learning_outcomes": ["用户认证", "数据库设计", "部署"]},
                {"name": f"{stack_label} 实时聊天室",  "difficulty": "intermediate", "estimated_hours": 35, "learning_outcomes": ["WebSocket", "并发处理", "消息持久化"]},
            ]
        }

    if tool_id == "knowledge_graph_query":
        target = input_params.get("target_skill", "")
        result = _KNOWLEDGE_GRAPH_DEFAULT.copy()
        if target:
            result["target_skill"] = target
        return result

    return {"error": f"unknown tool: {tool_id}", "tool_id": tool_id}
