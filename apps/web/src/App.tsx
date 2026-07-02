import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AuthGate } from "./components/AuthGate";
import { AppShell } from "./components/AppShell";
import { PageSkeleton } from "./components/PageSkeleton";
import { CourseCreationProvider } from "./components/CourseCreationContext";

const AuthPage = lazy(() => import("./pages/AuthPage").then((m) => ({ default: m.AuthPage })));
const CoursesPage = lazy(() => import("./pages/CoursesPage").then((m) => ({ default: m.CoursesPage })));
const CourseWorkspacePage = lazy(() =>
  import("./pages/CourseWorkspacePage").then((m) => ({ default: m.CourseWorkspacePage })),
);
const LearningTaskPage = lazy(() =>
  import("./pages/LearningTaskPage").then((m) => ({ default: m.LearningTaskPage })),
);
const LibraryPage = lazy(() => import("./pages/LibraryPage").then((m) => ({ default: m.LibraryPage })));
const LibraryReaderPage = lazy(() =>
  import("./pages/LibraryReaderPage").then((m) => ({ default: m.LibraryReaderPage })),
);
const HistoryPage = lazy(() => import("./pages/HistoryPage").then((m) => ({ default: m.HistoryPage })));
const ParsingLabPage = lazy(() =>
  import("./pages/ParsingLabPage").then((m) => ({ default: m.ParsingLabPage })),
);
const StageSummaryPage = lazy(() =>
  import("./pages/StageSummaryPage").then((m) => ({ default: m.StageSummaryPage })),
);
const BuildProfilePage = lazy(() =>
  import("./pages/SetupPages").then((m) => ({ default: m.BuildProfilePage })),
);
const ConfirmPlanPage = lazy(() =>
  import("./pages/SetupContinuationPages").then((m) => ({ default: m.ConfirmPlanPage })),
);

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

function LazyRoute({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageSkeleton />}>{children}</Suspense>;
}

export function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={(
          <LazyRoute>
            <AuthPage />
          </LazyRoute>
        )}
      />
      <Route element={<AuthGate />}>
        <Route path="/" element={<Navigate replace to="/courses" />} />
        <Route
          path="/courses"
          element={(
            <LazyRoute>
              <CoursesPage />
            </LazyRoute>
          )}
        />
        <Route element={<CourseCreationProvider><Outlet /></CourseCreationProvider>}>
          <Route
            path="/courses/new"
            element={(
              <LazyRoute>
                <BuildProfilePage />
              </LazyRoute>
            )}
          />
          <Route
            path="/courses/new/plan"
            element={(
              <LazyRoute>
                <ConfirmPlanPage />
              </LazyRoute>
            )}
          />
        </Route>
        <Route
          path="/courses/:courseId"
          element={(
            <LazyRoute>
              <CourseWorkspacePage />
            </LazyRoute>
          )}
        />
        <Route
          path="/courses/:courseId/tasks/:taskId"
          element={(
            <LazyRoute>
              <LearningTaskPage />
            </LazyRoute>
          )}
        />
        <Route
          path="/courses/:courseId/phases/:phaseId/summary"
          element={(
            <LazyRoute>
              <StageSummaryPage />
            </LazyRoute>
          )}
        />
        <Route
          path="/library"
          element={(
            <LazyRoute>
              <LibraryPage />
            </LazyRoute>
          )}
        />
        <Route
          path="/library/read/:sourceVersionId"
          element={(
            <LazyRoute>
              <LibraryReaderPage />
            </LazyRoute>
          )}
        />
        <Route
          path="/history"
          element={(
            <LazyRoute>
              <HistoryPage />
            </LazyRoute>
          )}
        />
        <Route
          path="/lab/parsing"
          element={(
            <LazyRoute>
              <ParsingLabPage />
            </LazyRoute>
          )}
        />
        <Route path="/notifications" element={<PlaceholderPage title="通知" />} />
        <Route path="/settings" element={<PlaceholderPage title="设置" />} />
        <Route path="*" element={<Navigate replace to="/courses" />} />
      </Route>
    </Routes>
  );
}
