import ReactDOM from "react-dom/client";
import App from "./App";
import { init } from "./api";
import "./style.css";
// apply the saved appearance before React renders, so there is no flash of the wrong theme
{
  const root = document.documentElement; const t = localStorage.getItem("theme"); const c = localStorage.getItem("contrast"); const a = localStorage.getItem("accent");
  if (a && /^#[0-9a-f]{6}$/i.test(a)) { root.dataset.accent = ""; root.style.setProperty("--a", a); }
  if (t === "light" || t === "dark") root.dataset.theme = t;
  // "system" (the default, also when nothing is saved) follows the OS; "on"/"high" and "off" are explicit choices
  if (c === "on" || c === "high" || (c !== "off" && matchMedia("(prefers-contrast: more)").matches)) root.dataset.contrast = "high";
}
init().then(() => ReactDOM.createRoot(document.getElementById("root")!).render(<App />));
