import { lazy, Suspense } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";

const ModelPage = lazy(() => import("./pages/ModelPage").then((m) => ({ default: m.ModelPage })));
const ComparePage = lazy(() => import("./pages/ComparePage").then((m) => ({ default: m.ComparePage })));
const EdaPage = lazy(() => import("./pages/EdaPage").then((m) => ({ default: m.EdaPage })));
const LearnPage = lazy(() => import("./pages/LearnPage").then((m) => ({ default: m.LearnPage })));
const StreamingPage = lazy(() => import("./pages/StreamingPage").then((m) => ({ default: m.StreamingPage })));

function PageFallback() {
  return <div className="state-message">Loading…</div>;
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/models/arima" replace />} />
          <Route
            path="/models/:modelKey"
            element={
              <Suspense fallback={<PageFallback />}>
                <ModelPage />
              </Suspense>
            }
          />
          <Route
            path="/compare"
            element={
              <Suspense fallback={<PageFallback />}>
                <ComparePage />
              </Suspense>
            }
          />
          <Route
            path="/eda"
            element={
              <Suspense fallback={<PageFallback />}>
                <EdaPage />
              </Suspense>
            }
          />
          <Route
            path="/learn"
            element={
              <Suspense fallback={<PageFallback />}>
                <LearnPage />
              </Suspense>
            }
          />
          <Route
            path="/streaming"
            element={
              <Suspense fallback={<PageFallback />}>
                <StreamingPage />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </HashRouter>
  );
}
