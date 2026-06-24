# 测试用虚拟用户画像

供 Career Agent 系统端到端测试使用的虚拟 persona 数据。每个文件的 `profile` 字段直接对应系统的 `ProfileRecord` 接口，可灌入 `user.profileJson` 进行全链路测试。

## 画像列表

| 文件 | 原型 | 阶段 | 目标方向 |
|------|------|------|---------|
| `junior-frontend-graduate.json` | 应届生 | entry | 前端开发 |
| `career-switcher-to-backend.json` | 转行者 | entry | Python 后端 |
| `mid-level-fullstack-promotion.json` | 在职晋升 | mid | 全栈 → 技术 TL |
| `senior-backend-job-hopping.json` | 资深跳槽 | senior | 后端架构师 |
| `freelancer-indie-developer.json` | 自由职业 | mid | 独立开发者 |
| `overseas-remote-rust-engineer.json` | 资深跳槽 | senior | 海外远程 Rust |

## 数据结构

```
{
  "_meta": { ... },     // 测试元数据（personaId, archetype, expectedSkills 等）
  "profile": { ... }    // 直接对应 ProfileRecord 接口
}
```

## 使用方式

```typescript
import personaData from './personas/junior-frontend-graduate.json';

// 直接写入用户记录
user.profileJson = JSON.stringify(personaData.profile);

// 验证系统输出
expect(generatedPlan.complexity).toBe(personaData._meta.expectedPlanComplexity);
```
