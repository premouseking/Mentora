# ADR-0008：建课 Session 与学习 Course 身份分离

- 状态：Accepted
- 日期：2026-07-01
- 关联：ADR-0004、`docs/architecture/module-boundaries.md`

## 背景

`CourseCreationSession` 最初承载建课全流程；`Course` 在「开始学习」后创建。下游
`learning`、`assessment`、`topics`、`knowledge` 仍用 `course_session_id`（UUID 无 FK）
关联，导致：

- 一门课同时存在 session_id 与 course_id；
- 工作区 URL 用 course_id，计划/任务查询仍翻译 session_id；
- Session 在 `started` 后仍被当作运行时主键。

## 决策

1. **建课期（collecting → completed）** 仅使用 `CourseCreationSession` 与
   `/api/courses/sessions/{session_id}/...`。
2. **点「开始学习」** 在同一事务内：`confirm_course_from_session` 创建/激活
   `Course`，绑定 `LearningPlan.course`，Session 置为 `archived`（只读审计）。
3. **学习期** 所有 durable 事实（计划、任务、测评、Topic、作用域读）以
   **`Course.id` FK** 为主键；API 收敛到 `/api/courses/{course_id}/...`。
4. **`course_session_id` 列** 双写一个 sprint 后废弃；新代码禁止新增依赖。
5. **`CourseSource`** 仅建课期临时表；确认后只认 `CourseScopeBinding`。

## Session 状态

```text
collecting → inquiring → generating_plan → completed → archived
```

- `archived`：已创建 Course，Session 不可写（PATCH/plan/sources 返回 409）。
- 历史 `started` 在 data migration 中映射为 `archived`。

## 结果

- 用户心智：建课 = session；学习 = course。
- 消除双 ID 查询与 `_resolve_*` 重复逻辑。
- 代价：DB migration、API 兼容层、前端列表字段 breaking change。

## 验收

1. `get_active_plan(course_id)` 不查 session。
2. archived session 写接口 409。
3. 列表 API：active 课程仅含 `course_id`；待确认方案仅含 `session_id`。
