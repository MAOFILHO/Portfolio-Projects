import React from "react";
import ReactDOM from "react-dom/client";
import { MsalProvider } from "@azure/msal-react";
import App from "./App";
import "./styles/theme.css";
import { isEntraEnabled, msalInstance } from "./auth/msalConfig";

async function bootstrap() {
  const root = ReactDOM.createRoot(document.getElementById("root")!);

  // msal-browser requires an explicit async initialize() before the
  // instance is handed to MsalProvider — skipped entirely in local/mock
  // dev, where isEntraEnabled is false and msalInstance is null.
  if (isEntraEnabled && msalInstance) {
    await msalInstance.initialize();
    root.render(
      <React.StrictMode>
        <MsalProvider instance={msalInstance}>
          <App />
        </MsalProvider>
      </React.StrictMode>,
    );
    return;
  }

  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void bootstrap();
