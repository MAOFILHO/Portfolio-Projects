# Deployed Lambda layer v2 — provenance

**This is the first written record, anywhere in this repo, of the actual package closure running in
production.** Every prior document (`docs/phase8/STAGE4-LAMBDA-LAYER-PLAN.md` §7, `PROJECT_STATE.md`'s
`D82`/`D83` entries) records the *build procedure* and the deployed artifact's *hash*; none records what
packages, at what versions, that hash actually resolves to. That gap is what this document closes, from a
byte-exact backup of the deployed zip — not from re-deriving it via a fresh build, which (§3/§4 below) does
not currently reproduce the same bytes.

Source: `~/fnol-layer-v2-backup.zip`, held outside git by Marco, MD5-verified
`73deb4753ca856a7cc60270092e4be96` — matching the deployed S3 key exactly (§2). Extracted read-only to a
scratch directory (`/tmp/layer-determinism/layer/`) for inspection; nothing in this document's production
was written into, or read from, the project repo's tracked tree.

---

## 1. The complete 44-package closure

Read directly from the backup extract's 44 `python/*.dist-info` directories (one per installed
distribution) — `pip`'s own installed-package accounting, not `requirements`/`STAGE4`'s 8 top-level pins,
which is why this list is 44 long and not 8.

```
annotated_types==0.8.0
anyio==4.14.2
boto3==1.43.69
botocore==1.43.71
certifi==2026.7.22
charset_normalizer==3.5.0
distro==1.9.0
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.18
jmespath==1.1.0
jsonpatch==1.33
jsonpointer==3.1.1
langchain_core==1.5.4
langchain_protocol==0.0.18
langgraph_checkpoint_aws==1.2.1
langgraph_checkpoint==4.2.0
langgraph_prebuilt==1.1.0
langgraph_sdk==0.4.2
langgraph==1.2.11
langsmith==0.10.18
numpy==2.5.2
openfeature_sdk==0.10.0
orjson==3.11.9
ormsgpack==1.12.2
packaging==26.3
pydantic_core==2.46.4
pydantic==2.13.4
python_dateutil==2.9.0.post0
PyYAML==6.0.2
requests_toolbelt==1.0.0
requests==2.34.2
s3transfer==0.19.2
six==1.17.0
sniffio==1.3.1
tenacity==9.1.4
typing_extensions==4.16.0
typing_inspection==0.4.4
urllib3==2.7.0
uuid_utils==0.17.0
websockets==15.0.1
xxhash==4.0.0
zstandard==0.25.0
```

Of these, `§7`'s documented plan (`STAGE4-LAMBDA-LAYER-PLAN.md:356-368`) pins exactly 8 by name (`boto3`,
`langgraph`, `langchain_core`, `pydantic`, `httpx`, `PyYAML`, `openfeature_sdk`, and one more — see that
document for the exact set); the other 36 are transitive, resolved by `pip` at install time with no
lockfile and no hash pinning anywhere in this repo (confirmed via a repo-wide search for
`--require-hashes`, which returns no hits).

## 2. Layer v2 identity

| Field | Value |
|---|---|
| Layer name | `fnol-codehook-deps` |
| Version | 2 |
| ARN | `arn:aws:lambda:us-west-2:759316130780:layer:fnol-codehook-deps:2` |
| `CodeSha256` | `gMs9BPR6MLBIZMe97OeK+wHKHeDZLjURFlnd+kEuxiE=` |
| `CodeSize` | 43849548 bytes |
| Created | 2026-08-13 |
| S3 bucket | `fnol-artifacts-759316130780-us-west-2` |
| S3 key | `lambda-layers/codehook-deps-73deb4753ca856a7cc60270092e4be96.zip` |
| Content MD5 (= S3 key suffix) | `73deb4753ca856a7cc60270092e4be96` |

Version 1's stale `CodeSize` (43793016, `PROJECT_STATE.md`'s `D82` entry) is recorded separately and
differs from v2's — a real rebuild happened between the two, corroborating that this closure is v2's own,
not v1's carried forward.

**The only recoverable copy of this exact artifact is `~/fnol-layer-v2-backup.zip`, held by Marco, outside
git.** No commit in this repo contains the zip itself; `docs/RESULTS.md:5769` and this project's own
`PROJECT_STATE.md` entries record its MD5 and size, never its bytes. See `D161`/`OI79` below for why this
matters on a deadline, not just in principle.

## 3. The 9 transitive drifts, backup (v2, 2026-08-13) vs. today's rebuild (2026-08-21)

A fresh `pip install --target` run following `STAGE4-LAMBDA-LAYER-PLAN.md` §7 verbatim, 8 days later,
resolved 9 of the 36 unpinned transitive packages to different versions:

| Package | v2 (deployed, 2026-08-13) | Today's rebuild (2026-08-21) |
|---|---|---|
| `botocore` | 1.43.71 | 1.43.77 |
| `charset_normalizer` | 3.5.0 | 3.5.1 |
| `idna` | 3.18 | 3.19 |
| `langchain_core` | 1.5.4 | 1.6.0 |
| `langgraph_sdk` | 0.4.2 | 0.4.3 |
| `langsmith` | 0.10.18 | 0.11.1 |
| `orjson` | 3.11.9 | 3.12.0 |
| `websockets` | 15.0.1 | 16.1.1 |
| `xxhash` | 4.0.0 | 4.0.1 |

Every drift is a forward version bump over 8 days — consistent with an unpinned transitive closure resolving
to whatever `pip`'s index served on each build date, not a fluke of any one package.

The remaining 35 packages matched by version across both builds — and even those 35, matched by version,
did **not** produce a matching zip (§4).

## 4. Evidence that `§7` is not a complete build spec

Two independent, empirically confirmed causes, either one alone sufficient to break a hash match. Neither
is addressed by pinning the 9 drifted versions above.

**(a) Every file in v2 carries a uniform, non-wall-clock mtime — `2049-01-01 00:00:00`. `§7` has no
timestamp-normalization step, and `archive_file` does not supply one on the build's behalf.**

Confirmed by direct inspection, not inferred from doc silence:

- `stat` on multiple files across the backup extract (`boto3/compat.py`, `certifi/__init__.py`,
  `numpy/_pytesttester.pyi`, `pydantic/functional_validators.py`, `distro/__init__.py`,
  `jmespath/functions.py`, `tenacity/before.py`, every `dist-info/METADATA` checked) — all read
  `2049-01-01 00:00:00`, uniformly, regardless of package.
- Today's fresh rebuild shows real wall-clock timestamps instead (`2026-08-21 10:48:0x`), spread across
  the seconds `pip install` actually ran.
- `archive_file` (`hashicorp/archive` provider) was proven, empirically, to **preserve** source-filesystem
  mtimes rather than normalize them: re-zipping the backup's own extracted files through a throwaway
  `archive_file` config and inspecting the regenerated zip's internal per-entry date (`unzip -lv`) shows
  `01-01-2049`, byte-identical to the original, untouched backup zip's own internal date for the same
  entry. The provider's only documented determinism guarantee
  (`raw.githubusercontent.com/hashicorp/terraform-provider-aws/main/website/docs/r/lambda_layer_version.html.markdown`
  and the `archive` provider's own docs) is normalizing `output_file_mode`; nothing in either doc claims
  timestamp normalization, and this test confirms the silence is accurate, not an oversight in reading it.
- **Origin of the `2049-01-01` value: UNKNOWN.** It is not the classic 1980 zip epoch, not today's
  wall-clock, and not something `archive_file` introduces (proven above) — it was already on the
  filesystem before whatever built v2 ever ran `archive_file`/zipped it. No step in `§7`'s documented
  sequence sets it. Whatever produced the deployed artifact did something to the build environment or its
  output that `§7`'s own text does not describe.

**(b) v2's `dist-info/RECORD` files reference `cpython-313`-tagged `.pyc` filenames; today's rebuild
references `cpython-312`. `§7` pins `--python-version`/`--abi` for wheel *selection* only — it never names
the interpreter meant to *run* `pip` itself.**

`pip`'s post-install bytecode-compilation step writes `.pyc` filenames into each package's `RECORD`
manifest, tagged by the interpreter actually executing `pip` — independent of `--python-version`/`--abi`,
which only constrain which wheel tag `pip` selects for download, not which interpreter compiles bytecode
afterward. Confirmed systemic, checked across 5 identical-version packages (only interpreter tag differs,
version identical both sides):

| Package | Today's RECORD | v2's (backup) RECORD |
|---|---|---|
| `boto3` (1.43.69) | `cpython-312` | `cpython-313` |
| `certifi` (2026.7.22) | `cpython-312` | `cpython-313` |
| `numpy` (2.5.2) | `cpython-312` | `cpython-312` **and** `cpython-313` (both present — unexplained, not investigated further) |
| `pydantic` (2.13.4) | `cpython-312` | `cpython-313` |
| `distro` (1.9.0) | `cpython-312` | `cpython-313` |

Today's rebuild ran under this session's `.venv`, Python 3.12.13. v2's `RECORD` files show `pip` itself ran
under Python 3.13 at build time on 2026-08-13 — a build-environment fact `§7` never pins and this repo
records nowhere else.

**Decisive test, ruling out "the 9 drifted packages are the whole story":** today's rebuild, with only
those 9 packages surgically replaced by v2's exact versions (package dir + `.dist-info` both, `__pycache__`
asymmetry cleaned per `§7`'s own cleanup step, 89/89 top-level entries confirmed matching v2's own count via
`diff`), still does not reproduce v2's hash:

```
output_md5 = "89a2e7101cb833e2aeb6abb65bab99e1"   # hybrid (9-package swap)
             "73deb4753ca856a7cc60270092e4be96"   # v2, deployed — does NOT match
```

Both (a) and (b) are live contributors to that mismatch, confirmed independently of each other and of the
version drift in §3.

## 5. The layer is not currently reproducible

Stated plainly: **no one can rebuild `fnol-codehook-deps` v2's exact bytes from this repo's committed
instructions today.** Three independent, unpinned dimensions all have to line up for a rebuild to match,
and none of the three is pinned anywhere in the repo:

1. **The transitive dependency closure** — 36 of 44 packages are resolved by `pip` with no lockfile and no
   `--require-hashes`, and drifted on 9 of them in 8 days (§3).
2. **A fixed file-mtime normalization step** — v2's build applied one (uniformly, to `2049-01-01`); `§7`
   documents none, and a plain `pip install --target` does not supply one on its own (§4a).
3. **The Python interpreter `pip` itself runs under** — v2 was built under 3.13; `§7` pins the *target*
   wheel ABI (3.12) but never the *build* interpreter, and these are not the same thing (§4b).

Any one of the three, left unpinned, is sufficient to make a fresh build's `output_md5` diverge from
`73deb4753ca856a7cc60270092e4be96`. All three are unpinned today. This is not a claim that the deployed
artifact is wrong or unsafe — it demonstrably works, per Layer 0/1 verification elsewhere in this repo —
only that it cannot currently be regenerated byte-for-byte from what is committed, which is the fact this
document exists to put on the record before the one recoverable copy of it (§2, `D161`/`OI79`) expires.
