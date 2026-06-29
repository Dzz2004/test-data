# 多轮轨迹生成改造记录

## 背景

原始系统只能生成**单轮**轨迹（一次用户输入 → agent 处理 → 最终回复），节点平铺为一个列表。  
本次改造将其升级为**多轮对话**轨迹，具备真实交互性：用户的后续输入会对 agent 上一轮输出产生反应。

---

## 核心理念

### 我们在造什么数据

这份数据是**未来 agent 的 loop 流程的模拟轨迹**。它不是普通的问答记录，而是展示 agent 如何一步步做决策的完整过程：

- agent 在每个节点执行之前，先经过一轮**规划-评估**的内部思考
- 规划的目标是"下一步对用户最有帮助的是什么"，而非"系统流程规定下一步是什么"
- 评估的目标是"这个规划真的对用户有帮助吗"，而非"规划是否符合系统规则"

这个规划-评估的来回交互过程（`planning_trace`）被完整记录在每个节点里，是数据的核心价值所在。

### 规划与评估的视角

**错误视角（系统规则视角）：**
- "这个节点 ID 存在吗？"
- "工具有没有重复调用？"
- "inputs 是否非空？"

**正确视角（用户需求视角）：**
- "用户现在最需要什么信息或分析？"
- "这一步做完之后，用户的问题会向前推进吗？"
- "inputs 是否真实反映了当前已知的上下文，而非空洞的占位符？"
- "有没有更重要的事情应该先做？"

---

## 数据结构

```
旧：trajectory → nodes: [user_input, skill, tool, ..., agent_response]

新：trajectory → turns: [
      turn1: {
        user_message,
        processing_nodes: [
          {
            node_type, name, skill_id/tool_id, input, output, rationale,
            planning_trace: [
              { attempt, plan, eval, accepted },  ← 每次规划-评估的记录
              ...
            ]
          },
          ...
        ],
        agent_response
      },
      ...
    ]
```

### planning_trace 结构

```json
{
  "planning_trace": [
    {
      "attempt": 1,
      "plan": {
        "node_type": "skill_call",
        "node_id":   "plan_revision",
        "node_name": "plan_revision",
        "inputs":    { "context": "用户的基本背景", "goal": "用户目标" },
        "rationale": "初步规划：对 plan_revision 做一次分析"
      },
      "eval": {
        "pass":        false,
        "rationale":   "inputs 没有反映用户本轮更新的约束，plan_revision 的分析会脱离当前实际情况",
        "suggestions": ["将用户本轮的关键信息明确写入 inputs，使分析更有针对性"]
      },
      "accepted": false
    },
    {
      "attempt": 2,
      "plan": {
        "node_type": "skill_call",
        "node_id":   "plan_revision",
        "inputs":    { "trigger": "constraint_update", "available_hours": 50, "...": "..." },
        "rationale": "根据用户更新的约束重新调整方案，确保规划与实际情况匹配"
      },
      "eval": {
        "pass":        true,
        "rationale":   "这一步能有效推进用户的需求，inputs 包含了足够的上下文",
        "suggestions": []
      },
      "accepted": true
    }
  ]
}
```

### Blueprint（任务蓝图）

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

## Agent Loop 执行链路

```
for each turn:
  user_message
    ↓
  while 本轮节点数 < MAX_NODES_PER_TURN:
    ┌─────────────────────────────────────────────┐
    │  小模型规划（plan_next_node）                │
    │  → 思考：用户现在最需要什么？               │
    │  → 输出：node_type, node_id, inputs,        │
    │          rationale, is_terminal             │
    └──────────────────┬──────────────────────────┘
                       │ plan
    ┌──────────────────▼──────────────────────────┐
    │  小模型评估（evaluate_node_plan）            │
    │  → 判断：这步对用户有帮助吗？inputs 充实吗？│
    │  → 输出：pass, rationale, suggestions       │
    └──────────┬──────────────┬───────────────────┘
               │ pass=True    │ pass=False（最多 MAX_PLAN_ITER 次）
               │              │
               │   feedback = 被拒方案 + 原因 + 建议
               │              └──────────────► 回到规划，附带 feedback
               ↓
    大模型执行节点（skill_call / tool_call）
    → 节点挂载 planning_trace（本次所有 attempt 记录）
    → 更新 ConversationState（下一轮规划可读到此节点输出）
```

**关键设计：**
- `feedback` 传回规划器时，包含**被拒方案本体** + 评估原因 + 改进建议（不只是原因字符串）
- feedback 在 planner prompt 里是**最显眼的第一个 section**，LLM 无法忽略
- 某些 trigger（`constraint_update`、`pushback`、`plan_revision`）下，节点的规划更容易需要 2 轮才通过，体现约束变化下的来回推敲
- `is_terminal=True` 且本轮无节点时，有安全保底机制防止空轮

---

## 模块说明

| 模块 | 操作 | 说明 |
|------|------|------|
| `src/schema.py` | 新增 | ArcTurn、Blueprint、ConversationTurn、MultiTurnTrajectory |
| `src/conversation_state.py` | 新增 | 跨轮 + 节点级状态追踪；`get_planning_context()` 为规划提供结构化上下文 |
| `src/node_planner.py` | 新增 | `plan_next_node()` — 小模型从用户需求视角规划下一节点 |
| `src/node_evaluator.py` | 新增 | `evaluate_node_plan()` — 小模型从用户价值视角评估规划质量 |
| `src/task_generator.py` | 重构 | `generate_blueprint()` 生成含 conversation_arc 的蓝图 |
| `src/planner.py` | 增加 | `plan_multi_turn()` 按轮次分别规划节点序列（用于静态 fallback） |
| `src/generator.py` | 增加 | `generate_multi_turn_trajectory()` — 动态规划-评估-执行主循环 |
| `src/mock_tools.py` | 增强 | 输出随 seniority/category/difficulty/technology 参数变化 |
| `generate.py` | 改造 | 主流程：blueprint → plan_multi_turn → generate_multi_turn_trajectory |

---

## 生成流程

```
1. generate_blueprint(domain, persona)
   → LLM 生成 initial_user_query + conversation_arc

2. plan_multi_turn(domain, blueprint, profile)
   → 按每个 arc_turn 的 trigger 类型，提供静态 fallback 节点序列（测试用）
   → use_llm=True 时 generator 自己动态规划，不依赖此处序列

3. generate_multi_turn_trajectory(plan, domain)
   → Turn 1: user_message = initial_user_query
   → Turn N>1: LLM 根据上一轮 agent_response + trigger 生成 user_message
   → 每轮：动态规划-评估循环，逐节点执行，节点携带 planning_trace
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
├── test_conversation_state.py    # 19 cases — 状态追踪（含节点级）
├── test_node_planner.py          # 14 cases — 规划器（12 静态 + 2 LLM）
├── test_node_evaluator.py        # 14 cases — 评估器（12 静态 + 2 LLM）
├── test_generator_multi.py       # 12 cases — 多轮生成（9 结构 + 3 LLM）
└── test_dynamic_generator.py     # 30 cases — 动态循环 + planning_trace（28 静态 + 2 LLM）
```

非 LLM 测试（113 个）可随时运行：`pytest tests/ -m "not llm"`  
LLM 测试需要 API key：`pytest tests/ -m llm`

---

## 待完成

- [ ] 评估模块（轨迹级质量评估 + 错误标签）
- [ ] 多 domain 扩展（目前只有 code_development）
- [ ] 真实工具接入（目前全部 mock）
- [ ] 数据质量筛选与导出管线
- [ ] 用真实 LLM 生成一批带多轮迭代 planning_trace 的完整样本，验证数据质量
