# Connection
A Python2 (linux-only) implemented socket wrapper.

TCP sockets offer developers the ability to send reliably delivered, ordered, and well-formed packets using sockets.  However one major usability issue that is often faced by developers is the need to manage the sending of data over a TCP socket to handle the following case:

```
>>> bytesSent = sock.send("Message")
>>> print "%d, %d" % (bytesSent, len("Message"))
4, 7
```

In other words, the developer typically needs to use a loop each time they wish to send or receive data over a TCP socket.

`Connection` is a threaded [polling](https://docs.python.org/2/library/select.html#select.poll) class which allows developers to send complete messages to and from an endpoint, as long as it is also using a Connection to communicate.  Note that by default, Connections will prefix messages to be sent with the length of the message to receive.  While this is transparent to the programs using Connections, it means that they should not be used to communicate with endpoints not using a `Connection` socket wrapper.

## Usage
### Initialization
The `Connection` class accepts two arguments, the first is a connected socket object, and the second is an integer representing the maximum size of a message we can send to the other endpoint.

```
import socket, connection

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 1234))

# Creates a sock with a maximum message length of 65536, 2 byte headers appended to each message
conn = connection.Connection(sock)

# Creates a sock with a maximum message length of 256, 1 byte headers appended to each message
conn = connection.Connection(sock, 256)

# Creates a sock with a maximum message length of 1024, 1 byte headers appended to each message
conn = connection.Connection(sock, maxMsgLen=1024)
```

### Sending & Receiving Messages
`Connection` wrappers have a `write` function which by default accepts a single string to send to the endpoint in it's entirety.

On the other end, the endpoint's `Connection` has a `read` function (accepting no arguments) which will return None until the string sent by the other endpoint has been received completely.

```
>>> conn.write("Test Message")
```

```
>>> conn.read()
"Test Message"
```

### Extending
Subclasses of `Connection` can override the following functions to modify functionality:

#### preWrite
`Connection.write` can accept any number of positional arguments and keyword arguments.  These will be passed to `Connection.preWrite`, and then the result of that function will be sent to the endpoint.  `Connection.preWrite` is expected to return a string.  By default, `Connection.preWrite` returns the first keyword argument passed (which allows `Connection.write("Test Message")` to work).  However, preWrite can be overridden to format the string to send.  For example

```
class MyConnection(connection.Connection):

  def preWrite(self, user, status="OK"):
      return "%s:%s" % (user, status)
...

myConnection.write("Username", status="ERROR")
# Sends "Username:ERROR" to the endpoint
```

#### postRead
In a similar fashion to preWrite, `Connection.postRead` will be passed the complete message (string) received from the endpoint, the result of this function will then be returned to the calling process.  Can be used to return instances of classes, tuples, etc. from the Connection.

```
class MyConnection(connection.Connection):

  def postRead(self, message):
    """ Returns a tuple containing (user, status) """

    return re.search("(.*):(.*)", message).groups()
...
```

#### handshake
`Connection.handshake` is a function which will be called upon initialization of a Connection.  This function should return True if the handshake was a success, else False.  This function will be executed in its own thread and should accept no arguments.  It should interact with the remote by using `self._write` and `self._read` (Note that these bypass preWrite & postRead).  `self._write` accepts a single string argument which will be sent to the remote in its entirety, and `self._read` accepts no arguments and returns either None, or a complete message from the remote.

Note that the thread which runs this function does not run as a daemon, and as such if looping is involved it should be aware of self.active.

```
class MyConnection(connection.Connection):

  def handshake(self):
    """ Sends our unique ID to the remote and receives the remotes unique ID. """
    
    self._write(str(self.uniqueID))
    
    while self.active:
      read = self._read()
      if read is not None:
        self.remoteID = read
        return True
        
    return False
```
