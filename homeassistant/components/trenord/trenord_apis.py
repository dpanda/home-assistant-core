"""Module to call Trenord APIs."""
import requests


class TrenordTrain:
    """DTO class for a Trenord train."""

    def __init__(self, train_id: str, name: str, status: str, delay: int) -> None:
        """Construct new instance."""

        self.train_id = train_id
        self.name = name
        self.status = status
        self.delay = delay


class TrenordApi:
    """class making calls to Trenord APIs."""

    # def __init__(self) -> None:
    #    self.base_url =

    def get_train(self, train_id: str) -> TrenordTrain:
        """Fetch a train details from Trenord APIs."""

        today = "2023-01-04"

        response = requests.get(
            f"https://admin.trenord.it/store-management-api/mia/train/{train_id}?date={today}",
            timeout=10,
        )

        response.raise_for_status()

        entry = response.json()[0]["journey_list"][0]
        train = entry["train"]

        train_dto = TrenordTrain(
            train_id, f"{train.line} {train.train_name}", train.status, train.delay
        )
        return train_dto
