// Shared progress-log widget: a running trail of "Agent: doing X +N.Ns"
// lines with a spinner on the currently active line, used by every demo that
// streams step-by-step agent progress. Ends with a bold "Total time" summary
// line once the run completes — the whole point being that every line's
// timing, and the total, reflects a real model/tool call, not a canned status.

const STYLES = `
  .progress-log { list-style: none; padding: 0; margin: 1.5rem 0 0 0; }
  .progress-log li { padding: 0.35rem 0; color: var(--muted); border-bottom: 1px dotted var(--line); }
  .progress-log li.active { color: var(--ink); font-weight: 500; }
  .progress-log li.active::before { content: "→ "; color: var(--brand); }
  .progress-log li.total { color: var(--ink); font-weight: 600; border-bottom: none; margin-top: 0.3rem; }
  .progress-log .elapsed { color: #999; font-size: 0.8em; margin-left: 0.4em; }
  .progress-log .spinner { display: inline-block; width: 0.8em; height: 0.8em; margin-left: 0.4em;
    border: 2px solid var(--line); border-top-color: var(--brand); border-radius: 50%;
    animation: progress-log-spin 0.8s linear infinite; vertical-align: middle; }
  @keyframes progress-log-spin { to { transform: rotate(360deg); } }
`;

let stylesInjected = false;
function ensureStyles() {
  if (stylesInjected) return;
  const style = document.createElement("style");
  style.textContent = STYLES;
  document.head.appendChild(style);
  stylesInjected = true;
}

/**
 * Attaches a progress trail to `listEl` (an empty <ul>, typically rendered at
 * the bottom of a demo's result area). Returns:
 *   - append(message): adds a new active (spinning) line, finalizing the
 *     previous one first.
 *   - stop(): finalizes the active line without adding a total — for runs
 *     that ended in an error, where "total time" isn't a meaningful claim.
 *   - finish(): finalizes the active line and appends a bold
 *     "Total time: N.Ns" line — call this once, when the run succeeds.
 */
export function createProgressLog(listEl) {
  ensureStyles();
  const startTime = Date.now();
  const elapsedSeconds = () => (Date.now() - startTime) / 1000;
  const formatElapsed = () => `+${elapsedSeconds().toFixed(1)}s`;

  function finalizeActive() {
    const prevActive = listEl.querySelector("li.active");
    if (!prevActive) return;
    prevActive.classList.remove("active");
    prevActive.querySelector(".spinner")?.remove();
    const waiting = prevActive.querySelector(".waiting-note");
    if (waiting) waiting.textContent = "";
  }

  function append(message) {
    finalizeActive();
    const item = document.createElement("li");
    item.className = "active";

    const text = document.createElement("span");
    text.textContent = message;
    item.appendChild(text);

    const elapsed = document.createElement("span");
    elapsed.className = "elapsed";
    elapsed.textContent = formatElapsed();
    item.appendChild(elapsed);

    const spinner = document.createElement("span");
    spinner.className = "spinner";
    item.appendChild(spinner);

    const waiting = document.createElement("span");
    waiting.className = "muted waiting-note";
    waiting.textContent = " (waiting on OpenAI API response...)";
    item.appendChild(waiting);

    listEl.appendChild(item);
  }

  function stop() {
    finalizeActive();
  }

  function finish() {
    finalizeActive();
    const item = document.createElement("li");
    item.className = "total";
    item.textContent = `Total time: ${elapsedSeconds().toFixed(1)}s`;
    listEl.appendChild(item);
  }

  return { append, stop, finish };
}
