import logging

from homeassistant import config_entries, core
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DELAY
)

from .const import DOMAIN, FILENAME_SENSOR_CGX
from .wes import WesApi
from .coordinator import WesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    session = async_get_clientsession(hass)
    api = WesApi(entry.data[CONF_HOST], user=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD], session=session, sensor_filename=FILENAME_SENSOR_CGX)
    _LOGGER.info("Prepare coordinator for WES")
    coordinator = WesCoordinator(hass, api, delay=entry.data.get(CONF_DELAY, 10))
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    _LOGGER.info("Set device property to retrive the wes serveur informations")
    await api.set_device_property()
    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    # Create switch object only if the specified user is admin
    if entry.data.get("is_admin"):
        _LOGGER.info("Configure web user is admin, enable relay control")
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "switch")
        )
    
    return True
