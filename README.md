# Rejseplanen — Home Assistant Integration

HACS integration that provides real-time and scheduled departure boards from [Rejseplanen](https://www.rejseplanen.dk) as Home Assistant sensors.

---

## Features

- One sensor per configured station
- Sensor state = realtime time of next departure (`HH:MM`)
- Full departure board (up to 10 departures) in sensor attributes, including:
  - Line name and direction
  - Scheduled and realtime time
  - Platform
  - Cancellation status
- Built-in station search — no need to look up stop IDs manually
- Configurable update interval (5–60 min, default 10 min)
- Manage stations via the options flow after initial setup

---

## Requirements

A personal Rejseplanen Labs API key (free). Apply at [labs.rejseplanen.dk](https://labs.rejseplanen.dk).

> **Rate limit:** The personal API allows 50,000 requests/month. At the default 10-minute interval, each station costs ~4,320 requests/month. Adjust the interval if you add many stations.

| Interval | Max safe stations |
|----------|------------------|
| 5 min    | ~5               |
| 10 min   | ~11              |
| 15 min   | ~17              |
| 30 min   | ~34              |

---

## Installation

### Via HACS

1. Open HACS in Home Assistant
2. Click the three-dot menu → **Custom repositories**
3. Add `https://github.com/macokay/hacs-rejseplanen` with category **Integration**
4. Search for **Rejseplanen** in HACS and install it
5. Restart Home Assistant

### Manual

Copy `custom_components/rejseplanen/` into your HA `config/custom_components/` directory and restart.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Rejseplanen**
3. Enter your API key and preferred update interval
4. Search for and select your first departure station
5. Optionally add more stations, then finish

To add or remove stations later: open the integration and click **Configure**.

---

## Sensor Attributes

| Attribute | Description |
|-----------|-------------|
| `station` | Station display name |
| `station_id` | Rejseplanen stop ID |
| `next_departure` | Dict with details of the next departure |
| `departures` | List of up to 10 upcoming departures |

Each departure in the list contains:

```yaml
line: "Re 91"
direction: "Aarhus H"
stop: "København H"
type: "IC"
platform: "5"
scheduled_time: "14:30"
scheduled_date: "14.03.2026"
realtime_time: "14:32"
realtime_date: "14.03.2026"
cancelled: false
```

---

## Example: Lovelace Card

```yaml
type: entities
title: Afgange fra København H
entities:
  - entity: sensor.rejseplanen_kobenhavn_h
    name: Næste afgang
```

For a full departure board, pair the sensor attributes with a custom card like [flex-table-card](https://github.com/custom-cards/flex-table-card):

```yaml
type: custom:flex-table-card
title: Afgange
entities:
  include: sensor.rejseplanen_kobenhavn_h
columns:
  - data: departures
    name: Linje
    attr_as_list: line
  - data: departures
    name: Retning
    attr_as_list: direction
  - data: departures
    name: Tid
    attr_as_list: realtime_time
  - data: departures
    name: Spor
    attr_as_list: platform
```

---

## Troubleshooting

**Sensor shows unavailable**
- Check that your API key is valid
- Verify the station was found correctly (try re-adding it via Configure)
- Check Home Assistant logs for errors from the `rejseplanen` domain

**No departures / empty list**
- Some stations may have no departures at certain hours
- The API may return an empty board for future/overnight times

---

## License

© 2026 Mac O Kay
Free to use and modify for personal, non-commercial use.
Credit appreciated if you share or build upon this work.
Commercial use is not permitted.

## Notes

- Changed API endpoint: the integration now uses the newer Rejseplanen API at
  `https://www.rejseplanen.dk/api` (see `custom_components/rejseplanen/const.py`).
  If you previously relied on the older XML endpoint, please update any
  external tooling accordingly.
