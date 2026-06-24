# Agent 多轮轨迹生成器

基于用户画像和领域配置，合成带有真实交互性的**多轮对话 agent 轨迹**数据集。
当前领域：`code_development`（代码开发工程师职业规划）。

---

## 目录结构

```
trajectory_generator/
├── generate.py                         # 主入口
├── requirements.txt                    # Python 依赖（openai）
├── domain/
│   └── code_development/
│       ├── domain_spec.json            # 领域定义（任务类型、交互模式）
│       ├── skills.json                 # Skill 池（12 个推理技能）
│       ├── tools.json                  # Tool 池（7 个外部工具）
│       ├── knowledge_base.json         # 领域知识库
│       └── trajectory_templates.json   # 6 种场景模板（fallback 用）
├── src/
│   ├── schema.py                       # 数据结构：ArcTurn / Blueprint / ConversationTurn / MultiTurnTrajectory
│   ├── domain.py                       # Domain 配置加载
│   ├── llm_client.py                   # LLM 调用（OpenAI 兼容接口）
│   ├── mock_tools.py                   # 参数敏感的工具 mock
│   ├── conversation_state.py           # 跨轮状态追踪
│   ├── task_generator.py               # Blueprint 生成（含 conversation_arc）
│   ├── planner.py                      # 多轮轨迹规划
│   └── generator.py                    # 多轮轨迹内容生成
└── output/
    ├── trajectories.jsonl              # 所有轨迹（每行一条）
    └── individual/                     # 每条轨迹单独 JSON
```

---

## 快速开始

```bash
cd test-data/trajectory_generator

# 安装依赖
pip install -r requirements.txt

# 确保 ../.env.json 中配置了 LLM 接口
# 生成 3 条轨迹（默认）
python generate.py

# 生成 10 条
python generate.py --num 10 --output ./output/batch1
```

---

## 生成流程

```
personas/*.json
      │
      ▼
1. generate_blueprint()         — LLM 生成初始请求 + conversation_arc（2-4 轮剧本）
      │
      ▼
2. plan_multi_turn()            — 按每轮 trigger 类型规划 processing_nodes 序列
      │
      ▼
3. generate_multi_turn_trajectory()
      │
      ├─ Turn 1: user_message = initial_user_query
      │          → 执行 skill_call（LLM）/ tool_call（mock）
      │          → 生成 agent_response
      │          → 更新 ConversationState
      │
      ├─ Turn N: user_message = LLM 根据上轮 agent_response + trigger 生成
      │          → 执行节点（同上）
      │          → 生成 agent_response（引用本轮分析结果）
      │          → 更新 ConversationState
      │
      └─ 输出 MultiTurnTrajectory
```

---

## 输出格式

```json
{
  "trajectory_id": "traj_task_senior-backend_4365_220",
  "domain": "code_development",
  "user_profile": { "currentRole": "后端技术专家（P7）", "targetRole": "后端架构师", ... },
  "task": {
    "task_type": "learning-plan",
    "initial_user_query": "我想规划一下未来三个月的学习路径...",
    "interaction_style": "偏好强烈型",
    "goal": "用户经过 4 轮交互，最终获得一份学习路径规划方案",
    "conversation_arc": [
      { "turn": 1, "trigger": "initial_request",  "description": "用户发起请求" },
      { "turn": 2, "trigger": "pushback",          "description": "用户质疑优先级排序" },
      { "turn": 3, "trigger": "constraint_update", "description": "用户补充时间约束" },
      { "turn": 4, "trigger": "clarification",     "description": "用户追问面试软技能" }
    ]
  },
  "turns": [
    {
      "turn_id": 1,
      "trigger": "initial_request",
      "user_message": "我想规划一下未来三个月的学习路径...",
      "processing_nodes": [
        { "node_type": "skill_call", "skill_id": "need_analysis",       "output": {...}, "rationale": "..." },
        { "node_type": "tool_call",  "tool_id":  "job_requirement_search","input": {...}, "output": {...} },
        ...
      ],
      "agent_response": "基于你的背景和目标，下面是 12 周的学习路径..."
    },
    {
      "turn_id": 2,
      "trigger": "pushback",
      "user_message": "我觉得这个优先级有问题，大规模数据架构应该先搞...",
      "processing_nodes": [ ... ],
      "agent_response": "你说得对，调整优先级..."
    }
  ],
  "evaluation": null
}
```

---

## LLM 配置

`test-data/.env.json`：

```json
{
  "llm": {
    "baseUrl": "https://api.deepseek.com/v1",
    "apiKey": "sk-xxxxx",
    "model": "deepseek-chat"
  }
}
```

---

## 测试

```bash
# 非 LLM 测试（无需 API key，54 个用例）
pytest tests/ -m "not llm"

# LLM 集成测试（需要 API key）
pytest tests/ -m llm
```
