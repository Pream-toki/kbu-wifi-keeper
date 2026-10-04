"""Tray app: keep KBU.WIFI / KBU.FL7 portal sessions alive."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import traceback
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import pystray

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
LOG_PATH = APP_DIR / "keeper.log"
PROBE_URLS = (
    "http://connectivitycheck.gstatic.com/generate_204",
    "http://www.msftconnecttest.com/connecttest.txt",
    "http://neverssl.com/",
)

stop_event = threading.Event()
state_lock = threading.Lock()
runtime = {"enabled": True, "last": "starting", "ssid": ""}


def log(msg: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            if f.tell() > 400_000:
                pass
    except OSError:
        pass


def load_config() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data.setdefault("enabled", True)
    data.setdefault("check_seconds", 20)
    data.setdefault("networks", {})
    return data


def save_config(data: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


STARTUP_NAME = "KBUWifiKeeper.vbs"


def startup_path() -> Path:
    return (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / STARTUP_NAME
    )


def startup_enabled() -> bool:
    return startup_path().exists()


def set_startup(icon, want: bool) -> None:
    p = startup_path()
    try:
        if want:
            script = Path(__file__).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                'Set sh = CreateObject("WScript.Shell")\n'
                f'sh.CurrentDirectory = "{script.parent}"\n'
                f'sh.Run "pythonw ""{script}""", 0, False\n',
                encoding="ascii",
            )
        elif p.exists():
            p.unlink()
        cfg = load_config()
        cfg["start_with_windows"] = want
        save_config(cfg)
    except OSError:
        pass
    try:
        icon.update_menu()
    except Exception:
        pass


def current_ssid() -> str:
    try:
        out = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return ""
    for line in out.splitlines():
        if "SSID" in line and "BSSID" not in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return ""


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict] = []
        self._cur: dict | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        a = dict(attrs)
        if tag == "form":
            self._cur = {
                "action": a.get("action", ""),
                "method": a.get("method", "post").lower(),
                "inputs": {},
            }
            self.forms.append(self._cur)
        elif tag in ("input", "select") and self._cur is not None:
            name = a.get("name")
            if name:
                self._cur["inputs"][name] = a.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._cur = None


def looks_like_portal(resp: requests.Response) -> bool:
    if resp.status_code in (401, 302, 303, 307, 308):
        return True
    if resp.status_code == 204:
        return False
    text = (resp.text or "")[:8000].lower()
    if "password" in text and ("login" in text or "username" in text or "user" in text):
        return True
    if "generate_204" in (resp.url or "") and resp.status_code == 204:
        return False
    if resp.status_code == 200 and len(resp.content) < 20 and b"Microsoft" in resp.content:
        return False
    host = urlparse(resp.url).hostname or ""
    if host.endswith("gstatic.com") or host.endswith("msftconnecttest.com"):
        return resp.status_code not in (200, 204)
    return "login" in text or "captive" in text or "auth" in text


def fill_credentials(inputs: dict, username: str, password: str) -> dict:
    data = dict(inputs)
    user_keys = []
    pass_keys = []
    for k in data:
        lk = k.lower()
        if any(x in lk for x in ("pass", "pwd", "password")):
            pass_keys.append(k)
        elif any(x in lk for x in ("user", "uid", "account", "login", "name", "id")):
            user_keys.append(k)
    if user_keys:
        data[user_keys[0]] = username
    else:
        data["username"] = username
        data["user"] = username
    if pass_keys:
        data[pass_keys[0]] = password
    else:
        data["password"] = password
        data["passwd"] = password
    return data


def try_login(session: requests.Session, username: str, password: str) -> bool:
    headers = {"User-Agent": "Mozilla/5.0 KBUWifiKeeper/1.0"}
    start = None
    for url in PROBE_URLS:
        try:
            start = session.get(url, timeout=8, allow_redirects=True, headers=headers)
            break
        except requests.RequestException:
            continue
    if start is None:
        return False
    if not looks_like_portal(start):
        return True

    html = start.text or ""
    parser = FormParser()
    try:
        parser.feed(html)
    except Exception:
        parser.forms = []

    forms = parser.forms or [
        {"action": start.url, "method": "post", "inputs": {}}
    ]
    for form in forms:
        action = urljoin(start.url, form.get("action") or "")
        payload = fill_credentials(form.get("inputs") or {}, username, password)
        try:
            if form.get("method") == "get":
                r = session.get(action, params=payload, timeout=12, headers=headers)
            else:
                r = session.post(action, data=payload, timeout=12, headers=headers)
            if r.status_code < 500:
                # confirm online
                chk = session.get(PROBE_URLS[0], timeout=8, allow_redirects=True, headers=headers)
                if not looks_like_portal(chk) or chk.status_code == 204:
                    return True
        except requests.RequestException:
            continue
    return False


def online() -> bool:
    try:
        r = requests.get(PROBE_URLS[0], timeout=6, allow_redirects=True)
        return r.status_code == 204 or not looks_like_portal(r)
    except requests.RequestException:
        return False


def worker() -> None:
    session = requests.Session()
    session.trust_env = False
    while not stop_event.is_set():
        try:
            cfg = load_config()
            enabled = bool(cfg.get("enabled", True))
            with state_lock:
                runtime["enabled"] = enabled
            ssid = current_ssid()
            with state_lock:
                runtime["ssid"] = ssid
            nets = cfg.get("networks") or {}
            wait = max(8, int(cfg.get("check_seconds") or 20))
            if not enabled:
                with state_lock:
                    runtime["last"] = "paused"
            elif ssid not in nets:
                with state_lock:
                    runtime["last"] = f"idle ({ssid or 'no wifi'})"
            else:
                creds = nets[ssid]
                user = str(creds.get("username") or "")
                pw = str(creds.get("password") or "")
                if online():
                    with state_lock:
                        runtime["last"] = f"ok {ssid}"
                else:
                    log(f"portal on {ssid}, logging in as {user}")
                    ok = try_login(session, user, pw)
                    with state_lock:
                        runtime["last"] = "logged in" if ok else "login retry"
                    log("login " + ("ok" if ok else "failed"))
            stop_event.wait(wait)
        except Exception:
            log(traceback.format_exc())
            stop_event.wait(15)


def open_settings(_icon=None, _item=None) -> None:
    try:
        os.startfile(str(CONFIG_PATH))
    except OSError:
        pass


def set_enabled(icon, value: bool) -> None:
    cfg = load_config()
    cfg["enabled"] = value
    save_config(cfg)
    with state_lock:
        runtime["enabled"] = value
        runtime["last"] = "on" if value else "paused"
    try:
        icon.update_menu()
    except Exception:
        pass


def quit_app(icon, _item=None) -> None:
    stop_event.set()
    icon.stop()


def menu(icon):
    with state_lock:
        en = runtime["enabled"]
        last = runtime["last"]
        ssid = runtime["ssid"]
    return pystray.Menu(
        pystray.MenuItem(f"Status: {last}", None, enabled=False),
        pystray.MenuItem(f"Wi-Fi: {ssid or '-'}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Keeper ON", lambda i, _: set_enabled(i, True), checked=lambda _: en, radio=True),
        pystray.MenuItem("Keeper OFF", lambda i, _: set_enabled(i, False), checked=lambda _: not en, radio=True),
        pystray.MenuItem(
            "Start with Windows",
            lambda i, _: set_startup(i, not startup_enabled()),
            checked=lambda _: startup_enabled(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open settings (accounts)", open_settings),
        pystray.MenuItem("Quit", quit_app),
    )


def make_icon_image():
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=(32, 140, 90, 255))
    d.arc((16, 22, 48, 54), 200, 340, fill="white", width=4)
    d.ellipse((28, 40, 36, 48), fill="white")
    return img


def run_tray() -> None:
    import pystray

    global pystray
    icon = pystray.Icon(
        "KBUWifiKeeper",
        make_icon_image(),
        "KBU Wi-Fi Keeper",
        menu=pystray.Menu(lambda: menu(icon)),
    )
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    icon.run()


if __name__ == "__main__":
    try:
        run_tray()
    except Exception:
        log(traceback.format_exc())
        # keep working even if tray UI fails
        worker()
