# publik build of Zenith

This repository is a fork of [Zac06/zenith](https://github.com/Zac06/zenith) (GNU GPL v3, see [`LICENSE`](LICENSE)).
publik (https://publikhq.com/moodledesk) builds its desktop downloads of Zenith from this fork.
The fork is not affiliated with the original author and is not endorsed by the original author.

## What this fork changes

Changed on 2026-11-06 and on 2026-11-11. The branch `telemetry/v2` carries the changes on top of the upstream tag `v0.2.5` (`0061e94`). The publik releases `v0.2.5-publik.1` and `v0.2.5-publik.2` are built from it. The older publik release `v0.2.2-publik.1` came from the branch `telemetry/v1` (upstream tag `v0.2.2`, which had no self-updater).

- **Sign in with publik (desktop only, from `v0.2.5-publik.2`).** The desktop app opens with a small window, "Sign in with publik", before its own window. The button opens the publik sign-in page in the browser. The window continues by itself when you are signed in. There is no other way past it: closing the window quits the app. Zenith's own window, with its first screen "Welcome to Zenith", opens only after the sign-in. A computer that is signed in already goes to Zenith's window directly. When publik does not answer, the window says "publik is not reachable. Check your connection." and has a Retry button. Zenith uses no AI, so there is no plan screen and no key step.
  - `src-tauri/src/publik.rs`: the publik module (https://publikhq.com/sdk/publik.rs.md) with `APP_SLUG = "moodledesk"` and `USES_AI = false`. It gets the publik key of this computer (`POST /api/v1/installs`), checks the sign-in (`GET /api/v1/wallet`) and sends the usage counts (`POST /api/v1/telemetry`). It uses the system `curl` for HTTP. Changes to the page: the app token comes from `build.rs`, and on Windows `curl` opens no console window.
  - `src-tauri/src/publik_gate.rs`: the sign-in window. The app serves its page itself (the `publik-gate` protocol). The page has no access to the app's commands.
  - `src-tauri/src/lib.rs`: the `mod` lines; the self-test at the start of `run`; the `publik-gate` protocol; `publik_gate::start` in `setup`. On a desktop, the main window is made after the sign-in, not at start-up. A second start brings the sign-in window to the front.
  - `src-tauri/build.rs`: compiles in the publik app token. The token is not in this repository. `publik-build.yml` writes `src-tauri/publik-app-token.txt` (in `.gitignore`) from the repository secret `PUBLIK_APP_TOKEN`. A build without a token shows "This build has no publik app token. Ask the developer for a new build."
  - Self-test: with `PUBLIK_SELF_TEST=1`, the built app prints `publik self-test: ok moodledesk <version>` after a real `GET /api/v1/wallet`, and exits before any window opens.
- **Usage counts (desktop only).** After the sign-in, the app sends `app_opened` at each start and `active_session` every 30 minutes to `https://publikhq.com/api/v1/telemetry`. Each event holds the app name (`moodledesk`), the app version, the operating system, the CPU type and a random install ID, and goes with the publik key of this computer. Turn the usage counts off with `DO_NOT_TRACK=1` (or `PUBLIK_TELEMETRY=0`, or `{"usage": false}` in `consent.json`). The sign-in stays on. Full text: [`PRIVACY.md`](PRIVACY.md) and https://publikhq.com/skills/telemetry.md.
  - From `v0.2.5-publik.2`, the publik module (`src-tauri/src/publik.rs`) sends the counts. The telemetry v1 client (`src-tauri/src/publik_telemetry.rs`) and its `ureq` crate are removed.
- **No self-update from the original feed (desktop only).** See "The updater" below.
  - `src-tauri/tauri.conf.json`: `bundle.createUpdaterArtifacts` is `false` and `plugins.updater.endpoints` is empty.
  - `src/App.tsx`: on a desktop, Settings → Updates shows "Updates come from publik" and a button that opens https://publikhq.com/moodledesk, in place of the update choices and "Check now".
- **Signed and notarized by publik.** The macOS app and dmg are signed with the Developer ID of publik (Mann Bellani, team `R5R3ZS54LV`) and notarized by Apple. The Windows and Linux files are not signed.
- **Build.** `.github/workflows/publik-build.yml` builds the files. It stops when the updater has an update address again, or when the repository secret `PUBLIK_APP_TOKEN` is missing. Each job runs the built app with `PUBLIK_SELF_TEST=1` against a fake publik on the runner (`.github/scripts/publik-telemetry-smoke.py`, never publikhq.com). `.github/workflows/release.yml` does not run for a `-publik` tag.
- **Text.** This file, the "Sign in with publik and usage counts" part of `README.md`, and the publik parts of `PRIVACY.md`.

Nothing else is changed. The Android and iOS apps do not change: they have no sign-in and send no usage counts.

## The updater

From version 0.2.3 the original desktop app updates itself with `tauri-plugin-updater`. It reads `github.com/zac06/zenith/releases/latest/download/latest.json` and installs the file that the original author signed with the author's updater key.

Rule for the publik build: it must never replace itself with a build that is not publik's. The original build is not signed by publik and sends no usage counts.

What the publik build does:

1. `plugins.updater.endpoints` is an empty list. The plugin then has no address to ask. Each check stops at once with "Updater does not have any endpoints set." and sends no request. The app code cannot give the plugin another address (the JavaScript `check()` takes no address). So the app cannot download or install any update.
2. `bundle.createUpdaterArtifacts` is `false`. `tauri build` then makes no signed update files and needs no updater private key. (With `true`, the build stops: "A public key has been found, but no private key".)
3. The public key of the original author stays in the file. The plugin needs a key to start, and with no address the key is never used.
4. Settings → Updates on a desktop says "This build does not update itself. Get new versions at publikhq.com/moodledesk." and has an "Open publik" button. The automatic check that the app starts in the background fails at once and shows nothing. So the publik build shows no update prompt.

Why not a publik update feed: a feed needs an updater key pair. publik would have to make a private key and keep it safe for every later release. publik has no such key today. Without that key, the smallest safe change is no feed.

To get a new version, the user downloads it from publik (https://publikhq.com/moodledesk).

## Versions

The app version stays the upstream version. A publik release has the tag `<upstream tag>-publik.<n>`, for example `v0.2.5-publik.1`.

## Source

The complete changed source of each publik release is this repository at the commit of the release tag: https://github.com/Blueturboguy07/zenith (branch `telemetry/v2` for `v0.2.5-publik.2` and `v0.2.5-publik.1`, branch `telemetry/v1` for `v0.2.2-publik.1`).
