# Standard imports
import socket, errno, threading, select, math, multiprocessing

class NotReady(Exception):
    """ Error raised when read/write operations are performed on a connection which has not yet finished its handshake. """

class Connection(threading.Thread):
    """
    Class which handles a connection with a remote endpoint.  Runs as a thread and can be interfaced with
    by using its `read` and `write` functions to read and write complete messages to a remote endpoint.
    """

    # Publically visible attributes
    sock = None               # The connection to the remote
    addr = None               # The address of the remote
    handshakeComplete = False # A boolean indicating whether or not this connection is ready for interaction with the remote
    active = True             # Flag which signals whether this thread is supposed to be running or not

    # Internal attributes
    _poller = None            # select.poll object used to manage I/O activity.
    _headerLen = None         # The number of bytes sent with each message indicating the length of the message to follow
    _maxMsgLen = None         # Integer representing the maximum length of a message we can send or receive
    _iBuffer = ""             # Partial message received from the remote that require further recv's to complete
    _iBufferLen = 0           # Length of the message we're currently receiving into self._iBuffer
    _oBuffer = ""             # Partial message sent to the remote that require further send's to complete
    _parentOut = None         # Pipe which our parent process will read from
    _parentIn = None          # Pipe which our parent process will write to
    _usIn = None              # Pipe which we will read from
    _usOut = None             # Pipe which we will write to

    def __init__(self, conn, maxMsgLen=65536):
        """
        Creates a new connection, wrapping the given connected socket.

        Inputs: conn             - A connected socket.
                maxMessageLength - The maximum length of message we will be able to send/receive.
                                        Default: 65536 (results in 2 byte headers)
        """

        threading.Thread.__init__(self)
        self.sock = conn
        self.addr = self.sock.getpeername()

        # We cannot run in blocking mode, because at any given time we may be in the process of sending a message to
        # the remove and receiving a message from the remote.  We cannot get stuck in one or the other.
        self.sock.setblocking(0)

        # Set message/header-length restrictions
        self._maxMsgLen = maxMsgLen
        self._headerLen = max(1, int(math.ceil(math.log(self._maxMsgLen, 2) / 8)))

        # Create two unidirectional pipes for communicating with our parent process
        self._parentIn, self._usOut = multiprocessing.Pipe(False)
        self._usIn, self._parentOut = multiprocessing.Pipe(False)

        # Start processing requests
        self.daemon = True
        self.start()

    # Data Model functions
    def __repr__(self):
        return "<Connection [%s]>" % str(self.addr)


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
            raise NotReady()

        toReturn = self._read()
        if toReturn is not None:
            return self.postRead(toReturn)


    def write(self, *args, **kwargs):
        """
        Queues a message to send to the remote if we've completed our handshake.

        Raises a NotReady Exception if the handshake has not yet completed.
        """

        if not self.handshakeComplete:
            raise NotReady()

        self._write(self.preWrite(*args, **kwargs))


    def fileno(self):
        """ Returns a file descriptor which the parent process can poll on, to wake when there is input to be read. """

        return self._parentIn.fileno()


    def close(self):
        """ Kills our connection and immediately halts the thread. """

        self.__signalClose()
        self._parentIn.close()


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


    # Internal functions
    def _read(self):
        """
        Function implementing the logic for receiving a message from the remote.

        Should only be called by this object, and only when performing a handshake with the remote.

        Returns the message received from the remote if there is one, else None.
        """

        if self.active and self._parentIn.poll():
            return self._parentIn.recv()


    def _write(self, msg):
        """
        Function implementing the logic for sending a message to the host.

        Should only be called by this object, and only when performing a handshake with the remote.
        """

        if len(msg) > self._maxMsgLen:
            raise Exception("Length of message to send is greater than maximum message length: %s" % self._maxMsgLen)

        if self.active and len(msg):
            self._parentOut.send(self.__serializeMessageLength(len(msg)) + msg)


    def __signalClose(self):
        """
        Should only be called by this thread.  Signals to any parent process polling on self.fileno() that we have closed.

        The parent process should still call close to close the other ends of the pipes.
        """

        self.active = False
        # Only close parentOut; leave parentIn open.  This is because our main loop polls for POLLHUP on parentIn.  If
        # we close it we won't receive the notification that parentOut has closed, causing it to hang.
        # Additionally, if we're closing for reasons other than our parent telling us to close, by leaving parentIn open
        # we allow it to consume any potential remaining messages.
        self._parentOut.close()
        self._usOut.close()
        self._usIn.close()
        self.sock.close()


    def __handshake(self):
        """
        Calls any subclassed handshake function, setting handshakeComplete upon completion, or closing
        this connection on failure.
        """

        try:
            self.handshakeComplete = self.handshake()

            # If the handshake failed, close the connection
            if not self.handshakeComplete:
                self.__signalClose()

        except:
            self.__signalClose()
            # Re raise the original exception
            raise


    def __deserializeMessageLength(self, st):
        """
        Deserializes the length of a message from a string into an integer.

        Inputs: st - The string containing the serialized length of the message we are to receive.

        Outputs: An integer containing the length of the message we are to receive.
        """

        length = 0
        exp = 0

        for char in st:
            length += (256**exp) * ord(char)
            exp += 1

        # Because we don't send messages of length 0, that serialization is unused.  To make better use of this we 
        # subtract the length by one when we serialize.  Account for this when we return the length
        return length + 1


    def __serializeMessageLength(self, length):
        """
        Serializes the length of a message to send as a string which can be parsed by the other endpoint.

        Inputs: length - The length (integer) to serialize as a string.

        Outputs: A string format of the length of the message we are to send.
        """

        st = ""

        # Because we don't send messages of length 0, that serialization is unused.  To make better use of this, subtract
        # the value we're serializing by one (which will be undone when it is deserialized).
        length -= 1

        while length:
            remainder = length % 256
            length /= 256
            st += chr(remainder)

        return st.ljust(self._headerLen, '\x00')


    def __recvMessage(self):
        """
        Attempts to receive a message from our remote endpoint into self._iBuffer.

        Returns True if we successfully received any bytes from the remote, else False.
        """

        retval = False

        try:
            # If self._iBufferLen is 0 we need to recv self._headerLen bytes
            # to determine the length of our next incoming message
            if not self._iBufferLen:
                # Attempt to read our message length header from the socket, taking into account any portion of it
                # already read into self._iBuffer
                bytesRead = self.sock.recv(self._headerLen - len(self._iBuffer))
                retval = bool(bytesRead)

                # Concatenate what we just read to self._iBuffer
                self._iBuffer += bytesRead

                # If we have successfully received the entirety of the message length header, move to self._iBufferLen
                if len(self._iBuffer) == self._headerLen:
                    self._iBufferLen = self.__deserializeMessageLength(self._iBuffer)
                    self._iBuffer = ""

                # Otherwise we're not ready to continue receiving the message itself yet
                else:
                    return retval

            # Attempt to recv our next incoming message into self._iBuffer
            bytesRead = self.sock.recv(self._iBufferLen - len(self._iBuffer))
            retval = bool(bytesRead) or retval
            self._iBuffer += bytesRead

            # If we've completed the message in self._iBuffer, write it to self._usOut so it
            # can be read from self._parentIn by the parent process
            if len(self._iBuffer) == self._iBufferLen:
                self._usOut.send(self._iBuffer)
                self._iBuffer = ""
                self._iBufferLen = 0

        except socket.error as e:
            # Only mask EAGAIN errors
            if e.errno != errno.EAGAIN:
                raise e

        return retval


    def __sendMessage(self):
        """ Attempts to send a message to our remote endpoint from self._oBuffer. """

        # If we have no remaining bytes to send from self._oBuffer, try to move a message over from self.iBuffer
        if not len(self._oBuffer) and self._usIn.poll():
            self._oBuffer = self._usIn.recv()

        # If we have any bytes in self._oBuffer to send, attempt to do so now
        if len(self._oBuffer):
            try:
                bytesSent = self.sock.send(self._oBuffer)
                self._oBuffer = self._oBuffer[bytesSent:]

                # If we were unable to write the entirety of the message to the socket, poll on it being writeable
                if len(self._oBuffer):
                    self._poller.register(self.sock, select.POLLIN | select.POLLOUT)

                # Otherwise self._oBuffer is empty; disable polling on our socket being writeable
                else:
                    self._poller.register(self.sock, select.POLLIN)

            except socket.error as e:
                # Only mask EAGAIN errors
                if e.errno != errno.EAGAIN:
                    raise e


    # Threading.Thread override
    def run(self):
        """ Main loop for this Connection. """

        try:
            # Start a new thread to handle connecting to the remote
            handshakeThread = threading.Thread(target=self.__handshake)
            handshakeThread.start()

            self._poller = select.poll()
            self._poller.register(self._parentIn, select.POLLHUP) # Detect if we've been closed by our parent
            self._poller.register(self.sock, select.POLLIN)       # Detect messages to recv from the remote endpoint
            self._poller.register(self._usIn, select.POLLIN)      # Detect messages to send from our parent

            while self.active:
                # Wait until we have input or output to act upon
                for fd, eventMask in self._poller.poll():
                    # eventMask will be POLLIN if we have data to process
                    if eventMask & select.POLLIN:
                        # If our socket was returned, there is data for us to recv
                        if self.sock.fileno() == fd:
                            # If our connected socket to the remote is in the list of readable sockets we expect that
                            # we can read from it; if for some reason we cannot we can assume we have become disconnected.
                            if not self.__recvMessage():
                                return

                        # Otherwise check if our parent sent us data
                        elif self._usIn.fileno() == fd:
                            self.__sendMessage()

                    # eventmask will be POLLOUT if we can continue sending data from self._oBuffer
                    elif eventMask & select.POLLOUT:
                        self.__sendMessage()

                    # Otherwise check if our parent has asked us to close
                    elif eventMask & select.POLLHUP:
                        return

        except socket.error as e:
            # Ignore bad file descriptor errors
            if e.errno != errno.EBADF:
                raise e

        except select.error as e:
            # Ignore bad file descriptor errors
            if not hasattr(e, 'args') or not hasattr(e.args, '__iter__') or not len(e.args) or e.args[0] != 9:
                raise e

        finally:
            self.__signalClose()

