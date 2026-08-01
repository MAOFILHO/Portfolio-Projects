// Helpers every demo module uses. Kept deliberately small — this is a
// no-build, no-framework frontend, and the demos are the interesting part.

/** Renders the title / mechanism chip / blurb block above a demo's own UI. */
export function renderDemoHeader(root, demo) {
  const header = document.createElement("header");
  header.className = "demo-header";
  header.innerHTML = `<span class="demo-mechanism"></span><h1></h1><p class="blurb"></p>`;
  header.querySelector(".demo-mechanism").textContent = demo.mechanism;
  header.querySelector("h1").textContent = demo.title;
  header.querySelector(".blurb").textContent = demo.blurb;
  root.appendChild(header);
}

/** Escapes text destined for an innerHTML template. */
export function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

// 170s: just under the ALB's 180s idle timeout, so a stalled connection fails
// with a clear message instead of hanging indefinitely.
export const REQUEST_TIMEOUT_MS = 170_000;

export async function fetchJson(url, options) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed: HTTP ${response.status}`);
    }
    return await response.json();
  } finally {
    clearTimeout(timeoutId);
  }
}

export function postJson(url, payload) {
  return fetchJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/**
 * Consumes a Server-Sent Events stream, invoking `onEvent` per decoded event.
 *
 * The stall timer is reset by every event rather than bounding the whole run,
 * so a genuinely slow multi-step pipeline is never cut short, but a connection
 * that goes silent for 170s (just under the ALB idle timeout) fails fast.
 */
export async function streamSse(url, payload, onEvent) {
  const controller = new AbortController();
  let timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const resetStallTimer = () => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  };

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: controller.signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`Request failed: HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      resetStallTimer();
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop();
      for (const block of blocks) {
        if (!block.startsWith("data: ")) continue;
        onEvent(JSON.parse(block.slice("data: ".length)));
      }
    }
  } finally {
    clearTimeout(timeoutId);
  }
}

/** Turns an AbortError into language a demo viewer can act on. */
export function describeError(err) {
  return err.name === "AbortError"
    ? "Connection stalled (no update for a while) — a flaky network may have dropped it."
    : `Something went wrong (${err.message}).`;
}
