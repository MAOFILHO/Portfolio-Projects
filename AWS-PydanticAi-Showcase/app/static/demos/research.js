// Research Analyst — the pydantic_graph pipeline demo.
//
// Streams live progress over SSE while the graph runs, then hands the draft to
// a human compliance officer to approve or annotate.

import { describeError, escapeHtml, postJson, streamSse } from "./shared.js";

const styles = `
  .research-report { margin-top: 0.75rem; }
  .research-finding { border-left: 3px solid var(--brand); padding-left: 0.75rem; margin: 0.6rem 0; }
  .review-actions { margin-top: 1rem; border-top: 1px solid var(--line); padding-top: 1rem; }
  .review-actions textarea { height: 3rem; margin-bottom: 0.6rem; }
  #progress-log { list-style: none; padding: 0; margin: 1.5rem 0 0 0; }
  #progress-log li { padding: 0.35rem 0; color: var(--muted); border-bottom: 1px dotted var(--line); }
  #progress-log li.active { color: var(--ink); font-weight: 500; }
  #progress-log li.active::before { content: "→ "; color: var(--brand); }
  #progress-log .elapsed { color: #999; font-size: 0.8em; margin-left: 0.4em; }
  .spinner { display: inline-block; width: 0.8em; height: 0.8em; margin-left: 0.4em;
    border: 2px solid var(--line); border-top-color: var(--brand); border-radius: 50%;
    animation: research-spin 0.8s linear infinite; vertical-align: middle; }
  @keyframes research-spin { to { transform: rotate(360deg); } }
`;

export function render(root) {
  root.innerHTML = `
    <style>${styles}</style>
    <form id="ask-form">
      <textarea id="question" required
        placeholder="e.g. What are the tradeoffs between vector databases and full-text search for RAG?"></textarea>
      <div class="action">
        <button type="submit" id="ask-button">Submit</button>
      </div>
    </form>
    <div id="report" class="research-report"></div>
  `;

  const form = root.querySelector("#ask-form");
  const askButton = root.querySelector("#ask-button");
  const reportEl = root.querySelector("#report");
  let currentReviewId = null;
  let researchStartTime = null;

  // The log is a permanent trail once a run starts: appendProgress() only ever
  // adds to it, and finishing the run never clears it. It renders below
  // #report-result, which holds the report itself — right under the Submit
  // button, so the log stays a scrollable audit trail at the bottom.
  function startNewTrail() {
    researchStartTime = Date.now();
    reportEl.innerHTML = `
      <div id="report-result"></div>
      <p class="muted">Waiting on OpenAI API responses — each line below is a real model/search call, not a canned status:</p>
      <ul id="progress-log"></ul>
    `;
  }

  const resultEl = () => reportEl.querySelector("#report-result");
  const formatElapsed = () => `+${((Date.now() - researchStartTime) / 1000).toFixed(1)}s`;

  function renderReportBody(report) {
    const findings = (report.key_findings || [])
      .map(
        (f) =>
          `<div class="research-finding"><strong>${escapeHtml(f.sub_topic)}</strong><br>${escapeHtml(f.summary)}</div>`
      )
      .join("");
    const openQuestions = (report.open_questions || [])
      .map((q) => `<li>${escapeHtml(q)}</li>`)
      .join("");
    return `
      <h2>Summary</h2>
      <p>${escapeHtml(report.summary)}</p>
      <p class="muted">Confidence: ${report.confidence}</p>
      <h3>Key findings</h3>
      ${findings}
      ${openQuestions ? `<h3>Open questions</h3><ul>${openQuestions}</ul>` : ""}
    `;
  }

  function renderPendingReview(record) {
    finalizeActiveLogLine();
    currentReviewId = record.review_id;
    resultEl().innerHTML = `
      <span class="badge pending">pending compliance review</span>
      ${renderReportBody(record.draft)}
      <div class="review-actions">
        <textarea id="notes" placeholder="Add annotation notes here (used only by Annotate & finalize, below)..."></textarea>
        <div class="action">
          <button id="approve-button">Approve</button>
          <p>Signs off on this draft exactly as written. Nothing is regenerated; any notes above are ignored.</p>
        </div>
        <div class="action">
          <button id="annotate-button" class="secondary">Annotate &amp; finalize</button>
          <p>Sends your notes above to the synthesizer agent, which rewrites the report to address them.</p>
        </div>
      </div>
    `;
    reportEl.querySelector("#approve-button").addEventListener("click", () => {
      const notes = reportEl.querySelector("#notes")?.value.trim();
      if (
        notes &&
        !confirm(
          "You've typed notes but clicked Approve, which finalizes the draft as-is and ignores them. Continue without applying your notes?"
        )
      ) {
        return;
      }
      submitDecision("approve", null);
    });
    reportEl
      .querySelector("#annotate-button")
      .addEventListener("click", () => submitDecision("annotate"));
  }

  function renderFinal(record) {
    resultEl().innerHTML = `
      <span class="badge final">final</span>
      ${renderReportBody(record.final)}
      ${record.officer_notes ? `<p class="muted">Officer notes: ${escapeHtml(record.officer_notes)}</p>` : ""}
    `;
  }

  function renderError(message, { retryLabel, onRetry } = {}) {
    finalizeActiveLogLine();
    resultEl().innerHTML = `
      <p class="error">${escapeHtml(message)}</p>
      ${retryLabel ? `<button id="retry-button">${escapeHtml(retryLabel)}</button>` : ""}
    `;
    if (onRetry) reportEl.querySelector("#retry-button").addEventListener("click", onRetry);
  }

  async function submitDecision(decision, notesOverride) {
    const notes =
      notesOverride !== undefined ? notesOverride : reportEl.querySelector("#notes")?.value || null;
    try {
      renderFinal(
        await postJson(`/api/research/reviews/${currentReviewId}/decision`, { decision, notes })
      );
    } catch (err) {
      renderError(`Couldn't submit that decision (${err.message}). Your draft is still pending review.`, {
        retryLabel: "Retry",
        onRetry: () => submitDecision(decision),
      });
    }
  }

  function finalizeActiveLogLine() {
    const prevActive = reportEl.querySelector("#progress-log li.active");
    if (!prevActive) return;
    prevActive.classList.remove("active");
    prevActive.querySelector(".spinner")?.remove();
    const waiting = prevActive.querySelector(".waiting-note");
    if (waiting) waiting.textContent = "";
  }

  function appendProgress(message) {
    finalizeActiveLogLine();
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

    reportEl.querySelector("#progress-log").appendChild(item);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = root.querySelector("#question").value;
    askButton.disabled = true;
    startNewTrail();

    try {
      await streamSse("/api/research/research", { question }, (event) => {
        if (event.type === "progress") appendProgress(event.message);
        else if (event.type === "done") renderPendingReview(event.record);
        else if (event.type === "error") throw new Error(event.message);
      });
    } catch (err) {
      renderError(describeError(err), { retryLabel: "Retry", onRetry: () => form.requestSubmit() });
    } finally {
      askButton.disabled = false;
    }
  });
}
