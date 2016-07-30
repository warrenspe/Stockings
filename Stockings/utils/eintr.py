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

import errno, socket

# Because in python3, (pre 3.5) interrupted system calls raise Exceptions, we want to be able to run
# system calls without worrying about them being interrupted.

# We also deal with operations on closed sockets, or sockets which have no data waiting for them.
MASKED_ERRORS = (
    "EAGAIN",
    "WSAEWOULDBLOCK",
    "EWOULDBLOCK",
    "ENOTSOCK",
    "WSAESHUTDOWN"
)

def recv(sock, bytes):
    """
    Receives data from the given socket, masking socket-closed, and EAGAIN errors (returning None in this case).
    Also repeatedly runs the command if it is interrupted by another system call.

    Returns: The bytes read if successful, else None if we were unable to read from the socket.
    """

    while True:
        try:
            return sock.recv(bytes)

        except (IOError, socket.error) as e:
            if e.errno == errno.EINTR:
                continue
            if errno.errorcode[e.errno] in MASKED_ERRORS:
                return
            raise
