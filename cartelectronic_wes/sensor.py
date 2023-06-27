"""Platform for sensor integration."""
from __future__ import annotations

import logging

from homeassistant import config_entries, core
from homeassistant.core import callback
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfEnergy, UnitOfPower, UnitOfApparentPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorEntity,
    SensorStateClass
)

from .const import DOMAIN, SENSOR_CLAMP_POWER_PATTERN, SENSOR_ID_PREFIX

_LOGGER = logging.getLogger(__name__)


def setup_clamps_sensors(coordinator):
    entities_sensors = list()
    data = coordinator.data.get("clamps")
    if data.get("V"):
        entities_sensors.append(ClampVoltageSensor(coordinator))
    for i in range(1, 5):
        clamp_data = data.get(f"clamp{i}")
        available = True if clamp_data["enabled"] == "1" else False
        # Check if the power metric is apparent power or not
        if match := SENSOR_CLAMP_POWER_PATTERN.match(clamp_data["power"]):
            if match.group("va"):
                entities_sensors.append(ClampPowerSensor(coordinator, id=i, available=available))
            else:
                entities_sensors.append(ClampPowerSensor(coordinator, id=i, apparent_power=False, available=available))
        entities_sensors.append(ClampCurrentSensor(coordinator, i, available=available))
        entities_sensors.append(ClampIndexSensor(coordinator, i, available=available))
        entities_sensors.append(ClampIndexSensor(coordinator, i, inject=True, available=available))
            
    return entities_sensors

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup sensors from a config entry created in the integrations UI."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    # coordinator = WesCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    # Create sensors for clamp objects
    entities_sensors = setup_clamps_sensors(coordinator)

    async_add_entities(entities_sensors)

class BaseClampSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = "WES from Cartelectronic"
    _attr_device_class = SensorDeviceClass.ENERGY

    def __init__(self, coordinator, available=True, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.serial_number = coordinator.api.serial
        self._attr_available = available
        self._state = None

    @property
    def device_info(self) -> DeviceInfo:
        device = self.coordinator.api.device
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

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state


class ClampCurrentSensor(BaseClampSensor):
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, coordinator, id=1, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, **kwargs)
        self.__id = id
        self._attr_name = f"Clamp{self.__id} current"
        self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_clamp{self.__id}_current"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        clamps_data = self.coordinator.data.get("clamps")
        clamp_data = clamps_data.get(f"clamp{self.__id}")
        if clamp_data:
            entity_value = float(clamp_data.get(f"I"))
            self._state = entity_value
            self.async_write_ha_state()

class ClampVoltageSensor(BaseClampSensor):
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE

    def __init__(self, coordinator, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, **kwargs)
        self._attr_name = f"Main voltage"
        self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_main_voltage"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        clamps_data = self.coordinator.data.get("clamps")
        if clamps_data:
            entity_value = int(clamps_data.get(f"V"))
            self._state = entity_value
            self.async_write_ha_state()

class ClampIndexSensor(BaseClampSensor):
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, id=1, inject=False, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, **kwargs)
        self.__id = id
        self._state = None
        self.inject = inject
        if self.inject:
            self._attr_name = f"Clamp{self.__id} inject index"
            self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_clamp{self.__id}_inject_index"
        else:
            self._attr_name = f"Clamp{self.__id} consumption index"
            self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_clamp{self.__id}_consumption_index"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        clamps_data = self.coordinator.data.get("clamps")
        clamp_data = clamps_data.get(f"clamp{self.__id}")
        if clamp_data:
            if self.inject:
                index_name = f"idxinject"
            else:
                index_name = f"index"
            entity_value = float(clamp_data.get(index_name))
            self._state = entity_value
            self.async_write_ha_state()

class ClampPowerSensor(BaseClampSensor):

    _attr_state_class = SensorStateClass.MEASUREMENT

    POWER_REGEXP = SENSOR_CLAMP_POWER_PATTERN

    def __init__(self, coordinator, id=1, apparent_power=True, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, **kwargs)
        self.__id = id
        self._state = None
        self.apparent_power = apparent_power
        if self.apparent_power:
            self._attr_native_unit_of_measurement = UnitOfApparentPower.VOLT_AMPERE
            self._attr_device_class = SensorDeviceClass.APPARENT_POWER
            self._attr_name = f"Clamp{self.__id} apparent power"
            self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_clamp{self.__id}_apparent_power"
        else:
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_name = f"Clamp{self.__id} power"
            self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_clamp{self.__id}_power"
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        clamps_data = self.coordinator.data.get("clamps")
        clamp_data = clamps_data.get(f"clamp{self.__id}")
        if clamp_data:
            if match := self.POWER_REGEXP.search(clamp_data["power"]):
                value = match.groupdict()
                if power_value := value.get("w"):
                    self._state = power_value
                    self.apparent_power = False
                else:
                    self._state = value.get("va")
            self.async_write_ha_state()
            