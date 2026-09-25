# Teleco Automation for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

Unofficial Home Assistant integration for **Teleco Automation** boxes: the box behind the
*Daisy Teleco* app and the apps Teleco builds for other brands (Biossun, Brustor, Durmi,
Gibus, Hardtop, Kettal, Pratic, Wise). It controls pergola slats, screens, shutters,
awnings, gates, lights (on/off, dimmers, RGB), fans and heaters, and runs your scenarios.

It is built on [aioteleco](https://github.com/trois-six/aioteleco) and talks to the box on
your local network when it can, through the Teleco cloud otherwise.

> **Disclaimer.** Not affiliated with or endorsed by Teleco Automation or any of the
> brands above; their names are trademarks of their owners. The devices it drives are
> motorised: keep them in sight while you set things up.

## Installation

With [HACS](https://hacs.xyz/):

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/trois-six/ha-teleco`,
   type **Integration**.
2. Install **Teleco Automation**, then restart Home Assistant.
3. **Settings → Devices & services → Add integration → Teleco Automation**, and log in
   with the email and password of your brand app. If the account has several
   installations (boxes), pick one; add the integration again for the others.

Manual installation: copy `custom_components/teleco` into your `config/custom_components/`
and restart.

## What you get

One device per Teleco device (in the room it has in the app), under a device for the box.

| Teleco device | Entity |
|---|---|
| Pergola slats | `cover`: open / close / stop, and the app's steps (0, 33, 66, 100 %) |
| Screens, shutters, awnings, gates, garage doors, windows | `cover`: open / close / stop; a position once travel times are set (below) |
| On/off lights | `light` |
| Dimmers | `light` with brightness (4 steps, or free level on slider dimmers) |
| RGB and tunable-white lights | `light` with color and brightness |
| RGB lights with presets | `light` with the presets and the color cycle as effects |
| Fans | `fan` (3 speeds) |
| Heaters | `select`: off or power step 1–4 |
| Scenarios | `button` on the box device |
| Box | `binary_sensor` (reachable by the cloud), `sensor` (Wi-Fi signal) |

## Options

**Settings → Devices & services → Teleco Automation → Configure**:

- **Connection and polling**: send commands locally with the cloud as fallback (default),
  locally only, or through the cloud only; a fixed box IP address; the polling interval
  (30 s by default; the state is also refreshed right after each command).
- **Cover travel times**: screens and shutters only take open / stop / close. Enter the
  time a full opening and a full closing take (a stopwatch is enough, or
  `teleco cover calibrate` from aioteleco) and the cover gets a position: Home Assistant
  times the move, then sends stop. The position is an estimate: it is reset each time
  the cover reaches an end (fully open or closed).

## How the state works

The box does not report what the motors actually do: the state shown is the one the box
assumes from the last command (as in the app), read from the Teleco cloud. A device moved
with its own remote control shows up once the cloud knows about it.

## Development

```bash
uv sync
uv run pytest
uv run ruff check custom_components tests && uv run ruff format --check custom_components tests
uv run mypy
```

Commits follow [Conventional Commits](https://www.conventionalcommits.org/); releases are
made by release-please.

## License

MIT
