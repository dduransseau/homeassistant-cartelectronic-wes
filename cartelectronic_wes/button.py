
import logging

from homeassistant import config_entries, core

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup switch from a config entry created in the integrations UI."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([ResetButton(coordinator.api),])

class ResetButton(ButtonEntity):
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_name = "WES reset"

    def __init__(self, api):
        super().__init__()
        self.api = api


    @property
    def device_info(self) -> DeviceInfo:
        device = self.api.device
        return DeviceInfo(
            identifiers={
                (DOMAIN, device.serial)
            },
            name=device.name,
            manufacturer=device.manufacturer_name,
            model=device.model,
            sw_version=device.sw_version,
            hw_version=device.hw_version,
            via_device=(DOMAIN, device.serial),
        )

    async def async_press(self) -> None:
        _LOGGER.debug(f"Reset WES server")
        return await self.api.reset_server()