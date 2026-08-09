import { useEffect, useState } from "react";
import { useMsal, MsalAuthenticationTemplate } from "@azure/msal-react";
import { InteractionType } from "@azure/msal-browser";
import Sidebar, { type View } from "./components/Sidebar";
import Login from "./components/Login";
import Home from "./pages/Home";
import Demo1Discovery from "./pages/Demo1Discovery";
import Demo2FineTune from "./pages/Demo2FineTune";
import Demo3Comparison from "./pages/Demo3Comparison";
import { api, setAuthTokenProvider, type HealthResponse } from "./api/client";
import { isEntraEnabled, apiScope } from "./auth/msalConfig";

const SESSION_KEY = "foundry-demo-session";

/**
 * Two independent gates in front of the same app shell:
 *
 * - Local/mock dev (`isEntraEnabled` false — no VITE_ENTRA_* set at build
 *   time): the original demo/demo123 sessionStorage gate, unchanged.
 * - The hosted public deployment (`isEntraEnabled` true): real Microsoft
 *   sign-in via MSAL.js, required because the backend behind it has a real
 *   Container Apps Easy Auth wall — the demo/demo123 screen was never
 *   enforced server-side, so it stays local-only rather than giving a false
 *   sense of protection in public (see README's known-issues list).
 */
export default function App() {
  return isEntraEnabled ? <EntraGatedApp /> : <DemoGatedApp />;
}

/**
 * `MsalAuthenticationTemplate` (not a hand-rolled loginRedirect-in-a-
 * useEffect) deliberately — this project's own hand-rolled version hit a
 * real race twice in practice (MSAL's `inProgress` state has a window on
 * first render, before the provider's own redirect-handling effect has run,
 * where a naive "idle → trigger login" check fires a second competing
 * loginRedirect and cancels the one already in flight). This component is
 * msal-react's purpose-built answer to that exact race, so it's used
 * instead of continuing to patch a bespoke state machine.
 */
export function EntraGatedApp() {
  return (
    <MsalAuthenticationTemplate
      interactionType={InteractionType.Redirect}
      authenticationRequest={{ scopes: [apiScope] }}
      loadingComponent={() => (
        <div className="login-shell">
          <p style={{ color: "#fff" }}>Signing in…</p>
        </div>
      )}
      errorComponent={({ error }) => (
        <div className="login-shell">
          <div className="login-card">
            <p>Sign-in failed: {error?.errorMessage ?? "unknown error"}</p>
          </div>
        </div>
      )}
    >
      <EntraAuthenticatedShell />
    </MsalAuthenticationTemplate>
  );
}

function EntraAuthenticatedShell() {
  const { instance, accounts } = useMsal();

  useEffect(() => {
    setAuthTokenProvider(async () => {
      try {
        const result = await instance.acquireTokenSilent({
          scopes: [apiScope],
          account: accounts[0],
        });
        return result.accessToken;
      } catch (err) {
        console.error("acquireTokenSilent failed, falling back to redirect:", err);
        await instance.acquireTokenRedirect({ scopes: [apiScope] });
        return null;
      }
    });
    return () => setAuthTokenProvider(null);
  }, [instance, accounts]);

  const username = accounts[0]?.username ?? "signed-in user";
  return <AppShell username={username} onLogout={() => instance.logoutRedirect()} />;
}

function DemoGatedApp() {
  const [username, setUsername] = useState<string | null>(() =>
    sessionStorage.getItem(SESSION_KEY),
  );

  function handleLogin(name: string) {
    sessionStorage.setItem(SESSION_KEY, name);
    setUsername(name);
  }

  function handleLogout() {
    sessionStorage.removeItem(SESSION_KEY);
    setUsername(null);
  }

  if (!username) {
    return <Login onLogin={handleLogin} />;
  }

  return <AppShell username={username} onLogout={handleLogout} />;
}

function AppShell({ username, onLogout }: { username: string; onLogout: () => void }) {
  const [view, setView] = useState<View>("home");
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  function handleLogout() {
    onLogout();
    setView("home");
  }

  return (
    <div className="app-shell">
      <Sidebar
        active={view}
        onNavigate={setView}
        username={username}
        onLogout={handleLogout}
        demoMode={health?.demo_mode ?? "…"}
      />
      <main className="main-canvas">
        {view === "home" && <Home health={health} onNavigate={setView} />}
        {view === "discovery" && <Demo1Discovery />}
        {view === "finetune" && <Demo2FineTune />}
        {view === "comparison" && <Demo3Comparison />}
      </main>
    </div>
  );
}
