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
import socket, errno, threading, select, os

# Project imports
from ._Stocking import _Stocking

# Globals

# select.select timeout.  We will wake up every `this` seconds in order to check if we have a new message to send
# to the remote
SEND_INTERVAL = float(os.environ.get("STOCKING_SELECT_SEND_INTERVAL", .5))


class SelectStocking(_Stocking):
    """
    Class which handles a connection with a remote endpoint.  Runs as a thread and can be interfaced with
    by using its `read` and `write` functions to read and write complete messages to a remote endpoint.

    Uses the select.select construct to manage its sockets I/O.
    """


    # Threading.Thread override
    def run(self):

        try:
            # Start a new thread to handle connecting to the remote
            handshakeThread = threading.Thread(target=self._handshake)
            handshakeThread.start()

            while self.active:
                selectWrite = []
                # We always want to be interrupted when we can read from our socket
                selectRead = [self.sock]
                # If we have data that we need to send, interrupt when we can write to our socket
                if len(self._oBuffer) or self._checkReadablePipe(self._usIn):
                    selectWrite.append(self.sock)

                # Wait until we have input or output to act upon
                try:
                    readable, writable, _ = select.select(selectRead, selectWrite, [], SEND_INTERVAL)

                except ValueError:
                    # This is typically caused by our socket being closed when we go into the select.
                    # If this happens, break out and close our connection
                    break

                # If we have data to receive, receive it
                if readable:
                    # If our connected socket to the remote is in the list of readable sockets we expect that
                    # we can read from it; if for some reason we cannot we can assume we have become disconnected.
                    if not self._recvMessage():
                        return

                # If we have data to send, send it
                if writable or len(self._oBuffer) or self._checkReadablePipe(self._usIn):
                    self._sendMessage()

        except socket.error as e:
            # Ignore bad file descriptor errors
            if e.errno != errno.EBADF:
                raise

        except select.error as e:
            # Ignore bad file descriptor errors
            if not hasattr(e, 'args') or not hasattr(e.args, '__iter__') or not len(e.args) or e.args[0] != errno.EBADF:
                raise

        finally:
            self._signalClose()
