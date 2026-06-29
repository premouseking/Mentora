# 学习计划重设计 v9

> 版本：v9 | 日期：2026-06-29 | 状态：交互逻辑重设计完成（三区变更追踪 + dirty 状态 + 确认方案）

---

## 变更记录

| 版本 | 主要变更 |
|------|----------|
| v1 | Phase → Chapter → Task 三层结构，课程页上划栏树状图设计 |
| v2 | 建课确认页：横向箭头导航 + 下方内容区；阶段类型池 8 种 |
| v3 | 去掉加强/精简按钮；补充 AI 分阶段 prompt 策略；明确区分两页职责 |
| v4 | 确立调整入口为「调整计划」按钮（不直接改面板）；明确当前 Task 为 mock |
| v5 | 建课确认页导航栏重设计：滑轨式滚动 + 箭头形阶段块 + 空详情占位区 |
| v6 | 课程页上划栏重设计：三栏布局（纵向阶段导航 + 主干分支画板 + 可收起详情栏） |
| v7 | v6 实现落地 + 六边形箭头块、双向 snap、SVG 连线、右栏三段内容 |
| v8 | 调整方案页面：AI 对话栏（4 阶段交互）+ 可编辑学习档案 + 学习计划概览（留空） |
| **v9** | **交互逻辑重设计**：三区变更追踪 + dirty 状态机 + 底部确认方案按钮 + 阶段导航滑轨 + 计划详情框 + 章节画布 + 章节详情栏 + 滚动 Bug 修复 |

---

## 一、入口与导航

- **进入方式**：课程页上划栏底部「调整方案」按钮 → `adjustMode = true` 切换面板
- **退出方式**：左上角 ↶ 返回按钮 → 回到三栏学习计划预览
- **模式区分**：
  - `adjustMode = false`：左上角显示「学习计划」，X 关闭按钮
  - `adjustMode = true`：左上角显示「调整学习方案」，↶ 返回按钮

---

## 二、调整面板整体布局

```
┌───────────────────────────────────────────────┐
│  调整学习方案                          [↶]   │  ← 顶栏
├───────────────────────────────────────────────┤
│  ← scrollbar-gutter: stable，溢出时显示滚动条 │
│                                               │
│  1️⃣ AI 对话栏                                │
│  ┌─────────────────────────────────────────┐  │
│  │    调整学习方案 / 选项 / 思考 / 结果     │  │
│  ├─────────────────────────────────────────┤  │
│  │  [提示小字]                   [发送/按钮] │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  2️⃣ 学习档案  *                       ↩ ✎   │  │
│  ┌──────┬─────────────────────────────────┐  │
│  │ 项目 │ 内容                            │  │
│  └──────┴─────────────────────────────────┘  │
│                                               │
│  3️⃣ 学习计划概览  *                    ↩ ✎  │  │
│  ┌───────────────────────────────────────┐   │
│  │ [1 基础][2 知识][3 专项][4 …] ← 滑轨  │   │
│  ├───────────────────────────────────────┤   │
│  │  [第 1 阶段] 基础入门                 │   │
│  │  掌握集合、函数等核心概念与基本方法    │   │
│  │  章节 3 章  任务 12 个  预估 8 小时   │   │
│  └───────────────────────────────────────┘   │
│                                               │
├───────────────────────────────────────────────┤
│          [  确认方案  ]  绿色/灰色            │  ← 底部固定
└───────────────────────────────────────────────┘
```

---

## 三、核心交互设计：三区变更 + 统一确认

### 3.1 设计原则

学习方案的更改分为三个独立入口：
1. **AI 对话栏**：通过文字输入和选项与 AI 沟通需求
2. **学习档案**：直接编辑档案表格中的字段值
3. **学习计划**：编辑计划内容（具体编辑方式待设计）

**不论从哪个入口发起更改，最终都通过 AI 对话栏的按钮触发方案更新**。编辑档案/计划不再自动触发 AI 思考。

### 3.2 状态变量

```ts
// 原始状态（v8 已有）
const [chatStage, setChatStage] = useState<ChatStage>("input");
const [chatInput, setChatInput] = useState("");
const [selectedOption, setSelectedOption] = useState("");
const [profileEditing, setProfileEditing] = useState(false);
const [planEditing, setPlanEditing] = useState(false);

// v9 新增：三区变更追踪
const [chatChanged, setChatChanged] = useState(false);   // AI 对话已输入或选中选项
const [profileChanged, setProfileChanged] = useState(false); // 档案已编辑确认
const [planChanged, setPlanChanged] = useState(false);    // 计划已编辑确认
const [planGenerated, setPlanGenerated] = useState(false); // 刚点击过「确认并生成学习方案」
```

### 3.3 变更追踪流程

```
chatChanged 触发条件：
  - textarea 输入非空内容时（onChange 中判断）
  - 选中 options 的任一选项时
  - 点击发送按钮后

profileChanged 触发条件：
  - 档案编辑模式点击 ✓ 确认编辑后

planChanged 触发条件：
  - 计划编辑模式点击 ✓ 确认编辑后

清除所有 dirty（三个 changed 全置 false）：
  - 点击「确认并生成学习方案」→ 同时 planGenerated = true
  - 点击「确认并继续调整」→ planGenerated 保持上一轮
  - 点击底部「确认方案」后退出调整模式（不在这时清，在生成时清）
```

### 3.4 AI 对话栏提示小字

当 `chatChanged`、`profileChanged` 或 `planChanged` 任一为 true 时，显示提示小字：

```
已说明需求；已更改学习档案；已更改学习计划。发送给AI以确认更改。
```

- 只有对应 changed 为 true 的部分才出现在文本中
- 三段之间以中文分号分隔，末尾句号
- **input 阶段**：显示在发送按钮同行左侧（`.ps-adjust-chat-send-row` 内）
- **options / ai-result 阶段**：显示在两个确认按钮上方（block 模式）

---

## 四、AI 对话栏（第一部分）

### 4.1 ChatStage 状态机

```
input ──[发送]──→ options ──[选选项]──→ (等待按钮操作)
                       ↓
              [确认并生成] / [确认并继续调整]
                       ↓
                  清 dirty → planGenerated 更新
```

### 4.2 阶段一：input

- textarea 输入框 + 右侧发送按钮（`justify-content: flex-end`，按钮始终靠右）
- textarea onChange：内容非空时立即 `setChatChanged(true)`
- 发送按钮：有内容绿色 `#059669`，空内容灰色 `#d1d5db`
- 有任何时候任一 changed 为 true → 发送按钮同行左侧显示提示小字

### 4.3 阶段二：options

- 6 个时间选项两列排布
- 点击选项 → `handleOptionSelect`（设置 selectedOption + chatChanged）
- **两个确认按钮**：
  - 未选选项时：`disabled`，灰色不可点
  - 已选选项时：绿色/白色可点击
- 按钮上方显示提示小字（如有变更）

### 4.4 阶段四：ai-result

- AI 回复卡片（mock）
- 两个确认按钮（同上，未选选项时灰色不可点）
- 按钮上方显示提示小字

### 4.5 两个确认按钮行为

| 按钮 | 行为 |
|------|------|
| 确认并生成学习方案 | `clearAllDirty()` → `planGenerated = true` |
| 确认并继续调整 | `clearAllDirty()`（planGenerated 保持原值） |

---

## 五、学习档案（第二部分）

### 5.1 标题栏

| 条件 | 标题 | 操作按钮 |
|------|------|---------|
| 未编辑 + 未 dirty | 学习档案 | 🖉 Pencil |
| dirty（已确认过编辑） | 学习档案 <span style="color:red">\*</span> | ↩ 撤回 + 🖉 Pencil |
| 编辑中 | 学习档案 | ✕ 取消 + ✓ 确认 |

- 红色星号 `*`：`color: #e53e3e`，`margin-left: 2px`
- 撤回按钮（`Undo2` 图标）：恢复 `MOCK_PROFILE` 原始值 + 清除 `profileChanged`
- 编辑中不显示撤回按钮，只有 ✕ 和 ✓

### 5.2 编辑确认

- ✓ 确认 → `setProfileEditing(false)` + `setProfileChanged(true)`
- ✕ 取消 → `setProfileEditing(false)` + 恢复 `MOCK_PROFILE` 原始值
- **不再触发 AI 思考**（与 v8 行为不同）

---

## 六、学习计划概览（第三部分）

### 6.1 标题栏

与学习档案相同的按钮逻辑：
- dirty 时标题后红色 * + Pencil 左边显示 ↩ 撤回
- 编辑中显示 ✕ + ✓（无撤回）
- 编辑内容暂未设计，✓ 仅标记 `planChanged = true`

### 6.2 阶段导航滑轨

- 复刻建课确认页的 `phase-track`：
  - 平行四边形 clip-path 切角
  - `flex: 0 0 25%`（最多 4 块可见）
  - 滚轮纵向 → 逐阶段切换，方向感知对齐：
    - **右滚（index ↑）**：选中项固定在左起第 3 位（`snapIndex = index - 2`，尾端贴边）
    - **左滚（index ↓）**：选中项固定在左起第 2 位（`snapIndex = index - 1`，首端贴边）
  - 点击 → 直接跳转；再次点击当前阶段 → 回到阶段信息（取消章节选中）
  - 横向 touch-pad 滑动 → 原生 `overflow-x: auto` 正常滚动
- **滚轮事件隔离**：
  - 使用原生 `addEventListener("wheel", handler, { passive: false })`
  - `|deltaY| > |deltaX|` 时拦截为阶段切换（`preventDefault` + `stopPropagation`）
  - `|deltaY| ≤ |deltaX|` 时只 `stopPropagation` 阻止冒泡，不阻止默认横向滚动
- **防页面滚动泄漏**：`.phase-track` 添加 `overscroll-behavior: contain`，切断浏览器 scroll chaining 到父容器
- **监听器生命周期**：useEffect 依赖包含 `adjustMode`，确保切到调整面板时重新绑定 wheel 事件

### 6.3 章节横向画布（PlanOverviewCanvas）

阶段导航栏下方新增横向画布，展示当前阶段的所有章节：

```
┌───────────────────────────────────────────────────────┐
│  [1] 集合与逻辑  ──→  [2] 函数基础  ──→  [3] 基本初等函数  │
└───────────────────────────────────────────────────────┘
```

- 章节块横向排列，序号 badge + 标题，`position: absolute` 精确定位
- SVG `<line>` + `<marker>` 右指向箭头连接相邻章节
- `overflow-x: auto` + `overflow-y: hidden` + `scrollbar-gutter: stable`（与上划栏中间栏同款自动隐藏+预留空间滚动条）
- **只显示章节选项卡，不显示任务**，无已完成绿色填色
- 点击章节 → 详情栏切换为章节信息；再次点击 → 回到阶段信息

### 6.4 详情栏（PlanOverviewDetail）

画布下方详情栏，复用 `PhaseDetail` 的 `.ps-detail-section` 样式，分两种模式：

| 模式 | 内容 | 触发条件 |
|------|------|---------|
| **阶段信息** | 基础信息（序号/章节数/任务数/预估时长）+ 概述（objective） | 刚进入阶段 / 再次点击当前阶段导航栏 |
| **章节信息** | 基础信息（序号/任务数/目标深度/预估时长）+ 概述 + 相关资料列表 | 点击画布中的章节块 |

- 章节模式中「相关资料」从该章所有任务的 `materials` 汇总，纯列表展示（无按钮态）
- 交互状态由 `overviewSelectedUnitId`（`string | null`）驱动

---

## 七、底部确认方案按钮

- **位置**：面板底部固定，`.ps-adjust-footer` 内
- **尺寸**：满宽，高度与 `.ps-btn` 一致（`border-radius: 10px`）
- **可点击条件**：`planGenerated === true` **且** `profileChanged === false` **且** `planChanged === false`
- **状态**：
  - 可点击：绿色背景 `var(--green-700)`，白色文字
  - 不可点击：灰色背景 `#d1d5db`，灰色文字 `#9ca3af`，`disabled`
- **点击行为**：`setAdjustMode(false)` → 回到三栏学习计划预览

---

## 八、滚动与布局

- `.ps-adjust-body`：`overflow-y: auto` + `scrollbar-gutter: stable`（始终预留 5px 滚动条空间）
- WebKit 滚动条：5px 宽，灰色滑块 `#c7d0cc`，hover 加深至 `#a3b0aa`
- `.ps-adjust-body::-webkit-scrollbar-track`：透明背景

---

## 九、当前功能状态

| 功能 | 状态 |
|------|------|
| AI 对话 input / options / ai-thinking / ai-result | ✅ 完成 |
| 三区变更追踪（chatChanged / profileChanged / planChanged） | ✅ 完成 |
| 提示小字动态显示 | ✅ 完成 |
| 红色星号 dirty 标记 | ✅ 完成 |
| 撤回按钮 + 编辑/取消/确认三态按钮 | ✅ 完成 |
| 未选选项时确认按钮灰色不可点 | ✅ 完成 |
| 底部确认方案按钮（条件绿色可点） | ✅ 完成 |
| 阶段导航滑轨（方向感知对齐 + 滚轮隔离子页面滚动） | ✅ 完成 |
| 章节横向画布（PlanOverviewCanvas） | ✅ 完成 |
| 阶段/章节详情栏（PlanOverviewDetail） | ✅ 完成 |
| 编辑计划具体内容 | 🔴 待后续设计 |
| 真实 AI 对话接入 | 🔴 待后续 |
| 「确认并生成学习方案」后端逻辑 | 🔴 待后续 |
| 「确认并继续调整」后端逻辑 | 🔴 待后续 |

---

## 十、文件清单

| 文件 | 改动 |
|------|------|
| `apps/web/src/components/PhaseSummary.tsx` | 新增 ~5 个状态变量（overviewSelectedUnitId 等）、~8 个 handler 重写、提示小字渲染、阶段滑轨+方向感知 scrollTrackTo、章节画布 PlanOverviewCanvas、阶段/章节详情栏、底部确认按钮、原生 wheel 事件隔离 |
| `apps/web/src/styles.css` | 新增 ~110 行：overscroll-behavior、章节画布+SVG 箭头、章节节点、资料列表、列表 reset、撤回按钮样式等 |
| `docs/core-features/learning-plan-redesign-v9.md` | 更新第六节（画布+详情栏设计）、第九节（功能状态）、第十节（文件清单） |
