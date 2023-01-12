"""Platform for sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .trenord_apis import TrainStatus, TrenordApi

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    # add_entities([TrainSensor()], True)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.info("Adding Sensor %s %s", entry.title, entry.data)
    async_add_entities(
        [TrainSensor(entry.data["train_id"], entry.data["train_name"])], True
    )


class TrainSensor(SensorEntity):
    """Representation of a Sensor."""

    # _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = SensorDeviceClass.ENUM
    # _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, train_id: str, name: str) -> None:
        """Construct the instance."""
        self._attr_name = name
        self._attr_train_id = train_id
        self._attr_native_value = TrainStatus.NONE.name

    async def async_update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.info("Refreshing train %s", self._attr_name)
        api = TrenordApi()
        train = await self.hass.async_add_executor_job(
            api.get_train, self._attr_train_id
        )
        if train is not None:
            self._attr_native_value = train.status.name
