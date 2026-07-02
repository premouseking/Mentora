import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { HashRouter } from "react-router-dom";

import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { installGlobalCrashHandlers } from "./lib/crashReporter";
import { queryClient } from "./lib/queryClient";
import "./styles.css";

installGlobalCrashHandlers();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </HashRouter>
    </QueryClientProvider>
  </StrictMode>,
);
