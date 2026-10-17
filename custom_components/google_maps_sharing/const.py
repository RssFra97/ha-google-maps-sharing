"""Costanti per Google Maps (condivisione posizione)."""

from datetime import timedelta

DOMAIN = "google_maps_sharing"

CONF_COOKIES = "cookies"
CONF_MAX_GPS_ACCURACY = "max_gps_accuracy"
CONF_ROTATE_COOKIES = "rotate_cookies"

DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MAX_GPS_ACCURACY = 200
DEFAULT_ROTATE_COOKIES = True

# Ogni quanto chiedere a Google di rinnovare __Secure-1PSIDTS.
ROTATE_INTERVAL = timedelta(minutes=15)
# Salvataggio dei cookie su file al massimo con questa frequenza (oltre che dopo un rinnovo).
SAVE_INTERVAL = timedelta(minutes=15)

# File dei cookie gestito da questa integrazione.
COOKIE_FILE = ".google_maps_sharing.cookies.{slug}"
# File usato dall'integrazione core google_maps (legacy), importato alla prima configurazione.
LEGACY_COOKIE_FILE = ".google_maps_location_sharing.cookies.{slug}"

ATTR_ADDRESS = "address"
ATTR_FULL_NAME = "full_name"
ATTR_LAST_SEEN = "last_seen"
ATTR_NICKNAME = "nickname"
