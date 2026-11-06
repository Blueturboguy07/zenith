# publik build of Zenith

This repository is a fork of [Zac06/zenith](https://github.com/Zac06/zenith) (GNU GPL v3, see [`LICENSE`](LICENSE)).
publik (https://publikhq.com/moodledesk) builds its desktop downloads of Zenith from this fork.
The fork is not affiliated with the original author and is not endorsed by the original author.

## What this fork changes

Changed on 2026-11-06. This branch (`main`) carries the change on top of upstream `main` at `0061e94` (version 0.2.5). The publik release `v0.2.2-publik.1` carries the same change on top of the upstream tag `v0.2.2` (branch `telemetry/v1`).

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

## Not changed: the updater

From version 0.2.3 the desktop app updates itself (`tauri-plugin-updater`). The update address (`github.com/zac06/zenith/releases/latest/download/latest.json`) and the public key in `src-tauri/tauri.conf.json` are those of the original author. They are not changed here.
So a build from this branch updates itself to the original build: that build is not signed by publik and it sends no usage counts. publik has no update feed for this app. Decide on the update feed before a publik release is made from this branch.

For the same reason `publik-build.yml` does not build this branch as it is: `tauri build` stops with "A public key has been found, but no private key" (it wants the updater signing key of the original author, which publik does not have). The publik release `v0.2.2-publik.1` comes from the branch `telemetry/v1`, where the app has no updater.
