# Agent 轨迹数据合成技术文档

## 1. 文档目标

本文档用于指导后续代码实现，目标是构建一个可扩展的 **Agent 轨迹数据合成系统**。

系统需要支持：

1. 以指定领域 `domain` 为单位构造数据。
2. 为每个领域独立配置用户画像、skill、工具和知识库。
3. 通过用户画像、任务目标、skill 组合、工具调用顺序等因素生成多样化 agent 轨迹。
4. 对生成轨迹进行过程合理性评估。
5. 输出可用于训练、评估或分析的结构化轨迹数据集。

本文档重点关注 **流程链路、模块设计、数据结构、生成算法与评估逻辑**。

---

## 2. 核心概念定义

### 2.1 Domain

`Domain` 表示一个数据合成领域。

示例：

```text
计算机学习路径规划
医疗问诊辅助
法律咨询辅助
旅行规划
科研文献辅助
```

每个 domain 拥有独立配置：

```text
domain
├── skill 池
├── tool 池
├── 用户画像池
├── 知识库
├── 任务模板
├── 轨迹模板
└── 评估规则
```

---

### 2.2 User Profile

`User Profile` 表示被模拟用户的画像。

它决定用户的背景、目标、约束和交互风格。

示例：

```json
{
  "user_id": "user_001",
  "background": "非计算机专业本科生",
  "level": "学过一点 Python",
  "goal": "6 个月内准备数据分析实习",
  "time_budget": "每天 1 小时",
  "language_preference": "中文资源优先",
  "interaction_style": "信息充分型"
}
```

---

### 2.3 Skill

`Skill` 表示 agent 内部可使用的能力模块。

Skill 不等同于外部工具。Skill 更像 agent 的推理、规划、诊断或整合能力。

示例：

```text
需求解析
学习者水平诊断
知识点依赖分析
学习路径规划
资源推荐
时间预算分配
计划可行性检查
```

---

### 2.4 Tool

`Tool` 表示 agent 可调用的外部能力或外部信息源。

示例：

```text
课程资源检索工具
岗位技能要求检索工具
知识点图谱检索工具
项目库检索工具
学习时间规划工具
能力测评工具
```

---

### 2.5 Task

`Task` 表示用户本轮交互中的具体目标。

示例：

```text
为零基础用户规划 6 个月 Python 学习路径
为转码用户设计后端开发求职路线
为会 Python 的用户规划数据分析实习准备路径
```

---

### 2.6 Trajectory

`Trajectory` 表示一条完整 agent 轨迹。

一条轨迹包括：

```text
用户输入
→ agent 理解
→ skill 调用
→ tool 调用
→ 工具返回
→ 信息整合
→ 计划生成
→ 自我校验
→ 最终输出
→ 过程评估
```

---

### 2.7 Node

`Node` 是轨迹中的一个步骤。

常见节点类型：

```text
user_input
agent_analysis
skill_call
tool_call
tool_result
agent_reasoning
agent_response
evaluation
```

---

### 2.8 Edge

`Edge` 表示轨迹节点之间的逻辑依赖关系。

例如：

```text
Node_3 的技能缺口识别依赖 Node_2 的用户需求解析结果
Node_5 的学习路径规划依赖 Node_4 的岗位技能要求检索结果
```

评估时需要判断这些依赖是否合理。

---

## 3. 总体流程链路

系统整体流程如下：

```text
Step 1：确定 domain
        ↓
Step 2：加载 domain spec
        ↓
Step 3：加载 skill 池
        ↓
Step 4：加载 tool 池
        ↓
Step 5：加载用户画像池
        ↓
Step 6：加载知识库
        ↓
Step 7：生成任务池
        ↓
Step 8：采样用户画像 + 任务 + skill 组合 + tool 组合
        ↓
Step 9：生成轨迹计划
        ↓
Step 10：执行轨迹生成
        ↓
Step 11：生成过程评估
        ↓
Step 12：筛选、修正、回流
        ↓
Step 13：导出高质量轨迹数据集
```

---

## 4. 系统模块设计

**当前实现结构**（`trajectory_generator/`）：

```text
trajectory_generator/
├── generate.py                     # 主入口
├── domain/
│   └── code_development/           # 当前唯一领域
│       ├── domain_spec.json
│       ├── skills.json             # 12 个推理技能
│       ├── tools.json              # 7 个外部工具
│       ├── knowledge_base.json
│       └── trajectory_templates.json
├── src/
│   ├── schema.py                   # 数据结构定义（新）
│   ├── domain.py                   # Domain 加载
│   ├── llm_client.py               # LLM 调用封装
│   ├── mock_tools.py               # 参数敏感工具 mock
│   ├── conversation_state.py       # 跨轮状态追踪（新）
│   ├── task_generator.py           # Blueprint 生成
│   ├── planner.py                  # 多轮轨迹规划
│   └── generator.py                # 多轮轨迹生成
└── output/
    ├── trajectories.jsonl
    └── individual/

tests/                              # 与 trajectory_generator/ 平级
├── conftest.py
├── test_schema.py
├── test_mock_tools.py
├── test_blueprint.py
├── test_planner_multi.py
├── test_conversation_state.py
└── test_generator_multi.py
```

**规划中的扩展模块**（未实现）：

```text
src/evaluator/    # 节点级/边级/轨迹级评估
src/exporter/     # 数据筛选与多格式导出
configs/domains/  # 更多领域配置（医疗/法律/旅行等）
```

---

## 5. 模块职责

### 5.1 Domain Manager

负责加载和管理 domain 配置。

输入：

```text
domain_name
```

输出：

```text
DomainSpec
SkillRegistry
ToolRegistry
UserProfilePool
KnowledgeBase
TaskTemplatePool
TrajectoryTemplatePool
EvaluationConfig
```

---

### 5.2 Skill Registry

负责管理所有 skill。

主要功能：

```text
注册 skill
查询 skill
校验 skill 输入输出
根据任务类型选择候选 skill
根据轨迹模板返回 skill 序列
```

---

### 5.3 Tool Registry

负责管理所有工具。

主要功能：

```text
注册工具
查询工具
校验工具输入参数
模拟工具返回结果
记录工具调用日志
```

在数据合成阶段，工具可以是真实工具，也可以是 mock 工具。

---

### 5.4 User Simulator

负责生成用户画像和模拟用户多轮行为。

主要功能：

```text
生成用户画像
生成用户初始请求
根据 agent 追问生成用户补充回答
模拟用户修改目标或新增约束
模拟用户质疑或要求解释
```

---

### 5.5 Task Generator

负责基于用户画像和 domain 生成任务。

主要功能：

```text
根据用户画像生成任务目标
根据任务模板生成用户请求
控制任务难度
控制任务类型分布
控制单轮 / 多轮比例
```

---

### 5.6 Trajectory Planner

负责规划一条轨迹应当包含哪些节点。

输入：

```text
user_profile
task
available_skills
available_tools
trajectory_template
```

输出：

```text
TrajectoryPlan
```

TrajectoryPlan 示例：

```json
{
  "trajectory_id": "traj_001",
  "template": "job_oriented_learning_path",
  "planned_nodes": [
    "user_input",
    "need_analysis",
    "job_skill_search",
    "skill_gap_analysis",
    "learning_path_planning",
    "project_based_learning_design",
    "feasibility_check",
    "final_response"
  ]
}
```

---

### 5.7 Trajectory Generator

负责根据轨迹计划生成完整轨迹内容。

主要功能：

```text
生成用户输入
生成 agent 中间分析
执行 skill 调用
执行 tool 调用
生成工具返回结果
生成 agent 信息整合过程
生成最终回复
```

---

### 5.8 Evaluator

负责评估轨迹过程是否合理。

评估分为三层：

```text
节点级评估
边级评估
轨迹级评估
```

输出：

```json
{
  "node_score": 0.91,
  "edge_score": 0.88,
  "trajectory_score": 0.90,
  "overall_label": "reasonable",
  "error_tags": []
}
```

---

### 5.9 Exporter

负责将轨迹导出为指定格式。

支持格式：

```text
json
jsonl
parquet
markdown report
```

推荐训练数据主格式：

```text
jsonl
```

---

## 6. 核心数据结构

### 6.1 DomainSpec

```json
{
  "domain_id": "cs_learning_path",
  "domain_name": "计算机学习路径规划",
  "description": "面向不同背景用户生成计算机学习路径规划轨迹数据",
  "task_types": [
    "learning_path_planning",
    "skill_gap_diagnosis",
    "resource_recommendation",
    "job_oriented_planning",
    "project_based_learning"
  ],
  "supported_interaction_modes": [
    "single_turn",
    "multi_turn_clarification",
    "multi_turn_revision"
  ]
}
```

---

### 6.2 SkillSpec

```json
{
  "skill_id": "skill_learning_path_planning",
  "name": "学习路径规划",
  "type": "domain_specific",
  "description": "根据用户目标、基础和时间约束生成阶段化学习路径",
  "inputs": [
    "user_goal",
    "user_level",
    "time_budget",
    "knowledge_dependencies"
  ],
  "outputs": [
    "learning_stages",
    "weekly_plan",
    "milestones"
  ],
  "preconditions": [
    "用户目标已明确",
    "用户基础已识别"
  ],
  "postconditions": [
    "生成可执行学习路径"
  ],
  "possible_next_skills": [
    "资源推荐",
    "时间预算分配",
    "计划可行性检查"
  ]
}
```

---

### 6.3 ToolSpec

```json
{
  "tool_id": "tool_job_skill_search",
  "name": "岗位技能要求检索工具",
  "description": "根据岗位名称检索所需技能",
  "input_schema": {
    "job_title": "string",
    "seniority": "string"
  },
  "output_schema": {
    "required_skills": "list[string]",
    "optional_skills": "list[string]",
    "project_requirements": "list[string]"
  },
  "failure_modes": [
    "岗位名称过于模糊",
    "检索结果为空",
    "结果与目标不匹配"
  ]
}
```

---

### 6.4 UserProfile

```json
{
  "user_id": "user_001",
  "domain": "cs_learning_path",
  "background": {
    "education": "本科",
    "major": "非计算机专业",
    "work_experience": "无"
  },
  "current_level": {
    "programming": "学过一点 Python",
    "math": "一般",
    "project_experience": "无完整项目"
  },
  "goal": {
    "primary_goal": "6 个月内准备数据分析实习",
    "secondary_goals": [
      "掌握 SQL",
      "完成一个数据分析项目"
    ]
  },
  "constraints": {
    "time_budget": "每天 1 小时",
    "language": "中文资源优先",
    "budget": "免费资源优先"
  },
  "interaction_style": "信息充分型"
}
```

---

### 6.5 Blueprint（原 Task，已扩展）

增加 `conversation_arc` 字段，描述多轮对话的剧本结构。

```json
{
  "task_id": "task_001",
  "domain": "code_development",
  "task_type": "mock-interview",
  "user_id": "senior-backend-job-hopping",
  "task_description": "为资深后端工程师规划面试准备",
  "initial_user_query": "帮我规划两个月的面试准备计划，目标是后端架构师岗位...",
  "interaction_style": "偏好强烈型",
  "expected_skills": ["系统设计", "行为面试"],
  "goal": "用户经过 3 轮交互，最终获得一份调整后的面试计划",
  "conversation_arc": [
    { "turn": 1, "trigger": "initial_request",   "description": "用户发起面试规划请求" },
    { "turn": 2, "trigger": "constraint_update",  "description": "用户将每周时间从 15h 改为 8h" },
    { "turn": 3, "trigger": "clarification",      "description": "用户追问系统设计练习方式" }
  ]
}
```

Trigger 类型：`initial_request` / `constraint_update` / `clarification` / `plan_revision` / `pushback`

---

### 6.6 TrajectoryNode

```json
{
  "node_id": "node_001",
  "node_type": "skill_call",
  "name": "技能缺口识别",
  "input": {
    "user_profile": "user_001",
    "job_required_skills": [
      "Python",
      "SQL",
      "统计基础",
      "数据可视化",
      "项目经验"
    ]
  },
  "output": {
    "skill_gaps": [
      "SQL",
      "统计基础",
      "数据可视化",
      "完整项目经验"
    ]
  },
  "used_skill": "skill_gap_analysis",
  "used_tool": null,
  "rationale": "用户只具备少量 Python 基础，而数据分析实习通常还需要 SQL、统计、可视化和项目经验，因此需要识别技能缺口。",
  "depends_on": [
    "node_000"
  ]
}
```

---

### 6.7 MultiTurnTrajectory（原 Trajectory，已重构）

轨迹从"平铺节点列表"改为"按轮次组织"，每轮包含完整的用户消息、处理节点和 agent 回复。

```json
{
  "trajectory_id": "traj_001",
  "domain": "code_development",
  "template_used": "multi_turn_llm",
  "user_profile": {},
  "task": { "...Blueprint 结构，含 conversation_arc..." },
  "turns": [
    {
      "turn_id": 1,
      "trigger": "initial_request",
      "user_message": "帮我规划两个月的面试准备计划...",
      "processing_nodes": [
        { "node_type": "skill_call", "skill_id": "need_analysis", "output": {}, "rationale": "..." },
        { "node_type": "tool_call",  "tool_id": "job_requirement_search", "input": {}, "output": {} }
      ],
      "agent_response": "基于你的背景，建议分三个阶段准备..."
    },
    {
      "turn_id": 2,
      "trigger": "constraint_update",
      "user_message": "第6-8周我需要加班，每周只有8小时...",
      "processing_nodes": [ "..." ],
      "agent_response": "没问题，第 6-8 周切换为轻量复习模式..."
    }
  ],
  "evaluation": null
}
```

---

### 6.8 EvaluationResult

```json
{
  "trajectory_id": "traj_001",
  "node_level": {
    "score": 0.92,
    "issues": []
  },
  "edge_level": {
    "score": 0.88,
    "issues": [
      {
        "type": "weak_dependency",
        "description": "资源推荐节点对前序技能缺口识别结果引用不足"
      }
    ]
  },
  "trajectory_level": {
    "score": 0.90,
    "issues": []
  },
  "overall_label": "reasonable",
  "error_tags": []
}
```

---

## 7. 轨迹生成流程

### 7.1 输入

```text
DomainSpec
SkillPool
ToolPool
UserProfilePool
KnowledgeBase
TaskTemplatePool
TrajectoryTemplatePool
GenerationConfig
```

---

### 7.2 输出

```text
Raw Trajectory Dataset
Evaluated Trajectory Dataset
Filtered High-quality Trajectory Dataset
```

---

### 7.3 生成伪代码（当前实现）

```python
def generate_dataset(domain_name: str, num_samples: int):
    domain = load_domain(domain_name)
    trajectories = []

    for _ in range(num_samples):
        user_data = random.choice(domain.user_profiles)

        # Step 1: 生成含对话弧线的蓝图
        blueprint = generate_blueprint(domain, user_data)
        # blueprint.conversation_arc 定义了 2-4 轮的剧本

        # Step 2: 按轮次规划节点序列
        multi_plan = plan_multi_turn(domain, blueprint, user_data["profile"])
        # 每轮根据 trigger 类型选择合适的 skill/tool 序列

        # Step 3: 逐轮生成内容，维护跨轮对话状态
        trajectory = generate_multi_turn_trajectory(multi_plan, domain)
        # Turn 1: user_message = initial_user_query
        # Turn N: user_message 由 LLM 根据上轮 agent_response + trigger 生成
        # 每轮的 agent_response 引用本轮 processing_nodes 的分析结果

        # Step 4: 评估（待实现）
        # evaluation = Evaluator.evaluate(trajectory)
        # trajectory.evaluation = evaluation

        trajectories.append(trajectory)

    return trajectories
```

---

## 8. Skill 与 Tool 组合策略

轨迹多样性主要通过 skill 和 tool 的组合产生。

### 8.1 模板式组合

预先定义常见轨迹模板。

示例：

```text
基础学习路径规划模板：
需求解析
→ 学习者水平诊断
→ 知识点依赖分析
→ 学习路径规划
→ 资源推荐
→ 时间预算分配
→ 可行性检查
→ 最终回复
```

适合 MVP 阶段。

---

### 8.2 随机采样组合

从候选 skill 和 tool 中随机采样。

需要满足：

```text
前置依赖合法
输入输出兼容
任务目标相关
节点顺序合理
工具调用不冗余
```

---

### 8.3 图搜索组合

将 skill 和 tool 建模为有向图。

```text
节点：skill 或 tool
边：输入输出依赖关系
```

然后从起点节点搜索到终点节点。

起点通常是：

```text
需求解析
```

终点通常是：

```text
最终回复生成
```

---

### 8.4 约束修复

如果采样出的轨迹存在问题，需要修复。

常见修复方式：

```text
缺少用户基础 → 插入学习者水平诊断节点
缺少岗位信息 → 插入岗位技能检索节点
时间约束未使用 → 插入时间预算分配节点
计划不合理 → 插入计划可行性检查节点
工具调用无输入 → 回退并重新采样前置节点
```

---

## 9. 用户模拟设计

用户模拟需要覆盖多样性，而不是只替换表面字段。

### 9.1 用户画像维度

```text
基础背景：
- 高中生
- 本科生
- 研究生
- 在职人员
- 转专业用户

技术基础：
- 零基础
- 学过 Python
- 有项目经验
- 算法较弱
- 数学较强
- 工程经验较强

目标类型：
- 兴趣学习
- 求职
- 科研
- 考试
- 项目实践
- 补短板

约束条件：
- 时间少
- 周期短
- 只能使用中文资源
- 免费资源优先
- 不喜欢理论
- 需要项目驱动

交互风格：
- 信息充分型
- 信息缺失型
- 目标模糊型
- 反复修改型
- 质疑型
- 偏好强烈型
```

---

### 9.2 用户行为策略

#### 信息充分型

用户初始请求中提供较完整信息。

```text
我不是计算机专业，但学过一点 Python。想在 6 个月内准备数据分析实习，每天能学 1 小时，中文资源优先。
```

#### 信息缺失型

用户初始请求模糊，需要 agent 追问。

```text
我想学 AI，帮我规划一下。
```

合理轨迹：

```text
用户输入
→ agent 判断信息不足
→ agent 追问基础、目标、时间
→ 用户补充信息
→ agent 继续规划
```

#### 反复修改型

用户中途改变约束。

```text
我原来以为每天有 2 小时，但现在可能只有 30 分钟，还能继续这个计划吗？
```

合理轨迹：

```text
用户新增约束
→ agent 检测冲突
→ 压缩目标或调整节奏
→ 生成修改后的计划
```

#### 质疑型

用户要求解释原因。

```text
为什么我不能直接学深度学习框架？
```

合理轨迹：

```text
用户质疑
→ agent 引用知识依赖
→ 解释先修知识
→ 给出替代路径
```

---

## 10. 轨迹模板设计

### 10.1 基础学习路径规划模板

```text
user_input
→ need_analysis
→ learner_level_diagnosis
→ knowledge_dependency_analysis
→ learning_path_planning
→ resource_recommendation
→ time_budget_allocation
→ feasibility_check
→ final_response
```

适用场景：

```text
用户目标明确
用户希望系统学习某个方向
用户不一定以求职为目标
```

---

### 10.2 求职导向路径规划模板

```text
user_input
→ need_analysis
→ job_skill_search
→ skill_gap_analysis
→ learning_path_planning
→ project_based_learning_design
→ interview_preparation_planning
→ feasibility_check
→ final_response
```

适用场景：

```text
用户明确有实习、求职、转码、岗位准备目标
```

---

### 10.3 信息不足澄清模板

```text
user_input
→ need_analysis
→ information_sufficiency_check
→ clarification_question
→ user_followup
→ learner_level_diagnosis
→ learning_path_planning
→ final_response
```

适用场景：

```text
用户没有说明基础、目标、时间或偏好
```

---

### 10.4 约束冲突修正模板

```text
user_input
→ initial_plan_generation
→ user_constraint_update
→ constraint_conflict_detection
→ goal_compression_or_replanning
→ revised_plan_generation
→ feasibility_check
→ final_response
```

适用场景：

```text
用户中途修改时间、目标、资源偏好或学习周期
```

---

### 10.5 项目制学习模板

```text
user_input
→ need_analysis
→ target_project_identification
→ required_skill_mapping
→ project_milestone_planning
→ resource_recommendation
→ risk_check
→ final_response
```

适用场景：

```text
用户希望通过项目学习，而不是按照课程线性学习
```

---

## 11. 评估设计

评估目标：

```text
只评估过程是否合理，不以最终答案是否唯一正确为主要目标。
```

---

### 11.1 节点级评估

检查每个节点本身是否合理。

评估项：

```text
节点是否必要
节点输入是否充分
节点输出是否有效
skill 是否匹配当前任务
tool 是否匹配当前任务
节点输出是否与用户画像一致
节点输出是否可支撑后续节点
```

评分示例：

```json
{
  "node_id": "node_004",
  "score": 0.85,
  "label": "reasonable",
  "issues": []
}
```

---

### 11.2 边级评估

检查节点之间的逻辑关系。

评估项：

```text
后一节点是否自然依赖前一节点
是否存在逻辑跳跃
是否存在必要节点缺失
是否存在冗余调用
是否存在前后矛盾
是否正确使用了工具返回结果
```

评分示例：

```json
{
  "edge": ["node_003", "node_004"],
  "score": 0.78,
  "label": "partially_reasonable",
  "issues": [
    "node_004 对 node_003 的工具结果使用不足"
  ]
}
```

---

### 11.3 轨迹级评估

检查整条轨迹是否合理。

评估项：

```text
是否围绕用户目标展开
是否遵守用户约束
是否完成必要分析
是否合理追问
是否合理调用工具
是否避免无意义重复
最终回复是否由前序过程支撑
```

输出示例：

```json
{
  "trajectory_score": 0.91,
  "overall_label": "reasonable",
  "error_tags": []
}
```

---

### 11.4 错误标签

建议使用统一错误标签。

```text
unnecessary_node
missing_node
wrong_skill_selection
wrong_tool_selection
tool_input_error
weak_dependency
logic_jump
constraint_violation
profile_ignored
inconsistent_output
redundant_tool_call
insufficient_clarification
unsupported_final_answer
```

---

## 12. 数据输出格式

推荐使用 JSONL，每一行是一条完整轨迹。

示例：

```json
{
  "trajectory_id": "traj_001",
  "domain": "cs_learning_path",
  "user_profile": {
    "background": "非计算机专业本科生",
    "level": "学过一点 Python",
    "goal": "6 个月内准备数据分析实习",
    "time_budget": "每天 1 小时"
  },
  "task": {
    "task_type": "job_oriented_planning",
    "description": "为用户规划数据分析实习准备路径"
  },
  "nodes": [
    {
      "node_id": "node_001",
      "node_type": "user_input",
      "content": "我不是计算机专业，但学过一点 Python。现在想在 6 个月内准备数据分析实习，每天大概能学 1 小时。你能帮我规划一条学习路径吗？"
    },
    {
      "node_id": "node_002",
      "node_type": "skill_call",
      "skill": "需求解析",
      "input": "用户原始请求",
      "output": {
        "goal": "准备数据分析实习",
        "time_budget": "每天 1 小时",
        "current_level": "学过一点 Python",
        "constraints": [
          "6 个月周期"
        ]
      },
      "rationale": "需要先抽取用户目标、基础和约束，才能决定后续规划路径。"
    },
    {
      "node_id": "node_003",
      "node_type": "tool_call",
      "tool": "岗位技能要求检索工具",
      "input": {
        "job_title": "数据分析实习生"
      },
      "output": {
        "required_skills": [
          "Python",
          "SQL",
          "统计基础",
          "数据可视化",
          "业务分析",
          "项目经验"
        ]
      },
      "rationale": "用户目标是数据分析实习，因此需要先明确岗位所需技能。"
    }
  ],
  "edges": [
    {
      "from": "node_001",
      "to": "node_002",
      "relation": "用户输入被解析为结构化需求"
    },
    {
      "from": "node_002",
      "to": "node_003",
      "relation": "解析出求职目标后，需要查询岗位技能要求"
    }
  ],
  "final_response": "基于你的背景和 6 个月目标，建议将学习路径分成 Python 巩固、SQL、统计基础、数据可视化、项目实践和简历准备六个阶段……",
  "evaluation": {
    "node_score": 0.92,
    "edge_score": 0.90,
    "trajectory_score": 0.91,
    "overall_label": "reasonable",
    "error_tags": []
  }
}
```

---

## 13. MVP 实现范围

第一版建议只实现一个 domain：

```text
Domain：计算机学习路径规划
```

### 13.1 MVP 用户画像

至少覆盖以下用户：

```text
P1：零基础高中生，想提前学习计算机
P2：非 CS 本科生，想转码找实习
P3：在职人员，想学习后端开发
P4：数学基础较好，想入门机器学习
P5：会 Python，想做数据分析项目
P6：计算机本科生，算法薄弱，准备秋招
P7：研究生，想学习深度学习并读论文
P8：前端开发者，想转全栈
```

---

### 13.2 MVP Skill 池

```text
S1：需求解析
S2：信息充分性判断
S3：追问生成
S4：学习者水平诊断
S5：目标拆解
S6：知识点依赖分析
S7：岗位技能分析
S8：技能缺口识别
S9：学习路径规划
S10：课程资源推荐
S11：项目制学习设计
S12：时间预算分配
S13：计划可行性检查
S14：最终回复生成
```

---

### 13.3 MVP Tool 池

```text
T1：知识点图谱检索工具
T2：课程资源检索工具
T3：岗位技能要求检索工具
T4：项目库检索工具
T5：学习时间规划工具
T6：能力测评工具
```

---

### 13.4 MVP 轨迹模板

```text
Template A：基础学习路径规划
Template B：求职导向路径规划
Template C：信息不足澄清
Template D：约束冲突修正
Template E：项目制学习路径
```

---

### 13.5 MVP 生成规模

建议第一阶段不要直接大规模生成。

```text
用户画像：20 个
任务模板：20 个
轨迹模板：5 个
每个画像生成任务：3-5 个
第一轮轨迹规模：100-300 条
人工抽检数量：30-50 条
```

---

## 14. 实现优先级

### Phase 1：配置与数据结构

目标：

```text
完成 domain、skill、tool、user profile、task、trajectory 的基础 schema。
```

需要实现：

```text
DomainSpec
SkillSpec
ToolSpec
UserProfile
Task
TrajectoryNode
Trajectory
EvaluationResult
```

---

### Phase 2：模板式轨迹生成

目标：

```text
基于固定模板生成第一批可控轨迹。
```

需要实现：

```text
UserProfileSampler
TaskGenerator
TrajectoryTemplateSampler
TrajectoryGenerator
MockToolExecutor
```

---

### Phase 3：过程合理性评估

目标：

```text
实现节点级、边级、轨迹级评估。
```

需要实现：

```text
NodeEvaluator
EdgeEvaluator
TrajectoryEvaluator
ErrorTagger
```

---

### Phase 4：多样性增强

目标：

```text
通过 skill 组合、工具顺序、用户行为模拟增加轨迹多样性。
```

需要实现：

```text
SkillCombinationSampler
ToolSequenceSampler
MultiTurnUserSimulator
ConstraintUpdateSimulator
FailureRecoveryTrajectoryGenerator
```

---

### Phase 5：数据筛选与导出

目标：

```text
输出高质量 jsonl 轨迹数据集。
```

需要实现：

```text
QualityFilter
DatasetExporter
ReportGenerator
```

---

## 15. 关键实现注意事项

### 15.1 通用框架与领域配置分离

代码层面应避免将计算机学习路径规划写死在主逻辑中。

推荐结构：

```text
通用代码：
src/

领域配置：
configs/domains/cs_learning_path/
```

新增 domain 时，应主要新增配置，而不是修改核心代码。

---

### 15.2 Skill 输入输出必须结构化

不要只保存自然语言描述。

错误示例：

```json
{
  "output": "用户需要先学 SQL 和统计"
}
```

推荐示例：

```json
{
  "output": {
    "skill_gaps": [
      "SQL",
      "统计基础"
    ],
    "priority": [
      "SQL",
      "统计基础",
      "数据可视化"
    ],
    "reason": "用户目标是数据分析实习，但当前只具备少量 Python 基础"
  }
}
```

---

### 15.3 轨迹节点需要保存 rationale

每个关键节点都应保存 `rationale`。

用途：

```text
解释为什么需要这个节点
支撑过程合理性评估
便于人工审查
便于后续训练模型学习推理过程
```

---

### 15.4 工具调用需要区分真实工具和 mock 工具

MVP 阶段可以优先实现 mock 工具。

```text
真实工具：
调用外部 API、数据库、搜索系统

Mock 工具：
从本地配置文件或预定义知识库中返回模拟结果
```

推荐先实现 mock 工具，保证轨迹结构可控。

---

### 15.5 评估重点是过程，不是最终答案

评估逻辑应避免只看最终回答质量。

需要检查：

```text
是否该追问却没有追问
是否没有岗位目标却调用岗位工具
是否没有使用工具结果就生成结论
是否忽略用户时间约束
是否 skill 顺序不合理
是否最终回答无法由前序节点支撑
```

---

## 16. 后续可扩展方向

### 16.1 支持更多 domain

```text
科研文献辅助
代码调试
旅行规划
医疗健康咨询
法律咨询辅助
金融投资学习
```

---

### 16.2 支持真实工具接入

```text
搜索引擎
知识库检索
课程平台 API
岗位招聘数据
日历工具
代码执行工具
```

---

### 16.3 支持自动反思与修复

当评估器发现问题时，系统可以自动修复轨迹。

示例：

```text
发现缺少追问节点
→ 自动插入信息充分性判断和追问节点

发现工具调用无依赖
→ 回退到前序节点重新生成

发现最终回复未遵守时间约束
→ 重新执行时间预算分配
```

---

### 16.4 支持难度控制

可以为轨迹设置难度等级。

```text
Level 1：单轮、无工具、简单规划
Level 2：单轮、多 skill、有工具
Level 3：多轮澄清、多工具
Level 4：用户中途修改约束
Level 5：工具失败、agent 需要恢复
```

---

## 17. 推荐第一版实现 checklist

```text
[ ] 定义 DomainSpec schema
[ ] 定义 SkillSpec schema
[ ] 定义 ToolSpec schema
[ ] 定义 UserProfile schema
[ ] 定义 Task schema
[ ] 定义 TrajectoryNode schema
[ ] 定义 Trajectory schema
[ ] 定义 EvaluationResult schema

[ ] 创建 cs_learning_path domain 配置
[ ] 创建 20 个用户画像
[ ] 创建 14 个 skill
[ ] 创建 6 个 mock tool
[ ] 创建 5 个轨迹模板
[ ] 创建 20 个任务模板

[ ] 实现用户画像采样
[ ] 实现任务生成
[ ] 实现轨迹模板采样
[ ] 实现 skill/tool 序列生成
[ ] 实现 mock tool executor
[ ] 实现轨迹节点生成
[ ] 实现轨迹边生成
[ ] 实现最终回复生成

[ ] 实现节点级评估
[ ] 实现边级评估
[ ] 实现轨迹级评估
[ ] 实现错误标签生成
[ ] 实现质量筛选
[ ] 实现 jsonl 导出

[ ] 生成 100-300 条样例轨迹
[ ] 人工抽检 30-50 条
[ ] 归纳错误类型
[ ] 迭代 skill、tool、template 和 evaluator 配置
```

---

## 18. 总结

本系统的核心设计原则是：

```text
通用生成框架 + 领域独立配置 + 多样化轨迹采样 + 过程合理性评估
```

其中：

```text
用户画像池决定用户多样性
skill 池决定 agent 能力边界
tool 池决定外部交互能力
知识库决定领域事实基础
轨迹模板决定基础流程结构
skill/tool 组合决定轨迹多样性
评估器决定最终数据质量
```

第一版实现应优先保证：

```text
流程闭环
结构清晰
轨迹可解释
评估可追踪
数据可导出
```

在此基础上，再逐步扩展到更复杂的多轮交互、工具失败恢复、自动修复和多 domain 数据合成。
