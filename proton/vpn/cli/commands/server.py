
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
from typing import Optional

import click

from proton.vpn.cli.core.run_async import run_async
from proton.vpn.cli.core.controller import Controller
from proton.vpn.cli.core.wait_for_current_tasks import wait_for_current_tasks


@click.command()
@click.pass_context
@click.argument("name", required=False)
@run_async
async def connect(ctx, name: Optional[str]):
    """Connect to a vpn server by name"""
    controller = await Controller.create(params=ctx.obj)
    await controller.connect(name)


@click.command()
@click.pass_context
@run_async
async def disconnect(ctx):
    """Disconnect from a vpn server by name"""
    controller = await Controller.create(params=ctx.obj)
    await controller.disconnect()

    # wait for post-disconnect notification killswitch implementation setting
    await wait_for_current_tasks()
