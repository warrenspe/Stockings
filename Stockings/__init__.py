"""
    This file is part of Stockings.

    Stockings is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Stockings is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Stockings.  If not, see <http://www.gnu.org/licenses/>.

    Author: Warren Spencer
    Email:  warrenspencer27@gmail.com
"""

# Standard imports
import select

# Project imports
from ._pollStocking import PollStocking
from ._selectStocking import SelectStocking
from .exceptions.notReady import NotReady

# Depending on whether or not we have poll support, set the appropriate module as `Stocking`
Stocking = PollStocking if hasattr(select, 'poll') else SelectStocking
