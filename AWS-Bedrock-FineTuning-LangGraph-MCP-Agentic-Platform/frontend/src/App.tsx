import { useState } from "react";

import { CostBanner } from "./components/CostBanner";
import { LeftNav } from "./components/LeftNav";
import { LoginStub } from "./components/LoginStub";
import { TopBar } from "./components/TopBar";
import { DemoScenario } from "./pages/DemoScenario";
import { HomePage } from "./pages/HomePage";
import { LearningMLPage } from "./pages/LearningMLPage";

const DEMO_SESSION_KEY = "bedrock-platform-demo-session";

export function App() {
  // DELIBERATE INSECURE STUB: persisting only a "logged in as demo" flag in
  // localStorage so a page refresh doesn't force re-login. This is not a real
  // session/token and grants no actual access — see insecure_demo_auth.py.
  const [username, setUsername] = useState<string | null>(
    () => localStorage.getItem(DEMO_SESSION_KEY),
  );
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [showLearningMl, setShowLearningMl] = useState(false);

  function handleLogin(user: string) {
    localStorage.setItem(DEMO_SESSION_KEY, user);
    setUsername(user);
  }

  function handleSignOut() {
    localStorage.removeItem(DEMO_SESSION_KEY);
    setUsername(null);
  }

  if (!username) {
    return <LoginStub onLogin={handleLogin} />;
  }

  return (
    <div className="app-shell">
      <TopBar username={username} onSignOut={handleSignOut} />
      <div className="body-row">
        <LeftNav
          selectedScenarioId={selectedScenarioId}
          learningMlActive={showLearningMl}
          onSelectHome={() => {
            setSelectedScenarioId(null);
            setShowLearningMl(false);
          }}
          onSelectScenario={(id) => {
            setSelectedScenarioId(id);
            setShowLearningMl(false);
          }}
          onSelectLearningMl={() => {
            setSelectedScenarioId(null);
            setShowLearningMl(true);
          }}
        />
        <main className="content-pane">
          {selectedScenarioId ? (
            <DemoScenario scenarioId={selectedScenarioId} />
          ) : showLearningMl ? (
            <LearningMLPage />
          ) : (
            <HomePage />
          )}
        </main>
      </div>
      <CostBanner />
    </div>
  );
}
