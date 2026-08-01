// Code Review Assistant — the agent-delegation demo.
//
// The usage line under the verdict is deliberately prominent: the whole reason
// this demo exists next to the graph-based one is that delegation hands control
// of the call count to the model, so the budget has to be visible.

import { escapeHtml, fetchJson, postJson } from "./shared.js";

const styles = `
  .review-toolbar { display: flex; gap: 0.5rem; align-items: center; margin-top: 0.5rem; }
  #diff { height: 16rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.8rem; white-space: pre; overflow-wrap: normal; overflow-x: auto; }
  .review-result { margin-top: 1.5rem; }
  .review-verdict { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 1rem; }
  .badge.approve { background: #d4edda; color: #14532d; }
  .badge.comment { background: #eaf2fd; color: #1f5fa8; }
  .badge.request_changes { background: #fde2e1; color: #7f1d1d; }
  .review-usage { margin-top: 0.9rem; padding-top: 0.75rem; border-top: 1px solid var(--line); font-size: 0.8rem; color: var(--muted); }
  .review-usage strong { color: var(--ink); font-variant-numeric: tabular-nums; }
  .review-comment { background: var(--surface); border: 1px solid var(--line); border-left-width: 4px; border-radius: var(--radius); padding: 0.7rem 0.9rem; margin-top: 0.5rem; }
  .review-comment.critical, .review-comment.major { border-left-color: #b91c1c; }
  .review-comment.minor { border-left-color: #b58105; }
  .review-comment.info { border-left-color: #94a3b8; }
  .review-comment .loc { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.78rem; color: var(--muted); }
  .review-comment p { margin: 0.35rem 0 0; }
  .badge.cat { background: #eef1f4; color: #40464d; font-weight: 500; }
  .badge.sev-critical, .badge.sev-major { background: #fde2e1; color: #7f1d1d; }
  .badge.sev-minor { background: #fff3cd; color: #7a5c00; }
  .badge.sev-info { background: #eef1f4; color: #40464d; }
`;

const SEVERITY_RANK = { critical: 0, major: 1, minor: 2, info: 3 };

export async function render(root) {
  root.innerHTML = `
    <style>${styles}</style>
    <form id="review-form">
      <label for="diff">Unified diff</label>
      <textarea id="diff" required placeholder="Paste a unified diff (git diff output)..."></textarea>
      <div class="review-toolbar">
        <button type="submit" id="review-button">Review diff</button>
        <button type="button" class="secondary" id="sample-button">Load sample diff</button>
      </div>
      <p class="muted" style="margin:0.4rem 0 0;font-size:0.78rem">
        The lead reviewer chooses which specialists to consult. Every delegated call bills to one
        shared budget, capped with <code>UsageLimits</code>.
      </p>
    </form>
    <div class="review-result" id="review-result"></div>
  `;

  const diffEl = root.querySelector("#diff");
  const resultEl = root.querySelector("#review-result");
  const button = root.querySelector("#review-button");

  root.querySelector("#sample-button").addEventListener("click", async () => {
    try {
      const { diff } = await fetchJson("/api/review/sample-diff");
      diffEl.value = diff;
      resultEl.innerHTML = "";
    } catch (err) {
      resultEl.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
    }
  });

  function renderComments(comments) {
    if (!comments.length) {
      return `<p class="muted">No comments — the specialists found nothing worth raising.</p>`;
    }
    const sorted = [...comments].sort(
      (a, b) => (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9)
    );
    return sorted
      .map(
        (c) => `
        <div class="review-comment ${escapeHtml(c.severity)}">
          <span class="badge sev-${escapeHtml(c.severity)}">${escapeHtml(c.severity)}</span>
          <span class="badge cat">${escapeHtml(c.category)}</span>
          <span class="loc">${escapeHtml(c.file)}${c.line ? `:${c.line}` : ""}</span>
          <p>${escapeHtml(c.message)}</p>
        </div>`
      )
      .join("");
  }

  function renderResult({ verdict, usage }) {
    resultEl.innerHTML = `
      <div class="review-verdict">
        <span class="badge ${escapeHtml(verdict.verdict)}">${escapeHtml(verdict.verdict.replace("_", " "))}</span>
        <p style="margin:0.6rem 0 0">${escapeHtml(verdict.summary)}</p>
        <p class="review-usage">
          Delegated run used <strong>${usage.requests}</strong> of its
          <strong>${usage.request_limit}</strong> allowed model requests —
          <strong>${usage.input_tokens.toLocaleString()}</strong> input and
          <strong>${usage.output_tokens.toLocaleString()}</strong> output tokens.
        </p>
      </div>
      <h3 style="margin:1.25rem 0 0">${verdict.comments.length} comment${verdict.comments.length === 1 ? "" : "s"}</h3>
      ${renderComments(verdict.comments)}
    `;
  }

  root.querySelector("#review-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    resultEl.innerHTML = `<p class="muted">Lead reviewer is consulting specialists — this fans out to several model calls...</p>`;
    try {
      renderResult(await postJson("/api/review/analyze", { diff: diffEl.value }));
    } catch (err) {
      resultEl.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
    } finally {
      button.disabled = false;
    }
  });
}
