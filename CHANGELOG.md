# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.2.0] - 2026-03-14

### Added
- Direction filter per sensor — add the same station twice with different directions to get two sensors (e.g. "Stenlille St. → København H" and "Stenlille St. → Slagelse")
- Transport type filter per sensor — multiselect from IC, Re, S-tog, Lokalbane, Metro, Bus, Togbus, Færge
- New config flow step `station_filters` appears after selecting a station
- Sensor name automatically includes direction and type filters (e.g. "Rejseplanen Stenlille St. → København H")
- Coordinator now fetches a larger batch per station and applies filters locally — no extra API calls for filtered sensors of the same station

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
