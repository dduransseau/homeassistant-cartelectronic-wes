
import re


DOMAIN = "cartelectronic_wes"

SENSOR_CLAMP_POWER_PATTERN = re.compile("(?:(?:(?P<va>\d+) VA)|(?:(?P<w>\d+) W cos phi (?P<cos_phi>\d.\d+)))")
SENSOR_ID_PREFIX = "wes_"

FILENAME_SENSOR_CGX = "homeassistant.cgx"