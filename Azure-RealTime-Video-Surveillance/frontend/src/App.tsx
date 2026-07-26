import { useCallback, useEffect, useRef, useState } from "react";
import { logAuditEvent } from "./api/client";
import { ContosoLogo } from "./components/ContosoLogo";
import { Dashboard } from "./components/Dashboard";
import { IdleWarningModal } from "./components/IdleWarningModal";
import { TopNav, type PageId } from "./components/TopNav";
import { useAuth } from "./hooks/useAuth";
import { useIdleLogout } from "./hooks/useIdleLogout";
import { AuditTrailPage } from "./pages/AuditTrailPage";
import { ObservabilityPage } from "./pages/ObservabilityPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SettingsPage } from "./pages/SettingsPage";

const IDLE_TIMEOUT_MS = 10 * 60 * 1000;
const IDLE_WARNING_MS = 60 * 1000;

export default function App() {
  const { user, loading } = useAuth();
  const [activePage, setActivePage] = useState<PageId>("capture");
  const loggedSignIn = useRef(false);

  useEffect(() => {
    if (user && !loggedSignIn.current) {
      loggedSignIn.current = true;
      void logAuditEvent(user.userDetails, "sign_in", user.identityProvider);
    }
  }, [user]);

  const handleIdleTimeout = useCallback(() => {
    if (user) void logAuditEvent(user.userDetails, "auto_logout_idle", "10 min inactivity timeout");
    window.location.href = "/.auth/logout?post_logout_redirect_uri=/";
  }, [user]);

  const { secondsRemaining, stayActive } = useIdleLogout(
    IDLE_TIMEOUT_MS,
    IDLE_WARNING_MS,
    Boolean(user),
    handleIdleTimeout
  );

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <ContosoLogo />
          <p className="brand-tagline">Real-Time Surveillance — Capture, analyze with Azure AI Vision, and alert</p>
        </div>
        {user && (
          <div className="user-bar">
            <span>Signed in as {user.userDetails}</span>
            <a href="/.auth/logout?post_logout_redirect_uri=/">Sign out</a>
          </div>
        )}
      </header>
      {loading ? (
        <p className="capture-hint">Checking sign-in status…</p>
      ) : user ? (
        <>
          <TopNav activePage={activePage} onNavigate={setActivePage} />
          <main>
            {activePage === "capture" && <Dashboard />}
            {activePage === "profile" && <ProfilePage user={user} />}
            {activePage === "settings" && <SettingsPage />}
            {activePage === "observability" && <ObservabilityPage />}
            {activePage === "audit" && <AuditTrailPage />}
          </main>
          {secondsRemaining !== null && (
            <IdleWarningModal secondsRemaining={secondsRemaining} onStayActive={stayActive} />
          )}
        </>
      ) : (
        <div className="panel signed-out-panel">
          <h3>You're signed out</h3>
          <p className="capture-hint">Sign in with your Microsoft account to access the dashboard.</p>
          <a className="button-link" href="/.auth/login/aad?post_login_redirect_uri=/">
            Sign in
          </a>
        </div>
      )}
    </div>
  );
}
