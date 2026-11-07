# publik build of Zenith

This repository is a fork of [Zac06/zenith](https://github.com/Zac06/zenith) (GNU GPL v3, see [`LICENSE`](LICENSE)).
publik (https://publikhq.com/moodledesk) builds its desktop downloads of Zenith from this fork.
The fork is not affiliated with the original author and is not endorsed by the original author.

## What this fork changes

Changed on 2026-11-06. The branch `telemetry/v2` carries the change on top of the upstream tag `v0.2.5` (`0061e94`). The publik release `v0.2.5-publik.1` is built from it. The older publik release `v0.2.2-publik.1` came from the branch `telemetry/v1` (upstream tag `v0.2.2`, which had no self-updater).

- **Usage telemetry v1 (desktop only).** The app sends `app_opened` at each start and `active_session` every 30 minutes to `https://publikhq.com/api/v1/telemetry`. Each event holds the app name (`moodledesk`), the app version, the operating system, the CPU type and a random install ID. Turn it off with `DO_NOT_TRACK=1`. Full text: [`PRIVACY.md`](PRIVACY.md) and https://publikhq.com/skills/telemetry.md.
  - `src-tauri/src/publik_telemetry.rs`: the client (one file, the publik reference client for Rust).
  - `src-tauri/src/lib.rs`: the `mod` line and one `publik_telemetry::start(...)` call in `setup`.
  - `src-tauri/Cargo.toml`, `src-tauri/Cargo.lock`: the `ureq` crate (desktop targets only).
- **No self-update from the original feed (desktop only).** See "The updater" below.
  - `src-tauri/tauri.conf.json`: `bundle.createUpdaterArtifacts` is `false` and `plugins.updater.endpoints` is empty.
  - `src/App.tsx`: on a desktop, Settings → Updates shows "Updates come from publik" and a button that opens https://publikhq.com/moodledesk, in place of the update choices and "Check now".
- **Signed and notarized by publik.** The macOS app and dmg are signed with the Developer ID of publik (Mann Bellani, team `R5R3ZS54LV`) and notarized by Apple. The Windows and Linux files are not signed.
- **Build.** `.github/workflows/publik-build.yml` builds the files. It stops when the updater has an update address again. `.github/workflows/release.yml` does not run for a `-publik` tag.
- **Text.** This file, the "Usage counts" part of `README.md`, and the publik parts of `PRIVACY.md`.

Nothing else is changed. The Android and iOS code is not changed and sends no usage counts.

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

The complete changed source of each publik release is this repository at the commit of the release tag: https://github.com/Blueturboguy07/zenith (branch `telemetry/v2` for `v0.2.5-publik.1`, branch `telemetry/v1` for `v0.2.2-publik.1`).
