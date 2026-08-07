# Lessons Learned

What building this project actually taught — spanning model behaviour, data engineering, and the
cloud deployment. Each item is something that changed a decision in the codebase, not a generic
best-practice list.

← Back to the [README](../README.md)

1. **Match the model's structure to the data's structure — that beat model capacity here.** SARIMAX
   beat both LSTMs by ~13% RMSE, but the headline isn't "classical beats deep learning": plain,
   non-seasonal ARIMA is equally classical and finished *last*, ~2.7× worse than the same family with
   a seasonal term added. The variable that actually predicted performance was whether the model
   represented seasonality at all, not whether it was statistical or neural.
2. **A hyperparameter search is worthless if its result never reaches the estimator.**
   `run_auto_arima()` correctly identifies `seasonal_order=(1,0,1,12)` and surfaces it in the
   dashboard — then `fit_and_forecast_arima()` fits a non-seasonal model anyway, a quirk inherited
   from the source notebook. The search *looked* like it was working, and its output was even
   displayed to users, which is exactly what made it easy to miss for so long. It cost ~2.7× RMSE.
3. **"Same architecture" does not mean "same result."** Identical LSTM stacks in TensorFlow and
   PyTorch differed by ~2.2× RMSE on identical inputs, with seeds fixed and checkpoint strategy
   matched on both sides. The dominant cause is default **weight initialization** — Keras seeds the
   forget-gate bias at 1 (`unit_forget_bias=True`) and uses `glorot_uniform`/`orthogonal`; PyTorch
   uses a single uniform scheme with no forget-gate special case. If you're porting a model between
   frameworks and expecting parity, initialization is the first place to look, not the last.
4. **Enforce data quality once, upstream.** A single Spark validation stage that fails fast with a
   diagnosable error beats five models each failing differently and confusingly several stages later.
5. **Never pin infrastructure to a floating base-image tag.** `python:3.12-slim` silently drifted to a
   Debian release without the JDK the build required. Pin the OS release, not just the language
   version.
6. **Understand your tools' implicit search behavior.** Docker Compose walking up parent directories
   silently built the wrong stack — the run "succeeded" while starting entirely the wrong services.
7. **Cloud quota is multi-dimensional.** Spot quota, regular quota, per-VM-generation quota, and
   regional capacity are four *independent* limits. Hitting one tells you nothing about the other
   three — check `az vm list-usage` before guessing.
8. **Container UID mismatches are a first-class deployment concern.** Root-owned files from a
   `git clone` blocked a non-root container from writing, which surfaced as a mid-DAG
   `PermissionError` rather than anything resembling a permissions problem.
9. **Don't self-discover what the deployment already knows.** Querying IMDS for the VM's own public IP
   raced against metadata propagation; the IaC layer already had the value and could inject it
   deterministically.
10. **Retry the transient, fix the systematic.** Concurrent Spark JVM contention is a genuine race, not
   a logic bug — `retries=2` is the correct response. A wrong compose file is systematic — retrying
   would just fail identically forever.
11. **Verify teardown, don't assume it.** "I ran teardown" and "nothing is billing me" are different
    claims. A post-teardown check for leftover resource groups and tagged resources turns the second
    into evidence.
12. **Guard clauses can neutralize themselves.** A placeholder-substitution check that compared against
    the literal placeholder string was itself rewritten by the substitution — so it always reported
    failure. Validate on a property the real value can't have, not on the placeholder text.
13. **Scope CI to what it can actually test.** Airflow needs a ~7GB image and a live multi-container
    stack, so it's verified manually rather than bloating every CI run — while Spark, all 5 models, and
    the Kafka logic all stay fully covered, broker-free, at $0.



