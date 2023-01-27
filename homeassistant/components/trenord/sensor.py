"""Platform for sensor integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from aiohttp.client_exceptions import ClientError
import async_timeout
from dateutil import tz
from dateutil.parser import parse

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

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
    """Set up the data update coordinator and sensors for the train."""
    train_name = entry.data["train_name"]
    coordinator = TrainUpdateCoordinator(
        hass,
        entry.data["train_id"],
        train_name,
        entry.data["departure_time"],
        entry.data["arrival_time"],
    )
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            TrainSensorStatus(coordinator, train_name),
            TrainSensorDelay(coordinator, train_name),
            TrainSensorSuppression(coordinator, train_name),
        ]
    )


class TrainUpdateCoordinator(DataUpdateCoordinator):
    """Coordinate a single train info updates for multiple sensors."""

    def __init__(
        self,
        hass,
        train_id: str,
        name: str,
        departure_time: datetime | str,
        arrival_time: datetime | str,
    ):
        """Initialize the train update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Trenord update coordinator",
            update_interval=timedelta(seconds=60),
        )
        self.train_id = train_id
        self.name = name
        self.departure_time = (
            departure_time
            if isinstance(departure_time, datetime)
            else parse(departure_time)
        )
        self.arrival_time = (
            arrival_time if isinstance(arrival_time, datetime) else parse(arrival_time)
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(30):
                api = TrenordApi()

                if self._is_polling_allowed():
                    _LOGGER.info("Refreshing train %s", self.name)
                    api = TrenordApi()
                    train = await self.hass.async_add_executor_job(
                        api.get_train, self.train_id
                    )
                    if train is not None:
                        self.departure_time = train.departure_time
                        self.arrival_time = train.arrival_time
                        return train
                else:
                    _LOGGER.info("Train polling conditions not met")
                return self.data
        except ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _is_polling_allowed(self) -> bool:
        """Return if polling is allowed.

        Try not to make useless call if it's too early or too late, in relation to the train's schedule.
        """
        now = datetime.now(tz.gettz("Europe/Rome"))

        if now.day != self.departure_time.day:
            # date has changed - refresh
            _LOGGER.info("Detected date change, refreshing train")
            return True

        if self.data is not None:
            # always allow first polling
            _LOGGER.info("First polling (no previous data), refreshing train")
            return True

        _LOGGER.debug(
            "Now: %s, arrival time %s %s, arrival time in the past: %s, departure time %s, dep. time in the future %s, delta from departure %s, delta < 30min %s",
            now,
            self.arrival_time,
            type(self.arrival_time),
            now > self.arrival_time,
            self.departure_time,
            self.departure_time > now,
            self.departure_time - now,
            (self.departure_time - now) < timedelta(minutes=30),
        )

        if self.departure_time > now:
            # Departure time in the future: allow polling only if within half an hour of it
            delta = self.departure_time - now
            return delta < timedelta(minutes=30)
        if now > self.arrival_time:
            # Arrival time in the past: allow polling only if wiithin 10 minutes of it
            delta = now - self.arrival_time
            return delta < timedelta(minutes=10)
        # We are during the train schedule: always poll
        return True


class TrainSensorStatus(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor for Train Status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [state.name for state in TrainStatus]
    _attr_icon = "mdi:train-variant"

    def __init__(self, coordinator, train_name):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_name = f"{train_name} - Stato"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        train = self.coordinator.data
        self._attr_native_value = train.status.name
        self.async_write_ha_state()


class TrainSensorDelay(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor for Train delay in minutes."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:train-variant"

    def __init__(self, coordinator, train_name):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_name = f"{train_name} - Ritardo"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        train = self.coordinator.data

        now = datetime.now(tz.gettz("Europe/Rome"))

        if train.arrival_time > now:
            self._attr_native_value = train.delay
        else:
            # reset the value after train has arrived
            self._attr_native_value = 0
        self.async_write_ha_state()


class TrainSensorSuppression(CoordinatorEntity, BinarySensorEntity):
    """Sensor mapping partial or full suppression of the train."""

    _attr_icon = "mdi:train-variant"

    def __init__(self, coordinator, train_name):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_name = f"{train_name} - Cancellazioni"
        self._attr_from_station_name = None
        self._attr_to_station_name = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        train = self.coordinator.data

        now = datetime.now(tz.gettz("Europe/Rome"))

        if train.arrival_time > now:
            if train.suppression is not None:
                self._attr_is_on = True
                self._attr_from_station_name = train.suppression.from_station_name
                self._attr_to_station_name = train.suppression.to_station_name
            else:
                self._attr_is_on = False
                self._attr_to_station_name = None
                self._attr_from_station_name = None
        else:
            # reset the value after train has arrived
            self._attr_is_on = False
            self._attr_to_station_name = None
            self._attr_from_station_name = None
        self.async_write_ha_state()
