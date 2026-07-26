import { useEffect, useRef } from "react";

/**
 * Fires `onTick` every `intervalSeconds` while `active` is true. Ported from
 * Ai-Detect-Video-Alert's VideoStream.razor `while (isCapturing) { ...; await
 * Task.Delay(3000); }` loop, using setInterval instead of an async while-loop.
 */
export function useCaptureLoop(active: boolean, intervalSeconds: number, onTick: () => void) {
  const onTickRef = useRef(onTick);
  onTickRef.current = onTick;

  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => onTickRef.current(), Math.max(1, intervalSeconds) * 1000);
    return () => clearInterval(id);
  }, [active, intervalSeconds]);
}
