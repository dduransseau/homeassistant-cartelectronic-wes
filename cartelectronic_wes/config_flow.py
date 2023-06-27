from __future__ import annotations

import logging
import pathlib

from typing import Any, Dict, Optional

from homeassistant import config_entries, core
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DELAY
)

import voluptuous as vol

from .const import DOMAIN, FILENAME_SENSOR_CGX

from .wes import WesApi, WesFtp

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA  = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME, default="admin"): cv.string,
        vol.Required(CONF_PASSWORD, default="wes"): cv.string,
        vol.Optional(CONF_DELAY, default=10): int
    }
)

FTP_AUTH_SCHEMA  = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default="adminftp"): cv.string,
        vol.Required(CONF_PASSWORD, default="wesftp"): cv.string
    }
)

class WesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            wes_api = WesApi(user_input[CONF_HOST], user=user_input[CONF_USERNAME], password=user_input[CONF_PASSWORD], sensor_filename=FILENAME_SENSOR_CGX)
            try:
                is_admin = await wes_api.is_admin
                if is_admin == True:
                    _LOGGER.info("WES logged as admin")
                elif is_admin == False:
                    _LOGGER.info("WES logged as user")
                self.data = user_input
                self.data["is_admin"] = is_admin
            except:
                raise
            return await self.async_step_ftp()

        return self.async_show_form(
            step_id="user", 
            data_schema=AUTH_SCHEMA,
            errors=errors
        )
    
    async def async_step_ftp(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            local_directory = pathlib.Path(__file__).parent.resolve()
            _LOGGER.info(f"Setup FTP on {self.data[CONF_HOST]}")
            sensor_file = local_directory.joinpath(FILENAME_SENSOR_CGX)
            wes_ftp = WesFtp(self.data[CONF_HOST], user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            wes_ftp.upload_file(sensor_file)

            return self.async_create_entry(title=f"WES {self.data[CONF_HOST]}", data=self.data)

        return self.async_show_form(
            step_id="ftp", data_schema=FTP_AUTH_SCHEMA, errors=errors
        )