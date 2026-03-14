"""Constants for the Rejseplanen integration."""

DOMAIN = "rejseplanen"

# Rejseplanen HAFAS REST API base URL (personal Labs API)
BASE_URL = "https://xmlopen.rejseplanen.dk/bin/rest.exe"

# Config keys
CONF_API_KEY = "api_key"
CONF_STATIONS = "stations"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_SCAN_INTERVAL = 10  # minutes — balances freshness vs. 50k/month API limit
MAX_DEPARTURES = 10
MAX_STATIONS = 6
