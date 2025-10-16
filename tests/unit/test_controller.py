"""
Copyright (c) 2025 Proton AG

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
from unittest.mock import AsyncMock, MagicMock, Mock, patch, PropertyMock
import pytest
import asyncio

from click.core import Context as ClickContext

from proton.vpn.cli.core.controller import Controller, Params
from proton.vpn.cli.core.exceptions import \
    AuthenticationRequiredError, \
    RequiresHigherTierError
from proton.vpn.connection import states
from proton.vpn.core.api import ProtonVPNAPI, VPNDataRefresher
from proton.vpn.core.connection import VPNConnector
from proton.vpn.session.servers.types import LogicalServer


@pytest.mark.asyncio
async def test_connect_fails_if_not_logged_in():
    api_mock = Mock()
    params_mock = Mock()
    click_ctx_mock = Mock()
    server = Mock()

    api_mock.is_user_logged_in.return_value = False
    controller = Controller(params_mock, click_ctx_mock, api_mock)
    with pytest.raises(AuthenticationRequiredError):
        await controller.connect(server)


@pytest.mark.asyncio
async def test_find_logical_server_fails_if_not_logged_in():
    api_mock = Mock()
    params_mock = Mock()
    click_ctx_mock = Mock()

    api_mock.is_user_logged_in.return_value = False
    controller = Controller(params_mock, click_ctx_mock, api_mock)
    with pytest.raises(AuthenticationRequiredError):
        await controller.find_logical_server()


@pytest.mark.asyncio
async def test_find_logical_server_fails_when_specifying_server_name_as_free_user():
    api_mock = Mock()
    params_mock = Mock()
    click_ctx_mock = Mock()

    # mock free user tier
    user_tier_property = PropertyMock(return_value=0)
    type(api_mock).user_tier = user_tier_property

    controller = Controller(params_mock, click_ctx_mock, api_mock)
    with pytest.raises(RequiresHigherTierError):
        await controller.find_logical_server(server_name="name")


@pytest.mark.asyncio
async def test_connect_disconnects_first_when_already_connected():
    api_mock = AsyncMock(spec=ProtonVPNAPI)
    api_mock.refresher = AsyncMock(spec=VPNDataRefresher)
    params_mock = Mock(spec=Params)
    click_ctx_mock = Mock(spec=ClickContext)
    vpn_connector_mock = Mock(spec=VPNConnector)
    server = Mock(spec=LogicalServer)

    # mock active connection
    vpn_connector_mock.is_connection_active = True
    api_mock.get_vpn_connector.return_value = vpn_connector_mock

    # grab subscribers to connection events and
    # send them artificial events to avoid disconnect and connect blocking
    def notify_event(subscriber):
        if notify_event.disconnect_subscribe:
            # first we let the controller know we "disconnected"
            subscriber.status_update(states.Disconnected)
            notify_event.disconnect_subscribe = False
        else:
            # then we let it know the "connection" has completed
            subscriber.status_update(states.Connected)
    notify_event.disconnect_subscribe = True
    vpn_connector_mock.register.side_effect = notify_event

    controller = Controller(params_mock, click_ctx_mock, api_mock)
    await controller.connect(server)
    vpn_connector_mock.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_connect_disconnects_when_connection_fails():
    api_mock = AsyncMock(spec=ProtonVPNAPI)
    api_mock.refresher = AsyncMock(spec=VPNDataRefresher)
    params_mock = Mock(spec=Params)
    click_ctx_mock = Mock(spec=ClickContext)
    vpn_connector_mock = Mock(spec=VPNConnector)
    server = Mock(spec=LogicalServer)

    # mock inactive connection
    vpn_connector_mock.is_connection_active = False
    api_mock.get_vpn_connector.return_value = vpn_connector_mock

    # grab subscribers to connection events and
    # send them an Error event to simulate connection failure
    # followed by a Disconnected event to indicate end of disconnection
    def notify_event(subscriber):
        if not notify_event.error_sent:
            # first we let the controller know the connection failed
            subscriber.status_update(states.Error)
            notify_event.error_sent = True
        else:
            # then we let it know the "disconnection" has completed
            subscriber.status_update(states.Disconnected)
    notify_event.error_sent = False
    vpn_connector_mock.register.side_effect = notify_event

    controller = Controller(params_mock, click_ctx_mock, api_mock)
    await controller.connect(server)
    vpn_connector_mock.disconnect.assert_called_once()


@pytest.mark.parametrize("server_name, country, city", [
    (None, None, None),  # fastest
    (None, "United Kingdom", "London"),  # fastest in city
    (None, "Brazil", None),  # fastest in country
    ("UK#42", "United Kingdom", "London")  # server with server name
])
@pytest.mark.asyncio
async def test_find_logical_server_respects_highest_priority_constraint(
    server_name, country, city
):
    api_mock = AsyncMock()
    params_mock = Mock()
    click_ctx_mock = Mock()
    vpn_connector_mock = Mock()

    api_mock.get_vpn_connector.return_value = vpn_connector_mock

    # Avoid awaitable errors
    # awaitable
    vpn_connector_mock.connect = AsyncMock()
    vpn_connector_mock.disconnect = AsyncMock()
    # not awaitable
    api_mock.refresher.get_up_to_date_server_list.return_value = MagicMock()
    api_mock.is_user_logged_in = MagicMock()

    controller = Controller(params_mock, click_ctx_mock, api_mock)
    await controller.find_logical_server(server_name, country, city)
    server_list = await controller.get_updated_server_list()
    if server_name:
        server_list.get_by_name.assert_called_once()
    elif city:
        server_list.get_fastest_in_city.assert_called_once()
    elif country:
        server_list.get_fastest_in_country.assert_called_once()
    else:
        server_list.get_fastest.assert_called_once()
