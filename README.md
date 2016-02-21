# Connection
A Python2 (linux-only) implemented socket wrapper.

TCP offers developers the ability to send reliably delivered, ordered, and well-formed packets using sockets.  However one major usability issue that is often faced by developers is the need to manage the sending of data over a TCP socket to handle the following case:

```
>>> bytesSent = sock.send("Message")
>>> print "%d, %d" % (bytesSent, len("Message"))
4, 7
```

In other words, the developer essentially needs to use a loop each time they wish to send or receive data over a socket.

An instance of `Connection` offers the ability to send complete messages to endpoints using a single command by using a daemonized [select.poll'ing](https://docs.python.org/2/library/select.html#select.poll) thread.

Note that when using a `Connection` to send data, a header will be appended to every message you send, detailing the length of the message which is being sent.  This header is intended to be interpreted by another Connection wrapped socket on the endpoint.

## Usage
### Initialization
The Connection class accepts two arguments, the first is a connected socket object, and the second is an integer representing the maximum size of a message we can send to the other endpoint.
