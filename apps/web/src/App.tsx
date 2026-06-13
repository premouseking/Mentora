import { Navigate, Route, Routes } from "react-router-dom";

import { AuthGate } from "./components/AuthGate";
import { AppShell } from "./components/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { CoursesPage } from "./pages/CoursesPage";
import { CourseWorkspacePage } from "./pages/CourseWorkspacePage";
import { LearningTaskPage } from "./pages/LearningTaskPage";
import { LibraryPage } from "./pages/LibraryPage";
import { StageSummaryPage } from "./pages/StageSummaryPage";
import {
  ConfirmPlanPage,
  ConfirmProfilePage,
  SelectSourcesPage,
} from "./pages/SetupContinuationPages";
import { ClarifyPage, DescribeGoalPage } from "./pages/SetupPages";

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
        <Route path="/courses/new" element={<DescribeGoalPage />} />
        <Route path="/courses/new/clarify" element={<ClarifyPage />} />
        <Route path="/courses/new/sources" element={<SelectSourcesPage />} />
        <Route path="/courses/new/profile" element={<ConfirmProfilePage />} />
        <Route path="/courses/new/plan" element={<ConfirmPlanPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/history" element={<PlaceholderPage title="学习记录" />} />
        <Route path="/notifications" element={<PlaceholderPage title="通知" />} />
        <Route path="/settings" element={<PlaceholderPage title="设置" />} />
        <Route path="*" element={<Navigate replace to="/courses" />} />
      </Route>
    </Routes>
  );
}
