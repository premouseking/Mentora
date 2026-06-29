import type { CourseSessionListItem } from "../services/courseApi";

/**
 * 内存级 mock 课程存储。
 *
 * 约定：
 * - 不接入后端，仅在当前会话中保留
 * - 刷新页面后数据丢失
 *
 * @module data/mockCourses
 */

let mockCourses: CourseSessionListItem[] = [];

/** 添加一门 mock 课程 */
export function addMockCourse(course: CourseSessionListItem): void {
  mockCourses.push(course);
}

/** 获取全部 mock 课程 */
export function getMockCourses(): CourseSessionListItem[] {
  return mockCourses;
}

/** 删除指定 mock 课程 */
export function removeMockCourse(id: string): void {
  mockCourses = mockCourses.filter((c) => c.id !== id);
}
