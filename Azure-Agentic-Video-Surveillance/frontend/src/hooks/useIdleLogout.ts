import { useEffect, useRef, useState } from "react";

const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "touchstart", "scroll"];

/** Tracks user activity and returns seconds-remaining once idle time enters
 * the warning window, so the UI can show a countdown before actually
 * redirecting to /.auth/logout. `enabled` gates the whole thing (only run
 * while signed in -- no point idling-out an already-signed-out screen).
 */
export function useIdleLogout(timeoutMs: number, warningMs: number, enabled: boolean, onTimeout: () => void) {
  const lastActivityRef = useRef(Date.now());
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);

  useEffect(() => {
    if (!enabled) {
      setSecondsRemaining(null);
      return;
    }

    lastActivityRef.current = Date.now();
    const markActive = () => {
      // Only reset while no warning is showing -- once the countdown is
      // visible, activity should go through the explicit "Stay signed in"
      // button (stayActive), not silently swallow the warning on a stray
      // mouse twitch.
      setSecondsRemaining((current) => {
        if (current !== null) return current;
        lastActivityRef.current = Date.now();
        return current;
      });
    };
    ACTIVITY_EVENTS.forEach((event) => window.addEventListener(event, markActive));

    const interval = setInterval(() => {
      const idleMs = Date.now() - lastActivityRef.current;
      const remainingMs = timeoutMs - idleMs;
      if (remainingMs <= 0) {
        onTimeout();
        return;
      }
      setSecondsRemaining(remainingMs <= warningMs ? Math.ceil(remainingMs / 1000) : null);
    }, 1000);

    return () => {
      ACTIVITY_EVENTS.forEach((event) => window.removeEventListener(event, markActive));
      clearInterval(interval);
    };
  }, [enabled, timeoutMs, warningMs, onTimeout]);

  const stayActive = () => {
    lastActivityRef.current = Date.now();
    setSecondsRemaining(null);
  };

  return { secondsRemaining, stayActive };
}
