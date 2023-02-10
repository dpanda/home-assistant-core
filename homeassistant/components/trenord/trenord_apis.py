"""Module to call Trenord APIs."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from itertools import takewhile
import logging

import pytz
import requests

_LOGGER = logging.getLogger(__name__)


class TrainStatus(Enum):
    """Enum status."""

    NONE = "NONE"
    TRAVELLING = "TRAVELING"
    CANCELLED = "CANCELLED"


class TrainStationType(Enum):
    """Enum station type."""

    ORIGIN = "ORIGIN"
    STOP = "STOP"
    DESTINATION = "DESTINATION"


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
        current_station: TrenordTrainCurrentStation | None,
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
        self.current_station = current_station


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


class TrenordTrainCurrentStation:
    """DTO class for a Train Station."""

    def __init__(
        self,
        station_id: str,
        name: str,
        station_type: TrainStationType,
        arrival_time: datetime | None,
        departure_time: datetime | None,
    ) -> None:
        """Construct new instance."""
        self.station_id = station_id
        self.name = name
        self.station_type = station_type
        self.arrival_time = arrival_time
        self.departure_time = departure_time


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

        current_station = self._get_current_station(entry["pass_list"])

        train_dto = TrenordTrain(
            train_id,
            f"{line} {name} - {departure_time.strftime('%H:%M')} da {departure_station} per {direction}",
            self._get_status(
                train["status"] if "status" in train else None,
                json["cancelled"],
                departure_station_id,
                arrival_station_id,
                suppression,
                current_station,
            ),
            0 if train["delay"] is None else train["delay"],
            departure_time,
            departure_station_id,
            departure_station,
            arrival_time,
            suppression,
            current_station,
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
        train_status: str | None,
        cancelled: bool,
        departure_station_id: str,
        arrival_station_id: str,
        suppression: TrenordTrainSuppression | None,
        current_station: TrenordTrainCurrentStation | None,
    ) -> TrainStatus:
        """Compute the train status from various attributes."""
        if (
            current_station is not None
            and current_station.station_type == TrainStationType.DESTINATION
        ):
            return TrainStatus.NONE
        if (
            suppression is not None
            and suppression.from_station_id == departure_station_id
            and suppression.to_station_id == arrival_station_id
        ):
            return TrainStatus.CANCELLED
        if cancelled is True:
            return TrainStatus.CANCELLED
        if train_status == "V":
            return TrainStatus.TRAVELLING
        return TrainStatus.NONE

    def _get_current_station(
        self, train_pass_list: list
    ) -> TrenordTrainCurrentStation | None:
        """Parse the last station passed by the train."""

        passed_stations = list(
            takewhile(
                lambda x: not x["cancelled"]
                and "actual_data" in x
                and "actual_station_mir" in x["actual_data"]
                and "actual_station_name" in x["actual_data"],
                train_pass_list,
            )
        )

        if len(passed_stations) == 0:
            return None

        last_passed_station = passed_stations[-1]

        _LOGGER.info(last_passed_station)

        return TrenordTrainCurrentStation(
            last_passed_station["actual_data"]["actual_station_mir"],
            last_passed_station["actual_data"]["actual_station_name"],
            TrainStationType.DESTINATION
            if last_passed_station["type"] == "D"
            else TrainStationType.ORIGIN
            if last_passed_station["type"] == "O"
            else TrainStationType.STOP,
            None,
            None,
        )
