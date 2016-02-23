"""
    This file is part of Connection.

    Connection is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Connection is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Connection.  If not, see <http://www.gnu.org/licenses/>.


    Author: Warren Spencer
    Email:  warrenspencer27@gmail.com
"""

# Standard imports
import unittest, socket, time

# Project imports
import connection

SOCKET_IP = 'localhost'
SOCKET_PORT = 5005

class ConnectionTests(unittest.TestCase):

    serverConn = None
    clientConn = None
    serverSocket = None

    # Setup / Teardown functions
    @classmethod
    def setUpClass(cls):
        cls.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cls.serverSocket.bind((SOCKET_IP, SOCKET_PORT))
        cls.serverSocket.listen(1)

    @classmethod
    def tearDownClass(cls):
        cls.serverSocket.close()

    def setUp(self, maxMsgLen=65536):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect((SOCKET_IP, SOCKET_PORT))
        serverSocket = self.serverSocket.accept()[0]

        self.serverConn = connection.Connection(serverSocket, maxMsgLen=maxMsgLen)
        self.clientConn = connection.Connection(clientSocket, maxMsgLen=maxMsgLen)

    def tearDown(self):
        self.serverConn.close()
        self.clientConn.close()

    # Unit tests
    def testInit(self):
        time.sleep(.25)

        self.assertTrue(self.serverConn.active)
        self.assertTrue(self.serverConn.isAlive())
        self.assertTrue(self.serverConn.handshakeComplete)

        self.assertTrue(self.clientConn.active)
        self.assertTrue(self.clientConn.isAlive())
        self.assertTrue(self.clientConn.handshakeComplete)

    def testClose(self):
        self.serverConn.close()

        time.sleep(.25)

        self.assertFalse(self.serverConn.active)
        self.assertFalse(self.serverConn.isAlive())

        self.assertFalse(self.clientConn.active)
        self.assertFalse(self.clientConn.isAlive())

    def testSerializeMessageLength(self):
        for val in (1, 50, 128, 255, 256, 1023, 1024, 1025, 65536):
            self.assertEqual(val, self.clientConn._Connection__deserializeMessageLength(
                                      self.clientConn._Connection__serializeMessageLength(val)))

    def testReadWrite(self):
        while not (self.serverConn.handshakeComplete and self.clientConn.handshakeComplete):
            pass

        # Assert None's are read when there's no data to read
        self.assertIsNone(self.serverConn.read())
        self.assertIsNone(self.clientConn.read())

        # Assert we can write messages up to the maximum length'd message allowed
        msg = 'a' * self.serverConn._maxMsgLen
        self.serverConn.write(msg)
        time.sleep(.1)
        self.assertEqual(msg, self.clientConn.read())

        # Assert that attempts to write over the maximum length'd messages allowed raise Exceptions
        self.assertRaises(Exception, self.serverConn.write, msg + 'a')

        self.serverConn.write('test')
        time.sleep(.1)
        self.assertEqual(self.clientConn.read(), 'test')

        self.clientConn.write('a')
        self.serverConn.write('b')
        self.serverConn.write('c')
        self.clientConn.write('d')
        time.sleep(.1)
        self.assertEqual(self.clientConn.read(), 'b')
        self.assertEqual(self.clientConn.read(), 'c')
        self.assertEqual(self.serverConn.read(), 'a')
        self.assertEqual(self.serverConn.read(), 'd')

        for i in range(5000):
            self.clientConn.write(str(i))

        for i in range(5000):
            read = None
            while read is None:
                read = self.serverConn.read()
            self.assertEqual(read, str(i))

        self.serverConn.write('')
        time.sleep(.1)
        self.assertIsNone(self.clientConn.read())


    def testReadWriteLongmessage(self):

        time.sleep(1)

        self.tearDown()

        # Create new connections with larger message lengths
        self.setUp(maxMsgLen=13000000)

        while not (self.serverConn.handshakeComplete and self.clientConn.handshakeComplete):
            pass

        msg = 'a' * self.serverConn._maxMsgLen
        self.serverConn.write(msg)

        start = time.time()
        while self.serverConn._oBuffer and time.time() - start < 5:
            pass

        time.sleep(1)

        self.assertEqual(msg, self.clientConn.read(), msg="Test long message failed; len: %s" % len(msg))


if __name__ == '__main__':
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(ConnectionTests)
        unittest.TextTestRunner().run(suite)
