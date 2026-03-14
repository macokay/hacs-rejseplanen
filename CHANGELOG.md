# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.3.0] - 2026-03-14

### Added
- Live direction suggestions in config flow — after selecting transport type, available directions are fetched from the actual departure board and presented as a dropdown
- "Alle retninger" option always available as first choice in direction step
- Config flow is now split into clear steps: Station search → Select station → Transport type → Direction → Add more

### Changed
- `station_filters` step replaced by separate `select_type` and `select_direction` steps for better UX
- Direction filter is now a dropdown (from live data) instead of a free-text field

## [1.2.0] - 2026-03-14

### Added
- Direction filter per sensor — add the same station twice with different directions for two sensors
- Transport type filter per sensor (IC, Re, S-tog, Lokalbane, Metro, Bus, Togbus, Færge)
- Coordinator fetches a larger batch per station and applies filters locally — no extra API calls

### Fixed
- `location.name` parsing now correctly uses `stopLocationOrCoordLocation` root key (API 2.0)
- `departureBoard` parsing reads `Departure` at root level (API 2.0)
- Corrected `BASE_URL` from API 1.0 to API 2.0 (`www.rejseplanen.dk/api`)

## [1.0.0] - 2026-03-14

### Added
- Initial release
- Config flow with station search (no manual stop ID required)
- One sensor per station with next departure as state
- Full departure board (up to 10 departures) in sensor attributes
- Realtime departure times with fallback to scheduled times
- Options flow to add/remove stations and change update interval
- Danish and English translations
- Configurable update interval (5–60 min, default 10 min)
- Rate limit guidance for 50,000 requests/month personal API
