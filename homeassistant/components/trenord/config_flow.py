"""Config flow for Trenord integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .trenord_apis import TrenordApi

_LOGGER = logging.getLogger(__name__)

# TOD adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required("train_id", description="Id del treno"): str}
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = TrenordApi()

    train = await hass.async_add_executor_job(api.get_train, data["train_id"])

    if train is None:
        raise TrainNotFound

    # Return info that you want to store in the config entry.
    return {
        "title": train.name,
        "id": train.train_id,
        "departure_time": train.departure_time,
        "arrival_time": train.arrival_time,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trenord."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
            # await self.async_set_unique_id(info["id"])
            # self._abort_if_unique_id_configured()

            config_entry_data = {
                "train_id": info["id"],
                "train_name": info["title"],
                "departure_time": info["departure_time"],
                "arrival_time": info["arrival_time"],
            }

        except TrainNotFound:
            errors["base"] = "train_not_found"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=config_entry_data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class TrainNotFound(HomeAssistantError):
    """Provided train id is wrong."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
