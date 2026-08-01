// Travel Itinerary Planner — the streaming-structured-output demo.
//
// Each SSE "partial" event carries the whole Itinerary as validated so far by
// Pydantic's partial-validation mode, so day cards fill in live rather than
// appearing all at once at the end.

import { describeError, escapeHtml, streamSse } from "./shared.js";

const styles = `
  .travel-form-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 0.75rem; align-items: end; }
  .travel-form-grid label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.3rem; }
  .travel-result { margin-top: 1.5rem; }
  .travel-meta { display: flex; gap: 1rem; flex-wrap: wrap; align-items: baseline; margin-bottom: 0.75rem; }
  .travel-meta h2 { margin: 0; }
  .travel-cost { font-size: 0.95rem; color: var(--muted); }
  .travel-day { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 0.9rem 1rem; margin-top: 0.6rem; }
  .travel-day h3 { margin: 0 0 0.3rem; font-size: 0.95rem; }
  .travel-day .weather { font-size: 0.8rem; color: var(--brand-dark); margin: 0 0 0.4rem; }
  .travel-day ul { margin: 0.3rem 0 0; padding-left: 1.2rem; }
  .travel-packing { margin-top: 0.9rem; font-size: 0.85rem; color: var(--muted); }
  .travel-refine { margin-top: 1.25rem; border-top: 1px solid var(--line); padding-top: 1rem; }
  .travel-refine textarea { height: 2.5rem; margin-bottom: 0.5rem; }
  .travel-disclaimer { margin-top: 1rem; font-size: 0.75rem; color: var(--muted); }
  .travel-pending { color: var(--muted); }
`;

export function render(root) {
  root.innerHTML = `
    <style>${styles}</style>
    <form id="plan-form">
      <div class="travel-form-grid">
        <div>
          <label for="destination">Destination</label>
          <input type="text" id="destination" required placeholder="e.g. Lisbon" />
        </div>
        <div>
          <label for="trip-days">Trip length (days)</label>
          <input type="text" id="trip-days" inputmode="numeric" value="3" />
        </div>
      </div>
      <label for="interests" style="display:block;margin-top:0.6rem;font-size:0.85rem;font-weight:600">Interests (optional)</label>
      <input type="text" id="interests" placeholder="e.g. food markets, museums, hiking" />
      <div class="action">
        <button type="submit" id="plan-button">Plan itinerary</button>
        <p>Streams a real weather lookup, then builds each day live as the model's structured output validates.</p>
      </div>
    </form>
    <div class="travel-result" id="travel-result"></div>
  `;

  const form = root.querySelector("#plan-form");
  const button = root.querySelector("#plan-button");
  const resultEl = root.querySelector("#travel-result");
  let sessionId = null;

  function renderItinerary(itinerary, { pending } = {}) {
    const days = (itinerary.days || [])
      .map(
        (d) => `
        <div class="travel-day">
          <h3>Day ${d.day ?? "?"}${d.summary ? ` — ${escapeHtml(d.summary)}` : ""}</h3>
          ${d.weather ? `<p class="weather">${escapeHtml(d.weather)}</p>` : ""}
          <ul>${(d.activities || []).map((a) => `<li>${escapeHtml(a)}</li>`).join("")}</ul>
        </div>`
      )
      .join("");

    const packing = itinerary.packing_notes?.length
      ? `<div class="travel-packing"><strong>Packing:</strong> ${itinerary.packing_notes.map(escapeHtml).join(", ")}</div>`
      : "";

    resultEl.innerHTML = `
      <div class="travel-meta">
        <h2>${escapeHtml(itinerary.destination || "")}</h2>
        ${itinerary.estimated_cost_usd ? `<span class="travel-cost">~$${itinerary.estimated_cost_usd.toLocaleString()} estimated</span>` : ""}
        ${pending ? `<span class="travel-pending">streaming...</span>` : ""}
      </div>
      ${days || `<p class="muted">Building the itinerary...</p>`}
      ${packing}
      <p class="travel-disclaimer">
        Weather is a live lookup against Open-Meteo. Flight and hotel figures behind the cost
        estimate are simulated inventory, not real prices.
      </p>
      ${
        !pending
          ? `
        <div class="travel-refine">
          <label for="refine-instruction">Refine this itinerary</label>
          <textarea id="refine-instruction" placeholder="e.g. make it cheaper, or add a rest day"></textarea>
          <div class="action">
            <button type="button" id="refine-button" class="secondary">Refine</button>
            <p>Re-runs the agent with the conversation so far as message_history, so it edits this plan instead of starting over.</p>
          </div>
        </div>`
          : ""
      }
    `;

    if (!pending) {
      resultEl.querySelector("#refine-button").addEventListener("click", submitRefine);
    }
  }

  async function submitRefine() {
    const instruction = resultEl.querySelector("#refine-instruction").value.trim();
    if (!instruction || !sessionId) return;
    const refineButton = resultEl.querySelector("#refine-button");
    refineButton.disabled = true;
    try {
      await streamSse("/api/travel/refine", { session_id: sessionId, instruction }, (event) => {
        if (event.type === "partial") renderItinerary(event.itinerary, { pending: true });
        else if (event.type === "done") {
          sessionId = event.session_id;
          renderItinerary(event.itinerary);
        } else if (event.type === "error") throw new Error(event.message);
      });
    } catch (err) {
      resultEl.innerHTML += `<p class="error">${escapeHtml(describeError(err))}</p>`;
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    resultEl.innerHTML = `<p class="muted">Looking up weather and building the plan...</p>`;
    const days = Math.min(14, Math.max(1, parseInt(root.querySelector("#trip-days").value, 10) || 3));

    try {
      await streamSse(
        "/api/travel/plan",
        {
          destination: root.querySelector("#destination").value,
          trip_days: days,
          interests: root.querySelector("#interests").value,
        },
        (event) => {
          if (event.type === "partial") renderItinerary(event.itinerary, { pending: true });
          else if (event.type === "done") {
            sessionId = event.session_id;
            renderItinerary(event.itinerary);
          } else if (event.type === "error") throw new Error(event.message);
        }
      );
    } catch (err) {
      resultEl.innerHTML = `<p class="error">${escapeHtml(describeError(err))}</p>`;
    } finally {
      button.disabled = false;
    }
  });
}
