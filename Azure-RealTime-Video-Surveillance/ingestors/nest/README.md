# Nest Camera Ingestor

Feeds motion/person events from a Google Nest camera into this project's
existing pipeline, doing nothing but POST a JPEG frame to the backend's
`POST /api/v1/frames` whenever Nest detects activity. Everything downstream
(Azure AI Vision analysis, alert rules, WebSocket alerts, email/SMS) is
unchanged and already built. Runs either locally (your Mac, a Raspberry Pi, a
home NAS -- zero Azure cost) or as an opt-in always-on Azure Container App
(see "Running in Azure" below).

Event-driven, not polling: Nest's own on-device motion/person classifier
decides when something happened (via Google Cloud Pub/Sub); this script only
reacts, so it costs nothing in Google Cloud while your house is quiet
(running it in Azure does have a fixed cost regardless, since it must stay
up 24/7 to hold the subscription -- see docs/cost.md).

This walkthrough is written from an actual first-time setup, including the
dead ends -- if a step below doesn't match what you see, the "Troubleshooting"
section at the bottom covers every snag hit while building this.

## One-time setup

### 1. Google Cloud OAuth client
- Google Cloud Console -> **APIs & Services -> Credentials** -> **Create
  OAuth 2.0 Client ID** (Application type: **Web application**). Name it
  something recognizable, e.g. `nest-ingestor`.
- Leave **Authorized JavaScript origins** empty (that's for browser apps;
  this is a Python script).
- Under **Authorized redirect URIs**, add exactly:
  ```
  https://www.google.com
  ```
- Click **Create**. Copy the **Client ID** and **Client secret** shown.
- If Google Cloud instead sends you to configure the **OAuth consent
  screen** first (newer UI calls this the "Google Auth Platform" ->
  **Audience** page), that's expected for a new Cloud project -- fill in
  app name/support email, set **User type: External**, save, then come back
  and create the client.
- Search the top bar for **Smart Device Management API** and click
  **Enable** on it for this same Cloud project.

### 2. Add yourself as a test user (avoids an "Access blocked" error later)
Your OAuth app starts in **Testing** publishing status, which only allows
pre-approved accounts to sign in -- including your own.
- Google Cloud Console -> **Google Auth Platform -> Audience**.
- Under **Test users**, click **+ Add users**, add the Gmail address tied to
  your Nest structure, save.
- You do **not** need to submit for Google's verification review -- that's
  only required to let the *public* use the app. Staying in Testing with
  yourself as a test user is correct and permanent for a personal project.

### 3. Device Access Console ($5 one-time fee)
- Go to https://console.nest.google.com/device-access (a different Google
  product from Cloud Console -- sign in with the Google account tied to
  your actual Nest/Google Home devices).
- Accept **both** Terms of Service shown, pay the one-time **$5** fee (must
  be a consumer `@gmail.com`-style account, not Workspace).
- Click **Create project**. Give it any name (doesn't need to match
  anything else -- it's just a label Google shows you later, e.g. in the
  "unsafe app" consent warning). Paste in the **Client ID** from step 1.
- The **Events** screen requires a **self-hosted Pub/Sub topic** you own
  (there is no zero-setup Google-hosted option anymore) -- create it in your
  own GCP project *before* filling this field in. From Google Cloud Shell or
  a local terminal with `gcloud` installed:
  ```bash
  gcloud pubsub topics create nest-events \
    --project=<your-gcp-project-id> --message-retention-duration=10m

  gcloud pubsub topics add-iam-policy-binding \
    projects/<your-gcp-project-id>/topics/nest-events \
    --member="group:sdm-publisher@googlegroups.com" \
    --role="roles/pubsub.publisher"
  ```
  `<your-gcp-project-id>` is the real project ID (e.g.
  `computervision1-503213`), **not** the display name shown in the console
  header (e.g. `ComputerVision1`) -- your shell prompt shows the real one in
  parentheses if you're using Cloud Shell.
  Note: `--message-retention-duration` has a **10 minute minimum**; `0s`
  will be rejected.
- Back in the Device Access Console, enable **Events**, enter:
  ```
  projects/<your-gcp-project-id>/topics/nest-events
  ```
  and finish creating the project. Note the **Project ID** it shows you (a
  UUID, e.g. `8cb86d74-7d7b-45c3-b497-cffa5599d37b`) -- that's
  `GOOGLE_DEVICE_ACCESS_PROJECT_ID`.

### 4. Set up `.env`
```bash
cd ingestors/nest
cp .env.example .env
```
Fill in what you have so far: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
(from step 1), `GOOGLE_DEVICE_ACCESS_PROJECT_ID` (from step 3),
`GCP_PUBSUB_PROJECT_ID` (your GCP project ID), `GCP_PUBSUB_SUBSCRIPTION_ID`
(pick a name, e.g. `nest-surveillance-sub` -- created in step 6).

### 5. Authorize your Nest account (mint a refresh token)
```bash
python3 -m venv ../../.venv   # if the repo-root .venv doesn't already exist
source ../../.venv/bin/activate
pip install -r requirements.txt
python get_refresh_token.py
```
It prompts for your Device Access Project ID + OAuth Client ID/Secret, then
prints an authorization URL. Open it in a browser, signed in as your Nest
account:
1. You'll see camera-by-camera toggles ("Allow `<project-name>` to see your
   camera's livestream / know about camera events / access snapshots") --
   leave all on, click through.
2. If you see **"Google hasn't verified this app"**, click **Continue**
   (safe -- you added yourself as a test user in step 2, so this warning is
   expected, not an error).
3. Final screen: **CV_API1 wants access to your Google Account** (or
   whatever your OAuth consent screen's app name is) -- click **Continue**.
4. You land on `https://www.google.com/?code=...&scope=...`. Copy the value
   between `code=` and `&scope` (don't include the trailing `&`) and paste
   it into the waiting terminal prompt.

The script prints `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` /
`GOOGLE_REFRESH_TOKEN` / `GOOGLE_DEVICE_ACCESS_PROJECT_ID` -- copy these into
`.env`. **Treat the client secret and refresh token as long-lived
credentials** (unlike the authorization code, which is single-use and
expires in minutes) -- don't paste them anywhere outside your own `.env`.

### 6. Create your own Pub/Sub subscription
```bash
gcloud pubsub subscriptions create nest-surveillance-sub \
  --topic=nest-events --project=<your-gcp-project-id>
```
Matches `GCP_PUBSUB_SUBSCRIPTION_ID` in `.env`.

### 7. Authenticate the Pub/Sub client library
This is a **separate credential** from the Nest OAuth refresh token above --
it's what the `google-cloud-pubsub` Python library uses to read from your
subscription.
- If `gcloud` isn't installed yet:
  ```bash
  brew install --cask google-cloud-sdk
  ```
  then open a new terminal tab so `PATH` picks it up, and run `gcloud init`
  (pick/confirm your GCP project).
- Then:
  ```bash
  gcloud auth application-default login
  ```
  Browser opens, sign in, grant access. Stores credentials at
  `~/.config/gcloud/application_default_credentials.json`, which the Python
  client reads automatically -- no code or config needed.

### 8. Find your device IDs
```bash
ACCESS_TOKEN=$(curl -s -X POST https://www.googleapis.com/oauth2/v4/token \
  -d client_id=$GOOGLE_CLIENT_ID -d client_secret=$GOOGLE_CLIENT_SECRET \
  -d refresh_token=$GOOGLE_REFRESH_TOKEN -d grant_type=refresh_token \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://smartdevicemanagement.googleapis.com/v1/enterprises/$GOOGLE_DEVICE_ACCESS_PROJECT_ID/devices" \
  | python3 -m json.tool
```
Lists every camera/doorbell you authorized, each with a `customName` (e.g.
"Front yard camera") and a `name` field like:
```
enterprises/<project-id>/devices/AVPHwEvyfbBqQ3tAFmOxmKXmmg4p4j8Osp...
```
Device names/IDs aren't secrets. Note down the segment after
`.../devices/` for every camera you want watched, and check each device's
`traits` for `sdm.devices.traits.CameraClipPreview` -- **only devices with
this trait reliably produce frames** (see "CameraEventImage vs
CameraClipPreview" below, and "Known limitation: WebRTC fallback never
completes a frame" further down). Devices without it fall back to a WebRTC
capture that's confirmed *not* to work on current plain-camera hardware --
they'll still log every event, just without ever producing a frame, until
Google adds `CameraClipPreview` (or working `GenerateImage`) support.

### 9. Fill in the rest of `.env`
```
GOOGLE_DEVICES=AVPHwEvyfb...:nest-front-yard,AVPHwEtZor...:nest-backyard,AVPHwEs8td...:nest-garage,AVPHwEtprl...:nest-front-door
BACKEND_URL=http://localhost:8000   # or your deployed Container App FQDN once live
```
One `main.py` process watches all cameras listed in `GOOGLE_DEVICES`
simultaneously -- each fired event is routed to the matching `camera_id`
label automatically, so the dashboard/event history can tell them apart.

## Validating it works before deploying anything to Azure

Since the real backend needs deployed Azure Storage/Vision resources, use
`stub_backend.py` (a throwaway local FastAPI stand-in, not part of the
deployed system) to prove the Nest side works end-to-end first:

**Terminal 1:**
```bash
cd ingestors/nest
pip install fastapi uvicorn
uvicorn stub_backend:app --port 8000
```

**Terminal 2:**
```bash
source ../../.venv/bin/activate
cd ingestors/nest
python main.py
```
Trigger motion in front of the camera you configured. Terminal 2 should log
`Camera event fired: ...`; Terminal 1 should log `Received frame for
<camera-id> ... saved to ...`. Open the saved `.jpg` in
`ingestors/nest/received_frames/` to confirm it's a real snapshot.

Once confirmed, point `BACKEND_URL` at the real deployed backend and drop
`stub_backend.py` from your workflow (it's gitignored via
`ingestors/nest/received_frames/` for its output, but the stub script itself
stays checked in as a reusable dev tool).

## Running for real

```bash
cd ingestors/nest
source ../../.venv/bin/activate
python main.py
```

Leave it running (foreground, `screen`/`tmux`, or a `launchd`/`systemd` unit
later if you want it to survive reboots). It blocks, listening on the
Pub/Sub subscription, and logs each event it processes.

## CameraEventImage vs CameraClipPreview

Discovered during real-world testing: `CameraEventImage.GenerateImage`
(keyed off a trait event's `eventId`) is implemented internally via RTSP
capture. Every current-generation Nest camera/doorbell that only supports
`WEB_RTC` (check a device's `CameraLiveStream.supportedProtocols` --  if it
doesn't list `RTSP`, this applies) gets a 400 back:
```
"Command sdm.devices.commands.CameraEventImage.GenerateImage is not
supported due to camera not supporting RTSP protocol."
```
despite the device still advertising the `CameraEventImage` trait. This is
a real, current SDM API/hardware gap, not a bug in this ingestor.

The workaround: devices that also advertise `sdm.devices.traits.
CameraClipPreview` (so far, seen on doorbells, not plain cameras) include a
`previewUrl` directly in the same Pub/Sub message alongside the broken
`eventId` -- no extra `executeCommand` call needed. `main.py` prefers
`preview_url` whenever a parsed event has one, and only falls back to the
`eventId`/`GenerateImage` path for devices that don't send a preview (older
RTSP-capable hardware, if you have any). The clip is downloaded with the
OAuth **Bearer** access token (not the Basic-auth event token
`CameraEventImage` uses). The clip itself is an **MP4 video**, not an image
-- its first frame is extracted with OpenCV (written to a temp file since
`cv2.VideoCapture` needs a real file path, not in-memory bytes).

**Practical implication:** if your plain (non-doorbell) cameras don't
advertise `CameraClipPreview`, `GenerateImage` fails on them, so `main.py`
falls back to a third path -- a real WebRTC capture (see below) -- rather
than skipping the camera entirely.

### Fallback: WebRTC capture (`webrtc_capture.py`)

**WebRTC** (Web Real-Time Communication) is an open standard, originally
from Google and now maintained by W3C/IETF, for sending audio, video, and
data directly between two endpoints in real time -- no plugins, and usually
no media server in the middle. It's what browsers use for video calls, and
it's the only streaming protocol your plain cameras (Front yard, Backyard,
Garage) support -- unlike the doorbell/older hardware, they don't support
RTSP. That's why grabbing a frame from them can't be a simple HTTP request:
it requires actually negotiating a live WebRTC session (exchanging
connection details via SDP offer/answer, establishing a peer connection via
ICE, encrypting the media via DTLS-SRTP, and decoding incoming video via
RTP), which is what `aiortc` handles below.

For devices where both `CameraClipPreview` and `CameraEventImage` are
unavailable, `main.py` negotiates a real `CameraLiveStream.GenerateWebRtcStream`
session and grabs the first decoded video frame using
[`aiortc`](https://github.com/aiortc/aiortc):

1. Build an `RTCPeerConnection` with a `recvonly` video transceiver, create
   an SDP offer, and wait for ICE gathering to fully complete -- Google's
   SDM WebRTC implementation doesn't support trickle ICE, so the complete
   candidate set must be in the offer sent to `GenerateWebRtcStream`.
2. Send the offer via `executeCommand`, get back an `answerSdp` +
   `mediaSessionId`, set it as the remote description.
3. Wait for the first frame on the incoming video track, convert it to a
   JPEG via OpenCV, then close the peer connection and call
   `StopWebRtcStream` to clean up (best-effort -- failures here are logged
   but don't break frame capture).

This only runs as a fallback (`GenerateImage` is attempted first, since it's
cheaper when it works) and only on the event that actually failed -- not
proactively for every camera. `aiortc` installed with prebuilt wheels with
no extra system dependencies on Apple Silicon/Python 3.12 during
development; if `pip install -r requirements.txt` fails to build it on your
platform, you likely need `ffmpeg`/`libvpx`/`opus` dev headers
(`brew install ffmpeg opus libvpx pkg-config` on macOS) since some
platforms fall back to a source build.

### Known limitation: WebRTC fallback never completes a frame

Confirmed via real hardware testing: this fallback correctly completes an
entire WebRTC session end-to-end (SDP offer/answer, ICE connectivity, DTLS-
SRTP, RTP delivery of thousands of real packets, RTCP PLI keyframe requests,
and codec negotiation forced to H264) -- but never once successfully decodes
a video frame, on any plain camera, across extensive live testing. This is
not a bug left to fix in this codebase; it's the practical ceiling of what
the public SDM API supports for this hardware, confirmed two ways:

1. **Querying each device's advertised traits directly** shows the plain
   cameras (Front yard, Backyard, Garage) never advertise
   `sdm.devices.traits.CameraClipPreview` -- only the doorbell does. Google's
   own API says the cheap path was never going to work for them; this isn't
   a timing/cooldown issue.
2. **The WebRTC fallback's remaining failure is below the application
   layer.** Every structural bug that *was* fixable from here was fixed and
   verified working (SDP m-line ordering, a missing ICE candidate
   `foundation` field, `aiortc` never requesting a keyframe proactively, and
   `aiortc` defaulting to offering VP8 before H264). After all of that, real
   packets keep arriving in volume with low loss, yet the decoder never
   produces a frame -- pointing to a deeper `aiortc`/Google encoder interop
   gap (e.g. an undocumented parameter or extension Google's WebRTC media
   server expects) that isn't diagnosable from RTP-level application logs.
   The Google Home app itself almost certainly uses Nest's private, internal
   API for its own live view and thumbnails -- not the public SDM API this
   ingestor is restricted to -- so there's no equivalent "do what the app
   does" shortcut available to third-party code.

**Practical outcome:** the doorbell (`CameraClipPreview`) is the fully
reliable capture path, confirmed repeatedly end-to-end (real frames posted
to the backend). Plain cameras remain wired up and will automatically start
working the moment Google adds `CameraClipPreview` (or a working
`GenerateImage`) support to that hardware -- no code changes needed, since
`main.py` already prefers those cheaper paths whenever a device advertises
them.

### Diagnosing further: `diagnose_webrtc.py`

If you want to re-investigate the limitation above (e.g. after an `aiortc`
upgrade, or against new hardware), `diagnose_webrtc.py` runs a single capture
attempt with structured diagnostic logging enabled and feeds the result to an
LLM-based diagnostic agent (`WebrtcDiagnosticAgent`, Semantic Kernel + Azure
OpenAI) that writes a plain-language status report -- covering ICE/DTLS
health, SDP negotiation, packet/frame counters, and H264 NAL types seen,
compared against the conclusion above.

This is a local/on-demand tool only -- it is not deployed to Azure, and adds
no telemetry infrastructure to the ingestor itself (see the module docstring
in `diagnose_webrtc.py` for the one-time RBAC grant needed and full usage):

```bash
OPENAI_ENDPOINT=https://<name>.openai.azure.com/ \
OPENAI_CHAT_DEPLOYMENT=chat \
    python diagnose_webrtc.py nest-front-yard --output report.md
```

## Why Pub/Sub instead of polling

`CameraEventImage.GenerateImage` requires a real `eventId` from a motion/
person/sound event that already fired -- it can't be called as an arbitrary
"give me a snapshot now" poll. Pub/Sub is what delivers that `eventId`, so
it's not just more efficient than polling, it's the only way the snapshot
API actually works. (Nest *wired* cameras also support a true live stream
via the `CameraLiveStream` trait over WebRTC, but that's a constant stream
whether or not anything is happening -- overkill for an alerting use case
like this one.)

## Troubleshooting

- **`gcloud.pubsub.topics.create: value must be >= 10m`** -- the
  `--message-retention-duration` minimum is 10 minutes; `0s` is rejected.
- **`Access blocked: <app> has not completed the Google verification
  process` (Error 403: access_denied)** -- your OAuth consent screen is in
  Testing status and you haven't added yourself as a test user. Fix in
  Google Auth Platform -> Audience -> Test users (see step 2).
- **`Google hasn't verified this app` warning** -- not an error; click
  Continue. Expected for any personal/dev Device Access integration.
- **`google.auth.exceptions.DefaultCredentialsError: Your default
  credentials were not found`** -- you ran `python main.py` without first
  running `gcloud auth application-default login` (step 7), or `gcloud`
  itself isn't installed (`brew install --cask google-cloud-sdk`).
- **`gcloud: command not found`** -- Google Cloud SDK isn't installed;
  separate from the Azure CLI used elsewhere in this project.
- **`The project property must be set to a valid project ID, not the
  project name`** -- you passed the Cloud Console *display name* (e.g.
  `ComputerVision1`) instead of the actual project ID (e.g.
  `computervision1-503213`); find the real one in `gcloud projects list` or
  your Cloud Shell prompt.
- **`403 Cloud Pub/Sub API has not been used in project ... or it is
  disabled`** -- run `gcloud services enable pubsub.googleapis.com
  --project=<your-gcp-project-id>`, wait ~30-60s, retry.
- **`google.auth.exceptions.DefaultCredentialsError`** even after `gcloud
  init` -- `gcloud init` only authenticates the `gcloud` CLI itself; the
  Python Pub/Sub client needs its own separate credential via `gcloud auth
  application-default login` (step 7).
- **`Command sdm.devices.commands.CameraEventImage.GenerateImage is not
  supported due to camera not supporting RTSP protocol`** -- see
  "CameraEventImage vs CameraClipPreview" above. Not fixable via
  configuration; the ingestor now prefers `CameraClipPreview`'s `previewUrl`
  automatically when a device provides one.
- **Nothing logged at all after triggering motion, no error either** -- two
  possible causes:
  1. Nest's own event-publish cooldown (a few minutes between notifications
     for the same device), not a bug. Confirm the event actually registered
     in the Google Home app's camera event history first.
  2. **The subscriber's own callback thread pool got starved** (fixed as of
     this version, but worth understanding): `main.py` used to run all event
     processing -- including a WebRTC capture that can block for up to a
     minute -- directly inside Pub/Sub's callback, on Pub/Sub's own limited
     internal worker threads. If enough events overlapped, that pool could
     starve: no threads free to promptly ack messages or service the
     streaming connection's internal keepalive, seen as message redelivery
     (the same `eventId` firing multiple times) and the whole subscriber
     going silent. Fixed by handing event processing off to a separate
     `ThreadPoolExecutor` (see `main.py`'s `worker_pool`), so the Pub/Sub
     callback itself always returns immediately regardless of how long
     downstream processing takes.
  3. To rule out a competing-consumer race (e.g. a manual `gcloud pubsub
     subscriptions pull` running at the same time as `main.py`), stop one
     before testing the other -- Pub/Sub delivers each message to only one
     active puller.
- **Plain camera (Front yard/Backyard/Garage) events log but never produce
  a frame, timing out in `webrtc_capture.py`** -- expected; see "Known
  limitation: WebRTC fallback never completes a frame" above. Not fixable
  from this codebase. The doorbell's `CameraClipPreview` path is unaffected
  and fully reliable.

## Running in Azure (always-on Container App)

Once the local walkthrough above works end-to-end, this can be deployed as a
second Container App alongside the backend -- always-on (it holds a
persistent Pub/Sub connection, so it can't scale to zero like everything
else in this project), reusing the same Container Apps environment. This is
opt-in and adds a fixed monthly cost -- see `docs/cost.md` before enabling it.

The one piece this needs that local development doesn't: a **GCP service
account** (a machine identity, separate from your own `gcloud auth
application-default login`) so the container can authenticate to Pub/Sub
without your personal credentials. Create it once:

```bash
gcloud iam service-accounts create nest-ingestor-pubsub \
  --project=<GCP_PUBSUB_PROJECT_ID> \
  --display-name="Nest ingestor Pub/Sub subscriber"

gcloud pubsub subscriptions add-iam-policy-binding <GCP_PUBSUB_SUBSCRIPTION_ID> \
  --project=<GCP_PUBSUB_PROJECT_ID> \
  --member="serviceAccount:nest-ingestor-pubsub@<GCP_PUBSUB_PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/pubsub.subscriber"

gcloud iam service-accounts keys create gcp-nest-ingestor-key.json \
  --project=<GCP_PUBSUB_PROJECT_ID> \
  --iam-account=nest-ingestor-pubsub@<GCP_PUBSUB_PROJECT_ID>.iam.gserviceaccount.com
```

Then in the **root** `.env` (not this directory's `.env` -- the deploy
pipeline reads Nest config from the root one when deploying to Azure):

```
NEST_INGESTOR_ENABLED=true
GOOGLE_CLIENT_ID=...            # same values as this directory's .env
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
GOOGLE_DEVICE_ACCESS_PROJECT_ID=...
GOOGLE_DEVICES=...
GCP_PUBSUB_PROJECT_ID=...
GCP_PUBSUB_SUBSCRIPTION_ID=nest-surveillance-sub
GCP_SERVICE_ACCOUNT_KEY_PATH=./gcp-nest-ingestor-key.json   # never commit this file
```

Run `surveil-deploy deploy` as usual -- it builds this directory's Docker
image via ACR, deploys it as a second Container App
(`infra/modules/nest-ingestor.bicep`), and mounts the service-account key as
a file inside the container so `google-cloud-pubsub`'s implicit credential
discovery picks it up automatically (`GOOGLE_APPLICATION_CREDENTIALS`) --
no code changes needed for that part.

The backend's `/api/v1/frames` endpoint requires a shared-secret
`X-Api-Key` header once this is enabled (generated automatically in Bicep,
wired into both apps as `FRAME_UPLOAD_API_KEY`/`BACKEND_API_KEY`). If you're
testing locally against a deployed backend that has this set, pass the same
value as `BACKEND_API_KEY` in this directory's `.env`.
