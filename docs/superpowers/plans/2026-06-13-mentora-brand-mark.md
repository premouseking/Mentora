# Mentora Brand Mark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic graduation-cap icon with the approved M-and-bookmark mark and establish the requested Chinese Conventional Commit format.

**Architecture:** Keep the logo code-native by adding one focused SVG component inside the existing shell module. Preserve the current brand link, dimensions, color tokens, and accessibility contract. Document commit types and the required subject/body structure in the repository contribution guide.

**Tech Stack:** React, TypeScript, inline SVG, CSS, Git.

---

### Task 1: Implement the brand mark

**Files:**
- Modify: `apps/web/src/components/AppShell.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] Remove the `GraduationCap` dependency.
- [ ] Add a `MentoraMark` SVG using an M outline, center bookmark, and bottom page line.
- [ ] Keep the existing 25px container and verify optical alignment.

### Task 2: Document commit conventions

**Files:**
- Modify: `CONTRIBUTING.md`

- [ ] Define supported commit types.
- [ ] Require a short Chinese subject.
- [ ] Require a blank line followed by a concrete Chinese change description.
- [ ] Include valid examples.

### Task 3: Verify and commit

**Files:**
- Verify: `apps/web/src/components/AppShell.tsx`
- Verify: `apps/web/src/styles.css`
- Verify: `CONTRIBUTING.md`

- [ ] Run `corepack pnpm typecheck:web`.
- [ ] Run `corepack pnpm test:web`.
- [ ] Run `corepack pnpm build:web`.
- [ ] Check the logo at desktop and narrow browser widths.
- [ ] Commit using the new format.
