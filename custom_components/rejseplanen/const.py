"""Constants for the Rejseplanen integration."""

DOMAIN = "rejseplanen"

# Rejseplanen HAFAS REST API base URL (personal Labs API)
BASE_URL = "https://www.rejseplanen.dk/api"

# Config keys
CONF_API_KEY = "api_key"
CONF_STATIONS = "stations"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DIRECTION_FILTER = "direction_filter"
CONF_TYPE_FILTER = "type_filter"

# Defaults
DEFAULT_SCAN_INTERVAL = 10  # minutes — balances freshness vs. 50k/month API limit
MAX_DEPARTURES = 10
MAX_STATIONS = 6

# Transport type options shown in config flow
TRANSPORT_TYPES = ["IC", "Re", "S-tog", "Lokalbane", "Metro", "Bus", "Togbus", "Færge"]
