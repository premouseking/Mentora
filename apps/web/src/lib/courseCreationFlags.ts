/** 演示/联调时可设为 true，建课流程跳过 AI 追问环节。 */
export const skipCourseInquiry =
  (import.meta.env.VITE_SKIP_COURSE_INQUIRY as string | undefined)?.trim().toLowerCase() === "true";
