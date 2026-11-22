# FlashForge 3D printer for Home Assistant

[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]

Monitor and control a FlashForge 3D printer from Home Assistant over your local network.
No cloud account is needed.

This is a fork of [joseffallman/hass_flashforge][upstream], the original integration.
It keeps the same features and adds fixes found while using it every day on an Adventurer 5M.

## What this fork changes

- **Camera works for several viewers at once.** The printer's camera only accepts one
  connection, so a second dashboard or phone used to freeze it. The integration now keeps
  one connection to the printer and shares it.
- **Time remaining and finish time sensors**, estimated from the print progress (from a
  pull request to the original project, see [Credits](#credits-and-licence)).
- **Steadier current layer.** The printer sometimes reports a layer or two ahead for a
  moment (for example during a Z hop). The layer sensor smooths that out and never runs
  past the total.
- **Rides out short printer glitches.** One or two missed answers keep the last values;
  the sensors only go unavailable when the printer stays silent, with a clear reason in
  the log.
- **Clearer errors**, for example why a print can't start.
- **Diagnostics download** for bug reports, with the serial number and IP address removed.
- Updated dependencies and tests.

## Compatibility

| Printer | Firmware | Status |
|---|---|---|
| Adventurer 5M | 5.2.0 | Tested, used daily |
| Adventurer 5M Pro, AD5X | | Should work (same network protocol), not tested |
| Adventurer 3 / 4 | | Supported by the original integration, not tested with this fork |
| Creator 5 / 5 Pro | | Not supported (it doesn't have the network protocol this integration uses) |

If you use it on another printer or firmware, please open an issue with the diagnostics
file (see [Reporting a problem](#reporting-a-problem)) so the table can be updated.

## Installation

Requires Home Assistant 2026.2 or newer.

### Through HACS (recommended)

1. In HACS, open the three-dot menu and choose **Custom repositories**.
2. Add `https://github.com/bradyjh17/hass_flashforge` with the type **Integration**.
3. Find **FlashForge** in HACS, download it and restart Home Assistant.

### Manually

Copy the `custom_components/flashforge` folder from this repository into the
`custom_components` folder of your Home Assistant configuration, then restart Home Assistant.

### Switching from the original integration

This fork uses the same integration name (`flashforge`), so only one of the two can be
installed. In HACS, remove the original repository, add this one as above and restart.
Your printer should stay set up with its entities and history, because this fork builds
the entity IDs the same way as the original.

## Setup

Go to **Settings → Devices & services → Add integration** and search for **FlashForge**.

- Leave the IP address empty to search for the printer on your network, or enter it.
  Searching only works when the printer is on the same network as Home Assistant; on a
  separate network (VLAN), enter the IP address.
- The port is `8899` (the default).

Give the printer a fixed IP address in your router so Home Assistant can keep finding it.

## What you get

Default names (you can rename them in Home Assistant):

| Entity | What it shows or does |
|---|---|
| Print Status | Printer state, for example `READY`, `BUILDING_FROM_SD` (printing), `PAUSED`, `BUILDING_COMPLETED` |
| Status | Raw status line from the printer |
| Job Percentage | Print progress in % |
| File | File being printed |
| Print Layer / Layers | Current layer and total layers |
| Job Remaining / Job End | Estimated time remaining and finish time |
| Move Mode | Motion state reported by the printer |
| Extruder and Bed Current / Target | Nozzle and bed temperature and their targets |
| Camera | The printer camera, when it has one |
| Light | The printer light, on and off |
| Abort, Continue, Pause, Print File (buttons) | Control the current print, or print the file chosen in File list |
| File list (select) | Files stored on the printer |

Sensor entity IDs start with the printer's serial number, for example
`sensor.snxxxxxxxxxx_print_status`.

Actions (services) are also available: `flashforge.pause`, `flashforge.continue_print`,
`flashforge.abort`, `flashforge.print_file` and `flashforge.get_file_names`.

## Good to know

- **Time remaining and finish time are estimates.** The printer doesn't report the time
  left, so they are worked out from how fast the progress goes up. They stay empty until
  the print is about 5 % in, can be well off early in a print, and get close towards the
  end. For a "nearly done" notification, trigger on progress (for example 80 %) and read
  the finish time then.
- **Starting a print needs the printer READY.** After a print finishes, clear the bed and
  confirm on the printer's screen first.
- **The printer is polled every 30 seconds** over your local network. If it is switched
  off, its entities show as unavailable until it is back.

### Example: notify when a print finishes

```yaml
automation:
  - alias: "3D print finished"
    triggers:
      - trigger: state
        entity_id: sensor.snxxxxxxxxxx_print_status
        from: BUILDING_FROM_SD
        to: BUILDING_COMPLETED
    actions:
      - action: notify.notify
        data:
          message: "{{ states('sensor.snxxxxxxxxxx_file') }} has finished."
```

Replace `snxxxxxxxxxx` with your printer's entity IDs (see
**Settings → Devices & services → FlashForge → entities**).

## Reporting a problem

1. Go to **Settings → Devices & services → FlashForge**, open the three-dot menu and choose
   **Download diagnostics**. The file has the printer's serial number and IP address
   removed. Home Assistant also adds a section listing your Home Assistant version and
   other custom integrations; look through it before attaching.
2. [Open an issue][issues] with your printer model, firmware version and the file.

## Credits and licence

Based on [hass_flashforge][upstream] by Josef Fällman, and the [ffpp][ffpp] library.
The time remaining and finish time sensors come from
[pull request #118](https://github.com/joseffallman/hass_flashforge/pull/118) by da4id.
MIT licence, see [LICENSE](LICENSE).

[upstream]: https://github.com/joseffallman/hass_flashforge
[ffpp]: https://pypi.org/project/ffpp/
[issues]: https://github.com/bradyjh17/hass_flashforge/issues
[commits-shield]: https://img.shields.io/github/commit-activity/y/bradyjh17/hass_flashforge.svg?style=for-the-badge
[commits]: https://github.com/bradyjh17/hass_flashforge/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/bradyjh17/hass_flashforge.svg?style=for-the-badge
