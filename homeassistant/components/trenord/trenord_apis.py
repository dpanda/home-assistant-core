"""Module to call Trenord APIs."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
import logging

import requests

_LOGGER = logging.getLogger(__name__)


class TrainStatus(Enum):
    """Enum status."""

    NONE = "NONE"
    TRAVELLING = "TRAVELING"
    CANCELLED = "CANCELLED"


class TrenordTrain:
    """DTO class for a Trenord train."""

    def __init__(
        self,
        train_id: str,
        name: str,
        status: TrainStatus,
        delay: int,
        departure_time: datetime,
        departure_station_id: str,
        departure_station_name: str,
    ) -> None:
        """Construct new instance."""

        self.train_id = train_id
        self.name = name
        self.status = status
        self.delay = delay
        self.departure_time = departure_time
        self.departure_station_name = departure_station_name
        self.departure_station_id = departure_station_id


class TrenordApi:
    """class making calls to Trenord APIs."""

    # def __init__(self) -> None:
    #    self.base_url =

    def get_train(self, train_id: str) -> TrenordTrain | None:
        """Fetch a train details from Trenord APIs."""

        today = date.today().strftime("%Y-%m-%d")

        _LOGGER.info("Calling trenord apis for train %s in day %s", train_id, today)

        response = requests.get(
            f"https://admin.trenord.it/store-management-api/mia/train/{train_id}?date={today}",
            timeout=10,
        )

        response.raise_for_status()

        if len(response.json()) == 0:
            return None

        _LOGGER.debug(response.json()[0])

        # parse response
        json = response.json()[0]
        entry = json["journey_list"][0]
        train = entry["train"]
        line = train["line"]
        name = train["train_name"]
        direction = train["direction"].lower().capitalize()
        departure_time = self._get_next_departure_datetime(
            json["date"], json["dep_time"]
        )
        departure_station = json["dep_station"]["station_ori_name"].lower().capitalize()

        train_dto = TrenordTrain(
            train_id,
            f"{line} {name} - {departure_time.strftime('%H:%M')} da {departure_station} per {direction}",
            self._get_status(train["status"], json["cancelled"]),
            train["delay"],
            departure_time,
            json["dep_station"]["station_id"],
            departure_station,
        )

        _LOGGER.info("Train: %s", train_dto.__dict__)
        return train_dto

    def _get_next_departure_datetime(self, datestr: str, time: str) -> datetime:
        """Compute a datetime object for the next departure from date and time string."""
        return datetime.strptime(f"{datestr}{time}", "%Y%m%d%H:%M:%S")

    def _get_status(self, train_status: str, cancelled: bool) -> TrainStatus:
        """Compute the train status from various attributes."""
        if train_status == "V":
            return TrainStatus.TRAVELLING
        if cancelled is True:
            return TrainStatus.CANCELLED
        return TrainStatus.NONE
