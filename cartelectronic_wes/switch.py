"""Platform for switch integration."""
from __future__ import annotations

import logging

from homeassistant import config_entries, core
from homeassistant.core import callback

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription, SwitchDeviceClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_ID_PREFIX

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup switch from a config entry created in the integrations UI."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([RelaySwitch(coordinator, i) for i in range(1, 3)])
    async_add_entities([VirtualSwitch(coordinator, i) for i in range(1, 25)])

class RelaySwitch(SwitchEntity, CoordinatorEntity):
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self,coordinator, id):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = coordinator.api
        self.serial_number = self.api.serial
        self.__id = id
        self._attr_name = f"relay{self.__id}"
        self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_relay{self.__id}"
        self._is_on = False

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
            hw_version=device.hw_version
        )

    @property
    def is_on(self):
        try:
            return self._is_on
        except KeyError:
            _LOGGER.error(f"Unable to find status for relay{id}")
        return self._is_on

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        _LOGGER.debug(f"Turn off wes relay {self.__id}")
        if await self.api.switch_relay(self.__id, on=False):
            self._is_on = False
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        _LOGGER.debug(f"Turn on wes relay {self.__id}")
        if await self.api.switch_relay(self.__id, on=True):
            self._is_on = True
            self.async_write_ha_state()

    async def async_toggle(self, **kwargs):
        _LOGGER.debug(f"Toggle wes relay {self.__id}")
        return await self.api.toggle_relay(self.__id)
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            relay_status = self.coordinator.data["relays"][f"relay{self.__id}"]["enabled"]
            _LOGGER.debug(f"Found status {relay_status} for relay {self.__id}")
            if relay_status == "1":
                self._is_on = True
            else:
                self._is_on = False
            self.async_write_ha_state()
        except KeyError:
            _LOGGER.error(f"Unable to find status for relay{self.__id}")
            _LOGGER.warning(f"Coordinator data: {self.coordinator.data}")
        except:
            raise


class VirtualSwitch(SwitchEntity, CoordinatorEntity):
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self,coordinator, id):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = coordinator.api
        self.serial_number = self.api.serial
        self.__id = id
        self._attr_name = f"virtual switch{self.__id}"
        self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_virtual_switch{self.__id}"
        self._is_on = False

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
            hw_version=device.hw_version
        )

    @property
    def is_on(self):
        try:
            return self._is_on
        except KeyError:
            _LOGGER.error(f"Unable to find status for virtual_switch{id}")
        return self._is_on

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        _LOGGER.debug(f"Turn off wes virtual_switch {self.__id}")
        if await self.api.switch_vs(self.__id, on=False):
            self._is_on = False
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        _LOGGER.debug(f"Turn on wes virtual_switch {self.__id}")
        if await self.api.switch_vs(self.__id, on=True):
            self._is_on = True
            self.async_write_ha_state()

    async def async_toggle(self, **kwargs):
        _LOGGER.debug(f"Toggle wes virtual_switch {self.__id}")
        return await self.api.toggle_vs(self.__id)
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            switch_status = self.coordinator.data["virtual_switch"][f"switch{self.__id}"]
            _LOGGER.debug(f"Found status {switch_status} for virtual_switch {self.__id}")
            if switch_status == "1":
                self._is_on = True
            else:
                self._is_on = False
            self.async_write_ha_state()
        except KeyError:
            _LOGGER.error(f"Unable to find status for virtual_switch{self.__id}")
        except:
            raise