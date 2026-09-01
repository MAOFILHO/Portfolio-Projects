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

## Reading (not yet a verdict)

Buckets 19:24–20:54 (7 buckets, ~166–190 KB in / ~104–119 KB out each) sit well under PLAN.md's
stated 1,000 B/s active threshold (≈167 B/s average) — consistent with idle platform-level traffic
(health probes etc.), not an open audio stream. The 21:09 bucket (23.9 MB in / 22.8 MB out) is the
call itself.

**This single reading does not answer IDLE-vs-ACTIVE.** PLAN.md's step 5 method requires a second
reading ~1h after this one: if traffic in that follow-up bucket settles back to the ~180 KB/15min
baseline above, the container closed its WebSocket and went idle (R-04's Phase 0 verdict holds). If
it stays elevated, that is the ACTIVE result the R-08 branch decision (`docs/PLAN.md`, Phase 1
section) governs — tear down and rework, not carry the higher cost forward. Pending.
