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


async def wait_for_current_tasks(timeout=10):
    """
    Pauses the current task until all other tasks are processed. This is
    usefull for when we want to shutdown cleanly, or when waiting for some
    processing to complete.
    """
    async with asyncio.timeout(timeout):
        await asyncio.gather(*[t for t in asyncio.all_tasks()
                             if t is not asyncio.current_task()])
