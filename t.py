def m():
    import socket, Stockings
    c = Stockings.SelectStocking


    SOCKET_IP = 'localhost'
    SOCKET_PORT = 5005

    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind((SOCKET_IP, SOCKET_PORT))
    serverSocket.listen(1)
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientSocket.connect((SOCKET_IP, SOCKET_PORT))
    serverSocket = serverSocket.accept()[0]
    serverConn = c(serverSocket)
    clientConn = c(clientSocket)
    return serverConn, clientConn
