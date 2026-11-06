# Privacy

> **publik build.** This copy of Zenith is built from the fork https://github.com/Blueturboguy07/zenith and distributed by publik (https://publikhq.com/moodledesk). It differs from the original app (https://github.com/zac06/zenith) in one point: the desktop app sends anonymous usage counts to publik. See "publik" below and [`PUBLIK-BUILD.md`](PUBLIK-BUILD.md). The original app sends no usage counts.

Zenith runs on your computer. It has no accounts, no crash reporting and no servers of its own. The publik build sends the usage counts described below to publik. Nothing else is sent to the developer or to publik, and your Moodle data is not collected.

**What it stores on your computer**
- Your Moodle login token, in the system keychain.
- The files you download, in the folder you choose, and a list of those downloads in the app's data folder.
- Your settings (theme, download mode, download folder), in the app's local storage.
- A copy of the course pages, assignments and forum posts you opened, in the same local storage, so they stay readable offline. It is not encrypted, and signing out deletes it. Android does not include it in backups.

**Who it talks to**
- **Your Moodle site.** Everything you see (courses, files, grades, dates) and your login go there. With password login your username and password are sent to it. Only `https://` sites are accepted. Your site sees the requests as coming from a Moodle mobile app and may log them under its own privacy policy.
- **GitHub (`github.com`).** The app asks it for the latest version, and the About page shows the author's picture from it. GitHub can see your IP address. The project website asks `api.github.com` for the same reason, to show the download buttons.
- **Images in course text** are shown only if they come from your Moodle site, so a teacher's pasted picture from another website is not loaded and cannot reveal your IP address. Cover images use the address your Moodle site provides.
- **Links** you click open in your browser. After that, the other website's own policy applies.
- **publik (`publikhq.com`), desktop app of the publik build only.** The app sends one small message when it starts and one every 30 minutes while it runs. The message holds: the app name (`moodledesk`), the app version, the operating system (`macos`, `windows` or `linux`), the CPU type (`arm64` or `x64`) and a random install ID. The install ID is kept in the file `telemetry.json` in the `publik` folder of your user account (macOS: `~/Library/Application Support/publik`, Windows: `%LOCALAPPDATA%\publik`, Linux: `~/.config/publik`). Other publik apps on the same account use the same ID. The message holds no Moodle site, no login, no course data and no file name. publik can see your IP address when the message arrives. It does not store the address with the count; its rate limiter keeps a hashed form for up to one day. If a publik API key for this app is on the computer (the environment variable `PUBLIK_API_KEY` or the file `apps/moodledesk.json` in the `publik` folder), the key goes with the message and the count is linked to that publik account. Zenith does not create such a key.
  **To turn it off:** set `DO_NOT_TRACK=1` (or `PUBLIK_TELEMETRY=0`) in the environment, or put `{"usage": false}` in the file `consent.json` in the `publik` folder. The app then sends nothing and creates no install ID. Details: https://publikhq.com/skills/telemetry.md

Questions or problems with the app: open an issue at https://github.com/zac06/zenith/issues. Questions about the publik build or its usage counts: https://publikhq.com/moodledesk (do not ask the original author).
