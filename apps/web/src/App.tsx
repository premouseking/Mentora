import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AuthGate } from "./components/AuthGate";
import { AppShell } from "./components/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { CoursesPage } from "./pages/CoursesPage";
import { CourseWorkspacePage } from "./pages/CourseWorkspacePage";
import { HistoryPage } from "./pages/HistoryPage";
import { LearningTaskPage } from "./pages/LearningTaskPage";
import { LibraryPage } from "./pages/LibraryPage";
import { ParsingLabPage } from "./pages/ParsingLabPage";
import { StageSummaryPage } from "./pages/StageSummaryPage";
import { ConfirmPlanPage } from "./pages/SetupContinuationPages";
import { BuildProfilePage } from "./pages/SetupPages";
import { CourseCreationProvider } from "./components/CourseCreationContext";

function PlaceholderPage({ title }: { title: string }) {
  return (
    <AppShell>
      <div className="placeholder-page">
        <h1>{title}</h1>
        <p>该模块将在核心建课与学习流程之后继续设计。</p>
      </div>
    </AppShell>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route element={<AuthGate />}>
        <Route path="/" element={<Navigate replace to="/courses" />} />
        <Route path="/courses" element={<CoursesPage />} />
        <Route path="/courses/:courseId" element={<CourseWorkspacePage />} />
        <Route path="/courses/:courseId/tasks/:taskId" element={<LearningTaskPage />} />
        <Route
          path="/courses/:courseId/phases/:phaseId/summary"
          element={<StageSummaryPage />}
        />
        {/* 课程创建流程共享 Context，确保跨步骤状态持久 */}
        <Route element={<CourseCreationProvider><Outlet /></CourseCreationProvider>}>
          <Route path="/courses/new" element={<BuildProfilePage />} />
          <Route path="/courses/new/plan" element={<ConfirmPlanPage />} />
        </Route>
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/lab/parsing" element={<ParsingLabPage />} />
        <Route path="/notifications" element={<PlaceholderPage title="通知" />} />
        <Route path="/settings" element={<PlaceholderPage title="设置" />} />
        <Route path="*" element={<Navigate replace to="/courses" />} />
      </Route>
    </Routes>
  );
}
