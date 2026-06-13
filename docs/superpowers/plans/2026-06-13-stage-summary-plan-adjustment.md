# Stage Summary And Plan Adjustment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the stage summary page that presents learning evidence, previews the next phase, and requires explicit confirmation before applying an AI plan adjustment.

**Architecture:** Add one route-level page composed from four focused presentation components and local prototype state. Reuse the existing desktop shell and course visual tokens, while keeping phase transition and plan adjustment as independent decisions. Connect the page from the course workspace and the completed inline check.

**Tech Stack:** React 19, TypeScript, React Router, Lucide React, CSS, Vitest, Vite.

---

### Task 1: Create the visual reference

**Files:**
- Create: `docs/design/concepts/desktop-stage-summary-v1.png`

- [ ] **Step 1: Generate the complete desktop concept**

Create a 1280x900 Mentora desktop screen containing:

- existing desktop shell and course context;
- completed “重点突破” stage summary;
- evidence groups for mastered, needs reinforcement, and unfinished content;
- compact “综合应用” next-stage preview;
- one plan adjustment suggestion with collapsed and expanded impact treatment;
- primary “进入下一阶段” and secondary “先补强薄弱项” actions;
- white background, deep green actions, restrained borders, no gradients or card grid.

- [ ] **Step 2: Review the concept**

Use `view_image` and confirm that evidence, next stage, adjustment decision, and transition actions are readable without exposing the full next-stage task list.

### Task 2: Add stage summary data and route

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/data/courses.ts`
- Create: `apps/web/src/pages/StageSummaryPage.tsx`

- [ ] **Step 1: Add structured prototype data**

Add typed arrays for:

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

Include at least two mastered items, two reinforcement items, and one unfinished item. Add a next-phase preview and adjustment impact rows.

- [ ] **Step 2: Register the route**

Add:

```tsx
<Route
  path="/courses/:courseId/phases/:phaseId/summary"
  element={<StageSummaryPage />}
/>
```

- [ ] **Step 3: Create the page composition**

Implement `StageSummaryPage` with local state:

```ts
type AdjustmentDecision = "pending" | "accepted" | "kept";

const [impactOpen, setImpactOpen] = useState(false);
const [adjustmentDecision, setAdjustmentDecision] =
  useState<AdjustmentDecision>("pending");
const [transitionNotice, setTransitionNotice] = useState<string | null>(null);
```

Render semantic header, evidence section, next-phase preview, adjustment section, and transition actions.

### Task 3: Implement focused components and interactions

**Files:**
- Create: `apps/web/src/components/stage-summary/StageEvidenceList.tsx`
- Create: `apps/web/src/components/stage-summary/NextPhasePreview.tsx`
- Create: `apps/web/src/components/stage-summary/PlanAdjustmentCard.tsx`
- Create: `apps/web/src/components/stage-summary/StageTransitionActions.tsx`
- Modify: `apps/web/src/pages/StageSummaryPage.tsx`

- [ ] **Step 1: Implement evidence groups**

Group evidence by `state`, and show the source and detail for each item. Color and icon cannot be the only status signal.

- [ ] **Step 2: Implement the next-phase preview**

Show the “综合应用” goal, three representative tasks, the relationship to the current stage, and weak reference workload text.

- [ ] **Step 3: Implement adjustment impact**

The card starts collapsed. “查看调整影响” reveals added or changed tasks and unaffected scope. “接受调整” changes the visible status to “已应用”; “保持原方案” changes it to “已保留原方案”.

- [ ] **Step 4: Implement transition actions**

“进入下一阶段” displays a success notice and then navigates to the course workspace. “先补强薄弱项” navigates back with `?focus=reinforcement`.

### Task 4: Connect the existing learning chain

**Files:**
- Modify: `apps/web/src/pages/LearningTaskPage.tsx`
- Modify: `apps/web/src/pages/CourseWorkspacePage.tsx`

- [ ] **Step 1: Add the completed-check transition**

After the correct answer, show a single link:

```tsx
<Link to={`/courses/${courseId}/phases/focus/summary`}>
  查看阶段总结
</Link>
```

- [ ] **Step 2: Add the course-page revisit entry**

Add a low-emphasis “查看阶段总结” link beside the active phase heading or stage task heading. Do not add another large card.

- [ ] **Step 3: Show reinforcement return state**

Read `focus=reinforcement` in the course workspace and replace the recommended task copy with the highest-priority reinforcement item plus a dismissible context note.

### Task 5: Style and responsive behavior

**Files:**
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Add desktop layout styles**

Use:

```css
.stage-summary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(280px, 0.75fr);
  gap: 22px;
}
```

Keep evidence as compact rows, adjustment impact as an inline disclosure, and transition actions in one clear footer row.

- [ ] **Step 2: Add narrow-window behavior**

At the existing responsive breakpoint, stack evidence and next-stage preview, keep actions readable, and ensure no horizontal overflow at 760px.

- [ ] **Step 3: Preserve visual constraints**

Use the current white/green/neutral token system. Do not add gradients, glass effects, dashboard metrics, or equal-weight card grids.

### Task 6: Verify and document

**Files:**
- Modify: `docs/design/desktop-product-ux-design.md`

- [ ] **Step 1: Run static checks**

Run:

```powershell
corepack pnpm typecheck:web
corepack pnpm test:web
corepack pnpm build:web
git diff --check
```

Expected: all commands exit `0`; Vitest may report no test files.

- [ ] **Step 2: Verify the browser workflow**

Verify:

```text
learning task
  -> answer correctly
  -> view stage summary
  -> expand adjustment impact
  -> accept adjustment
  -> enter next stage
```

Also verify the independent path:

```text
stage summary
  -> keep original plan
  -> reinforce weak items
  -> course workspace with reinforcement context
```

Check 1280x720 and 760x900 viewports, no horizontal overflow, and no console errors.

- [ ] **Step 3: Compare concept and implementation**

Capture the latest browser screenshot and use `view_image` on both the concept and implementation. Compare copy, layout, type hierarchy, palette, evidence density, adjustment disclosure, and action priority.

- [ ] **Step 4: Record the delivery**

Add the fourth delivery group to `docs/design/desktop-product-ux-design.md`, including routes, completed interactions, and the fact that state remains frontend-simulated.

- [ ] **Step 5: Commit**

Stage only files from this plan and commit:

```powershell
git commit -m "Design stage summary and plan adjustment"
```
