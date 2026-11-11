//! publik build of Zenith (see PUBLIK-BUILD.md): Sign in with publik, in a small window, before Zenith's own window.
//!
//! On a desktop, Zenith's main window is not made at start-up (`main_window_after_sign_in` sets `create: false`).
//! `start` runs `publik::ensure_signed_in` on its own thread. Each screen of the gate is a small page on the
//! `publik-gate` protocol, served from this file with no IPC: a button is a link to `/press/<id>`, and the page asks
//! `/seq` and loads again when the screen changes. When the person is signed in, `start` makes the main window from
//! tauri.conf.json and closes the gate window. Closing the gate window before that quits the app (it is the only
//! window), so there is no way past the gate. Zenith's own first screen ("Welcome to Zenith") is in the main window,
//! so it always comes after the sign-in.
//!
//! The gate window opens at the first screen of the gate, or when the check takes longer than `OPEN_AFTER`. A person
//! who is signed in already sees only Zenith's window.
//!
//! `PUBLIK_SELF_TEST=1`: `self_test_if_asked` prints `publik self-test: ok moodledesk <version>` after a real
//! GET /wallet and exits, before Tauri starts and before any window opens.

use crate::publik::{self, GateUi, Screen};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, MutexGuard};
use std::time::{Duration, Instant};
use tauri::http::{header, Request, Response, StatusCode};
use tauri::{AppHandle, Manager, UriSchemeResponder, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_opener::OpenerExt;

/// The custom protocol of the gate page: `publik-gate://localhost/` (macOS, Linux), `http://publik-gate.localhost/`
/// (Windows). Tauri maps it.
pub const SCHEME: &str = "publik-gate";
const WINDOW: &str = "publik-gate";
const MAIN: &str = "main";
const PRESS: &str = "/press/";
/// The gate window opens after this time when the gate has no answer yet (a slow network).
const OPEN_AFTER: Duration = Duration::from_millis(700);
/// How long a press waits for the next screen, so that the page it answers with is the next one.
const PRESS_SETTLE: Duration = Duration::from_millis(1500);

/// The screen on display: a copy of the module's `Screen`.
struct Shown {
    title: &'static str,
    body: String,
    note: Option<&'static str>,
    buttons: Vec<(&'static str, &'static str)>,
}

struct Slot {
    /// None before the first screen: the page says "Connecting to publik…".
    shown: Option<Shown>,
    /// Counts the screens. The page loads again when it changes.
    seq: u64,
    /// The button the person pressed, until the gate thread takes it.
    pressed: Option<&'static str>,
    /// The sign-in link, when the browser did not open. The page shows it so that the person can copy it.
    link: Option<String>,
}

static SLOT: Mutex<Slot> = Mutex::new(Slot {
    shown: None,
    seq: 0,
    pressed: None,
    link: None,
});
/// true once the gate has passed. Every window change takes this lock, so the gate window and the main window
/// never race.
static PASSED: Mutex<bool> = Mutex::new(false);

fn slot() -> MutexGuard<'static, Slot> {
    SLOT.lock().unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn passed() -> MutexGuard<'static, bool> {
    PASSED.lock().unwrap_or_else(|poisoned| poisoned.into_inner())
}

/// First thing in `run()`. With PUBLIK_SELF_TEST set, the module prints its one line and exits at once; it shows no
/// screen. Without it, this does nothing.
pub fn self_test_if_asked() {
    if std::env::var_os("PUBLIK_SELF_TEST").is_some() {
        let _ = publik::ensure_signed_in(&mut publik::TerminalUi);
    }
}

/// The main window is made after the sign-in (`start`), not by Tauri at start-up.
pub fn main_window_after_sign_in<R: tauri::Runtime>(mut context: tauri::Context<R>) -> tauri::Context<R> {
    for window in context.config_mut().app.windows.iter_mut() {
        window.create = false;
    }
    context
}

/// Called first in the setup hook: runs the gate on its own thread, then opens Zenith's main window.
pub fn start(app: &AppHandle) {
    let gate_app = app.clone();
    let spawned = std::thread::Builder::new().name("publik-gate".into()).spawn(move || {
        let mut ui = WindowUi { app: gate_app.clone() };
        let _ = publik::ensure_signed_in(&mut ui);
        pass(&gate_app);
    });
    if let Err(e) = spawned {
        eprintln!("publik: the sign-in could not start: {e}");
        app.exit(1);
        return;
    }
    let late_app = app.clone();
    let _ = std::thread::Builder::new()
        .name("publik-gate-window".into())
        .spawn(move || {
            std::thread::sleep(OPEN_AFTER);
            open_window(&late_app);
        });
}

/// A second start of the app (single instance) brings the gate window to the front while it is open.
pub fn focus<R: tauri::Runtime>(app: &AppHandle<R>) {
    if let Some(window) = app.get_webview_window(WINDOW) {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn open_window(app: &AppHandle) {
    let passed = passed();
    if *passed || app.get_webview_window(WINDOW).is_some() {
        return;
    }
    let url: tauri::Url = match format!("{SCHEME}://localhost/").parse() {
        Ok(url) => url,
        Err(_) => return,
    };
    let built = WebviewWindowBuilder::new(app, WINDOW, WebviewUrl::CustomProtocol(url))
        .title("Sign in with publik")
        .inner_size(480.0, 360.0)
        .resizable(false)
        .maximizable(false)
        .center()
        .focused(true)
        .build();
    if let Err(e) = built {
        // No gate window means no way to sign in, and the main window must not open without it.
        eprintln!("publik: the sign-in window did not open: {e}");
        app.exit(1);
    }
}

/// The gate passed: make Zenith's main window (from tauri.conf.json), then close the gate window. In this order the
/// app always has a window, so it does not quit.
fn pass(app: &AppHandle) {
    let mut passed = passed();
    *passed = true;
    if app.get_webview_window(MAIN).is_none() {
        let made = match app.config().app.windows.iter().find(|w| w.label == MAIN).cloned() {
            Some(config) => WebviewWindowBuilder::from_config(app, &config)
                .and_then(|b| b.build())
                .map(|_| ()),
            None => Err(tauri::Error::WindowNotFound),
        };
        if let Err(e) = made {
            eprintln!("publik: Zenith's window did not open after the sign-in: {e}");
            app.exit(1);
            return;
        }
    }
    if let Some(window) = app.get_webview_window(WINDOW) {
        let _ = window.close();
    }
}

/// `publik::GateUi` over the slot: the gate thread's side.
struct WindowUi {
    app: AppHandle,
}

impl GateUi for WindowUi {
    fn show(&mut self, screen: &Screen, done: Arc<AtomicBool>) -> Option<&'static str> {
        {
            let mut s = slot();
            s.shown = Some(Shown {
                title: screen.title,
                body: screen.body.clone(),
                note: screen.note,
                buttons: screen.buttons.clone(),
            });
            s.seq = s.seq.wrapping_add(1);
            s.pressed = None;
        }
        open_window(&self.app);
        loop {
            if let Some(id) = slot().pressed.take() {
                return Some(id);
            }
            if done.load(Ordering::SeqCst) {
                return None;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }

    fn open_url(&mut self, url: &str) {
        if let Err(e) = self.app.opener().open_url(url, None::<&str>) {
            eprintln!("publik: the browser did not open: {e}");
            slot().link = Some(url.to_string());
        }
    }
}

/// The `publik-gate` protocol: `/seq` (the screen counter), `/press/<id>` (a button), and the page for anything else.
pub fn serve(request: Request<Vec<u8>>, responder: UriSchemeResponder) {
    let path = request.uri().path().to_string();
    if let Some(id) = path.strip_prefix(PRESS) {
        let id = id.to_string();
        // The answer waits for the next screen: not on the webview's thread.
        std::thread::spawn(move || responder.respond(press(&id)));
        return;
    }
    if path == "/seq" {
        let seq = slot().seq;
        return responder.respond(reply("text/plain; charset=utf-8", seq.to_string().into_bytes()));
    }
    responder.respond(page());
}

fn press(id: &str) -> Response<Vec<u8>> {
    let before = {
        let mut s = slot();
        // Only a button of the screen on display counts; the id becomes that screen's own str.
        let button = s
            .shown
            .as_ref()
            .and_then(|shown| shown.buttons.iter().map(|(b, _)| *b).find(|b| *b == id));
        if button.is_some() && s.pressed.is_none() {
            s.pressed = button;
        }
        s.seq
    };
    let start = Instant::now();
    while start.elapsed() < PRESS_SETTLE && slot().seq == before {
        std::thread::sleep(Duration::from_millis(25));
    }
    page()
}

fn reply(content_type: &str, body: Vec<u8>) -> Response<Vec<u8>> {
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, content_type)
        .header(header::CACHE_CONTROL, "no-store")
        .body(body)
        .unwrap_or_else(|_| Response::new(Vec::new()))
}

/// Zenith's colours (src/style.css), light and dark.
const STYLE: &str = r#":root{--bg:#eceeed;--card:#f8f9f8;--fg:#1d2522;--mut:#5b6762;--line:#d1d7d4;--acc:#1f5c4a;--accon:#fff;color-scheme:light}
@media(prefers-color-scheme:dark){:root{--bg:#161b19;--card:#1c2220;--fg:#e3e8e5;--mut:#94a19b;--line:#2c3531;--acc:#6fbf9f;--accon:#10231b;color-scheme:dark}}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,"Segoe UI Variable Text","Segoe UI",Roboto,"Helvetica Neue",sans-serif;-webkit-user-select:none;user-select:none;cursor:default}
main{min-height:100%;display:flex;flex-direction:column;justify-content:center;padding:28px 32px;max-width:480px;margin:0 auto}
.app{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);margin:0 0 6px}
h1{font:600 24px/1.2 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;margin:0 0 12px}
p{margin:0 0 12px}.note{color:var(--mut)}.link{font-size:13px;word-break:break-all;-webkit-user-select:text;user-select:text;cursor:text}
.buttons{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}
.button{display:inline-block;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:600;background:var(--card);color:var(--fg);border:1px solid var(--line);cursor:pointer}
.button.primary{background:var(--acc);color:var(--accon);border-color:var(--acc)}.button:hover{filter:brightness(1.08)}
.button:focus-visible{outline:2px solid var(--acc);outline-offset:2px}body.busy .button{opacity:.6;pointer-events:none}"#;

/// The page asks /seq every 0.7 s and loads "/" again when the screen changed. After a press it puts "/" back in the
/// address, so a reload never presses again. When /seq does not answer three times, it loads the page again.
const SCRIPT: &str = r#"(function(){var seq=document.body.getAttribute("data-seq"),fails=0;
try{if(location.pathname!=="/")history.replaceState(null,"","/")}catch(e){}
var bs=document.querySelectorAll("a.button");for(var i=0;i<bs.length;i++){bs[i].addEventListener("click",function(){document.body.className="busy"})}
function tick(){fetch("/seq?t="+Date.now(),{cache:"no-store"}).then(function(r){return r.text()}).then(function(t){fails=0;if(t.trim()!==seq){location.replace("/")}},function(){fails+=1;if(fails>=3){location.replace("/")}}).then(function(){setTimeout(tick,700)})}
setTimeout(tick,700)})();"#;

fn page() -> Response<Vec<u8>> {
    let s = slot();
    let (title, body, note, buttons) = match &s.shown {
        Some(shown) => (shown.title, shown.body.as_str(), shown.note, shown.buttons.as_slice()),
        None => ("Sign in with publik", "Connecting to publik…", None, &[][..]),
    };
    let mut html = format!(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\
         <noscript><meta http-equiv=\"refresh\" content=\"3;url=/\"></noscript><title>{}</title><style>{STYLE}</style></head>\
         <body data-seq=\"{}\"><main><p class=\"app\">Zenith</p><h1>{}</h1><p>{}</p>",
        escape(title),
        s.seq,
        escape(title),
        escape(body)
    );
    if let Some(note) = note {
        html.push_str(&format!("<p class=\"note\">{}</p>", escape(note)));
    }
    if let (Some(link), Some(_)) = (&s.link, note) {
        html.push_str(&format!("<p class=\"link\">{}</p>", escape(link)));
    }
    html.push_str("<div class=\"buttons\">");
    for (i, (id, label)) in buttons.iter().enumerate() {
        let class = if i == 0 { "button primary" } else { "button" };
        html.push_str(&format!(
            "<a class=\"{class}\" role=\"button\" href=\"{PRESS}{}\">{}</a>",
            escape(id),
            escape(label)
        ));
    }
    html.push_str(&format!("</div></main><script>{SCRIPT}</script></body></html>"));
    reply("text/html; charset=utf-8", html.into_bytes())
}

fn escape(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(c),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn text(response: Response<Vec<u8>>) -> String {
        String::from_utf8_lossy(response.body()).to_string()
    }

    #[test]
    fn the_page_shows_the_screen_and_takes_a_press() {
        assert!(text(page()).contains("Connecting to publik"));
        let screen = publik::gate_screen("sign_in", None, None, None);
        {
            let mut s = slot();
            s.shown = Some(Shown {
                title: screen.title,
                body: screen.body.clone(),
                note: screen.note,
                buttons: screen.buttons.clone(),
            });
            s.seq = 1;
        }
        let html = text(page());
        assert!(html.contains("<title>Sign in with publik</title>"));
        assert!(html.contains("<h1>Sign in with publik</h1>"));
        assert!(html.contains("href=\"/press/sign_in\""));
        assert!(html.contains("data-seq=\"1\""));
        press("not_a_button");
        assert_eq!(slot().pressed, None);
        press("sign_in");
        assert_eq!(slot().pressed, Some("sign_in"));
    }

    #[test]
    fn escape_keeps_markup_out() {
        assert_eq!(escape("<a href=\"x\">&'"), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;");
    }
}
