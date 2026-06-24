# Persona Calibrator — 用户画像校准工具

通过 Tavily Deep Search 验证 LLM 生成的用户画像中的事实性断言，自动修正不符合现实的内容。

## 安装

```bash
cd test-data
npm install
```

## 环境变量

```bash
export TAVILY_API_KEY="tvly-xxxxx"        # https://tavily.com 获取
export ANTHROPIC_API_KEY="sk-ant-xxxxx"   # https://console.anthropic.com
```

## 使用

```bash
# 校准单个画像
node calibrate.js ./personas/senior-backend-job-hopping.json

# 批量校准所有画像
for f in ./personas/*.json; do node calibrate.js "$f"; done
```

## 输出

校准后的文件写入 `test-data/calibrated/` 目录，结构如下：

```json
{
  "_meta": { ... },
  "_calibration": {
    "status": "corrected | passed",
    "conflicts": [...],
    "validatedClaims": [...],
    "overallRealism": "high | medium | low",
    "notes": "..."
  },
  "profile": { ... }
}
```

## 工作流程

```
Raw Persona → Extract Claims → Tavily Search → Conflict Detection → Rewrite
     │                                                                  │
     └──────── calibrated/*.json ◄──────────────────────────────────────┘
```

1. **Extract Claims** — Claude 从画像中提取可验证的事实性断言（薪资、技术栈、市场需求等）
2. **Tavily Search** — 对每个断言执行 `search_depth: advanced` 搜索
3. **Conflict Detection** — Claude 对比搜索结果与画像断言，识别矛盾
4. **Rewrite** — 仅修正有问题的字段，保持其他内容不变

## 成本参考

每个画像约消耗：
- Tavily: 6-8 次 advanced search ≈ $0.04-0.06
- Claude: 4 次 API call ≈ $0.08-0.12
- 总计: ~$0.15/画像
