# 阶段总结与方案调整实现计划

**目标：** 构建阶段总结页，展示学习证据、预览下一阶段，并在应用 AI 方案调整前要求用户明确确认。

**架构：** 新增一个路由级页面，由四个聚焦的展示组件与本地原型状态组成。复用现有桌面 shell 与课程视觉 token；阶段过渡与方案调整作为独立决策。从课程工作台与已完成 inline 检测串联入口。

**技术栈：** React 19、TypeScript、React Router、Lucide React、CSS、Vitest、Vite。

---

### 任务 1：创建视觉参考

**涉及文件：**
- 新建：`docs/design/concepts/desktop-stage-summary-v1.png`

- [ ] **步骤 1：生成完整桌面概念图**

创建 1280×900 Mentora 桌面画面，包含：

- 既有桌面 shell 与课程上下文；
- 已完成的「重点突破」阶段总结；
- 已掌握、需补强、未完成三类证据分组；
- 紧凑的「综合应用」下一阶段预览；
- 一条方案调整建议及折叠/展开的影响说明；
- 主操作「进入下一阶段」与次操作「先补强薄弱项」；
- 白底、深绿主操作、克制边框，无渐变或卡片网格。

- [ ] **步骤 2：评审概念图**

使用 `view_image`，确认证据、下一阶段、调整决策与过渡操作可读，且不暴露完整下一阶段任务列表。

### 任务 2：添加阶段总结数据与路由

**涉及文件：**
- 修改：`apps/web/src/App.tsx`
- 修改：`apps/web/src/data/courses.ts`
- 新建：`apps/web/src/pages/StageSummaryPage.tsx`

- [ ] **步骤 1：添加结构化原型数据**

添加类型化数组：

```ts
type EvidenceState = "mastered" | "reinforce" | "unfinished";

type StageEvidence = {
  id: string;
  name: string;
  source: string;
  detail: string;
  state: EvidenceState;
};
```

至少包含两条已掌握、两条需补强、一条未完成。添加下一阶段预览与调整影响行。

- [ ] **步骤 2：注册路由**

添加：

```tsx
<Route
  path="/courses/:courseId/phases/:phaseId/summary"
  element={<StageSummaryPage />}
/>
```

- [ ] **步骤 3：创建页面组合**

实现 `StageSummaryPage` 及本地状态：

```ts
type AdjustmentDecision = "pending" | "accepted" | "kept";

const [impactOpen, setImpactOpen] = useState(false);
const [adjustmentDecision, setAdjustmentDecision] =
  useState<AdjustmentDecision>("pending");
const [transitionNotice, setTransitionNotice] = useState<string | null>(null);
```

渲染语义化页头、证据区、下一阶段预览、调整区与过渡操作。

### 任务 3：实现聚焦组件与交互

**涉及文件：**
- 新建：`apps/web/src/components/stage-summary/StageEvidenceList.tsx`
- 新建：`apps/web/src/components/stage-summary/NextPhasePreview.tsx`
- 新建：`apps/web/src/components/stage-summary/PlanAdjustmentCard.tsx`
- 新建：`apps/web/src/components/stage-summary/StageTransitionActions.tsx`
- 修改：`apps/web/src/pages/StageSummaryPage.tsx`

- [ ] **步骤 1：实现证据分组**

按 `state` 分组，展示每条证据的来源与详情。颜色与图标不能作为唯一状态信号。

- [ ] **步骤 2：实现下一阶段预览**

展示「综合应用」目标、三条代表性任务、与当前阶段的关系及薄弱项引用工作量文案。

- [ ] **步骤 3：实现调整影响**

卡片默认折叠。「查看调整影响」展开新增/变更任务与未受影响范围。「接受调整」显示「已应用」；「保持原方案」显示「已保留原方案」。

- [ ] **步骤 4：实现过渡操作**

「进入下一阶段」显示成功提示后导航至课程工作台。「先补强薄弱项」返回并带 `?focus=reinforcement`。

### 任务 4：串联既有学习链路

**涉及文件：**
- 修改：`apps/web/src/pages/LearningTaskPage.tsx`
- 修改：`apps/web/src/pages/CourseWorkspacePage.tsx`

- [ ] **步骤 1：添加答对后的过渡入口**

答对后显示单一链接：

```tsx
<Link to={`/courses/${courseId}/phases/focus/summary`}>
  查看阶段总结
</Link>
```

- [ ] **步骤 2：添加课程页回访入口**

在活动阶段标题或阶段任务标题旁添加低强调「查看阶段总结」链接，不再新增大卡片。

- [ ] **步骤 3：展示补强回访状态**

在课程工作台读取 `focus=reinforcement`，将推荐任务文案替换为最高优先级补强项，并显示可关闭的上下文说明。

### 任务 5：样式与响应式

**涉及文件：**
- 修改：`apps/web/src/styles.css`

- [ ] **步骤 1：添加桌面布局样式**

使用：

```css
.stage-summary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(280px, 0.75fr);
  gap: 22px;
}
```

证据保持紧凑行；调整影响为 inline 展开；过渡操作置于清晰页脚行。

- [ ] **步骤 2：添加窄窗口行为**

在既有响应式断点下堆叠证据与下一阶段预览，保持操作可读，760px 无横向溢出。

- [ ] **步骤 3：保持视觉约束**

沿用白/绿/中性 token，不添加渐变、玻璃态、仪表盘指标或等权卡片网格。

### 任务 6：验证与文档

**涉及文件：**
- 修改：`docs/design/desktop-product-ux-design.md`

- [ ] **步骤 1：运行静态检查**

运行：

```powershell
corepack pnpm typecheck:web
corepack pnpm test:web
corepack pnpm build:web
git diff --check
```

预期：所有命令退出码为 0；Vitest 可能报告无测试文件。

- [ ] **步骤 2：验证浏览器工作流**

验证：

```text
学习任务
  -> 答对
  -> 查看阶段总结
  -> 展开调整影响
  -> 接受调整
  -> 进入下一阶段
```

另验证独立路径：

```text
阶段总结
  -> 保持原方案
  -> 先补强薄弱项
  -> 带补强上下文的课程工作台
```

检查 1280×720 与 760×900 视口、无横向溢出、无控制台错误。

- [ ] **步骤 3：对比概念图与实现**

截取最新浏览器截图，对概念图与实现分别使用 `view_image`，对比文案、布局、层级、色板、证据密度、调整展开与操作优先级。

- [ ] **步骤 4：记录交付**

在 `docs/design/desktop-product-ux-design.md` 添加第四组交付说明，含路由、已完成交互及状态仍为前端模拟的事实。

- [ ] **步骤 5：提交**

仅暂存本计划涉及文件并提交：

```powershell
git commit -m "feat: 实现阶段总结与方案调整页面

新增 StageSummaryPage 及相关组件，串联课程工作台与学习任务入口。"
```
