# Switch 2 Controllers on Linux

Wireless **Nintendo Switch 2** controller support for Linux. The **NSO GameCube
controller** and **Pro Controller 2** are tested and working — buttons, analog
sticks/triggers, **rumble**, **gyro/accelerometer** (via a built-in DSU/cemuhook
server), battery reporting, and reliable wake-from-sleep reconnection.
**Joy-Con 2** has experimental, **untested** scaffolding (see the table below).

The Switch 2 controllers use a proprietary Bluetooth LE (GATT) protocol that
standard Linux gamepad stacks don't understand. This project talks to them
directly over a **raw L2CAP ATT socket** (bypassing BlueZ's GATT layer
entirely), decodes the input reports, and exposes each controller as a normal
`uinput` gamepad that Steam, SDL, and emulators see as a standard pad. It runs
fully in user space — no kernel modules, no root.

> Unofficial and not affiliated with or endorsed by Nintendo. Built from
> community protocol research (see [Credits](#credits)). Use at your own risk.

## Features

- **Multiple controllers at once** (local multiplayer): one worker per pad, each
  with its own virtual gamepad, rumble, and DSU motion slot.
- **Wake-connect after pairing**: a shared BLE scan watches for your bonded
  controllers; press any button to wake and the bridge connects. This replaces
  the earlier blind retry loop, but **still needs real-world confirmation** on
  your box — especially with two pads waking at once.
- **Rumble**: HD rumble for Pro Controller 2 (real motor packets; Joy-Con 2
  paths exist but are untested); preset-based, edge-driven rumble for the NSO
  GameCube pad (no HD actuator).
- **Gyro everywhere**: an embedded **DSU (cemuhook) UDP server** on
  `127.0.0.1:26760` feeds accel/gyro to Dolphin, Cemu, Ryujinx, etc.
- **Analog triggers + C-stick** on the NSO GameCube pad; calibrated sticks.
- **Bluetooth Pro Controller 2 X/Y swap**: physical X reports `BTN_NORTH`
  (gamepad Y), and physical Y reports `BTN_WEST` (gamepad X).
- **Independent extra buttons**: Pro Controller 2 GL/GR rear buttons are
  exposed as extra gamepad inputs. C and Capture remain available too.
- **Auto-reconnect** with bonding (no re-pairing after the first time).
- **Desktop launchers** on Bazzite for first-time setup and pairing (no terminal
  or Decky plugin required).
- **systemd --user service** for hands-off background operation.

## Supported controllers

| Controller            | Status        | Buttons | Sticks | Triggers      | Rumble       | Gyro |
| --------------------- | ------------- | ------- | ------ | ------------- | ------------ | ---- |
| NSO GameCube          | ✅ tested      | ✅      | ✅     | ✅ analog L/R | ✅ presets   | ✅   |
| Pro Controller 2      | ✅ tested      | ✅      | ✅     | digital ZL/ZR | ✅ HD rumble | ✅   |
| Joy-Con 2 (L / R)     | ⚠️ untested   | ?       | ?      | ?             | ?            | ?    |

> **Joy-Con 2 is untested.** The code defines their product IDs, accepts them in
> the scanner, and has per-side vibration UUIDs, so they may connect — but this
> has never been verified against real hardware. A single Joy-Con also needs its
> own button/stick mapping and sideways orientation handling, which isn't
> implemented yet (it currently reuses the full-controller layout). Treat
> Joy-Con 2 as a starting point, not a working feature. Reports/PRs welcome.

## How it works

```
Controller (BLE)
   │  raw L2CAP ATT socket (BT_SECURITY_LOW), no BlueZ GATT
   ▼
ngc.att        — minimal ATT client (read/write/notify) over L2CAP
ngc.protocol   — input-report parsing, calibration, vibration, button maps
ngc.device     — SwitchController: handshake, GATT discovery, LEDs, rumble
   │
   ├─► ngc.gamepad — uinput virtual pad (buttons/axes/triggers + force-feedback)
   └─► ngc.dsu     — DSU/cemuhook UDP server (motion) on 127.0.0.1:26760
   │
ngc.bridge     — multi-controller manager: connect, reconnect, own gamepad+rumble
```

Key design choices:

- **Raw L2CAP instead of BlueZ GATT.** BlueZ's service discovery is unreliable
  with these controllers; a direct ATT socket with `BT_SECURITY_LOW` connects
  fast and predictably.
- **Serialized create-connection.** Most adapters allow only one outstanding LE
  connection initiation at a time, so the bridge serializes connects behind a
  lock — the fix for "only one of my two controllers wakes up."
- **Standard `uinput` layout.** The virtual pad uses the conventional
  Xbox-style evdev button codes, with X/Y swapped for Pro Controller 2.
  The NSO GameCube and experimental Joy-Con 2 layouts are unchanged.

## Requirements

- Linux with a Bluetooth LE adapter
- Python 3.12 (exactly: `bleak==0.22.2` does not install on 3.13+; if your
  distro ships a newer Python, get 3.12 via `uv`, `mise` or `pyenv`)
- `bleak==0.22.2` (BLE scanning during pairing) and `evdev>=1.6`
- `/dev/uinput` writable by your user (Bazzite/most distros grant this via a
  udev ACL; otherwise add a udev rule)

## Install

```bash
git clone https://github.com/BloodotakuZ/switch2-controllers-linux.git ~/nso-gc-bazzite
cd ~/nso-gc-bazzite
bash scripts/install.sh
```

**On Bazzite Desktop (easiest):** open the app menu and run **Switch 2
Controllers — First-Time Setup**, then **Pair Switch 2 Controller**. No terminal
and no Decky plugin needed.

## Usage

### First time only — pair each controller

1. Hold **Sync** until the player LEDs sweep/chase (pairing mode).
2. Run **Pair Switch 2 Controller** from the Desktop app menu (or
   `.venv312/bin/python -m ngc pair` from a terminal).
3. Repeat for a second pad if you use both GameCube + Pro.

The wizard bonds the controller so it can reconnect without pairing mode again.

### Every day — wake and play

1. Make sure the background service is running (setup enables it):
   `systemctl --user status nso-gc.service`
2. **Press any button** on a paired controller to wake it.
3. The bridge scans for that pad's advertisement and connects automatically.

Use **Switch 2 Controller Status** from the app menu to see what's paired and
whether the service is active.

> **Honest status:** pairing, input, rumble, and gyro are tested on real
> hardware (NSO GameCube + Pro Controller 2). Routine wake-connect *should* work
> after bonding, but it has been flaky in development (adapter scanning
> conflicts, Decky BT Wake plugin). The bridge now uses advertisement-driven
> wake-connect instead of blind retries — please verify on your box and report
> issues. Simultaneous dual-pad wake is still best-effort.

```bash
# Terminal equivalents
python -m ngc list          # show paired controllers
python -m ngc run           # foreground bridge (service uses this)
journalctl --user -u nso-gc.service -f   # live logs
```

## Bluetooth button mapping in this fork

The default Pro Controller 2 virtual gamepad swaps X and Y. A/B, sticks, and shoulders keep their existing mappings.

| Physical button | Linux input |
| --- | --- |
| X | `BTN_NORTH` (gamepad Y) |
| Y | `BTN_WEST` (gamepad X) |
| C | `BTN_C` |
| Capture | `BTN_Z` |
| GL / GR | `BTN_TRIGGER_HAPPY1` / `BTN_TRIGGER_HAPPY2` |

GL/GR are separate inputs, not copies of other buttons. Bind them in an
application that accepts extra joystick buttons. The optional SDL database
maps GR/GL to paddle1/paddle2, C to misc1, and Capture to misc2; support for
these extended SDL slots depends on the application's SDL version.

After updating an existing checkout, restart `nso-gc.service` and wake the pad
to recreate its virtual device. If you use the optional emulator integration,
rerun `scripts/install-emulator-integration.sh` with the pad connected to refresh
its SDL mapping. An existing nonempty `button_map` in
`~/.config/nso-gc/config.json` replaces the defaults; use `{}` for this fork's
defaults or add the extra buttons to your custom map.

These changes affect the Pro Controller 2 Bluetooth uinput gamepad.
The NSO GameCube and Joy-Con 2 mappings and the DSU motion server's original button layout are unchanged. DSU has no
standard GL/GR button slots; use uinput for the extra buttons and DSU for motion.

### Other desktops: let SDL apps see GL/GR

Without a mapping, SDL generates a generic one for the virtual pad that drops
GL, GR, C and Capture, so apps never see them even though the bridge sends
them. Outside Bazzite/EmuDeck, nothing loads the mapping that
`tools/sdl_guid.py` writes, so install it as a session environment variable:

```bash
mkdir -p ~/.config/environment.d
cp system/environment.d/60-switch2-pro.conf ~/.config/environment.d/
```

Then **log out and back in**. Apps started from your desktop inherit the
compositor's environment, which is only read at login, so restarting Steam or
the emulator is not enough. Tested on Arch (Omarchy, Hyprland + uwsm) with
Steam and PPSSPP 1.20.4. For a quick test without logging out, start an app with
the variable set inline:

```bash
SDL_GAMECONTROLLERCONFIG="$(sed -n 's/^SDL_GAMECONTROLLERCONFIG=//p' system/environment.d/60-switch2-pro.conf)" PPSSPPSDL
```

### Steam rear-button compatibility mode (experimental)

If Steam detects the Pro Controller 2 but does not show GL/GR in its layout
editor, try the optional Elite identity workaround. It presents only the Pro
virtual gamepad as a USB Xbox Elite Series 2 (`045e:0b00`) and reports GR/GL
using xpad's upper-right/upper-left paddle codes (`BTN_TRIGGER_HAPPY5` / `7`).
The physical connection remains Bluetooth; X/Y, sticks, triggers, and the
Bluetooth rumble implementation are retained. Steam may use Xbox labels and
create a fresh layout for this virtual identity. Existing saved emulator
device selections may need updating. Use DSU for motion in this mode.

This workaround is covered by simulated input tests, but Steam's paddle UI
still needs confirmation on real hardware; it is not enabled by default.

Fully exit Steam, then enable the mode:

```bash
mkdir -p ~/.config/systemd/user/nso-gc.service.d
cat > ~/.config/systemd/user/nso-gc.service.d/steam-elite.conf <<'EOF'
[Service]
Environment=NGC_STEAM_ELITE=1
EOF
systemctl --user daemon-reload
systemctl --user restart nso-gc.service
```

Wake the controller, regenerate the SDL mapping for the new identity, and
launch Steam with that file (requires PySDL2 in `.venv312`):

```bash
cd ~/nso-gc-bazzite
mkdir -p ~/.config/nso-gc
.venv312/bin/python tools/sdl_guid.py \
  | sed -n 's/^     mapping: //p' \
  > ~/.config/nso-gc/steam-gamecontrollerdb.txt
cat ~/.config/nso-gc/steam-gamecontrollerdb.txt
SDL_GAMECONTROLLERCONFIG_FILE="$HOME/.config/nso-gc/steam-gamecontrollerdb.txt" steam
```

The printed Pro mapping should include `[Steam Elite]`, `paddle1:b15` (GR),
and `paddle2:b16` (GL). If no mapping prints, do not launch with an empty file;
run `tools/sdl_guid.py` without redirection and inspect its output.

To revert, remove only `~/.config/systemd/user/nso-gc.service.d/steam-elite.conf`,
reload systemd, restart the service, wake the controller, and regenerate the
SDL mapping. The original Nintendo virtual identity will return.

## Gyro / motion (DSU)

When the bridge runs it starts a DSU/cemuhook server on `127.0.0.1:26760`
exposing one slot per controller (slot = player − 1). Point any cemuhook-capable
emulator at it:

- **Dolphin**: `DSUClient.ini` → add `127.0.0.1:26760`, enable in Wii motion
  bindings as needed.
- **Ryujinx**: set the controller's motion backend to **CemuHook**, host
  `127.0.0.1`, port `26760`, matching slot.
- **Cemu**: add the DSU server in the motion source settings.

## Rumble notes

- **Pro Controller 2 / Joy-Con 2** have real HD-rumble actuators driven by a
  sustaining worker thread, so effects feel continuous.
- **NSO GameCube** has no HD actuator (writing the HD characteristic powers it
  off), so it replays built-in presets. Rumble is edge-driven: a fresh onset
  fires a strong buzz, while sustained effects emit gentle light pulses — punchy
  hits without a constant slam.

## Bazzite / EmuDeck integration (optional)

The [`system/`](system/) folder contains an example integration for a Bazzite +
EmuDeck setup:

- `bazzite-controller-detect.py` — assigns emulator player order and per-pad
  profiles (recognizes the new virtual pads by name).
- `dolphin/GC_nso_gamecube.ini` — native GameCube Dolphin profile.
- `ryujinx/Switch2_Pro.json` + `patch_ryujinx_motion.py` — Switch 2 Pro profile
  and CemuHook motion wiring.

Install with `scripts/install-emulator-integration.sh`. Per-device MACs are
read from `BAZZITE_*_MAC` env vars (empty by default; name-based classification
works without them).

## Project layout

```
ngc/        core bridge (att, protocol, device, gamepad, dsu, bridge, cli)
scripts/    install / deploy / bluetooth-prep helpers
systemd/    user service unit
system/     optional Bazzite/EmuDeck emulator integration (example)
tools/      diagnostics: scanning, GATT discovery, rumble/preset tests, DSU test
```

## Credits

This stands on the shoulders of prior community work:

- [TommyWabg/switch2-controllers-windows10-gyro](https://github.com/TommyWabg/switch2-controllers-windows10-gyro)
  — Switch 2 BLE protocol research.
- [joaorb64/joycond-cemuhook](https://github.com/joaorb64/joycond-cemuhook) and
  [TheDrHax/ds4drv-cemuhook](https://github.com/TheDrHax/ds4drv-cemuhook)
  — DSU server reference.
- [v1993/cemuhook-protocol](https://github.com/v1993/cemuhook-protocol)
  — the cemuhook UDP protocol documentation.
- [bleak](https://github.com/hbldh/bleak) and
  [python-evdev](https://github.com/gvalkov/python-evdev).

## License

[MIT](LICENSE)
