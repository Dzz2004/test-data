# Plan: LLM-Driven Planner 改造

## 问题

当前纯模板方案的局限：
1. 6 个模板 → 最多 6 种节点序列，多样性差
2. 模板外的任务组合无法覆盖
3. 画像特征与模板不匹配时缺乏适应性

## 方案：模板作为 few-shot + LLM 自由规划 + 约束校验

### 核心设计

```
输入: 用户画像 + 任务 + skill池 + tool池 + 模板(作为参考)
         │
         ▼
┌──────────────────────────────┐
│  LLM Plan Generation         │
│  - 接收完整上下文             │
│  - 输出节点序列 (JSON)        │
│  - 可参考模板但不受限于模板    │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  Constraint Validator         │
│  - 前置条件检查               │
│  - 输入输出连通性验证         │
│  - 必要节点存在性检查         │
│  - 冗余/循环检测              │
└──────────────┬───────────────┘
               │ 不通过 → 修复/重试
               ▼
┌──────────────────────────────┐
│  Plan Output (same interface)│
└──────────────────────────────┘
```

### 改造点

1. **新增 `plan_with_llm()`** — 主路径，用 LLM 生成节点序列
2. **新增 `validate_plan()`** — 对 LLM 输出做结构/逻辑校验
3. **保留 `select_template()` + `plan_trajectory()`** — 作为 fallback 和 few-shot 素材
4. **输出接口不变** — generator.py 不需要修改

### LLM Prompt 设计

给 LLM 的信息：
- Skill 池完整列表（id + description + preconditions + possible_next）
- Tool 池完整列表（id + description + 输入输出）
- 用户画像摘要
- 任务描述
- 2 个相关模板作为 few-shot 示例
- 约束规则（必须以 user_input 开头、final_response 结尾、不重复调用同一 tool 等）

### 校验规则

1. **结构约束**: 必须以 user_input 开头，以 final_response 结尾
2. **前置条件**: 每个 skill 的 preconditions 必须被前序节点的 postconditions 覆盖
3. **工具输入**: tool_call 的 input 必须能从前序节点的 output 获得
4. **不冗余**: 同一 skill/tool 不应连续出现（除非有明确理由如二次分析）
5. **节点数合理**: 通常 6-15 个节点，过少可能缺分析，过多可能冗余

### 修复策略

校验不通过时：
- 缺少前置 skill → 自动插入
- 缺 user_input/final_response → 自动补上
- 节点数 < 4 → 重试一次
- 重试 2 次仍失败 → fallback 到模板方案

### 文件变更

- `src/planner.py` — 重写，新增 `plan_with_llm()` 和 `validate_plan()`
- `generate.py` — 调用入口改为 `plan_with_llm()`，保留 fallback
- 其他文件不动

### 接口兼容

输出格式保持不变：
```python
{
    "trajectory_id": "...",
    "template_id": "llm_generated",  # 标记为 LLM 生成
    "template_name": "LLM 自由规划",
    "planned_nodes": [...],           # 同样的 node_plan 结构
    "task": {...},
    "user_profile": {...},
}
```
