
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
from typing import Optional

import click

from proton.vpn.cli.core.run_async import run_async
from proton.vpn.cli.core.controller import Controller, ConnectionStateEnum
from proton.vpn.cli.core.wait_for_current_tasks import wait_for_current_tasks


@click.command()
@click.pass_context
@click.argument("name", required=False)
@run_async
async def connect(ctx, name: Optional[str]):
    """Connect to a vpn server by name"""

    controller = await Controller.create(params=ctx.obj)

    await wait_for_current_tasks()

    await controller.connect(name)

    # It's necessary to wait for one second to allow the background tasks
    # to start.
    #
    # This will be immediately cancelled after the sleep but they ensure
    # a completed connection.
    await asyncio.sleep(1)


@click.command()
@click.pass_context
@run_async
async def disconnect(ctx):
    """Disconnect from a vpn server by name"""

    controller = await Controller.create(params=ctx.obj)

    connector = await controller.get_vpn_connector()
    if connector.current_connection:
        await controller.wait_for_event([ConnectionStateEnum.CONNECTED])

        await controller.disconnect()

    await wait_for_current_tasks()


@click.group()  # nosemgrep: python.lang.best-practice.pass-body.pass-body-fn
def server():
    """The group that all server commands belong to"""


server.add_command(connect)
server.add_command(disconnect)
