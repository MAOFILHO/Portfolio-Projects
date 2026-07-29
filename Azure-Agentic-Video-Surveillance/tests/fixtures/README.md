Place `person_test_frame.jpg` here to enable the live E2E validation step
(`s11_validate_e2e.py` / `surveil-deploy smoke-test --stage post`). It is
intentionally not committed (binary, and licensing of the source clip is
unconfirmed for redistribution — see `sample_videos/README.md`).

Generate one from the bundled sample video:
```bash
ffmpeg -i ../../sample_videos/swat-soldier-with-weapon-13884574-720p.mp4 -vframes 1 person_test_frame.jpg
```

Without this file, `s11_validate_e2e` prints a warning and skips the live
detection check rather than failing the deployment.
