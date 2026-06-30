import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";
import { DesktopTitleBar } from "./DesktopTitleBar";

export function AuthGate() {
  const { status, loading } = useAuth();

  if (loading) {
    return (
      <div className="desktop-app auth-app">
        <DesktopTitleBar />
        <div className="auth-loading">
        <p>正在检查登录状态…</p>
        </div>
      </div>
    );
  }

  if (status.state !== "signed-in") {
    return <Navigate replace to="/login" />;
  }

  return <Outlet />;
}
