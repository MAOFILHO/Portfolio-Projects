// Support Triage Copilot — the dependency-injection demo.
//
// The result card's *shape* changes with the union branch the agent returned,
// which is the point: the frontend switches on `decision.action` and never
// checks whether an optional field happens to be present.

import { escapeHtml, fetchJson, postJson } from "./shared.js";

const styles = `
  .triage-grid { display: grid; grid-template-columns: minmax(220px, 1fr) 2fr; gap: 1rem; align-items: start; }
  .triage-account { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 0.9rem; }
  .triage-account dl { display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 0.75rem; margin: 0.6rem 0 0; font-size: 0.85rem; }
  .triage-account dt { color: var(--muted); }
  .triage-account dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; }
  .triage-result { margin-top: 1.5rem; }
  .triage-card { background: var(--surface); border: 1px solid var(--line); border-left-width: 4px; border-radius: var(--radius); padding: 1rem; margin-top: 0.6rem; }
  .triage-card.resolve { border-left-color: #2e7d44; }
  .triage-card.escalate { border-left-color: #c2410c; }
  .triage-card.needs_info { border-left-color: #b58105; }
  .triage-card h3 { margin: 0 0 0.5rem; font-size: 1rem; }
  .triage-reply { white-space: pre-wrap; margin: 0; }
  .badge.resolve { background: #d4edda; color: #14532d; }
  .badge.escalate { background: #ffe0d1; color: #7c2d12; }
  .badge.needs_info { background: #fff3cd; color: #7a5c00; }
  .badge.sev-critical, .badge.sev-high { background: #fde2e1; color: #7f1d1d; }
  .badge.sev-medium { background: #fff3cd; color: #7a5c00; }
  .badge.sev-low { background: #eef1f4; color: #40464d; }
  .triage-trace { margin-top: 1rem; }
  .triage-trace summary { cursor: pointer; font-size: 0.85rem; color: var(--brand-dark); }
  .triage-trace ol { margin: 0.5rem 0 0; padding-left: 1.2rem; font-size: 0.85rem; color: var(--muted); }
  .triage-trace code { background: #f1f3f6; padding: 0.05rem 0.3rem; border-radius: 3px; color: var(--ink); }
  @media (max-width: 900px) { .triage-grid { grid-template-columns: 1fr; } }
`;

export async function render(root) {
  root.innerHTML = `
    <style>${styles}</style>
    <form id="triage-form">
      <div class="triage-grid">
        <div>
          <label for="account">Customer account</label>
          <select id="account"></select>
          <div class="triage-account" id="account-card"></div>
        </div>
        <div>
          <label for="ticket">Inbound ticket</label>
          <textarea id="ticket" required style="height: 7.5rem"></textarea>
          <div class="action">
            <button type="submit" id="triage-button">Triage ticket</button>
            <p>Runs the agent with this account injected as <code>deps</code>. It decides on its own which lookups it needs.</p>
          </div>
        </div>
      </div>
    </form>
    <div class="triage-result" id="triage-result"></div>
  `;

  const accountSelect = root.querySelector("#account");
  const accountCard = root.querySelector("#account-card");
  const ticketEl = root.querySelector("#ticket");
  const resultEl = root.querySelector("#triage-result");
  const button = root.querySelector("#triage-button");

  let seeds = [];
  try {
    seeds = await fetchJson("/api/triage/accounts");
  } catch (err) {
    resultEl.innerHTML = `<p class="error">Couldn't load demo accounts (${escapeHtml(err.message)}).</p>`;
    return;
  }

  accountSelect.innerHTML = seeds
    .map(
      (s) =>
        `<option value="${escapeHtml(s.account.account_id)}">${escapeHtml(s.account.company)} — ${escapeHtml(s.account.plan)}</option>`
    )
    .join("");

  function syncAccount() {
    const seed = seeds.find((s) => s.account.account_id === accountSelect.value);
    const a = seed.account;
    accountCard.innerHTML = `
      <strong>${escapeHtml(a.company)}</strong>
      <dl>
        <dt>Plan</dt><dd>${escapeHtml(a.plan)}</dd>
        <dt>Seats</dt><dd>${a.seats.toLocaleString()}</dd>
        <dt>Monthly spend</dt><dd>$${a.monthly_spend_usd.toLocaleString()}</dd>
        <dt>SLA</dt><dd>${a.support_sla_hours}h</dd>
        <dt>Open incidents</dt><dd>${a.open_incidents}</dd>
      </dl>
      <p class="muted" style="margin:0.6rem 0 0;font-size:0.78rem">
        This record is injected as <code>TriageDeps</code>; the agent can only see it by calling a tool.
      </p>
    `;
    ticketEl.value = seed.sample_ticket;
    resultEl.innerHTML = "";
  }

  accountSelect.addEventListener("change", syncAccount);
  syncAccount();

  function renderDecision(decision) {
    // One branch per union member. No optional-field checks anywhere, because
    // the discriminator guarantees which fields exist.
    switch (decision.action) {
      case "resolve":
        return `
          <div class="triage-card resolve">
            <span class="badge resolve">resolve</span>
            <h3>Draft reply to the customer</h3>
            <p class="triage-reply">${escapeHtml(decision.draft_reply)}</p>
            <p class="muted" style="margin:0.75rem 0 0">Confidence: ${decision.confidence}</p>
          </div>`;
      case "escalate":
        return `
          <div class="triage-card escalate">
            <span class="badge escalate">escalate</span>
            <span class="badge sev-${escapeHtml(decision.severity)}">${escapeHtml(decision.severity)}</span>
            <h3>Route to the ${escapeHtml(decision.team)} team</h3>
            <p style="margin:0">${escapeHtml(decision.reason)}</p>
          </div>`;
      case "needs_info":
        return `
          <div class="triage-card needs_info">
            <span class="badge needs_info">needs info</span>
            <h3>Send these questions back to the customer</h3>
            <ul style="margin:0">${decision.questions.map((q) => `<li>${escapeHtml(q)}</li>`).join("")}</ul>
          </div>`;
      default:
        return `<p class="error">Unrecognized decision type: ${escapeHtml(decision.action)}</p>`;
    }
  }

  function renderTrace(toolCalls) {
    if (!toolCalls.length) {
      return `<p class="muted">The agent decided without calling any tools.</p>`;
    }
    const items = toolCalls
      .map((call) => {
        const args = Object.entries(call.args || {})
          .map(([k, v]) => `${escapeHtml(k)}=${escapeHtml(String(v))}`)
          .join(", ");
        return `<li><code>${escapeHtml(call.tool_name)}(${args})</code></li>`;
      })
      .join("");
    return `
      <details class="triage-trace" open>
        <summary>${toolCalls.length} tool call${toolCalls.length === 1 ? "" : "s"} the agent made against the injected deps</summary>
        <ol>${items}</ol>
      </details>`;
  }

  root.querySelector("#triage-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    resultEl.innerHTML = `<p class="muted">Triaging — waiting on the model...</p>`;
    try {
      const result = await postJson("/api/triage/classify", {
        account_id: accountSelect.value,
        ticket: ticketEl.value,
      });
      resultEl.innerHTML = renderDecision(result.decision) + renderTrace(result.tool_calls);
    } catch (err) {
      resultEl.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
    } finally {
      button.disabled = false;
    }
  });
}
