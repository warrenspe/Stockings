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
import socket, errno, threading, select

# Project imports
from ._Stocking import _Stocking

class PollStocking(_Stocking):
    """
    Class which handles a connection with a remote endpoint.  Runs as a thread and can be interfaced with
    by using its `read` and `write` functions to read and write complete messages to a remote endpoint.

    Uses the select.poll construct to manage its pipes/sockets I/O.
    """

    # Internal attributes
    _poller = None            # select.poll object used to manage I/O activity.

    def _pollSendMessage(self):
        """ Attempts to send a message to our remote endpoint from self._oBuffer. """

        self._sendMessage()

        # If we were unable to write the entirety of the message to the socket, poll on it being writeable
        if len(self._oBuffer):
            self._poller.register(self.sock, select.POLLIN | select.POLLOUT)

        # Otherwise self._oBuffer is empty; disable polling on our socket being writeable
        else:
            self._poller.register(self.sock, select.POLLIN)


    # Threading.Thread override
    def run(self):

        try:
            # Start a new thread to handle connecting to the remote
            handshakeThread = threading.Thread(target=self._handshake)
            handshakeThread.start()

            with self._ioLock:
                if self.active:
                    self._poller = select.poll()
                    # Detect if we've been closed by our parent
                    self._poller.register(self._parentIn, select.POLLHUP)
                    # Detect messages to recv from the remote endpoint
                    self._poller.register(self.sock, select.POLLIN)
                    # Detect messages to send from our parent
                    self._poller.register(self._usIn, select.POLLIN)

            while self.active:
                # Wait until we have input or output to act upon
                for fd, eventMask in self._poller.poll():
                    # eventMask will be POLLIN if we have data to process
                    if eventMask & select.POLLIN:
                        # If our socket was returned, there is data for us to recv
                        if self.sock.fileno() == fd:
                            # If our connected socket to the remote is in the list of readable sockets we expect that
                            # we can read from it; if for some reason we cannot we can assume we have become disconnected.
                            if not self._recvMessage():
                                return

                        # Otherwise check if our parent sent us data
                        elif not self._usIn.closed and self._usIn.fileno() == fd:
                            self._pollSendMessage()

                    # eventmask will be POLLOUT if we can continue sending data from self._oBuffer
                    elif eventMask & select.POLLOUT:
                        self._pollSendMessage()

                    # Otherwise check if our parent has asked us to close
                    elif eventMask & select.POLLHUP:
                        return

        except socket.error as e:
            # Ignore bad file descriptor & connection reset/abort errors
            if e.errno not in (errno.EBADF, errno.ECONNRESET, errno.ECONNABORTED):
                raise

        except select.error as e:
            # Ignore bad file descriptor errors
            if not hasattr(e, 'args') or not hasattr(e.args, '__iter__') or not len(e.args) or e.args[0] != errno.EBADF:
                raise

        finally:
            self._signalClose()
