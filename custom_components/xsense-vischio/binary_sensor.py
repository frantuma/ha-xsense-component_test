"""Support for xsense binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from xsense.device import Device
from xsense.entity import Entity
from xsense.station import Station

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import XSenseDataUpdateCoordinator
from .entity import XSenseEntity


@dataclass(kw_only=True, frozen=True)
class XSenseBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes XSense binary-sensor entity."""

    exists_fn: Callable[[Entity], bool] = lambda _: True
    value_fn: Callable[[Entity], bool]


SENSORS: tuple[XSenseBinarySensorEntityDescription, ...] = (
    XSenseBinarySensorEntityDescription(
        key="is_life_end",
        translation_key="is_life_end",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timelapse",
        exists_fn=lambda entity: "isLifeEnd" in entity.data,
        value_fn=lambda entity: entity.data["isLifeEnd"] == 1,
    ),
    XSenseBinarySensorEntityDescription(
        key="alarm_status",
        translation_key="alarm_status",
        # device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alarm-light-outline",
        exists_fn=lambda entity: "alarmStatus" in entity.data,
        value_fn=lambda entity: entity.data["alarmStatus"],
    ),
    XSenseBinarySensorEntityDescription(
        key="mute_status",
        translation_key="mute_status",
        # device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alarm-light-off",
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda entity: "muteStatus" in entity.data,
        value_fn=lambda entity: entity.data["muteStatus"],
    ),
    XSenseBinarySensorEntityDescription(
        key="activate",
        translation_key="activate",
        icon="mdi:bell-ring",
        exists_fn=lambda entity: "activate" in entity.data,
        value_fn=lambda entity: entity.data["activate"],
    ),
    XSenseBinarySensorEntityDescription(
        key="door",
        translation_key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        name="Door Sensor",
        value_fn=lambda device: device.data["isOpen"] == "1",
        exists_fn=lambda device: "isOpen" in device.data,
    ),
)

MQTTSensor = XSenseBinarySensorEntityDescription(
    key="connected",
    translation_key="connected",
    entity_category=EntityCategory.DIAGNOSTIC,
    icon="mdi:connection",
    name="Connected name",
    exists_fn=lambda entity: isinstance(entity, Station),
    value_fn=lambda entity: False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the xsense binary sensor entry."""
    LOGGER.debug("VISCHIO - async_setup_entry")
    devices: list[Device] = []
    coordinator: XSenseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    for station in coordinator.data["stations"].values():
        LOGGER.debug("VISCHIO - async_setup_entry stations")
        LOGGER.debug("VISCHIO - async_setup_entry stations 0 %s", station)
        LOGGER.debug("VISCHIO - async_setup_entry stations 1 %s", station.data)
        devices.extend(
            XSenseBinarySensorEntity(coordinator, station, description)
            for description in SENSORS
            if description.exists_fn(station)
        )
        devices.append(XSenseMQTTConnectedEntity(coordinator, station, MQTTSensor))

    for dev in coordinator.data["devices"].values():
        LOGGER.debug("VISCHIO - async_setup_entry devices")
        LOGGER.debug("VISCHIO - async_setup_entry devices 0 %s", dev)
        LOGGER.debug("VISCHIO - async_setup_entry devices 1 %s", dev.data)
        devices.extend(
            XSenseBinarySensorEntity(
                coordinator, dev, description, station_id=dev.station.entity_id
            )
            for description in SENSORS
            if description.exists_fn(dev)
        )

    async_add_entities(devices)


class XSenseBinarySensorEntity(XSenseEntity, BinarySensorEntity):
    """Binary sensors for xsense."""

    entity_description: XSenseBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: XSenseDataUpdateCoordinator,
        entity: Entity,
        entity_description: XSenseBinarySensorEntityDescription,
        station_id: str | None = None,
    ) -> None:
        """Set up the instance."""
        self._station_id = station_id
        self.entity_description = entity_description
        self._attr_available = True  # This overrides the default
        self._last_checked = None
        LOGGER.debug("VISCHIO - init 1 %s", entity.data)
        super().__init__(coordinator, entity, station_id)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        if self._station_id:
            device = self.coordinator.data["devices"][self._dev_id]
        else:
            device = self.coordinator.data["stations"][self._dev_id]

        LOGGER.debug("VISCHIO - is_on 1 %s", device.data)
        return self.entity_description.value_fn(device)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        attributes = super().extra_state_attributes or {}
        self._last_checked = self.coordinator.last_checked  # Update last checked time
        attributes["ultima_request_attr"] = self._last_checked  # Add last checked time to attributes
        return attributes


class XSenseMQTTConnectedEntity(XSenseBinarySensorEntity):
    """Binary sensors for MQTT connectivity."""

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""

        device = self.coordinator.data["stations"][self._dev_id]
        mqtt_server = self.coordinator.mqtt_server(device.house.mqtt_server)
        LOGGER.debug("VISCHIO - XSenseMQTTConnectedEntity is_on 1 %s", device)
        LOGGER.debug("VISCHIO - XSenseMQTTConnectedEntity is_on 2 %s", mqtt_server)
        return mqtt_server.connected
    
    def generate_entity_id(
        entity_id_format: str,
        name: str | None,
        current_ids: list[str] | None = None,
        hass: HomeAssistant | None = None,
    ) -> str:
        preferred_string = "connected_entity_id"
        test_string = preferred_string
        tries = 1
        while not hass.states.async_available(test_string):
            tries += 1
            test_string = f"{preferred_string}_{tries}"

        return test_string
