# KBU Wi-Fi Keeper

Campus wifi here (KBU.WIFI / KBU.FL7) dumps you every so often and makes you type the portal login again. This is a small Windows tray app that notices when the session dies and signs you back in. No extra window, no reconnecting the adapter, so Zoom/Chrome just keep going.

Two networks, two accounts. Right-click the green icon for ON/OFF.

## What it actually does

- Watches the current SSID (`netsh`)
- If you’re on one of the two KBU networks, pokes a connectivity URL every ~20s
- If a captive portal ate the request, it posts that network’s username/password
- Failures stay in `keeper.log`. It doesn’t pop error boxes.

## Run (Windows)

Python 3, then:

```
copy config.example.json config.json
```

Put your real logins in `config.json` (that file is gitignored on purpose).

```
START.bat
```

or `install_startup.bat` if you want it after reboot.

Tray: **Keeper ON / OFF**, **Open settings**, **Quit**.

## Notes

- This is just HTTP login against the portal, not a wifi cracker.
- If the school changes the login page, check `keeper.log` and we can tweak the form submit.
- Built for my own laptop because I got tired of the timeout mid-class.
