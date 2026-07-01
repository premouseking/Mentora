import { TOOL_PROGRESS } from "./assistantTypes";

export function mapStreamStateToProgress(
  state?: "running" | "completed" | "failed",
  success?: boolean,
): number {
  if (state === "running") return TOOL_PROGRESS.PROCESSING;
  if (state === "failed" || success === false) return TOOL_PROGRESS.FAILED;
  if (state === "completed" || success === true) return TOOL_PROGRESS.COMPLETED;
  return TOOL_PROGRESS.PROCESSING;
}

function extractQuery(arguments_: Record<string, unknown> | undefined): string {
  const query = arguments_?.query;
  return typeof query === "string" ? query.trim() : "";
}

export function buildToolBlockTitle(
  toolName: string,
  progress: number,
  arguments_?: Record<string, unknown>,
  fallbackMessage?: string,
): string {
  const query = extractQuery(arguments_);

  let built = "";
  if (toolName === "query_course_scope") {
    if (progress === TOOL_PROGRESS.PROCESSING || progress === TOOL_PROGRESS.GENERATING) {
      built = "正在查询课程资料范围";
    } else if (progress === TOOL_PROGRESS.COMPLETED) {
      built = "已查询课程资料范围";
    } else if (progress === TOOL_PROGRESS.FAILED) {
      built = "资料范围查询失败";
    }
  } else if (toolName === "retrieve_evidence") {
    if (progress === TOOL_PROGRESS.PROCESSING || progress === TOOL_PROGRESS.GENERATING) {
      built = query ? `正在检索资料：${query}` : "正在检索资料";
    } else if (progress === TOOL_PROGRESS.COMPLETED) {
      built = query ? `已检索资料：${query}` : "资料检索完成";
    } else if (progress === TOOL_PROGRESS.FAILED) {
      built = "资料检索失败";
    }
  } else if (progress === TOOL_PROGRESS.PROCESSING || progress === TOOL_PROGRESS.GENERATING) {
    built = "正在调用工具";
  } else if (progress === TOOL_PROGRESS.COMPLETED) {
    built = "工具调用完成";
  } else if (progress === TOOL_PROGRESS.FAILED) {
    built = "工具调用失败";
  }

  if (built) return built;
  return fallbackMessage?.trim() || "工具调用";
}

export function isHeaderOnlyTool(toolName: string): boolean {
  return toolName === "retrieve_evidence"
    || toolName === "query_course_scope"
    || toolName === "get_learning_progress";
}
