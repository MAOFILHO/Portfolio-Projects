# D2 live-call verification -- result

Run 2026-09-17, real call to `+17059100383`, Marco on the phone. Verifies Phase 7 exit criterion 9:
AOAI data-plane auth migrated off `AOAI_KEY` onto managed identity (D2), proven with a live call
using the new auth path -- the same "ARM/exporter 200 OK does not prove delivery" standard this
project holds everywhere else (`CLAUDE.md`, Resume discipline; `docs/phase6/d16-smoke-call-result.md`
is the pattern repeated here).

## Call

- Correlation id: `c30c38ee-5428-4724-853a-05134b51b261`
- Connection id: `5e005880-785d-4051-82d4-b66ba4f8d07d`
- Time: ~2026-09-17T11:33:5{3,3}Z (call ended 11:33:53 UTC per container logs)
- Container revision at call time: `ca-azbank-echo-p0--p7a20260916213434` (verified live before the
  call, via the /wizard preflight stage -- `p7a` is the commit `fd1da9b` image, Entra ID token auth
  only, no `AOAI_KEY` fallback in code)
- RBAC role `Cognitive Services OpenAI User` granted to the voice agent's identity
  (`5e09fe34-8913-4aa2-80ac-618af308a88f`) on `aoai-azure-banking-voice-cc` immediately before this
  call, same session -- confirmed readable back via `az role assignment list` before dialing.

## Outcome -- PASS

Balance was spoken after the PIN. The realtime connection to Azure OpenAI authenticated successfully
using the Container App's own identity token (`DefaultAzureCredential`, `cognitiveservices.azure.com`
scope) -- there is no key-based fallback in the deployed code, so reaching this point is direct proof
the new auth path works end-to-end, not just that the old key still happened to work.

Marco's own account of the call: pre-PIN balance request was refused (no balance spoken before PIN,
B1 held); PIN `1234` accepted and confirmed; balance request after PIN succeeded and a real chequing
balance was spoken; call ended cleanly on caller hangup.

## Next step

This clears the way to flip `disableLocalAuth: true` in `infra/modules/aoai.bicep` and retire
`AOAI_KEY` for real -- both of that file's own header gate conditions are now met (code migrated,
live call proven). That flip is its own diff and is never auto-accepted; review it separately before
it lands. `AOAI_KEY` remains present as a container env var and should be removed from the Container
App config in the same pass once `disableLocalAuth` flips.

## Separate finding from this call -- not a D2 defect

The pre-PIN refusal wording deviated from `agents/specs.py`'s own instructions: the caller heard an
escalate-to-human narration ("transfer you to a Banking agent... no one to transfer... the call will
end") instead of a plain PIN prompt. This does not touch B1 (no balance was spoken, no banking
operation reached the core-banking client) -- it is a conversational-quality regression of the same
class already documented twice in `agents/specs.py` (2026-09-12, both incidents). See the proposed
instruction fix under review as of this write-up.
