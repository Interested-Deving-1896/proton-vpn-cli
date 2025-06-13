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
from contextlib import contextmanager
import sys
import os

PROFILE = os.environ.get("PROTON_VPN_CLI_PROFILE", 0) == 1


@contextmanager
def profile():
    """
    Use this in a with statement to profile the time it takes to run a block
    of code.
    The environment variable PROTON_VPN_CLI_PROFILE switches it on or off.
    """
    if PROFILE:
        import cProfile  # pylint: disable=C0415

        profiler = cProfile.Profile()
        profiler.enable()
        yield
        profiler.disable()

        import pstats  # pylint: disable=C0415
        stats = pstats.Stats(profiler, stream=sys.stdout).sort_stats('cumtime')
        stats.print_stats(20)
    else:
        yield
