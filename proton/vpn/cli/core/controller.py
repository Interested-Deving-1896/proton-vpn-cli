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
from proton.session.exceptions import ProtonAPIAuthenticationNeeded
from proton.vpn.core.api import ProtonVPNAPI
from proton.vpn.connection.enum import ConnectionStateEnum
from proton.vpn.core.connection import VPNStateSubscriber, VPNConnector
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
        connector: VPNConnector,
        expected_hit_count=1,
        event_types: Optional[List[ConnectionStateEnum]] = None,
        ignore_types: Optional[List[ConnectionStateEnum]] = None,
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
        event_hit_count: int

        def status_update(self, status):
            if status.type in event_types:
                self.event_hit_count -= 1
                if self.event_hit_count == 0:
                    event.set()
            elif status.type not in ignore_types:
                if status.type is ConnectionStateEnum.ERROR:
                    print("Error occurred")
                else:
                    expected_types = ", ".join(ConnectionStateEnum(type).name for type in event_types)  # noqa: E501 # pylint: disable=C0301
                    received_type = ConnectionStateEnum(status.type).name
                    print(f"Unexpected event: Expected {expected_types}, Received {received_type}")

                event.set()

    subscriber = Subscriber()
    subscriber.event_hit_count = expected_hit_count
    connector.register(subscriber)

    yield

    try:
        await asyncio.wait_for(event.wait(), timeout)
    except asyncio.exceptions.TimeoutError:
        expected_types = ", ".join(ConnectionStateEnum(type).name for type in event_types)  # noqa: E501 # pylint: disable=C0301
        print(f"Timed out after {timeout}s waiting for event(s): {expected_types}")

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
            type="cli",
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
        if not self._api.is_user_logged_in():
            print("Authentication required. Please login before connecting.")
            return

        free_user = self._api.user_tier == 0
        if free_user and server_name:
            print("The free user plan does not include connecting to specified servers. "
                  "Please use protonvpn-cli connect.")
            return

        event_hit_count = 1  # only wait for the first connected event received during connection
        connector = await self.get_vpn_connector()
        if connector.is_connection_active:  # pylint: disable=C0301 # noqa: E501 # nosemgrep: python.lang.maintainability.is-function-without-parentheses.is-function-without-parentheses
            # we receive an additional connect event on debian based distros during
            # disconnection, so we need to separate disconnection from connection
            # to ensure we correctly time switching between servers
            await self.disconnect()

        async with _wait_for_event(connector,
                                   expected_hit_count=event_hit_count,
                                   event_types=[ConnectionStateEnum.CONNECTED],
                                   ignore_types=[ConnectionStateEnum.CONNECTING]):
            await self._connect(server_name)

    async def disconnect(self):
        """
        Terminates a VPN connection.
        """
        connector = await self.get_vpn_connector()
        if connector.is_connection_active:  # pylint: disable=C0301 # noqa: E501 # nosemgrep: python.lang.maintainability.is-function-without-parentheses.is-function-without-parentheses
            async with _wait_for_event(connector,
                                       event_types=[ConnectionStateEnum.DISCONNECTED],
                                       ignore_types=[ConnectionStateEnum.DISCONNECTING,
                                                     ConnectionStateEnum.CONNECTED]):
                await self._disconnect()

    async def login(self, username: str,
                    get_password: Callable[[], str],
                    get_2fa: Callable[[], str]):
        """
        Logs the user in.
        :param username:
        :param get_password: A callable that will return the account password
        :param get_2fa: A callable that will return the two factor
            authentication token if invoked.
        """
        if self._api.is_user_logged_in():
            print("Already logged in, please logout first before changing accounts.")
            return

        password = get_password()
        login_result = await self._api.login(username, password)
        if not login_result.authenticated:
            print("Authentication failed. Please check your username and password and try again.")
            return

        try:
            while login_result.twofa_required:
                login_result = await self._api.submit_2fa_code(get_2fa())
        except ProtonAPIAuthenticationNeeded:
            print("2FA Authentication failed. Please try again.")

    async def logout(self):
        """
        Logs the user out.
        """
        if (await self.get_vpn_connector()).is_connection_active:  # pylint: disable=C0301 # noqa: E501 # nosemgrep: python.lang.maintainability.is-function-without-parentheses.is-function-without-parentheses
            await self.disconnect()

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
