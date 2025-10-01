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
from types import TracebackType
from typing import Callable, List, Optional, Type, Union

from click.core import Context as ClickContext
import sentry_sdk

from proton.session.exceptions import ProtonAPIAuthenticationNeeded
from proton.vpn.cli.core.exception_handler import ExceptionHandler
from proton.vpn.cli.core.exceptions import \
    AuthenticationRequiredError, \
    CountryCodeError, \
    CountryNameError, \
    RequiresHigherTierError
from proton.vpn.cli.core.semver import from_pep440
from proton.vpn.connection import states
from proton.vpn.connection.enum import ConnectionStateEnum
from proton.vpn.core.api import ProtonVPNAPI
from proton.vpn.core.connection import VPNStateSubscriber, VPNConnection, VPNConnector
from proton.vpn.core.session_holder import ClientTypeMetadata
from proton.vpn.core.settings import Settings
from proton.vpn.session import ServerList
from proton.vpn.session.servers.country_codes import country_codes, get_country_code_for_name
from proton.vpn.session.servers.types import LogicalServer

from proton.vpn import logging  # pylint: disable=C0413 # noqa: E402

LOGGING_FILENAME = "vpn-cli"
DEFAULT_CLI_NAME = "protonvpn"


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
    def __init__(
        self,
        params: Params,
        click_ctx: ClickContext,
        api: ProtonVPNAPI = None
    ):
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

        ExceptionHandler.enable(exception_reporter=self)
        self._api = api or ProtonVPNAPI(client_type_metadata)
        self._click_context = click_ctx

    @staticmethod
    async def create(params: Params, click_ctx: ClickContext):
        """Preferred method to get an instance of Controller."""
        controller = Controller(params, click_ctx)
        await controller.get_settings()  # load settings
        return controller

    def set_uncaught_exceptions_to_absorb(self, exceptions: List[BaseException]):
        """
        Silences list of provided exceptions if raised and uncaught
        """
        ExceptionHandler.set_uncaught_exceptions_to_absorb(exceptions)

    # ExceptionReporter protocol
    def report_error(
        self,
        error: Union[
            BaseException,
            tuple[
                Optional[Type[BaseException]],
                Optional[BaseException],
                Optional[TracebackType]
            ]
        ]
    ):
        """Sends the error to Sentry."""
        self._api.usage_reporting.report_error(error)
        sentry_sdk.get_client().flush()  # pylint: disable=no-member

    @property
    def program_name(self) -> Optional[str]:
        """Returns the name of the CLI"""
        return self._click_context.find_root().info_name

    @property
    def is_logged_in(self) -> bool:
        """Returns whether the user is logged in or not"""
        return self._api.is_user_logged_in()

    @property
    def user_tier(self) -> int:
        """Returns the Proton VPN tier"""
        return self._api.user_tier

    async def get_settings(self) -> Settings:
        """Returns general settings."""
        return await self._api.load_settings()

    async def get_current_connection(self) -> Optional[VPNConnection]:
        """Returns the current VPN connection or None if there isn't one."""
        return (await self.get_vpn_connector()).current_connection

    async def is_connection_active(self) -> bool:
        """
        Returns whether the current connection is active or not.

        A connection is considered active in the connecting, connected
        and disconnecting states.
        """
        return (await self.get_vpn_connector()).is_connection_active

    async def find_logical_server(
        self,
        server_name: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None
    ) -> Optional[LogicalServer]:
        """
        Finds a server in the serverlist meeting the user's criteria
        :param server_name: The name of the server to connect to.
        :param country: The country whose fastest server we want to connect to.
        :param city: The city whose fastest server we want to connect to.
        :return: The fastest logical server meeting the provided constraints.
        """
        if not self._api.is_user_logged_in():
            raise AuthenticationRequiredError

        free_user = self.user_tier == 0
        if free_user and (server_name or country or city):
            raise RequiresHigherTierError

        logical_server = None

        server_list = await self.get_updated_server_list()
        # server name takes precedence
        if server_name:
            logical_server = server_list.get_by_name(server_name)
        # or check if we're looking in a city
        elif city:
            logical_server = server_list.get_fastest_in_city(city)
        # or see if we're looking in a country
        elif country:
            logical_server = self._get_country_server(country, server_list)
        # otherwise just look for the fastest available server
        else:
            logical_server = server_list.get_fastest()

        return logical_server

    async def connect(
        self,
        server: LogicalServer
    ) -> Optional[states.State]:
        """
        Establishes a VPN connection.
        :param server: The specified server to connect to.
        :return: Connection state on successful connection, None otherwise
        """
        if not self._api.is_user_logged_in():
            raise AuthenticationRequiredError

        # make sure our certificate hasn't expired, or isn't about to.
        # this needs to happen before we establish connection state
        # otherwise if we are in a connected/error state then we will block
        # after starting/restarting local agent listener synchronously
        await self._api.refresher.update_certificate_if_necessary()

        event_hit_count = 1  # only wait for the first connected event received during connection
        connector = await self.get_vpn_connector()
        if connector.is_connection_active:  # pylint: disable=C0301 # noqa: E501 # nosemgrep: python.lang.maintainability.is-function-without-parentheses.is-function-without-parentheses
            # an asynchronous connect event from local agent
            # makes it difficult to time a state machine driven disconnect and connect
            # ... So we need to separate disconnection from connection explicitly
            # to ensure we correctly time switching between servers
            await self.disconnect()

        async with _wait_for_event(connector,
                                   expected_hit_count=event_hit_count,
                                   event_types=[ConnectionStateEnum.CONNECTED],
                                   ignore_types=[ConnectionStateEnum.CONNECTING]):
            await self._connect(server)

        connection_state = None
        if isinstance(connector.current_state, states.Connected):
            connection_state = connector.current_state

        return connection_state

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

    async def get_updated_server_list(self) -> ServerList:
        """Returns an always-up-to-date server list."""
        cached_server_list = self._api.server_list
        if cached_server_list.expired or cached_server_list.loads_expired:
            print("Server list is outdated, updating... This may take a moment.")

        return await self._api.refresher.get_up_to_date_server_list()

    async def get_vpn_connector(self) -> VPNConnector:
        """Return the object that handles vpn connection and disconnection"""
        vpn_connector = await self._api.get_vpn_connector()
        return vpn_connector

    def _validate_country_code(self, country: str) -> Optional[str]:
        if country in country_codes:
            # user provided a valid code
            return country

        return None

    def _get_country_server(self, country: str, server_list: ServerList) -> Optional[LogicalServer]:
        server = None

        if len(country) == 2:
            # assume the user specified a country code
            country_code = self._validate_country_code(country)
            if not country_code:
                raise CountryCodeError
        else:
            # assume user specified a country name
            country_code = get_country_code_for_name(country)
            if not country_code:
                raise CountryNameError

        if country_code:
            server = server_list.get_fastest_in_country(country_code)

        return server

    async def _connect(self, server: LogicalServer):
        vpn_server = (await self.get_vpn_connector()).get_vpn_server(
            server, await self._api.refresher.get_up_to_date_client_config()
        )

        settings = await self._api.load_settings()

        await (await self.get_vpn_connector()).connect(
            vpn_server,
            protocol=settings.protocol
        )

    async def _disconnect(self):
        await (await self.get_vpn_connector()).disconnect()
