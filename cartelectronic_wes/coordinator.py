
from datetime import timedelta

import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

import async_timeout


_LOGGER = logging.getLogger(__name__)

class WesCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, api, delay=10):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="WES data",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=delay),
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from API endpoint.
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator."""
        async with async_timeout.timeout(10):
            response_data = await self.api.fetch_sensor_data()
            return response_data