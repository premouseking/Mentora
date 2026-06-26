# 前端同步清单

> 后端开发完成后更新此文件。前端同事按条目逐项接入。

---

## 2026-06-23 — assessment A1-A3 题目版本化 + 自检 + 反馈

### 新增 API

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|---|---|---|---|---|
| POST | `/api/assessment/items/<id>/revise/` | 修订题目（创建新版本） | `{question_text?, correct_answer?, ...}` | `{item_id, revision_id, version_number, status}` |
| POST | `/api/assessment/items/<id>/publish/` | 手动发布 draft 题目 | — | `{item_id, status: "published"}` |
| POST | `/api/assessment/items/<id>/flag/` | 学生反馈题目问题 | `{issue, student_note?}` | `{item_id, unresolved_flags, auto_revised?, revision_id?}` |

### 变更 API

| 路径 | 变更 |
|---|---|
| `POST /api/assessment/sessions/generate/` | 响应中的 `item_id` 现在引用 AssessmentItem，题干/答案需通过 `item.current_revision_id` 查 Revision |
| `GET /api/assessment/sessions/<id>/` | 响应 items 新增 `revision_id`，`question_text` 和 `correct_answer` 从 revision 读取 |

### 需新增 UI

**1. 题目详情弹窗**

| 项目 | 内容 |
|---|---|
| 触发 | 测验结果页 → 点击某道题 |
| 组件 | Modal：题干 + 选项 + 正确答案 + 解析 + 版本号 |
| 数据 | `GET /api/assessment/sessions/<id>/` 的 items 数组 |

**2. "反馈"按钮**

| 项目 | 内容 |
|---|---|
| 位置 | 题目详情弹窗底部 |
| 交互 | 点击 → 弹出下拉选择 issue 类型 + 文本框 → POST /api/assessment/items/<id>/flag/ |
| 状态 | 提交后显示 "已反馈，感谢" |

**3. "发布题目"按钮**

| 项目 | 内容 |
|---|---|
| 位置 | 题库管理页 → draft 状态的题目旁 |
| 交互 | 点击 → POST /api/assessment/items/<id>/publish/ → 状态变为 published |
| 数据 | 题目列表需显示 `status` 字段（draft/published/retired） |
