// ============================================================================
// DELIBERATE INSECURE STUB — NOT REAL AUTHENTICATION.
// Client-side only check against hardcoded demo/demo123. Mirrors the backend's
// api/insecure_demo_auth.py banner. No Cognito, no IAM, no token, no session store.
// ============================================================================
import { useState } from "react";

import { ContosoLogo } from "./ContosoLogo";

const DEMO_USERNAME = "demo";
const DEMO_PASSWORD = "demo123";

interface LoginStubProps {
  onLogin: (username: string) => void;
}

export function LoginStub({ onLogin }: LoginStubProps) {
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (username === DEMO_USERNAME && password === DEMO_PASSWORD) {
      setError(null);
      onLogin(username);
    } else {
      setError("Invalid demo credentials — use demo / demo123.");
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <ContosoLogo />
          <span>Contoso</span>
        </div>
        <h2>Sign in</h2>
        <p>Access the Bedrock fine-tuning demo showcase.</p>

        <form onSubmit={handleSubmit}>
          <label className="login-field-label" htmlFor="username">
            Username
          </label>
          <input
            id="username"
            className="login-field"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />

          <label className="login-field-label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            className="login-field"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && <p className="login-error">{error}</p>}

          <button type="submit" className="login-submit">
            Sign in
          </button>
        </form>

        <p className="login-note">
          <strong>Demo credentials — not real authentication.</strong> This is a client-side-only
          stub (username <code>demo</code>, password <code>demo123</code>) that exists solely to
          gate the demo UI. No identity provider is involved.
        </p>
      </div>
    </div>
  );
}
