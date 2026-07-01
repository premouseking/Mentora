import { describe, expect, it } from "vitest";

import {
  buildAdjustmentSupplement,
  buildTaskDetailSummary,
  buildWorkspaceEvidencePath,
  describePlanPhaseChanges,
  getTaskCardLabel,
  getTaskCardLabelForUnit,
  getTaskDeliveryLabel,
  getTaskDetailTitle,
  getTaskTypeDetailLabel,
  profileItemsToSessionUpdate,
  resolvePlanSessionId,
  resolveTaskLearningMode,
  resolveTaskStartPath,
  summarizeUnitTasks,
} from "./courseFlowHelpers";

describe("course flow contract helpers", () => {
  it("maps confirm-page profile rows to the session update contract", () => {
    expect(profileItemsToSessionUpdate([
      { key: "goal", title: "学习目标", value: "  学习线性代数  " },
      { key: "level", title: "当前基础", value: "学过一遍" },
      { key: "pace", title: "推进方式", value: "稳定节奏" },
      { key: "timeBudget", title: "每日时长", value: "每天 1 小时" },
      { key: "deadline", title: "目标日期", value: "" },
      { key: "school", title: "学校/地区", value: "上海" },
    ])).toEqual({
      goal: "学习线性代数",
      level: "学过一遍",
      pace: "稳定节奏",
      time_budget: "每天 1 小时",
      deadline: null,
      school: "上海",
    });
  });

  it("maps inquiry Q/A rows to inquiry_history", () => {
    expect(profileItemsToSessionUpdate([
      { key: "inquiry_0", title: "每天可投入多久？", value: "1 小时" },
    ])).toEqual({
      inquiry_history: [{ question: "每天可投入多久？", answer: "1 小时" }],
    });
  });

  it("summarizes plan phase reorder and additions for replanning", () => {
    const summary = describePlanPhaseChanges(
      [
        { id: "phase-1", title: "基础", objective: "补基础" },
        { id: "phase-2", title: "强化", objective: "做练习" },
      ],
      [
        { id: "phase-2", title: "强化", objective: "做练习" },
        { id: "phase-3", title: "冲刺", objective: "模拟考试" },
        { id: "phase-1", title: "基础", objective: "补基础" },
      ],
    );

    expect(summary).toBe("阶段顺序调整为：强化、冲刺、基础；新增阶段：冲刺（模拟考试）。");
  });

  it("combines free-text and structured adjustment notes", () => {
    expect(buildAdjustmentSupplement(" 增加练习量 ", "阶段顺序调整为：强化、基础。")).toEqual({
      用户调整要求: "增加练习量",
      计划结构调整: "阶段顺序调整为：强化、基础。",
    });
  });

  it("prefers backend session_id when resolving plan session id", () => {
    expect(resolvePlanSessionId("course-1", { session_id: "session-1" })).toBe("session-1");
    expect(resolvePlanSessionId("session-2", null)).toBe("session-2");
  });
});

describe("plan task display helpers", () => {
  it("maps task types to short card labels", () => {
    expect(getTaskCardLabel("lecture")).toBe("知识点学习");
    expect(getTaskCardLabel("exercise")).toBe("练习");
    expect(getTaskCardLabel("review")).toBe("复习");
    expect(getTaskCardLabel("project")).toBe("专题突破");
    expect(getTaskTypeDetailLabel("lecture")).toBe("知识点学习");
  });

  it("uses full title in detail view and falls back when missing", () => {
    expect(getTaskDetailTitle(
      { task_type: "lecture", title: "理解补码表示与转换规则" },
      0,
    )).toBe("理解补码表示与转换规则");

    expect(getTaskDetailTitle(
      { task_type: "exercise", knowledge_point: "溢出判断" },
      1,
    )).toBe("练习 2");
  });

  it("disambiguates duplicate task types within a unit", () => {
    const tasks = [
      { task_type: "lecture" },
      { task_type: "exercise" },
      { task_type: "exercise" },
    ];
    expect(getTaskCardLabelForUnit(tasks, tasks[1], 1)).toBe("练习");
    expect(getTaskCardLabelForUnit(tasks, tasks[2], 2)).toBe("练习 2");
  });

  it("summarizes unit task mix and delivery labels", () => {
    expect(summarizeUnitTasks(
      [{ task_type: "lecture" }, { task_type: "exercise" }, { task_type: "review" }],
      90,
    )).toContain("知识点学习、练习、复习");

    expect(getTaskDeliveryLabel("exercise", "interactive")).toBe("完成练习");
    expect(getTaskDeliveryLabel("lecture", "text")).toBe("自主确认");
  });

  it("builds readable task detail summaries", () => {
    const summary = buildTaskDetailSummary(
      { task_type: "lecture", title: "原码与补码" },
      "数据表示",
      0,
      40,
    );
    expect(summary).toContain("原码与补码");
    expect(summary).toContain("数据表示");
  });

  it("resolves task learning mode and navigation paths", () => {
    expect(resolveTaskLearningMode("exercise")).toBe("exercise");
    expect(resolveTaskLearningMode("lecture")).toBe("content");
    expect(resolveTaskStartPath("course-1", "task-9")).toBe("/courses/course-1/tasks/task-9");
    expect(buildWorkspaceEvidencePath("course-1", "sv-1", "ev-1")).toBe(
      "/courses/course-1?sourceVersionId=sv-1&evidenceId=ev-1",
    );
  });
});
