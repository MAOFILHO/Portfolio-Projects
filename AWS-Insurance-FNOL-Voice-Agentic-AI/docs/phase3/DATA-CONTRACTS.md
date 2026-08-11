# Data Contracts — Phase 3

Single source of truth for every identifier format this project generates or references. Resolves `Q3`
(claim-number format) and formalizes the four identifier formats harvested from the source corpus in Phase 0
(`docs/phase0/DOMAIN-ARTIFACTS.md`, §1). Everything under `data/synthetic/` and every Lex slot/validation rule
in later phases conforms to this document — it is the contract those things are built against, not the other
way around.

---

## 1. Claim number — `Q3`, resolved here

### Format

```
CLM-YYMM-NNNNN-C
```

- `CLM` — literal prefix, spoken as "claim."
- `YYMM` — 2-digit year + 2-digit month the claim was **created** (not the loss date — a claim reported in
  January for a December loss still gets the January stamp, since this is a record-creation timestamp, not
  a loss-date field. Loss date/time is its own structured field, per `ADR-011`).
- `NNNNN` — 5-digit zero-padded sequence number, reset to `00001` each month. 99,999 claims/month is far
  beyond this project's demo scale; the width is chosen for realism, not because this project will approach it.
- `C` — single Luhn check digit (0–9), computed over the preceding 9 digits (`YYMMNNNNN`).

Example: the 42nd claim created in August 2026 → payload `260800042` → **`CLM-2608-00042-4`** (worked below).

### Why this refines, not just adopts, the Phase 0 proposal

`docs/phase0/DOMAIN-ARTIFACTS.md` (§1, "Proposal for Phase 3") suggested `CLM-YYMM-XXXXX` with a check
character drawn from **a voice-safe letter+digit alphabet** (excluding `0/O`, `1/I/L`, `5/S`, `2/Z`) to catch
ASR confusion. That document is left unedited (historical record, same discipline `ADR-011` used for its own
reversal) — this is the refinement, stated by name:

**This project goes digits-only, not alphanumeric, for the sequence and check character.** Two reasons,
both specific to this being a voice-and-DTMF IVR system (constraint 14), not a typed-entry system:

1. **DTMF fallback is a first-class input path here**, not an edge case — every digit maps to exactly one
   keypress. Letters do not map to DTMF at all without an awkward multi-tap scheme this project doesn't build.
   A caller who can't get through on speech (noisy environment, accent mismatch, barge-in confusion) has a
   clean digit-only fallback; a mixed alphanumeric code would not.
2. **Restricting the letter alphabet reduces confusion but does not eliminate it**, because Lex's ASR doesn't
   know our restricted alphabet is in play — it will still transcribe against the full 26-letter space, so a
   caller saying "K" can still come back as "J" regardless of which letters *we* chose to allow. Going
   digits-only removes the letter-confusion problem at its source rather than narrowing it. The check digit
   still does the real work of *catching* whatever error gets through — its usefulness doesn't depend on the
   payload alphabet, only on being read back and re-validated.

### Check-digit algorithm — standard Luhn (mod 10), worked example

Chosen over a custom scheme because it's a well-understood, widely-implemented, single-pass algorithm that
catches all single-digit substitution errors and the overwhelming majority of adjacent-digit transpositions
(the one gap — `09`↔`90` — is accepted; it's a voice-IVR retry aid, not a security control).

**Procedure**, given the 9-digit payload `YYMMNNNNN`:

1. Number the payload's digits by position **counting from the right**, 1-indexed (rightmost digit = position 1).
2. Double every digit at an **odd** position (1, 3, 5, 7, 9). If doubling produces a two-digit result, sum its
   two digits (equivalently, subtract 9).
3. Sum all nine resulting digits (doubled-and-reduced at odd positions, unchanged at even positions).
4. Check digit `C = (10 − (sum mod 10)) mod 10`.

**Worked example** — payload `260800042` (claim #42, created 2026-08):

| Position (from right) | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|---|---|---|---|
| Digit | 2 | 6 | 0 | 8 | 0 | 0 | 0 | 4 | 2 |
| Odd position? doubled | yes→4 | no | yes→0 | no | yes→0 | no | yes→0 | no | yes→4 |

Sum = 4 + 6 + 0 + 8 + 0 + 0 + 0 + 4 + 4 = **26**. Check digit = (10 − (26 mod 10)) mod 10 = (10 − 6) mod 10 = **4**.

**`CLM-2608-00042-4`** — this exact worked example is the canonical test fixture for the check-digit unit
test in Phase 9 (any implementation must reproduce `4` for this input).

### Validation on inbound (status-check intent)

When a caller reads a claim number back for `CheckClaimStatus`, the recomputed check digit either matches
(proceed) or doesn't (Lex re-prompts once, then offers policy-number lookup as a fallback path — the same
graceful-degradation pattern `ADR-001`'s slot-filling design already uses elsewhere). This is a UX/error-
recovery mechanism, not an authentication control — it doesn't change the auth-bypass residual risk the
threat model already names (`docs/phase2/THREAT-MODEL.md`); a correctly-formed guessed claim number still
authenticates nothing on its own.

---

## 2. Policy number

### Format

```
PY####
```

4-digit, unpadded-from-1000 numeric suffix (e.g. `PY4821`). **This format is not new here** — it's the
format `docs/phase2/THREAT-MODEL.md` already reasoned about explicitly (`^PY\d{4}$`, "a 4-digit space") when
analyzing the auth-bypass residual risk. Formalized here rather than re-decided, for consistency with an
already-accepted document. Chosen over the source corpus's other candidates (`POL-AUTO-12345`, `POL-#####`,
bare UUID v4) as the shortest, most voice-speakable option — it's also, not coincidentally, the smallest
identifier space, which is precisely the property the threat model already flagged as a real, accepted
limitation of this prototype (no OTP/KBA gates it). Widening the digit count here would not close that gap —
the gap is the absence of a second factor, not the ID's guess-space — so this project doesn't treat digit-count
as a security lever and isn't widening it for that reason.

**No check digit.** Unlike the claim number, the policy number is not read back by the system to the caller
mid-call in the same self-service-lookup way — it's provided *by* the caller as an identifying credential, so
a check digit here would only help catch the caller's own transcription errors, not add anything the L2
safety/intent classifier or a simple "I couldn't find that policy, can you repeat the number?" re-prompt
doesn't already cover.

---

## 3. VIN — deliberately invalid check digit

17 characters, standard VIN structure (WMI 1–3, VDS 4–8, check digit 9, model year 10, plant 11, sequential
12–17), **but every VIN this project generates has an intentionally incorrect position-9 check digit.**

**Why:** per `CLAUDE.md`'s do-not-propagate list, item 2 — the source corpus contained a *structurally
valid* VIN (`1HGCF86461A130849`) that could map to a real vehicle, and the standing instruction is to
"generate our own with a deliberately invalid check digit," never reuse or produce a passably-real one.

**Generation rule:** compute the correct NHTSA check digit for the WMI/VDS/model-year/sequential combination
using the standard weighted-sum-mod-11 algorithm (transliterating letters to their NHTSA-assigned values,
weighting positions 1–8 and 10–17, dividing by 11, remainder 10 → `X`), then **replace it with a different
character from the valid check-digit alphabet** (`0–9` or `X`), chosen deterministically as `(correct + 1) mod 11`
mapped back through the same alphabet — guaranteeing every generated VIN fails NHTSA validation by exactly
one position, consistently and by design, not by accident of a lazy random string.

**WMI convention for this project's synthetic vehicles:** `9SY` — not assigned to any real manufacturer in
the current NHTSA WMI registry as of this writing (re-verify before Phase 3 record generation if this becomes
load-bearing beyond flavor text); signals "obviously synthetic" to anyone who looks it up, on top of the
invalid check digit.

---

## 4. Licence plate

```
^[A-Z]{3}-\d{4}$
```

E.g. `KJH-4523`. Unchanged from the Phase 0 harvest (`docs/phase0/DOMAIN-ARTIFACTS.md`, repo 8) — already
vetted as containing no real-world PII risk (no real plate reuse concern the way the VIN had one), no reason
to redesign.

## 5. Driver's licence number

```
^[A-Z]\d{8}$
```

E.g. `D08954142`. Unchanged from the Phase 0 harvest (repo 6). Same disposition as the plate format — no
redesign needed, no PII risk carried forward (the two DMV specimen images that accompanied this format in
the source repo are excluded entirely, per the blanket no-images rule; only the numeric pattern is reused).

## 6. Police report number

```
^\d{4}-\d{4}-\d{3}$
```

Year-MMDD-sequence, e.g. `2026-0811-042`. Unchanged from the Phase 0 harvest (repo 8) — the only such format
in the entire source corpus, no alternative to weigh it against.

---

## Summary table

| Entity | Format | Check digit? | Status |
|---|---|---|---|
| Claim number | `CLM-YYMM-NNNNN-C` | ✅ Luhn mod 10 | **New — resolves `Q3`** |
| Policy number | `PY####` | ✗ | Formalizes the format already used in `docs/phase2/THREAT-MODEL.md` |
| VIN | 17-char, standard structure | Position 9, **deliberately wrong** | Do-not-propagate compliance (`CLAUDE.md`) |
| Licence plate | `^[A-Z]{3}-\d{4}$` | ✗ | Reused from Phase 0 harvest, unchanged |
| Driver's licence | `^[A-Z]\d{8}$` | ✗ | Reused from Phase 0 harvest, unchanged |
| Police report number | `^\d{4}-\d{4}-\d{3}$` | ✗ | Reused from Phase 0 harvest, unchanged |

All six formats feed directly into `src/fnol_voice_agent/guardrails/pii.py`'s custom regex detectors (Phase 5,
per `docs/phase0/TARGET-LAYOUT.md`'s mapping) and every synthetic record generated for the rest of Phase 3.
