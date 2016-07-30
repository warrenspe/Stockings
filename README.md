# Stockings
A Windows/Linux/Unix Python 2 & 3 socket wrapper which allows sending/receiving of complete messages.

TCP sockets offer developers the ability to send reliably delivered, ordered, and well-formed packets using sockets.  However one obstacle that developers often face when using them is the need to handle the following case:
```
>>> bytesSent = sock.send("Message")
>>> print "%d, %d" % (bytesSent, len("Message"))
4, 7
```

In other words, a loop is typically required each time data is sent or received over a TCP socket to ensure complete sending or retrieval of a message.

`Stockings` is a threaded [polling](https://docs.python.org/2/library/select.html#select.poll) class wrapper which allows developers to send complete messages to and from an endpoint, as long as it is also using a Stocking to communicate.  Note that by default, the raw messages sent using Stockings will be prefixed with a header containing the length of the message being sent.  While this is transparent to the programs using Stockings, it means that they should not be used to communicate with endpoints not using a Stocking-wrapped socket.

`Stockings` is a threaded class wrapper which allows developers to send complete messages to and from an endpoint, as long as it is also using a Stocking to communicate.  Note that by default, the raw messages sent using Stockings will be prefixed with a header containing the length of the message being sent.  While this is transparent to the programs using Stockings, it means that they should not be used to communicate with endpoints not using a Stocking-wrapped socket.

There are two flavours to Stockings depending on whether or not the system its running on supports the [select.poll](https://docs.python.org/2/library/select.html#select.poll) construct.  If it does, a PollStocking will be used, utilizing select.poll.  If it doesn't, (like most Windows platforms), a SelectStocking will be used instead, using select.select.  Both provide the same functionality, however SelectStocking is less efficient as it requires the thread to wake up at a certain frequency to check whether or not we have data to send to the endpoint.  This frequency can be configured by setting the environment `STOCKING_SELECT_SEND_INTERVAL`, which should contain the frequency to wake in seconds.

Notes:
    * An endpoint using a PollStocking can communicate with an endpoint using a SelectStocking and vice versa.
    * The most efficient flavor of Stocking will be available at `Stockings.Stocking`, however both flavors can still be imported directly using `Stockings.SelectStocking` and (assuming that your system supports polling sockets) `Stockings.PollStocking`.


## Usage
### Initialization
The `Stocking` class accepts a single argument, a connected socket object.  To this, the only option/configuration change that is made is that it is set to nonblocking mode.  This is required for the Stocking to handle IO from/to both the endpoint and the calling process without getting blocked indefinitely in one phase or the other.

```
>>> import socket, Stockings
>>>
>>> sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
>>> sock.connect(('127.0.0.1', 1234))
>>>
>>> stock = Stockings.Stocking(sock)
```

### Sending & Receiving Messages
`Stocking` wrappers have a `write` function which by default accepts a single string to send to the endpoint in it's entirety.

On the other end, the endpoint's `Stocking` has a `read` function (accepting no arguments) which will return None until the string sent by the other endpoint has been received in its entirety.

```
>>> stock1.write("Test Message")
```

```
>>> stock2.read()
"Test Message"
```

### Extending
Subclasses of `Stocking` can override the following functions to modify functionality:

#### preWrite
`Stocking.write` can accept any number of positional arguments and keyword arguments.  These will be passed to `Stocking.preWrite`, and then the result of that function will be sent to the endpoint.  `Stocking.preWrite` is expected to return a string.  By default, `Stocking.preWrite` returns the first positional argument passed (to allow `Stocking.write("Test Message")` to work).  However, preWrite can be overridden to format the string to send.  For example

```
class MyStocking(Stockings.Stocking):

  def preWrite(self, user, status="OK"):
      return "%s:%s" % (user, status)
...

# Sends "Username:ERROR" to the endpoint
>>> myStocking.write("Username", status="ERROR")
```

#### postRead
In a similar fashion to preWrite, `Stocking.postRead` will be passed the complete message (string) received from the endpoint, the result of this function will then be returned to the calling process.  Can be used to return instances of classes, tuples, etc. from the Stocking.

```
class MyStocking(Stockings.Stocking):

  def postRead(self, message):
    """ Returns a tuple containing (user, status) """

    return re.search("(.*):(.*)", message).groups()
...

>>> myStocking.read()
('username', 'error')
```

#### handshake
`Stocking.handshake` is a function which will be called upon initialization of a Stocking.  This function should return True if the handshake was a success, else False.  By default, it simply returns True.  This function will be executed in its own thread and should accept no arguments.  It should interact with the remote by using `self._write` and `self._read` (Note that these bypass preWrite & postRead but in all other ways act like the default read & write functions).  `self._write` accepts a single string argument which will be sent to the remote in its entirety, and `self._read` accepts no arguments and returns either None, or a complete message from the remote.

Note that the thread which runs this function does not run as a daemon, and as such if looping is involved it should be aware of self.active.

Finally, use of the Stocking by the process that created it will raise a Stockings.NotReady exception until the handshake completes.

```
class MyStocking(Stockings.Stocking):

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



TESTED ON 3.4, 3.5, 2.7
