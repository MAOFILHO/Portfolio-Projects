import { useEffect, useState } from "react";

export interface ClientPrincipal {
  userId: string;
  userDetails: string;
  identityProvider: string;
  userRoles: string[];
}

/** Reads the signed-in user from Azure Static Web Apps' built-in auth
 * endpoint. `/.auth/me` only exists on the deployed Static Web Apps
 * platform (not plain `vite dev`), so a fetch failure there just means
 * "no identity available in this environment" -- not an error to surface.
 */
export function useAuth(): { user: ClientPrincipal | null; loading: boolean } {
  const [user, setUser] = useState<ClientPrincipal | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch("/.auth/me");
        const payload = (await response.json()) as { clientPrincipal: ClientPrincipal | null };
        if (!cancelled) setUser(payload.clientPrincipal);
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { user, loading };
}
