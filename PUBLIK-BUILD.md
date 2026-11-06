# publik build of Zenith

This repository is a fork of [Zac06/zenith](https://github.com/Zac06/zenith) (GNU GPL v3, see [`LICENSE`](LICENSE)).
publik (https://publikhq.com/moodledesk) builds its desktop downloads of Zenith from this fork.
The fork is not affiliated with the original author and is not endorsed by the original author.

## What this fork changes

Changed on 2026-11-06, on top of the upstream tag `v0.2.2`:

- **Usage telemetry v1 (desktop only).** The app sends `app_opened` at each start and `active_session` every 30 minutes to `https://publikhq.com/api/v1/telemetry`. Each event holds the app name (`moodledesk`), the app version, the operating system, the CPU type and a random install ID. Turn it off with `DO_NOT_TRACK=1`. Full text: [`PRIVACY.md`](PRIVACY.md) and https://publikhq.com/skills/telemetry.md.
  - `src-tauri/src/publik_telemetry.rs`: the client (one file).
  - `src-tauri/src/lib.rs`: the `mod` line and one `publik_telemetry::start(...)` call in `setup`.
  - `src-tauri/Cargo.toml`, `src-tauri/Cargo.lock`: the `ureq` crate (desktop targets only).
- **Signed and notarized by publik.** The macOS app and dmg are signed with the Developer ID of publik (Mann Bellani, team `R5R3ZS54LV`) and notarized by Apple. The Windows and Linux files are not signed.
- **Build.** `.github/workflows/publik-build.yml` builds the files. `.github/workflows/release.yml` does not run for a `-publik` tag.
- **Text.** This file, the "Usage counts" part of `README.md`, and the publik parts of `PRIVACY.md`.

Nothing else is changed. The Android and iOS code is not changed and sends no usage counts.

## Versions

The app version stays the upstream version. A publik release has the tag `<upstream tag>-publik.<n>`, for example `v0.2.2-publik.1`.

## Source

The complete changed source of each publik release is this repository at the commit of the release tag: https://github.com/Blueturboguy07/zenith (branch `telemetry/v1`).

## Not changed: the update notice

The update notice of the app still reads the releases of the original repository (`github.com/zac06/zenith`). A newer version that it shows is the original build: it is not signed by publik and it sends no usage counts.
