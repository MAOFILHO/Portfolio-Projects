import { PublicClientApplication, type Configuration } from "@azure/msal-browser";

// Set only in the production build (see Terraform outputs entra_signin_client_id
// / entra_tenant_id / entra_api_scope, wired in via VITE_ENTRA_* at `npm run
// build` time — see infra/terraform/hosting.tf). Local dev never sets these,
// so isEntraEnabled is false and the app falls back to the existing
// demo/demo123 gate (see Login.tsx) — nothing changes for local/mock dev.
const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID as string | undefined;
const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID as string | undefined;

export const isEntraEnabled = Boolean(clientId && tenantId);

// The scope MSAL requests to get an access token whose `aud` claim matches
// what Container Apps Easy Auth validates against (see hosting.tf's
// azuread_application.easy_auth `api` block + azapi_resource.backend_auth's
// allowedAudiences) — the standard "SPA calling its own protected API"
// pattern, one app registration playing both roles.
export const apiScope =
  (import.meta.env.VITE_ENTRA_API_SCOPE as string | undefined) ??
  (clientId ? `api://${clientId}/access_as_user` : "");

// Must exactly match the redirect URI registered on the Entra app (see
// hosting.tf's azuread_application.easy_auth) — Entra requires a trailing
// slash on a redirect URI with no path segment, but window.location.origin
// never has one, so it's appended explicitly here.
const redirectUri = `${window.location.origin}/`;

const msalConfig: Configuration = {
  auth: {
    clientId: clientId ?? "",
    authority: `https://login.microsoftonline.com/${tenantId ?? "common"}`,
    redirectUri,
    postLogoutRedirectUri: redirectUri,
  },
  cache: {
    // sessionStorage, not localStorage — closing the tab ends the session,
    // consistent with this being a demo/portfolio app, not something that
    // should stay silently signed in indefinitely on a shared machine.
    cacheLocation: "sessionStorage",
  },
};

// Only constructed when actually needed — instantiating PublicClientApplication
// with an empty clientId would be a confusing runtime error in local dev.
export const msalInstance = isEntraEnabled ? new PublicClientApplication(msalConfig) : null;
