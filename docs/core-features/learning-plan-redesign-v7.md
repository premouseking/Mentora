# 学习计划重设计 v7

> 版本：v7 | 日期：2026-06-29 | 状态：课程页上划栏实现完成（左/中/右三栏 + mock 数据）

---

## 变更记录

| 版本 | 主要变更 |
|------|----------|
| v1 | Phase → Chapter → Task 三层结构，课程页上划栏树状图设计 |
| v2 | 建课确认页：横向箭头导航 + 下方内容区；阶段类型池 8 种 |
| v3 | 去掉加强/精简按钮；补充 AI 分阶段 prompt 策略；明确区分两页职责 |
| v4 | 确立调整入口为「调整计划」按钮（不直接改面板）；明确当前 Task 为 mock |
| v5 | 建课确认页导航栏重设计：滑轨式滚动 + 箭头形阶段块 + 空详情占位区 |
| v6 | 课程页上划栏重设计：三栏布局（纵向阶段导航 + 主干分支画板 + 可收起详情栏）；关闭改为顶部 X 按钮 |
| **v7** | v6 实现落地 + 实现过程中的设计调整：六边形箭头块（真凹凸）、双向 snap、SVG 连线 + DOM 节点坐标预计算、右栏三段内容（基础信息/概述/相关资料）、任务类型展示规则、交付方式分类、练习按钮、边框样式 |

---

## 一、全局约束（继承 v6）

| 约束 | 说明 |
|------|------|
| **全部 Mock** | 所有数据均为 mock，不连后端 |
| **调整计划独立页** | 按钮指向独立页面，暂未设计，仅占位 |
| **去掉加强/精简** | 已移除 |
| **父组件下拉关闭手势未移除** | overlay 的 onPointerDown/Move/Up 尚在，但左/中栏已加 stopPropagation 隔离 |

---

## 二、v7 新增与调整（v6 → v7 差异）

| 类别 | v6 设计 | v7 实现 / 调整 |
|------|---------|---------------|
| **左栏箭头形** | 平行四边形（v5 遗留） | **六边形箭头块**：6 顶点 clip-path 实现真正「上凹下凸」，凸尖朝下，相邻块 margin-top:-14px 嵌合 |
| **左栏 snap 规则** | 单向（建课页 copy） | **双向感知**：向下滚选中停上起第 3 位(index-2)，向上滚停下起第 3 位(index-1) |
| **左栏滚动控制** | `overflow-y: auto` + `scroll-snap` | **`overflow: hidden` + 纯 JS `scrollTo`**（避免原生滚动抢控制权），用实测 `offsetTop` 替代估算 |
| **中栏连线方案** | SVG `<path>`（原文） | **SVG `<line>` + `<marker>` 箭头**：章节间主干带向下箭头（`<marker>` 表示学习顺序），任务分支"丰"字形无箭头 |
| **节点布局** | 运行时 getBoundingClientRect | **预算坐标 + DOM absolute + SVG 覆盖层共享坐标系**，无运行时测量 |
| **右栏内容** | 留空占位 | **三段内容**：①基础信息（键值对）②概述（拼句文本）③相关资料（仅任务，圆角按钮一行一个） |
| **任务标题** | 统一「类型 + 序号」 | 讲解/项目用 `knowledge_point` 字段名；练习用「练习 N」 |
| **任务类型标签** | 讲解/练习/项目/复习 | **讲解→「知识点」**，其余不变 |
| **交付方式** | 统一映射 `delivery_mode` | 讲解→「自主确认」，练习→「完成练习」，其他沿用原映射 |
| **练习按钮** | 无 | 练习任务右栏底部绿色「开始练习」按钮 |
| **节点边框** | 1px | 统一 1.5px `--border-strong` |
| **滚动条** | 默认 | 中/右栏加 `scrollbar-gutter: stable` 防抖 |
| **右栏收起按钮** | ◀ / ▶ | 🔴 未实现（暂不需要） |

---

## 三、左栏实现细节

### 3.1 六边形箭头块

弃用 v5 建课确认页的平行四边形，改为真正的六边形箭头（上凹下凸，凸尖朝下）：

**中间块**（6 顶点）：
```css
clip-path: polygon(0 0, 50% 14px, 100% 0, 100% calc(100% - 14px), 50% 100%, 0 calc(100% - 14px));
```

**首块**：上边平（5 顶点），`margin-top: 0`
**尾块**：下边平（5 顶点）

相邻块 `margin-top: -14px`，凸尖嵌合凹口，形成连续的箭头链。

> 建课确认页的平行四边形待后续同步改为六边形。

### 3.2 双向 snap 滚动规则

与建课确认页的单向规则（始终 `index-2`）不同，v7 改为方向感知：

| 滚动方向 | 选中停留位置 | 公式 |
|----------|-------------|------|
| 向下（index 增大） | 上起第 3 位 | `snapStart = clamp(index-2, 0, N-4)` |
| 向上（index 减小） | 下起第 3 位 | `snapStart = clamp(index-1, 0, N-4)` |

- 当选中的是首项或末项时，出现在 1 号位 / 4 号位（不受 2/3 号位约束）
- `targetRef` 记录方向，保持连续滚动时的方向一致性

### 3.3 滚动实现三关键

| 问题 | 修复 |
|------|------|
| CSS `overflow-y: auto` + React `onWheel` passive 导致原生滚动抢 `scrollTo` | `overflow: hidden`，纯 JS `scrollTo` |
| `flex: 0 0 25%` + `min-height: 56px` 块高不均 | `min-height: 0`，让 flex 严格生效 |
| `basis = clientHeight/4` 估算含误差 | 用 `querySelectorAll` 取实测 `block.offsetTop` |

### 3.4 点击交互

- 点击左栏阶段 → `PhaseNav` 回调 `onSelect(i)`，父组件 `handleSelectPhase` 切换中栏 + 设 `selected = {kind:"phase"}"`
- 点击当前已选中阶段 → 仅把右栏切回阶段信息（不切换中栏）
- **坑**：父组件 overlay 的 `handlePSPointerDown` 调了 `setPointerCapture`，会劫持 click 事件。左栏加 `onPointerDown stopPropagation` 阻断。

---

## 四、中栏实现细节

### 4.1 布局算法

`computeLayout(units)` 预计算所有节点坐标：

- 中心轴 X = `CANVAS.W / 2`（固定 600px 宽）
- 每个章节占据高度 = `max(章节块高, 任务数 × 任务高 + 间隙)`（防碰撞）
- 任务左右交替：`i % 2 === 0` → 右侧，`i % 2 === 1` → 左侧
- DOM 节点 `position: absolute`，SVG 覆盖层共享坐标系（`inset: 0; pointer-events: none`）

### 4.2 SVG 连线

- **主干箭头**：`<marker id="ps-arrow-down">` 定义向下箭头，`<line markerEnd="url(#ps-arrow-down)">` 在章节 i→i+1 之间绘制
- **分支"丰"字形**：章节中心横线 → 任务群竖线 → 每个任务短横线，均无箭头
- 连线颜色：`var(--border)`（#dce3e0）

### 4.3 滚动

`overflow: auto` + `scrollbar-gutter: stable`，支持滚轮 + 原生滚动条。未实现按住拖拽（当前原生滚动够用）。

---

## 五、右栏实现细节

### 5.1 三段内容

| 区域 | 阶段 | 章节 | 任务 |
|------|------|------|------|
| **基础信息**（键值对） | 序号、章节数、任务数、时长 | 序号、任务数、目标深度、时长 | 任务类型、交付方式、时长、是否必修 |
| **概述**（文本） | `objective` 字段 | 拼句（任务数+类型+时长） | 拼句（根据 task_type 生成） |
| **相关资料** | — | — | 圆角矩形按钮，一行一个，标题居中；无资料时显示"暂无" |

### 5.2 任务类型展示规则

| task_type | 任务类型字段 | 标题 | 交付方式 |
|-----------|-------------|------|---------|
| lecture | **知识点** | `knowledge_point` 字段名 | 自主确认 |
| exercise | 练习 | 「练习 N」 | 完成练习 |
| project | 项目 | `knowledge_point` 字段名 | 沿用 delivery_mode 映射 |
| review | 复习 | 「复习 N」 | 沿用 delivery_mode 映射 |

### 5.3 练习开始按钮

练习任务底部绿色圆角按钮「开始练习」，点击关闭上划栏（mock 阶段）。

---

## 六、实现期间的已知坑

| 现象 | 根因 | 修复 |
|------|------|------|
| 左栏阶段块点不了（click 无反应） | 父组件 overlay `setPointerCapture` 劫持 pointer 事件 | 左栏加 `onPointerDown stopPropagation` |
| 左栏滚动位置错位（`*2*345` 等异常状态） | `overflow-y: auto` 原生滚动 + JS `scrollTo` 打架 | `overflow: hidden` |
| 左栏滚动错位（续） | `min-height: 56px` 覆盖 `flex: 0 0 25%`，块高不均 | `min-height: 0` |
| 滚动位置错位（续） | `basis = clientHeight/4` 含亚像素误差 | 用实测 `block.offsetTop` |
| 类型报错 | `courseApi.ts` 有两个同名 `export interface PlanPhase`（58 行 / 241 行）声明合并 | 组件内用本地 `NavPhase` 类型（仅 id+title） |
| 中栏横向滚动异常 | `flex: center` + `overflow: auto` 经典 bug，左侧内容被裁 | 未修（当前固定 600px 宽，通常不横向超出；后续如要自由宽度需改为 `justify-content: flex-start` + JS 同步 scrollLeft） |

---

## 七、当前边界

| 项目 | 状态 |
|------|------|
| 课程页上划栏三栏布局 | ✅ v7 完成 |
| 左栏纵向阶段导航 + 六边形箭头 | ✅ v7 完成 |
| 中栏主干分支画板（SVG + DOM） | ✅ v7 完成 |
| 右栏详情（三段内容） | ✅ v7 完成 |
| Mock 数据（5 阶段、任务含 knowledge_point / materials） | ✅ v7 完成 |
| 建课确认页平行四边形改六边形 | 🔴 待后续 |
| 父组件下拉关闭手势移除 | 🔴 待后续 |
| 右栏收起按钮 | 🔴 待后续 |
| 中栏按住拖拽 | 🔴 可选（当前原生滚动够用） |
| 全部 Mock、不连后端 | ✅ |

---

## 八、文件清单

| 文件 | 改动 |
|------|------|
| `apps/web/src/components/PhaseSummary.tsx` | 完全重构（~780 行）：Mock 数据 + PhaseNav + PhaseCanvas + PhaseDetail + PhaseSummary 主体 |
| `apps/web/src/styles.css` | 新增 ~180 行：左栏六边形箭头、中栏画板节点/SVG、右栏三段内容、边框加粗、滚动条稳定 |
