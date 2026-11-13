# AgentSDR call worker

Runs WhatsApp voice calls for AgentSDR's AI voice agent. A **calling station** is one WhatsApp
number whose WhatsApp Web lives in a browser profile. The worker polls AgentSDR
(`/api/call-worker/*`) for jobs, opens the station's browser with the recorder extension
(`extensions/whatsapp-recorder/dist`) loaded, and either:

- **call** — waits for WhatsApp Web to show the chats, then hands the call to the extension's
  station mode (`agentsdrStation.startCall`) and watches until AgentSDR reports it done;
- **link** — shows WhatsApp Web's login screen, tries "Log in with phone number", and reports
  the 8-character code plus a screenshot every ~8 s so the operator can link the number.

One job at a time per worker. Run several workers for more concurrency.

With `KEEP_OPEN` > 0 the worker keeps that many numbers' WhatsApp Web open
between calls (`src/openStations.ts`): leased from AgentSDR
(`/api/call-worker/leases`, renewed every 20 s) so no other worker opens the
same profile, checked every tick (closed or crashed → reopened, logged out →
let go), and restarted every 4 hours, which saves the profile. A call on an
open number skips the browser start and WhatsApp's load (~13 s); a link
closes it first.

## Messaging (KEEP_OPEN > 0, extension 0.21.0+)

AgentSDR's own WhatsApp messages (no Unipile) go out through the numbers this worker keeps
open (`src/messaging.ts`); with `KEEP_OPEN=0` the worker does no messaging.

- **Send.** Every `MESSAGE_POLL_MS` it offers AgentSDR the open numbers that are ready, have
  no call or message on them, and whose extension can message:
  `POST /api/call-worker/messages/claim` `{ workerId, stations }` → `{ job }`. AgentSDR spaces
  sends per number and never hands a message for a number with an open call. The number is
  held while the extension sends (`agentsdrStation.sendMessage`, 45 s at most), then the
  result goes to `POST /api/call-worker/messages/:id/result` (retried for about a minute).
  A timeout or an error thrown by the extension is reported not retryable (it may have been
  sent); a number that turned busy before the send is handed back retryable — the only case
  AgentSDR requeues a message (once). A claimed message with no report for 2 minutes is never
  resent: AgentSDR fails it as "Delivery uncertain" and keeps its message row.
- **Receive.** Every `INBOUND_POLL_MS`, and right after a call on an open number ends, it takes
  what the extension saw arrive (`agentsdrStation.takeInbound`) and posts it to
  `POST /api/call-worker/stations/:id/inbound` in batches of at most 100. A failed post is
  kept in memory (1000 messages a number at most, oldest dropped) and sent first next time.
- **Calls come first.** A message only takes a number nobody is using. A call never waits on
  messaging, except for a send already running on its own number (at most 50 s); checks,
  restarts and closes wait the same way. On shutdown the worker stops claiming, finishes the
  send in flight, posts what was received, then closes the numbers.
- Extensions before 0.21.0 have no `sendMessage`/`takeInbound`: the worker says so once per
  number and leaves its messages alone (calls still work from 0.17.0).

## Incoming calls (KEEP_OPEN > 0, extension 0.22.0+)

A lead who calls a station's number back is answered by the AI agent (`src/incoming.ts`); with
`KEEP_OPEN=0` incoming calls ring out.

- **Notice.** In station mode only (never a rep's own WhatsApp Web), the extension's wa-hook
  watches WhatsApp's call store (`WAWebCallCollection`, as whatsapp-web.js does) and, as a
  fallback, the page's incoming-call screen. Each ring is kept in the extension until taken.
- **Ask.** Every `INCOMING_POLL_MS` the worker takes the rings of each open number that is ready
  and unused (`agentsdrStation.takeIncomingCalls` — a read of the extension's storage, so the
  number is not held for it) and posts each new one younger than 30 s to
  `POST /api/call-worker/stations/:id/incoming`. AgentSDR answers only a known lead who is not
  Do Not Contact, on a free number; anything else, or a failed post, rings out. Each ring is
  asked about once.
- **Answer.** On `{ answer: true, call }` the call row already exists, claimed by this worker. The
  call runs at once, beside the claim loop (not in it): the number is held as for a placed call,
  and `agentsdrStation.answerCall` arms the tab, starts the agent and presses Accept. From the
  pick-up on it is a placed call — recording, the agent, the upload, the transcript. No Accept
  to press (the caller hung up) finishes the call as not answered.
- Logs: `incoming: ringing on <number>`, then `incoming: answering (call <id>)` or
  `incoming: not answering (<reason>)`. Extensions before 0.22.0 are said once per number and
  their calls ring out.

## Rep calls (extension 0.24.0+)

A call can also be one a rep talks on from their own AgentSDR tab, through a station's number
(`WorkerCall.remoteRep: true`). The worker hands `agentsdrStation.startCall` `remoteRep: true` and
no agent. AgentSDR relays the audio (contract.ts, "a rep talking through a calling station"): the
extension's wa-agent opens `GET /api/call-recorder/calls/:id/relay` (the call's recorder token,
NDJSON `RepRelayEvent`s) for the rep's voice, which wa-hook plays into WhatsApp's microphone as it
does the AI agent's, and `POST`s the lead's side to the same path in ~40 ms chunks of 16 kHz PCM
from dialing on, so the rep hears it ring. WhatsApp dials at once; the rep's hang-up (`hangup` on
the stream, also sent when their tab is gone) presses End call. The down stream reconnects with a
short backoff when it drops; unreachable for 15 s, or refused (401/403/404/410), the call is hung
up — nobody could hear the lead. The relay is plain HTTPS to AgentSDR's own host, which is direct
(never through the number's proxy, see `directHosts` in `launchers.ts`), so no WebRTC of ours is
involved: the earlier WebRTC link (0.23.x, through Cloudflare TURN) never connected, because a
GoLogin browser rewrites and strips WebRTC. Each step is in the call's log as `rep relay: …`
(connected, first audio each way, reconnects, drops, hang-up). Recording, upload and transcript
are as for an agent call. Rep calls are outbound only. Extensions before 0.24.0 refuse them with a
message to update; logs say `starting rep call (relay)` vs `starting agent call`.

## Environment

| Variable | Default | |
|---|---|---|
| `AGENTSDR_URL` | required | e.g. `http://localhost:3000` |
| `CALL_WORKER_SECRET` | required | Bearer secret the app checks |
| `WORKER_ID` | hostname | shown on the station while held |
| `LAUNCHERS` | `local` (`gologin_sdk` in Docker) | comma list of `cloak`, `local`, `gologin_sdk`, `gologin_cloud` |
| `EXTENSION_PATH` | repo `extensions/whatsapp-recorder/dist` | built extension |
| `PROFILES_DIR` | `~/.agentsdr-call-worker/profiles` | `local` profiles, one folder per station id |
| `HEADLESS` | `false` | `true` for new headless Chromium |
| `CLAIM_INTERVAL_MS` | `1000` | poll gap when idle |
| `STATIONS` | – | comma list of station ids this worker serves (all when empty) |
| `KEEP_OPEN` | `0` (`3` in Docker) | numbers whose WhatsApp Web stays open between calls (~0.7–1 GB RAM each); 0 opens a browser per call |
| `CALL_TIMEOUT_MS` | 30 min | then the worker hangs up |
| `MESSAGE_POLL_MS` | `2000` | gap between message claims when there is nothing to send (open numbers only) |
| `INBOUND_POLL_MS` | `10000` | how often each open number's received messages are read and posted |
| `INCOMING_POLL_MS` | `1000` | how often each open, idle number is checked for a call ringing on it (open numbers only) |
| `CHROMIUM_PATH` | – | Chromium executable override |

## Run locally

```sh
bun run build:recorder                      # from the repo root, builds the extension
cd services/call-worker && bun install
bunx playwright-core install chromium       # once; Playwright's bundled Chromium (needed for extensions)
AGENTSDR_URL=http://localhost:3000 CALL_WORKER_SECRET=… LAUNCHERS=local npm start
# Runs on Node (tsx), not Bun: Bun's WebSocket cannot hold Playwright's connectOverCDP,
# which the GoLogin launchers use. Bun only installs.
```

Link the number once (Settings → WhatsApp → stations → Link); the session persists in
`PROFILES_DIR/<station id>`.

## Launchers

- `local` — `chromium.launchPersistentContext` on a profile folder. Loads the extension via
  `--load-extension`, fake mic/camera devices, no background throttling.
- `gologin_cloud` — `chromium.connectOverCDP("wss://cloudbrowser.gologin.com/connect?token=…&profile=…")`.
  The extension must already be installed on the GoLogin profile (upload `dist/` as a custom
  extension in GoLogin's UI, keep it updated).
- `gologin_sdk` — the `gologin` npm package: `new GoLogin({ token, profile_id, extra_params })`,
  `await gl.start()` returns `{ wsUrl }`, then `connectOverCDP(wsUrl)`; closing calls `gl.stop()`
  (which uploads the profile back). Extension passed as `--load-extension=` in `extra_params`
  (the SDK merges it with its own extensions). Needs the Orbita browser the SDK downloads.

The GoLogin token and profile id come from the claim (organization's GoLogin integration and the
station), never from env.

## Server deployment

Build from the repo root — the image builds the extension itself:
`docker build -f services/call-worker/Dockerfile -t agentsdr-call-worker .`
On Dokploy: an Application on this repo, build type Dockerfile, path
`services/call-worker/Dockerfile`, context `.`; env `AGENTSDR_URL` (the app's public URL),
`CALL_WORKER_SECRET` (the same value as the app's), `WORKER_ID`, `LAUNCHERS`; volumes on `/data`
and `/root/.gologin`; no domain or port (it only calls out). The app needs `CALL_WORKER_SECRET`
and, for the AI agent, `GEMINI_API_KEY`.

Redeploy only when the worker's own inputs change: every redeploy hangs up the calls in progress.
On Dokploy, auto-deploy with these Watch Paths (everything the image is built from; add a file
here when the worker or extension starts importing another one from `src/lib/calls/`):
`services/call-worker/**`, `extensions/whatsapp-recorder/**`, `src/lib/calls/contract.ts`,
`src/lib/calls/stationContract.ts`, `src/lib/calls/digits.ts`, `src/lib/calls/whatsappContact.ts`.
The app's own service watches the single path `!services/call-worker/**` (any file except the
worker's), so a worker-only change does not rebuild it; an extension change rebuilds both, since
the app serves the extension's zip. Not `**` beside it: with both, Dokploy rebuilt the app for a
worker-only change (29 Oct 2026). Should the lone exclusion ever stop the app deploying at all,
list what its image is built from instead: `src/**`, `public/**`, `extensions/**`, `db/**`,
`docker/**`, `scripts/db/setup.ts`, `scripts/create-scheduled-job-runs.ts`, `package.json`,
`bun.lock`, `Dockerfile`, `.dockerignore`, `next.config.ts`, `tsconfig.json`, `postcss.config.mjs`.

Only one worker may run a given number: a laptop worker pointed at a dev server that shares the
production database claims the same calls.
Run with `-e AGENTSDR_URL=… -e CALL_WORKER_SECRET=… -v profiles:/data`. The entrypoint starts
PulseAudio with a null sink (so WhatsApp has an audio output to tap) and runs the worker under
`xvfb-run` with `HEADLESS=false`; extensions and WhatsApp's audio are most reliable headful.
Give the container `--shm-size=1g` (or `--ipc=host`).

## GoLogin notes (tested 12 Oct 2026)

- **SDK (`gologin_sdk`)**: Orbita starts on this machine in about 5 s; the worker loads the extension
  from `EXTENSION_PATH`. Do **not** also upload the extension to that GoLogin profile, or two copies run.
  Needs a paid plan (Professional and up have the API; the trial's API allowance runs out fast).
  The SDK drops `IndexedDB` — WhatsApp Web's login — from every profile it uploads, and its `stop()`
  leaves the browser running; `openGologinSdk` works around both (23 Oct 2026). Set the profile's
  language to English (not "based on IP"), or WhatsApp Web loads in Hindi for an Indian IP.
- **Cloud (`gologin_cloud`)**: opens in about 17 s; the extension must be uploaded to the profile
  (Extensions → Upload custom extension, the built `dist/` folder) and re-uploaded after every change.
  GoLogin's cloud machines have no audio input; the extension supplies the agent's voice as the only
  microphone on agent calls (0.17.3+).

## CloakBrowser (`cloak`) — the default launcher (23 Oct 2026)

Stealth Chromium on the worker's own disk: `PROFILES_DIR/cloak/<station id>` holds the station's whole
state — WhatsApp Web's login (saved when the browser closes, loaded on the next open) and the
fingerprint seed CloakBrowser keeps in `.cloakbrowser-seed`, so a number shows the same device on
every call. Opens in under a second; WhatsApp Web loads headless.

- `npx cloakbrowser install` once (Docker does it at build). The free binary runs one session at a
  time, which the worker never exceeds; a Pro key goes in `CLOAKBROWSER_LICENSE_KEY`.
- `CLOAK_TIMEZONE` (default `Asia/Kolkata`) and `CLOAK_LOCALE` (default `en-US`) apply to every
  station; keep them matching the IP the calls leave from. The locale must be English — the
  extension finds WhatsApp's buttons by their English labels.
- Losing `PROFILES_DIR` logs every number out of WhatsApp Web and changes its fingerprint: back it up.
- **Check the audio before trusting it with calls: `npm run audio-check`** (in the container:
  `xvfb-run npm run audio-check`). WhatsApp makes its call audio at 16 kHz, and CloakBrowser's free
  macOS build (145) reports 48 kHz for that and runs at under a third of real time — the agent sounds
  choppy or humming and never hears the lead (23 Oct 2026; no flag fixes it, `--fingerprint=off`
  included). The Linux build is a different one (146). Every line must say `OK`; if `cloak` says
  `BAD`, use `local` on that machine.

## Call audio goes over TCP through the proxy (27 Oct 2026)

GoLogin's WebRTC mode "alerted" ("Based on IP") keeps the call's audio on TCP through the number's
proxy, so WhatsApp's "Connecting…" costs a few round trips to it (3.3 s from Austria, 1.5 s from
Mumbai). A tunnel sending WebRTC's UDP through Proxy-Cheap's SOCKS5-with-UDP was built and removed:
UDP went through (STUN saw the proxy's IP), but WhatsApp's call servers never completed UDP via that
proxy and waited ~4 s on it before ringing. Worth revisiting only with a proxy WhatsApp accepts UDP from.
