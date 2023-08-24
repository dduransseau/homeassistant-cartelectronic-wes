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

from .const import DOMAIN, SENSOR_CLAMP_POWER_PATTERN, SENSOR_ID_PREFIX, TIC_INDEX_LABELS, TIC_APPARENT_POWER_LABELS, TIC_INTENSITY_LABELS, TIC_VOLTAGE_LABELS

_LOGGER = logging.getLogger(__name__)


def setup_tic_sensors(coordinator):
    entities_sensors = list()
    data = coordinator.data.get("tics")
    for i in range(1, 3):
        tic_data = data.get(f"tic{i}")
        if tic_data["ADCO"] != "Pas Dispo":
            for label in TIC_INDEX_LABELS:
                try:
                    index_value = tic_data[label]
                    int_index_value = int(index_value)
                    if int_index_value > 0:
                        entities_sensors.append(TicIndexSensor(coordinator, i, label=label))
                except IndexError:
                    _LOGGER.warning(f"Unable to find index with label {label}")
                except ValueError:
                    _LOGGER.warning(f"Unable to parse index value for index {label}, value is {index_value}")
            for label in TIC_APPARENT_POWER_LABELS:
                entities_sensors.append(TicApparentPowerSensor(coordinator, i, label=label))
            for label in TIC_INTENSITY_LABELS:
                entities_sensors.append(TicIntensitySensor(coordinator, i, label=label))
            for label in TIC_VOLTAGE_LABELS:
                entities_sensors.append(TicVoltageSensor(coordinator, i, label=label))
    return entities_sensors
            

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

def setup_1wire_probe(coordinator):
    entities_sensors = list()
    for i in range(1, 31):
        entities_sensors.append(Probe1WireSensor(coordinator, id=i))
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
    entities_sensors += setup_1wire_probe(coordinator)
    entities_sensors += setup_tic_sensors(coordinator)

    async_add_entities(entities_sensors)

class BaseWesSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = "WES from Cartelectronic"

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
            hw_version=device.hw_version
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

class BaseClampSensor(BaseWesSensor):
    _attr_device_class = SensorDeviceClass.ENERGY

    def __init__(self, coordinator, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, **kwargs)

class ClampCurrentSensor(BaseClampSensor):
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, coordinator, id=1, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, **kwargs)
        self.__id = id
        self._attr_name = f"clamp{self.__id} current"
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
        self._attr_name = f"main voltage"
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
            self._attr_name = f"clamp{self.__id} inject index"
            self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_clamp{self.__id}_inject_index"
        else:
            self._attr_name = f"clamp{self.__id} consumption index"
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
            self._attr_name = f"clamp{self.__id} apparent power"
            self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_clamp{self.__id}_apparent_power"
        else:
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_name = f"clamp{self.__id} power"
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
            
class Probe1WireSensor(BaseWesSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, id=1, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, **kwargs)
        self.__id = id
        self._attr_name = f"probe{self.__id}"
        self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_{self._attr_name}".lower()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        clamps_data = self.coordinator.data.get("probes")
        clamp_data = clamps_data.get(f"probe{self.__id}")
        if clamp_data:
            self._state = clamp_data
            self.async_write_ha_state()

class BaseTicSensor(BaseWesSensor):
    _attr_device_class = SensorDeviceClass.ENERGY

    def __init__(self, coordinator, id, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, **kwargs)
        self.__id = id

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        clamps_data = self.coordinator.data.get("tics")
        clamp_data = clamps_data.get(f"tic{self.__id}")
        if clamp_data:
            entity_value = int(clamp_data.get(self.label))
            if entity_value != self._state:
                self._state = entity_value
                self.async_write_ha_state()

class TicIndexSensor(BaseTicSensor):
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, id, label=None, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, id, **kwargs)
        self.__id = id
        self._state = None
        self.label = label
        if self.label not in TIC_INDEX_LABELS:
            raise NotImplementedError(f"Label {self.label} is not supported yet, abort sensor creation")
        self._attr_name = f"tic{self.__id} {self.label} index"
        self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_tic{self.__id}_{self.label.lower()}_index"

class TicSubscriptionTextSensor(BaseTicSensor):

    def __init__(self, coordinator, id, label=None, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, id, **kwargs)
        self.__id = id
        self._state = None
        self.label = label
        self._attr_name = f"tic{self.__id} {self.label}"
        self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_tic{self.__id}_{self.label.lower()}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        clamps_data = self.coordinator.data.get("tics")
        clamp_data = clamps_data.get(f"tic{self.__id}")
        if clamp_data:
            entity_value = clamp_data.get(self.label) # Avoid to parse the value as integer
            if entity_value != self._state:
                self._state = entity_value
                self.async_write_ha_state()

class TicApparentPowerSensor(BaseTicSensor):
    _attr_native_unit_of_measurement = UnitOfApparentPower.VOLT_AMPERE
    _attr_device_class = SensorDeviceClass.APPARENT_POWER

    def __init__(self, coordinator, id, label=None, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, id, **kwargs)
        self.__id = id
        self._state = None
        self.label = label
        self._attr_name = f"tic{self.__id} {self.label}"
        self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_tic{self.__id}_{self.label.lower()}"

class TicIntensitySensor(BaseTicSensor):
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_device_class = SensorDeviceClass.ENERGY

    def __init__(self, coordinator, id, label=None, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, id, **kwargs)
        self.__id = id
        self._state = None
        self.label = label
        self._attr_name = f"tic{self.__id} {self.label}"
        self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_tic{self.__id}_{self.label.lower()}"

class TicVoltageSensor(BaseTicSensor):
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE

    def __init__(self, coordinator, id, label=None, **kwargs):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, id, **kwargs)
        self.__id = id
        self._state = None
        self.label = label
        self._attr_name = f"tic{self.__id} {self.label}"
        self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_tic{self.__id}_{self.label.lower()}"


# class TicProductionIndexSensor(BaseTicSensor):
#     _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
#     _attr_state_class = SensorStateClass.TOTAL_INCREASING

#     def __init__(self, coordinator, id=1, **kwargs):
#         """Pass coordinator to CoordinatorEntity."""
#         super().__init__(coordinator, **kwargs)
#         self.__id = id
#         self._state = None
#         self._attr_name = f"tic{self.__id} production index"
#         self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_clamp{self.__id}_production_index"

#     @callback
#     def _handle_coordinator_update(self) -> None:
#         """Handle updated data from the coordinator."""
#         clamps_data = self.coordinator.data.get("tics")
#         clamp_data = clamps_data.get(f"tic{self.__id}")
#         if clamp_data:
#             index_name = f"PRODUCTION"
#             entity_value = float(clamp_data.get(index_name))
#             self._state = entity_value
#             self.async_write_ha_state()

# class TicInjectionIndexSensor(BaseTicSensor):
#     _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
#     _attr_state_class = SensorStateClass.TOTAL_INCREASING

#     def __init__(self, coordinator, id=1, **kwargs):
#         """Pass coordinator to CoordinatorEntity."""
#         super().__init__(coordinator, **kwargs)
#         self.__id = id
#         self._state = None
#         self._attr_name = f"tic{self.__id} injection index"
#         self._attr_unique_id = f"{SENSOR_ID_PREFIX}{self.serial_number}_clamp{self.__id}_injection_index"

#     @callback
#     def _handle_coordinator_update(self) -> None:
#         """Handle updated data from the coordinator."""
#         clamps_data = self.coordinator.data.get("tics")
#         clamp_data = clamps_data.get(f"tic{self.__id}")
#         if clamp_data:
#             index_name = f"injection"
#             entity_value = float(clamp_data.get(index_name))
#             self._state = entity_value
#             self.async_write_ha_state()