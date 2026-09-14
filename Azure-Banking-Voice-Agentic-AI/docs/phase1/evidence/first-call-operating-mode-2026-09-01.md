# Phase 1 step 5 — operating-mode measurement, first real call, 2026-09-01

Raw `az monitor metrics list` output from the "immediately after hangup" reading, run by Marco right
after the first real Phase 1 call ended. Commands and metric-name verification (`Replicas`, `RxBytes`,
`TxBytes` — confirmed against Microsoft Learn's `Microsoft.App/containerapps` supported-metrics
reference, no Azure call made) are in the session that produced this file; not re-derived here.

Resource: `ca-azbank-echo-p0` (`rg-azure-banking-voice-agentic-ai`). Window: `PT15M` buckets, same
shape as R-04's own Phase 0 measurement (`docs/PLAN.md` decision to measure "the same way R-04
measured Phase 0's three calls").

## Replicas (Maximum)

```
Timestamp             Name           Maximum
--------------------  -------------  ---------
2026-09-01T19:24:00Z  Replica Count  1.0
2026-09-01T19:39:00Z  Replica Count  1.0
2026-09-01T19:54:00Z  Replica Count  1.0
2026-09-01T20:09:00Z  Replica Count  1.0
2026-09-01T20:24:00Z  Replica Count  1.0
2026-09-01T20:39:00Z  Replica Count  1.0
2026-09-01T20:54:00Z  Replica Count  1.0
2026-09-01T21:09:00Z  Replica Count  1.0
```

Held at 1.0 throughout — but this is **not idle/active evidence either way**. `ca-azbank-echo-p0` is
provisioned with `--min-replicas 1 --max-replicas 1` (`01-provision.sh:1182`), so it cannot scale to
zero on this configuration regardless of whether the underlying replica is idle-billed or
active-billed — Replicas would read 1.0 in both cases. RxBytes/TxBytes below is the only signal that
distinguishes them.

## RxBytes / TxBytes (Total)

```
Timestamp             Name               Total
--------------------  -----------------  ----------
2026-09-01T19:24:00Z  Network In Bytes   166938.0
2026-09-01T19:39:00Z  Network In Bytes   189223.0
2026-09-01T19:54:00Z  Network In Bytes   187854.0
2026-09-01T20:09:00Z  Network In Bytes   189322.0
2026-09-01T20:24:00Z  Network In Bytes   190183.0
2026-09-01T20:39:00Z  Network In Bytes   187937.0
2026-09-01T20:54:00Z  Network In Bytes   189112.0
2026-09-01T21:09:00Z  Network In Bytes   23855192.0
2026-09-01T19:24:00Z  Network Out Bytes  104162.0
2026-09-01T19:39:00Z  Network Out Bytes  118081.0
2026-09-01T19:54:00Z  Network Out Bytes  117064.0
2026-09-01T20:09:00Z  Network Out Bytes  118072.0
2026-09-01T20:24:00Z  Network Out Bytes  118933.0
2026-09-01T20:39:00Z  Network Out Bytes  117241.0
2026-09-01T20:54:00Z  Network Out Bytes  118024.0
2026-09-01T21:09:00Z  Network Out Bytes  22784753.0
```

## Extended window — through the second call, 2026-09-01

Reported by Marco (raw `az monitor metrics list` output for this later window not repasted here):
after the first call, the container returned to the ~189 KB in / ~118 KB out baseline within one
`PT15M` bucket and held flat there across four consecutive buckets (76 minutes) until the second
call. Both calls are visible as spikes against that flat baseline: first call ~23.8 MB at 21:10Z
(the 21:09 bucket above), second call ~18.0 MB at 22:25Z.

## Verdict: IDLE

**R-04's idle finding holds for a stateful agent loop with tool calls, not just the stateless echo
app.** The container returned to its pre-call baseline within one bucket after each call and stayed
there until the next call started — no lingering elevated traffic between calls across the full
four-hour window measured. The R-08 ACTIVE branch (`docs/PLAN.md`, Phase 1 section) does not
trigger: no teardown, no design rework.

**Two caveats stand alongside this verdict, not folded into it:**
- The idle baseline itself is ~180 KB/15min, not zero — likely platform-level health probes, present
  before any of this session's changes, not something newly introduced. The verdict rests on values
  three orders of magnitude below the call spikes, not on literal 0 B.
- This measured operating **mode** only. The dollar figures chained from it ($6.72/mo fixed, R-08's
  demo-runs figure) remain modeled from published Retail Prices API rates plus a hand-entered
  per-minute value, never measured from actual Cost Management billing. Confirming IDLE mode doesn't
  upgrade those numbers from modeled to measured.
