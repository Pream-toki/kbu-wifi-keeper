# KBU Wi-Fi Keeper

Campus wifi (KBU.WIFI / KBU.FL7) times out and asks for login again. This sits in the tray and signs you back in. It does **not** disconnect wifi, so other apps keep running.

## Setup (once)

1. Install [Python 3](https://www.python.org/downloads/) for Windows. Tick **Add python.exe to PATH**.
2. Copy `config.example.json` to `config.json`.
3. Put **your** usernames and passwords in `config.json`. Two networks = two accounts.
4. Double-click `START.bat`. First run may install packages; wait a few seconds.
5. Look in the tray (hidden-icons `^` if you don’t see a green circle).

`config.json` stays on your laptop. Do not commit it. Do not paste passwords into GitHub issues.

## Use

Right-click the green icon:

- **Keeper ON / OFF** — pause without quitting
- **Start with Windows** — only if you want it after reboot (click again to turn that off)
- **Open settings (accounts)** — edits `config.json`
- **Quit** — fully stops it

If login fails, open `keeper.log` in this folder. The school may have changed the portal page.

This only talks to the captive portal with **your** account. It is not a wifi hack.
