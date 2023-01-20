"""Module to call Trenord APIs."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
import logging

import pytz
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
        arrival_time: datetime,
        suppression: TrenordTrainSuppression | None,
    ) -> None:
        """Construct new instance."""

        self.train_id = train_id
        self.name = name
        self.status = status
        self.delay = delay
        self.departure_time = departure_time
        self.departure_station_name = departure_station_name
        self.departure_station_id = departure_station_id
        self.arrival_time = arrival_time
        self.suppression = suppression


class TrenordTrainSuppression:
    """DTO class for a Train Suppression."""

    def __init__(
        self,
        from_station_id: str,
        from_station_name: str,
        to_station_id: str,
        to_station_name: str,
    ) -> None:
        """Construct new instance."""
        self.from_station_id = from_station_id
        self.from_station_name = from_station_name
        self.to_station_id = to_station_id
        self.to_station_name = to_station_name


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
        departure_time = self._parse_datetime(json["date"], json["dep_time"])
        arrival_time = self._parse_datetime(json["date"], json["arr_time"])
        departure_station = json["dep_station"]["station_ori_name"].lower().capitalize()
        departure_station_id = json["dep_station"]["station_id"]
        arrival_station_id = json["arr_station"]["station_id"]

        suppression = None

        if "suppression_start" in train:
            suppression = TrenordTrainSuppression(
                train["suppression_start_mir"],
                train["suppression_start"],
                train["suppression_end_mir"],
                train["suppression_end"],
            )

        train_dto = TrenordTrain(
            train_id,
            f"{line} {name} - {departure_time.strftime('%H:%M')} da {departure_station} per {direction}",
            self._get_status(
                train["status"],
                json["cancelled"],
                departure_station_id,
                arrival_station_id,
                suppression,
            ),
            train["delay"],
            departure_time,
            departure_station_id,
            departure_station,
            arrival_time,
            suppression,
        )

        _LOGGER.info("Train: %s", train_dto.__dict__)
        return train_dto

    def _parse_datetime(self, datestr: str, time: str) -> datetime:
        """Compute a datetime object using the date an time as exposed in the api."""
        timezone = pytz.timezone("Europe/Rome")

        return datetime.strptime(f"{datestr}{time}", "%Y%m%d%H:%M:%S").replace(
            tzinfo=timezone
        )

    def _get_status(
        self,
        train_status: str,
        cancelled: bool,
        departure_station_id: str,
        arrival_station_id: str,
        suppression: TrenordTrainSuppression | None,
    ) -> TrainStatus:
        """Compute the train status from various attributes."""
        if train_status == "V":
            return TrainStatus.TRAVELLING
        if cancelled is True:
            return TrainStatus.CANCELLED
        if suppression is not None:
            if (
                suppression.from_station_id == departure_station_id
                and suppression.to_station_id == arrival_station_id
            ):
                return TrainStatus.CANCELLED
        return TrainStatus.NONE
