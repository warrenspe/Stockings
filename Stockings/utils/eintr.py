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

import errno

# Because in python3, (pre 3.5) interrupted system calls raise Exceptions, we want to be able to run
# system calls without worrying about them being interrupted.
def run(func, *args, **kwargs):
    while True:
        try:
            return func(*args, **kwargs)

        except IOError as e:
            if e.errno != errno.EINTR:
                raise
