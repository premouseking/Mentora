# 学习计划重设计 v10（实际实现）

> 版本：v10 | 日期：2026-06-29 | 状态：已实现  
> 对照：v1 → v3 为设计讨论，v10 为落地实现文档

---

## 变更记录

| 版本 | 主要变更 |
|------|----------|
| v1 | 基础概念定义：Phase → Chapter → Task 三层结构，两种展示场景 |
| v2 | 阶段展示改为横向箭头导航 + 下方内容区；阶段类型池 8 种 |
| v3 | 去掉加强/精简按钮；补充 AI 分阶段 prompt 策略；明确两页职责 |
| **v10** | **落地实现：建课流程 5→2 步 + mock 课程 + 调整方案重新生成 + 资料上传** |

---

## 一、v3 设计 vs v10 实现对照

| 设计点 | v3 设计 | v10 实际实现 | 说明 |
|--------|---------|-------------|------|
| 建课步骤 | 未明确步骤数 | 2 步（建立档案 → 确认方案） | 大幅精简 |
| BuildProfilePage | 无 | 4 子步骤（方向/资料/方式/时间）+ adjust 重生成态 | 新增页面 |
| ConfirmPlanPage | 阶段导航 + 章节卡片 + 返回修改 | 阶段导航滑轨 + 章节画布 + 详情栏 + 编辑表格（拖拽排序/添加阶段/锁定模式） | 交互升级 |
| 阶段展示 | 横向箭头导航 | 横向滑轨 + 选中阶段详情展开 | 更灵活 |
| 用户调整 | 增删/调序/改名 + 重新生成 | 编辑模式（🖉/✕✓/↩ 三态） + dirty 追踪 + 调整方案导航 | 更丰富的编辑体验 |
| 学习档案位置 | 底部折叠栏 | 顶部表格展示，支持编辑 | 更突出 |
| 按钮 | 返回修改 + 开始学习 | 调整方案 + 开始学习，逻辑互斥 | 明确操作 |
| 阶段调整 | 保持/精简/加强 三档 | 拖拽排序 + 添加/删除阶段 + 锁定模式 | 更直接 |
| 资料上传 | 无 | 资料选择页右上角「上传资料」按钮，弹窗复用资源库 UI | 新增 |
| mock 课程 | 无 | 内存级存储（`data/mockCourses.ts`），3 个导出函数 | 临时方案 |

---

## 二、建课流程全景

```
/courses/new ──────→ /courses/new/plan ──────→ /courses
  建立档案               确认方案                 课程首页
     ↑                      │
     │    调整方案           │ 开始学习
     └── /courses/new?adjust=true ──┘
```

- **步骤 1**：`BuildProfilePage`（4 子步骤），完成 → 跳转 `/courses/new/plan`
- **步骤 2**：`ConfirmPlanPage`，审视档案与计划 →「开始学习」→ 生成 mock 课程 → 跳转 `/courses`
- **调整**：`ConfirmPlanPage`「调整方案」→ `/courses/new?adjust=true`（重新生成态）→ 完成后回到步骤 2

---

## 三、步骤 1：建立学习档案（BuildProfilePage）

路径 `/courses/new`，文件 `apps/web/src/pages/SetupPages.tsx`。

### 4 个子步骤

| 序号 | 类型 | 副标题 | 问题 | 说明 |
|------|------|--------|------|------|
| 1 | `input` | 学习方向 | 你想学习什么？ | placeholder 引导描述学习目标 |
| 2 | `materials` | 学习资料 | 选择你想使用的学习资料 | 列表选择 + 右上角上传按钮 |
| 3 | `choice` | 学习方式 | 你更喜欢哪种学习方式？ | 6 选项多选 |
| 4 | `choice` | 时间安排 | 你的学习时间安排？ | 6 选项多选 |

### 子步骤类型定义

```ts
type SubStepType = "input" | "choice" | "materials";

interface SubStep {
  type: SubStepType;
  subtitle: string;   // 副标题（灰色小字）
  question: string;    // 问题描述
  placeholder?: string; // type === "input" 时
  options?: string[];   // type === "choice" 时
}
```

### 底部按钮逻辑

| 子步骤 | 确认并继续完善档案 | 确认并生成学习方案 |
|--------|-------------------|-------------------|
| 1（input） | 灰色不可用 | 灰色不可用（必须填写学习目标） |
| 2-3 | 可用 | 可用 |
| 4（最后一步） | 隐藏 | 可用（占满横向） |

### 资料选择子步骤（materials）

```
┌──────────────────────────────────┐
│               [上传资料]          │  ← 右上角
│ ├ 人教版高中数学必修一.pdf       │
│ ├ 五年高考三年模拟·数学.pdf      │
│ ├ 数学错题集·上学期.docx         │
│ └ ...                            │
└──────────────────────────────────┘
```

- 上传按钮弹出弹窗（拖拽上传区 + 本地文件 + 网页链接 + 进度/失败状态）
- 弹窗 UI 直接复用 `LibraryPage.tsx` 的上传逻辑，不抽共享组件

### 调整方案重新生成态（?adjust=true）

从确认方案页「调整方案」按钮进入时：
- 问题描述：「已收到你的更改。是否重新生成学习方案？」
- 内容区：一个输入框，placeholder「描述你希望如何调整学习方案…」
- 底部双按钮均可用（不受 step1 限制）
- 完成后回到 `/courses/new/plan`

---

## 四、步骤 2：确认学习方案（ConfirmPlanPage）

路径 `/courses/new/plan`，文件 `apps/web/src/pages/SetupContinuationPages.tsx`。

### 布局结构

```
┌───────────────────────────────────────────────┐
│  学习档案                                     │
│  ┌────────────────────────────────────┐      │
│  │ 目标   │ 高中数学一轮复习          │ 🖉   │  ← 可编辑
│  │ 基础   │ 有一定基础               │ 🖉   │
│  │ 方式   │ 视频课程、练习题         │ 🖉   │
│  │ 时间   │ 每天 2 小时              │ 🖉   │
│  └────────────────────────────────────┘      │
├───────────────────────────────────────────────┤
│  学习计划                                     │
│  [基础入门][知识梳理][专项训练][综合应用]     │  ← 阶段导航滑轨
│                                               │
│  ┌ 基础入门 ───────────────────────┐        │
│  │  集合与逻辑 (160min)             │        │  ← 章节画布
│  │  函数基础 (150min)               │        │
│  │  基本初等函数 (170min)           │        │
│  └──────────────────────────────────┘        │
│                                               │
│  ┌ 详情栏 ────────────────────────┐         │
│  │  阶段目标：掌握集合、函数等…     │         │  ← 选中阶段详情
│  │  预估总时长：480 分钟           │         │
│  └──────────────────────────────────┘        │
├───────────────────────────────────────────────┤
│  [调整方案]                    [开始学习]     │
│  （isDirty 时绿色）         （!isDirty 时绿色）│
└───────────────────────────────────────────────┘
```

### 学习档案编辑

- **🖉 编辑态**：点击 🖉 → 输入框出现 → ✕✓ 保存 / ↩ 撤销
- **dirty 追踪**：编辑后标题显示 * 星号
- 编辑时「调整方案」变绿，「开始学习」变灰

### 学习计划编辑

4 种操作模式：

| 操作 | 实现方式 |
|------|----------|
| 切换阶段 | 点击滑轨中的阶段卡片 |
| 拖拽排序 | 编辑模式下拖拽阶段卡片调整顺序 |
| 添加阶段 | 「添加阶段」按钮，从类型池选择 |
| 锁定模式 | 无 dirty 时自动锁定编辑 |

### 底部按钮互斥逻辑

| 状态 | 调整方案 | 开始学习 |
|------|----------|----------|
| `isDirty` | 🟢 绿色（→ `/courses/new?adjust=true`） | 灰色 |
| `!isDirty` | 灰色 | 🟢 绿色（→ 生成 mock + `/courses`） |

---

## 五、mock 课程生成

### 生成时机

点击「开始学习」→ `handleStartLearning()` → 从 `profileValues` 提取信息 → 生成 `CourseSessionListItem` → `addMockCourse()` 存入内存 → 跳转 `/courses`

### 存储文件：`apps/web/src/data/mockCourses.ts`

```ts
// 内存级存储，3 个导出函数

let mockCourses: CourseSessionListItem[] = [];

export function addMockCourse(course: CourseSessionListItem): void
export function getMockCourses(): CourseSessionListItem[]
export function removeMockCourse(id: string): void
```

### 关键约束

| 约束 | 说明 |
|------|------|
| **持久化** | 不接入后端，不写文件，仅在浏览器当前会话保留 |
| **刷新丢失** | 刷新页面后数据清空 |
| **ID 前缀** | mock 课程 ID 以 `mock-` 开头，与其他课程区分 |
| **删除** | `CoursesPage` 中删除 mock 课程时调 `removeMockCourse()`，不走 API |

### 未来删除方式

当后端 API 就绪后，一步到位移除 mock：

1. 删除 `apps/web/src/data/mockCourses.ts`
2. 移除 `CoursesPage.tsx` 中的 `getMockCourses` / `removeMockCourse` 引用
3. 移除 `SetupContinuationPages.tsx` 中的 `addMockCourse` 调用（第 6 行 import，第 675-700 行附近 `handleStartLearning`）

---

## 六、涉及文件

| 文件 | 角色 |
|------|------|
| `App.tsx` | 路由：`/courses/new` → `BuildProfilePage`，`/courses/new/plan` → `ConfirmPlanPage` |
| `AppShell.tsx` | `setupSteps = ["建立档案", "确认方案"]`，顶部进度条 |
| `SetupPages.tsx` | **BuildProfilePage**：4 子步骤 + adjust 重生成态 + 上传弹窗（~650 行） |
| `SetupContinuationPages.tsx` | **ConfirmPlanPage**：档案编辑 + 计划编辑 + mock 生成（~1100 行） |
| `CoursesPage.tsx` | 合并 API 结果 + `getMockCourses()` 显示 |
| `data/mockCourses.ts` | **mock 存储**：内存级，3 个导出函数，待 API 就绪后删除 |
| `styles.css` | 新增 `.build-profile` / `.material-list-top` / 编辑表格等样式（~+150 行） |

---

## 七、与 v3 设计的差距

| v3 设计中的项目 | v10 实现状态 |
|-----------------|-------------|
| 课程页上划栏（树状图 Phase → Chapter → Task） | 未实现（待 `CourseWorkspacePage`） |
| AI 分阶段与权重 prompt 策略 | 未实现（依赖后端 agent_runtime） |
| 8 种阶段类型池的 AI 自动选择 | 未实现（当前用 mock 数据） |
| 右侧侧边栏（Task / Chapter 解释） | 未实现（同上） |
| 权重比例条（展示/拖拽） | 未实现 |
