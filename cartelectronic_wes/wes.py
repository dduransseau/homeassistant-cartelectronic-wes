import logging
import asyncio

from ftplib import FTP
from urllib.parse import urljoin

import xmltodict
import aiohttp

logger = logging.getLogger(__name__)

USER_ADMIN_CHECK_URL = "/INFOCFG.HTM"
USER_READONLY_CHECK_URL = "/index.htm"
AJAX_URL = "/AJAX.CGX"
DATA_URL = "/DATA.cgx"

class WesDevice:

    def __init__(self, serial, hw_version, sw_version) -> None:
        self.manufacturer_name = "cartelectronic"
        self.model = "WES (Web energie supervisor)"
        self.name = "wes"
        self.serial = serial
        self.hw_version = hw_version
        self.sw_version = sw_version
        self.img_url = "https://www.cartelectronic.fr/356-square_small_default/serveur-wes.jpg"


class WesApi:

    def __init__(self, host, user, password, session=None, sensor_filename="/DATA.cgx") -> None:
        self.host = host
        if host.startswith("http://"):
            self.url = host
        else:
            self.url = f"http://{host}"
        self.user = user
        self.__password = password
        self.__auth = aiohttp.BasicAuth(self.user, password=self.__password)
        if session:
            self.client = session
            self.shared_session = True
        else:
            self.client = aiohttp.ClientSession()
            self.shared_session = False
        self._admin = None
        self.device = None
        self.SENSOR_FILENAME = sensor_filename

    def __del__(self):
        if not self.shared_session:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(self.client.close())
                else:
                    loop.run_until_complete(self.client.close())
            except:
                pass

    async def fetch_url(self, url):
        absolute_url = urljoin(self.url, url)
        async with self.client.get(absolute_url, auth=self.__auth) as response:
            return response

    async def fetch_xml_data(self, url):
        absolute_url = urljoin(self.url, url)
        async with self.client.get(absolute_url, auth=self.__auth) as response:
            if response.status == 200:
                response_text = await response.text()
                data = xmltodict.parse(response_text)
                try:
                    logger.debug(f"Retrieved data {data}")
                    return data.get("data", data)
                except KeyError:
                    logger.warning("Unable to retrieve data from response")
            else:
                logger.warning(f"Unable to retrieve {response}")

    async def fetch_data(self):
        return await self.fetch_xml_data(DATA_URL)

    async def fetch_sensor_data(self):
        return await self.fetch_xml_data(f"/{self.SENSOR_FILENAME}")
    
    async def set_device_property(self):
        data = await self.fetch_sensor_data()
        try:
            device = WesDevice
            serial = data["info"]["serial"]
            hw_version = data["info"]["hardware"]
            sw_version = data["info"]["firmware"]
            device = WesDevice(serial=serial, hw_version=hw_version, sw_version=sw_version)
            self.device = device
        except KeyError:
            logger.warning("Unable to set the device property, key not present on file")

    async def relay_is_on(self, id):
        data = await self.fetch_sensor_data()
        try:
            relay_status = data["data"]["relays"][f"relay{id}"]["enabled"]
            logger.debug(f"Found status {relay_status} for relay {id}")
            if relay_status == "1":
                return True
            else:
                return False
        except KeyError:
            logger.error(f"Unable to find status for relay{id}")
        except:
            raise

    async def switch_relay(self, id, on=True):
        value = "ON" if on else "OFF"
        absolute_url = urljoin(self.url, AJAX_URL)
        logger.debug(f"Switch relay {id} {value}")
        params = {f'rl{id}': value}
        logger.debug(f"Send query to {absolute_url} with params {params}")
        async with self.client.get(absolute_url, params=params, auth=self.__auth) as response:
            if response.status == 200:
                return True
            else:
                logger.warning(f"Unable to switch relay, status {response.status}")
                return False
            
    async def toggle_relay(self, id):
        logger.debug(f"Toggle relay {id}")
        absolute_url = urljoin(self.url, AJAX_URL)
        params = {f'frl': id}
        logger.debug(f"Send query to {absolute_url} with params {params}")
        async with self.client.get(absolute_url, params=params, auth=self.__auth) as response:
            if response.status == 200:
                return True
            else:
                logger.warning(f"Unable to toggle relay, status {response.status}")
                return False

    @property
    def serial(self):
        try:
            return self.device.serial
        except:
            raise

    @property
    async def is_admin(self):
        # Check if the auth user is admin
        if self._admin == None:
            response = await self.fetch_url(USER_ADMIN_CHECK_URL)
            if response.status == 403:
                # User is not admin
                logger.info("User is not admin")
                response = await self.fetch_url(USER_READONLY_CHECK_URL)
                if response.ok:
                    self._admin = False
            elif response.ok:
                self._admin = True
        return self._admin
    
    @property
    async def is_logged(self):
        if await self._admin != None:
            return True
        else:
            return False
        

class WesFtp:

    def __init__(self, host, user, password) -> None:
        self.host = host
        self.user = user
        self.__password = password
        self.client = FTP(self.host)
        self.logged = False

    def upload_file(self, filepath, filename=None):
        if not self.logged:
            self.client.login(self.user, self.__password)
        if not filename:
            filename = filepath.name
        with open(filepath, "rb") as fp:
            self.client.storbinary(f"STOR {filename}", fp)

    def __del__(self):
        self.client.close()