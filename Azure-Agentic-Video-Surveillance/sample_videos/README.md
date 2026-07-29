# Sample videos

Carried over from `Ai-Detect-Video-Alert/wwwroot/` (the source Blazor prototype) for use in the frontend's video-file demo capture mode and for generating an E2E test fixture frame. Filenames match stock-footage download IDs; verify licensing before using these specific clips outside of local development/demo purposes if you plan to publish this repository publicly with the videos included.

Also present at `frontend/public/sample_videos/` (served directly by the dev server / Static Web App) — kept in sync manually since they're binary assets.

Generate an E2E test fixture frame with:
```bash
ffmpeg -i swat-soldier-with-weapon-13884574-720p.mp4 -vframes 1 ../tests/fixtures/person_test_frame.jpg
```
