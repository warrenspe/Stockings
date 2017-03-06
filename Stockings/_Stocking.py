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
import socket, errno, threading, multiprocessing

# Project imports
from .utils import MessageHeaders, eintr
from .exceptions import notReady

class _Stocking(threading.Thread):
    """ Base class for a Stocking. """

    # Publically visible attributes
    sock = None               # The connection to the remote
    addr = None               # The address of the remote
    handshakeComplete = False # A boolean indicating whether or not this connection is ready for interaction with the remote
    active = True             # Flag which signals whether this thread is supposed to be running or not

    # Internal attributes
    _iBuffer = b""            # Partial message received from the remote that require further recv's to complete
    _iBufferLen = 0           # Length of the message we're currently receiving into self._iBuffer
    _iType = None             # Type of message that we're receiving (bytes vs string/unicode)
    _messageHeaders = None    # MessageHeaders object used when constructing _iBufferLen
    _oBuffer = ""             # Partial message sent to the remote that require further send's to complete
    _parentOut = None         # Pipe which our parent process will read from
    _parentIn = None          # Pipe which our parent process will write to
    _usIn = None              # Pipe which we will read from
    _usOut = None             # Pipe which we will write to
    _ioLock = None            # Mutex to prevent us from interfacing with a pipe at the same time

    def __init__(self, conn):
        """
        Creates a new connection, wrapping the given connected socket.

        Inputs: conn - A connected socket.
        """

        threading.Thread.__init__(self)
        self.sock = conn
        self.addr = self.sock.getpeername()
        self._messageHeaders = MessageHeaders.MessageHeaders()

        # We cannot run in blocking mode, because at any given time we may be in the process of sending a message to
        # the remote and receiving a message from the remote.  We cannot get stuck in one phase or the other.
        self.sock.setblocking(0)

        # Create two unidirectional pipes for communicating with our parent process
        self._parentIn, self._usOut = multiprocessing.Pipe(False)
        self._usIn, self._parentOut = multiprocessing.Pipe(False)

        self._ioLock = threading.RLock()

        # Start processing requests
        self.daemon = True
        self.start()


    # Data Model functions
    def __repr__(self):
        return "<Stocking (%s) [%s]>" % (self.__class__.__name__, str(self.addr))


    def __enter__(self):
        return self


    def __exit__(self, typ, value, tb):
        self.close()


    # API functions
    def read(self):
        """
        Returns a message from _parentIn if there is one and we've completed our handshake, else None.

        Raises a NotReady Exception if the handshake has not yet completed.
        """

        if not self.handshakeComplete:
            raise notReady.NotReady()

        toReturn = self._read()
        if toReturn is not None:
            return self.postRead(toReturn)


    def write(self, *args, **kwargs):
        """
        Queues a message to send to the remote if we've completed our handshake.

        Raises a NotReady Exception if the handshake has not yet completed.
        """

        if not self.handshakeComplete:
            raise notReady.NotReady()

        self._write(self.preWrite(*args, **kwargs))


    def fileno(self):
        """ Returns a file descriptor which the parent process can poll on, to wake when there is input to be read. """

        return self._runLocked(self._parentIn.fileno)


    def close(self):
        """ Kills our connection and immediately halts the thread. """

        def __close(self):
            if self.active:
                self._signalClose()
                if not self._parentIn.closed:
                    self._parentIn.close()

        self._runLocked(__close, self)


    def writeDataQueued(self):
        """ Returns a boolean indicating whether or not there is data waiting to be sent to the endpoint."""

        return self._usIn.poll() or len(self._oBuffer)


    # Subclassable functions
    def handshake(self):
        """
        Function which performs a handshake with the remote connection connecting to us.

        Inputs: None.

        Outputs: A boolean indicating whether or not the handshake completed successfully.

        Notes:
            * Should set whatever instance attributes are required by the calling program onto self.
            * Can and should use the _read and _write functions for interacting with the remote. (not read/write)
              Note that this will bypass the preWrite and postRead functions.
            * Should be aware of self.active if looping is used.
        """

        return True


    def postRead(self, message):
        """
        Function which will be called, being passed a complete message from the remote.

        The output of this function will be returned from all read calls.
        """

        return message


    def preWrite(self, *args, **kwargs):
        """
        Function which will be called, being passed positional arguments from the write function.

        When not overridden, accepts any number of arguments and returns the first argument passed.

        Outputs: A string which will be the message which is sent to the remote.
        """

        return args[0]


    def _read(self):
        """
        Function implementing the logic for receiving a message from the remote.

        Should only be called by this object, and only when performing a handshake with the remote.

        Returns the message received from the remote if there is one, else None.
        """

        return self._recvPipe(self._parentIn)


    def _write(self, msg):
        """
        Function implementing the logic for sending a message to the host.

        Should only be called by this object, and only when performing a handshake with the remote.
        """

        if len(msg):
            typ = type(msg)
            if type(msg) != bytes:
                msg = msg.encode('utf8')

            msg = self._messageHeaders.serialize(typ, len(msg)) + msg

            if not self._parentOut.closed:
                self._parentOut.send(msg)


    def _recvPipe(self, pipe):
        """
        Receives from a pipe, ensuring that it can be read from.
        Returns whatever the pipe has returned if possible, else None if it is not possible.
        """

        def __recvPipe(pipe):
            if self._checkReadablePipe(pipe):
                return pipe.recv()

        return self._runLocked(__recvPipe, pipe)


    def _checkReadablePipe(self, pipe):
        """
        Checks if a readable pipe has data to be read.  Returns True if so, else False.
        """

        return self._runLocked(lambda: not pipe.closed and pipe.poll())


    def _runLocked(self, func, *args, **kwargs):
        """
        Runs a function, wrapping it in acquire/release calls to our ioLock.  Returns whatever it returns.
        """

        with self._ioLock:
            return func(*args, **kwargs)


    def _signalClose(self):
        """
        Should only be called by this thread.  Signals to any parent process polling on self.fileno() that we have closed.

        The parent process should still call close to close the other ends of the pipes.
        """

        def __signalClose(self):
            if self.active:
                self.active = False
                # Only close parentOut; leave parentIn open.  If we're closing for reasons other than our parent telling
                # us to close, by leaving parentIn open we allow it to consume any potential remaining messages.
                if not self._parentOut.closed:
                    self._parentOut.close()
                if not self._usOut.closed:
                    self._usOut.close()
                if not self._usIn.closed:
                    self._usIn.close()
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()

        self._runLocked(__signalClose, self)


    def _handshake(self):
        """
        Calls any subclassed handshake function, setting handshakeComplete upon completion, or closing
        this connection on failure.
        """

        try:
            self.handshakeComplete = self.handshake()

            # If the handshake failed, close the connection
            if not self.handshakeComplete:
                self._signalClose()

        except:
            self._signalClose()
            # Re raise the original exception
            raise


    def _recvMessage(self):
        """
        Attempts to receive a message from our remote endpoint into self._iBuffer.

        Returns True if we successfully received any bytes from the remote, else False.
        """

        retval = False

        try:
            # If self._iBufferLen is 0 we need to recv a completed size header field
            # to determine the length of our next incoming message
            while not self._iBufferLen:
                # Attempt to read a byte from the socket
                byteRead = eintr.recv(self.sock, 1)

                # If we read no bytes, return False to indicate as such
                if not byteRead:
                    return retval

                # Since we've read a byte, we will return True
                retval = True

                # Run what we just read through our MessageHeaders object
                if self._messageHeaders.deserialize(byteRead):
                    # If it returned True, we've received the message size header in its entirety.
                    self._iBufferLen = self._messageHeaders.getLength()
                    self._iType = self._messageHeaders.getType()
                    self._messageHeaders.reset()
                    break

            while len(self._iBuffer) != self._iBufferLen:
                # Attempt to recv our next incoming message into self._iBuffer
                bytesRead = eintr.recv(self.sock, self._iBufferLen - len(self._iBuffer))
                if not bytesRead:
                    break
                retval = True
                self._iBuffer += bytesRead

            # If we've completed the message in self._iBuffer, write it to self._usOut so it
            # can be read from self._parentIn by the parent process
            if len(self._iBuffer) == self._iBufferLen:
                if self._iType == self._messageHeaders.UNICODE:
                    self._iBuffer = self._iBuffer.decode('utf8')
                if not self._usOut.closed:
                    self._usOut.send(self._iBuffer)
                self._iBuffer = b""
                self._iBufferLen = 0

        except socket.error as e:
            # Only mask EAGAIN errors
            if e.errno != errno.EAGAIN:
                raise

        return retval


    def _sendMessage(self):
        """ Attempts to send a message to our remote endpoint from self._oBuffer. """

        # If we have no remaining bytes to send from self._oBuffer, try to move a message over from self.iBuffer
        if not len(self._oBuffer):
            self._oBuffer =  self._recvPipe(self._usIn) or b''

        # If we have any bytes in self._oBuffer to send, attempt to do so now
        if len(self._oBuffer):
            try:
                bytesSent = self.sock.send(self._oBuffer)
                self._oBuffer = self._oBuffer[bytesSent:]

            except socket.error as e:
                # Only mask EAGAIN errors
                if e.errno != errno.EAGAIN:
                    raise


    # Subclass Overrides
    def run(self):
        raise NotImplementedError()
