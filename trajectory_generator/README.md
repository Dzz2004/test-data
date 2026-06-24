# Agent 轨迹生成器

基于 Pipeline.md 设计，实现代码开发领域的 agent 轨迹数据合成。

## 目录结构

```
trajectory_generator/
├── generate.py                         # 入口脚本
├── requirements.txt                    # Python 依赖
├── domain/
│   └── code_development/
│       ├── domain_spec.json            # 领域定义
│       ├── skills.json                 # Skill 池（12 个技能）
│       ├── tools.json                  # Tool 池（7 个工具）
│       ├── knowledge_base.json         # 知识库（技术依赖图谱）
│       └── trajectory_templates.json   # 轨迹模板（6 种模式）
├── src/
│   ├── __init__.py
│   ├── domain.py                       # Domain 加载
│   ├── llm_client.py                   # LLM 调用（OpenAI 兼容）
│   ├── mock_tools.py                   # 模拟工具返回
│   ├── task_generator.py               # 任务生成
│   ├── planner.py                      # 轨迹规划
│   └── generator.py                    # 轨迹内容生成
└── output/                             # 生成结果
    ├── trajectories.jsonl
    └── individual/
```

## 使用

```bash
cd test-data/trajectory_generator

# 安装依赖
pip install -r requirements.txt

# 确保 ../.env.json 配置了 LLM 接口

# 生成 3 条轨迹（默认）
python generate.py

# 生成 10 条轨迹
python generate.py --num 10

# 指定输出目录
python generate.py --num 5 --output ./output/batch1
```

## 生成流程

```
1. 从 personas/ 中随机采样用户画像
2. 根据画像特征推断交互风格（信息充分/缺失/反复修改...）
3. 生成任务（LLM 根据画像生成自然语言用户请求）
4. 选择轨迹模板（基于任务类型和交互风格匹配）
5. 规划节点序列（模板 → 具体 skill/tool 映射）
6. 逐节点生成内容:
   - user_input: 首轮用任务请求，后续轮 LLM 生成
   - tool_call: mock 工具返回预定义数据
   - skill_call: LLM 生成推理过程和输出
   - agent_response: LLM 综合前序分析生成最终回复
7. 生成节点间边（依赖关系描述）
8. 导出 JSONL + 独立 JSON
```

## 配置

所有 API key 从 `test-data/.env.json` 读取:

```json
{
  "llm": {
    "baseUrl": "https://api.deepseek.com/v1",
    "apiKey": "sk-xxxxx",
    "model": "deepseek-chat"
  }
}
```

## 输出格式

每条轨迹包含:

```json
{
  "trajectory_id": "traj_task_xxx_123",
  "domain": "code_development",
  "template_used": "job_oriented_planning",
  "user_profile": { ... },
  "task": { "task_type": "...", "initial_user_query": "...", ... },
  "nodes": [
    { "node_id": "node_000", "node_type": "user_input", "content": "..." },
    { "node_id": "node_001", "node_type": "skill_call", "skill_id": "...", "output": {...}, "rationale": "..." },
    { "node_id": "node_002", "node_type": "tool_call", "tool_id": "...", "input": {...}, "output": {...} },
    ...
  ],
  "edges": [
    { "from": "node_000", "to": "node_001", "relation": "..." }
  ],
  "final_response": "..."
}
```
