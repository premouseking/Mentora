import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { CoursesPage } from "./pages/CoursesPage";
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
      <Route path="/" element={<Navigate replace to="/courses" />} />
      <Route path="/courses" element={<CoursesPage />} />
      <Route path="/courses/new" element={<DescribeGoalPage />} />
      <Route path="/courses/new/clarify" element={<ClarifyPage />} />
      <Route path="/library" element={<PlaceholderPage title="资源库" />} />
      <Route path="/history" element={<PlaceholderPage title="学习记录" />} />
      <Route path="/notifications" element={<PlaceholderPage title="通知" />} />
      <Route path="/settings" element={<PlaceholderPage title="设置" />} />
      <Route path="*" element={<Navigate replace to="/courses" />} />
    </Routes>
  );
}
