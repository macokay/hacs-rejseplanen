# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased] - 2026-03-14

### Fixed
- Changed `_search_stations` log level from DEBUG to WARNING so API responses appear in HA's standard log viewer
- `location.name` parsing tries `StopLocation` at root level (API 2.0) with fallback to `LocationList` wrapper
- `departureBoard` parsing reads `Departure` at root level (API 2.0) with fallback to `DepartureBoard` wrapper
- Corrected `BASE_URL` from API 1.0 (`xmlopen.rejseplanen.dk`) to API 2.0 (`www.rejseplanen.dk/api`)

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
