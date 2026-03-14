# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.1.0] - 2026-03-14

### Fixed
- `location.name` parsing now correctly uses `stopLocationOrCoordLocation` root key from API 2.0, extracting `StopLocation` from each list item
- `departureBoard` coordinator logs raw response keys (WARNING level) for debugging API 2.0 response structure
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
