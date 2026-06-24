# 多轮轨迹生成改造记录

## 背景

原始系统只能生成**单轮**轨迹（一次用户输入 → agent 处理 → 最终回复），节点平铺为一个列表。  
本次改造将其升级为**多轮对话**轨迹，具备真实交互性：用户的后续输入会对 agent 上一轮输出产生反应。

---

## 核心变化

### 数据结构

```
旧：trajectory → nodes: [user_input, skill, tool, ..., agent_response]

新：trajectory → turns: [
      turn1: { user_message, processing_nodes[], agent_response },
      turn2: { user_message(↑响应 turn1 输出), processing_nodes[], agent_response },
      ...
    ]
```

### 新增 Blueprint（替换 task dict）

```json
{
  "task_id": "...",
  "initial_user_query": "...",
  "interaction_style": "偏好强烈型",
  "goal": "用户经过 N 轮交互，最终获得...",
  "conversation_arc": [
    { "turn": 1, "trigger": "initial_request",   "description": "用户发起请求" },
    { "turn": 2, "trigger": "constraint_update",  "description": "用户将时间从 15h 改为 8h" },
    { "turn": 3, "trigger": "clarification",      "description": "用户追问系统设计练习方式" }
  ]
}
```

Trigger 类型：`initial_request` / `constraint_update` / `clarification` / `plan_revision` / `pushback`

---

## 模块改动

| 模块 | 操作 | 说明 |
|------|------|------|
| `src/schema.py` | 新增 | ArcTurn、Blueprint、ConversationTurn、MultiTurnTrajectory |
| `src/conversation_state.py` | 新增 | 跨轮状态：history、established_facts、last_agent_response |
| `src/task_generator.py` | 重构 | `generate_blueprint()` 生成含 conversation_arc 的蓝图 |
| `src/planner.py` | 增加 | `plan_multi_turn()` 按轮次分别规划节点序列 |
| `src/generator.py` | 增加 | `generate_multi_turn_trajectory()` 多轮生成主函数 |
| `src/mock_tools.py` | 增强 | 输出随 seniority/category/difficulty/technology 参数变化 |
| `generate.py` | 改造 | 主流程改为 blueprint → plan_multi_turn → generate_multi_turn_trajectory |

---

## 生成流程

```
1. generate_blueprint(domain, persona)
   → LLM 生成 initial_user_query + conversation_arc

2. plan_multi_turn(domain, blueprint, profile)
   → 按每个 arc_turn 的 trigger 类型，规划该轮的 processing_nodes 序列
   → use_llm=True: LLM 规划；use_llm=False: 静态 trigger→template 映射（用于测试）

3. generate_multi_turn_trajectory(plan, domain)
   → Turn 1: user_message = initial_user_query
   → Turn N>1: LLM 根据上一轮 agent_response + trigger 生成 user_message
   → 每轮逐节点执行（skill_call 用 LLM，tool_call 用参数敏感 mock）
   → 每轮结束生成 agent_response，更新 ConversationState
```

---

## 测试覆盖

```
tests/
├── conftest.py                   # fixtures
├── test_schema.py                # 12 cases — 数据结构约束
├── test_mock_tools.py            # 10 cases — 参数敏感性
├── test_blueprint.py             # 11 cases — Blueprint 生成（6 结构 + 5 LLM）
├── test_planner_multi.py         # 10 cases — 多轮规划（8 结构 + 2 LLM）
├── test_conversation_state.py    # 9 cases  — 状态追踪
└── test_generator_multi.py       # 12 cases — 多轮生成（9 结构 + 3 LLM）
```

非 LLM 测试（54 个）可随时运行：`pytest tests/ -m "not llm"`  
LLM 测试需要 API key：`pytest tests/ -m llm`

---

## 待完成

- [ ] 评估模块（节点级 / 边级 / 轨迹级评估 + 错误标签）
- [ ] 多 domain 扩展（目前只有 code_development）
- [ ] 真实工具接入（目前全部 mock）
- [ ] 数据质量筛选与导出管线
