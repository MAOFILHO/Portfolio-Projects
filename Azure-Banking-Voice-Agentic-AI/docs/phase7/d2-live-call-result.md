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

## Separate findings from this call and its follow-up -- not D2 defects

**Finding 1 (this call, `p7a`).** The pre-PIN refusal wording deviated from `agents/specs.py`'s own
instructions: the caller heard an escalate-to-human narration ("transfer you to a Banking agent... no
one to transfer... the call will end") instead of a plain PIN prompt. Did not touch B1 (no balance
was spoken, no banking operation reached the core-banking client). Fixed in `agents/specs.py`,
redeployed as `p7b`.

**Finding 2 (the `p7b` verification call that followed, same day).** The fix for finding 1 caused its
own regression: asked for a balance, PIN accepted, but the agent never handed off to banking at
all -- confirmed via the trace (`OperationId 598dc5c49898059b37f077a201c57f24`), which has zero
`tool_call` spans after authentication, against the working call's (`ef64afac44e99697d8c8f8ecd3cfce4d`)
three. The new clause had no stated cutoff at PIN confirmation, so the model reused its "explain,
don't act" pattern past the point where it should have handed off. Fixed with an explicit boundary
sentence in the same clause; redeployed as the next image. Both findings and both fixes are one
commit (`11ca61d` plus the follow-up), same file, same recurring class this file's own comments have
tracked since 2026-09-12.
