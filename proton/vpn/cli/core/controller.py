"""
Semver utils.

Copyright (c) 2023 Proton AG

This file is part of Proton VPN.

Proton VPN is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Proton VPN is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ProtonVPN.  If not, see <https://www.gnu.org/licenses/>.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib import metadata
from typing import Optional, Callable, List

from proton.vpn.core.session_holder import ClientTypeMetadata
from proton.vpn.core.api import ProtonVPNAPI
from proton.vpn.connection.enum import ConnectionStateEnum
from proton.vpn.core.connection import VPNStateSubscriber
from proton.vpn.cli.core.semver import from_pep440
from proton.vpn.session import ServerList

from proton.vpn import logging  # pylint: disable=C0413 # noqa: E402

LOGGING_FILENAME = "vpn-cli"


@dataclass
class Params:
    """The parameters for constructing the Controller"""
    verbose: str = False


@asynccontextmanager
async def _wait_for_event(
        connector,
        event_types: Optional[List[ConnectionStateEnum]] = None,
        timeout=10):

    if not event_types:
        yield
        return

    event = asyncio.Event()

    class Subscriber(VPNStateSubscriber):  # pylint: disable=R0903
        """
        This class listens for a given set of status changes and then
        triggers the given event.
        """
        def status_update(self, status):
            if status.type in event_types:
                event.set()

    subscriber = Subscriber()
    connector.register(subscriber)

    yield

    async with asyncio.timeout(timeout):
        await event.wait()
    connector.unregister(subscriber)


class Controller:
    """
    The application business logic is in this class. The is the core of the
    application.
    """
    def __init__(self, params: Params, api: ProtonVPNAPI = None):
        logging.config(filename=LOGGING_FILENAME)
        if params.verbose:
            logging.logging.getLogger().setLevel(logging.logging.INFO)
        else:
            logging.logging.getLogger().setLevel(logging.logging.ERROR)

        version = from_pep440(metadata.version("proton-vpn-cli"))
        client_type_metadata = ClientTypeMetadata(
            type="gui",  # pylint: disable=W0511 # TODO LT: Switch to 'cli'
            version=version
        )

        self._api = api or ProtonVPNAPI(client_type_metadata)

    @staticmethod
    async def create(params: Params):
        """Preferred method to get an instance of Controller."""
        controller = Controller(params)
        await controller.get_vpn_connector()
        return controller

    async def connect(self, server_name: Optional[str] = None):
        """
        Establishes a VPN connection.
        :param server_name: The name of the server to connect to.
        """
        async with _wait_for_event(await self.get_vpn_connector(),
                                   [ConnectionStateEnum.CONNECTED]):
            await self._connect(server_name)

    async def disconnect(self):
        """
        Terminates a VPN connection.
        """
        if (await self.get_vpn_connector()).is_connected:  # pylint: disable=C0301 # noqa: E501 # nosemgrep: python.lang.maintainability.is-function-without-parentheses.is-function-without-parentheses
            async with _wait_for_event(await self.get_vpn_connector(),
                                       [ConnectionStateEnum.DISCONNECTED]):
                await self._disconnect()

    async def login(self, username: str, password: str,
                    get_2fa: Callable[[], str]):
        """
        Logs the user in.
        :param username:
        :param password:
        :param get_2fa: A callable that will return the two factor
            authentication token if invoked.
        """
        login_result = await self._api.login(username, password)
        if login_result.twofa_required:
            await self._api.submit_2fa_code(get_2fa())

    async def logout(self):
        """
        Logs the user out.
        """
        await self._api.logout()

    def account_info(self):
        """
        Provides information about the proton vpn accout currently logged in.
        """
        return dict(
            name=self._api.account_name
        )

    @property
    def server_list(self) -> ServerList:
        """Returns the current server list."""
        return self._api.refresher.server_list

    async def wait_for_event(
            self,
            event_type: Optional[List[ConnectionStateEnum]] = None,
            timeout=10):
        """Asyncronously waits for a connection state change to occur"""
        async with _wait_for_event(await self.get_vpn_connector(),
                                   event_type,
                                   timeout):
            pass

    async def get_vpn_connector(self):
        """Return the object that handles vpn connection and disconnection"""
        return await self._api.get_vpn_connector()

    async def _connect(self, server_name: Optional[str] = None):
        if server_name:
            server = self._api.server_list.get_by_name(server_name)
        else:
            server = self._api.server_list.get_fastest()

        vpn_server = (await self.get_vpn_connector()).get_vpn_server(
            server, self._api.refresher.client_config
        )

        settings = await self._api.load_settings()

        await (await self.get_vpn_connector()).connect(
            vpn_server,
            protocol=settings.protocol)

    async def _disconnect(self):
        await (await self.get_vpn_connector()).disconnect()
