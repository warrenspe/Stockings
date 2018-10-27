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
import unittest, socket, time, os, select

os.environ['STOCKING_SELECT_SEND_INTERVAL'] = '0'

# Project imports
import Stockings

SOCKET_IP = 'localhost'
SOCKET_PORT = 5005

class StockingTests(unittest.TestCase):

    serverConn = None
    serverSocket = None

    # Setup / Teardown functions
    @classmethod
    def setUpClass(cls):
        cls.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cls.serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cls.serverSocket.bind((SOCKET_IP, SOCKET_PORT))
        cls.serverSocket.listen(1)

    @classmethod
    def tearDownClass(cls):
        cls.serverSocket.close()

    def setUp(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect((SOCKET_IP, SOCKET_PORT))
        serverSocket = self.serverSocket.accept()[0]

        self.serverConn = self.StockingClass(serverSocket)
        self.clientConn = self.StockingClass(clientSocket)

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


    def testQuickClose(self):
        return


    def testClose(self):
        self.serverConn.close()

        time.sleep(.5)

        self.assertFalse(self.serverConn.active)
        self.assertFalse(self.clientConn.active)

    def testSerializemessageHeaders(self):
        messageHeaders = self.clientConn._messageHeaders
        for length in (1, 50, 128, 255, 256, 1023, 1024, 1025, 65536):
            for typ in "bytes", "unicode":
                val = "a" * length
                if typ == "unicode":
                    if str == bytes:
                        val = unicode(val)
                else:
                    if str != bytes:
                        val = bytes(val, 'ascii')

            typ = type(val)
            length = len(val)
            if type(val) != bytes:
                val2 = val.encode('utf8')
                length = len(val2)

            serialized = messageHeaders.serialize(typ, length)
            deserializedSuccessfully = messageHeaders.deserialize(serialized)
            self.assertTrue(deserializedSuccessfully)
            self.assertEqual(len(val), messageHeaders.getLength())
            self.assertEqual(messageHeaders.getType(), (messageHeaders.BYTES if typ == "bytes" else messageHeaders.UNICODE))
            messageHeaders.reset()

    def testSendType(self):
        time.sleep(.1)

        self.serverConn.write("a")
        time.sleep(.5)
        self.assertEqual(type(self.clientConn.read()), type("a"))
        try:
            self.serverConn.write(unicode('a'))
            time.sleep(.5)
            self.assertEqual(type(self.clientConn.read()), unicode)
        except NameError:
            self.serverConn.write(b'a')
            time.sleep(.5)
            self.assertEqual(type(self.clientConn.read()), bytes)

    def testReadWrite(self):
        while not (self.serverConn.handshakeComplete and self.clientConn.handshakeComplete):
            pass

        # Assert None's are read when there's no data to read
        self.assertFalse(self.serverConn.writeDataQueued())
        self.assertIsNone(self.serverConn.read())
        self.assertIsNone(self.clientConn.read())

        # Try writing some messages
        msg = 'a' * 2**16
        self.serverConn.write(msg)
        time.sleep(.1)
        self.assertEqual(msg, self.clientConn.read())

        self.serverConn.write('test')
        time.sleep(.5)
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

        for i in range(500):
            self.clientConn.write(str(i))

        for i in range(500):
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
        self.setUp()

        while not (self.serverConn.handshakeComplete and self.clientConn.handshakeComplete):
            pass

        msg = 'a' * 2**24
        self.serverConn.write(msg)

        start = time.time()
        while not self.clientConn._parentIn.poll() and time.time() - start < 15:
            pass

        time.sleep(1)

        self.assertEqual(msg, self.clientConn.read(), msg="Test long message failed; len: %s" % len(msg))


    def testSlowMessageHeaders(self):
        time.sleep(1)

        # Write a header bypassing the _write function
        self.clientConn._parentOut.send(b'\x01')

        time.sleep(.1)

        self.assertIsNone(self.serverConn.read())
        self.assertEqual(self.serverConn._messageHeaders._completed, False)
        self.assertEqual(self.serverConn._messageHeaders._msgLength, 1)

        self.clientConn._parentOut.send(b'\x81')

        time.sleep(.1)

        self.assertEqual(self.serverConn._iBufferLen, 65)


    def testFastMessageHeaders(self):
        time.sleep(1)

        # Write a header bypassing the _write function
        self.clientConn.write('a' * 256)

        time.sleep(.1)

        self.assertEqual(self.serverConn.read(), 'a' * 256)


    def testTwoJoinedMessages(self):
        # Write a header bypassing the _write function
        self.clientConn._parentOut.send(b'\x81a\x81b')

        time.sleep(.1)

        # Ensure both messages arrive at the destination
        self.assertEqual(self.serverConn.read(), 'a')
        self.assertEqual(self.serverConn.read(), 'b')


class PollTests(StockingTests):
    StockingClass = Stockings.PollStocking

class SelectTests(StockingTests):
    StockingClass = Stockings.SelectStocking


def main():
        loader = unittest.TestLoader()
        pollTests = loader.loadTestsFromTestCase(PollTests)
        selectTests = loader.loadTestsFromTestCase(SelectTests)
        tests = [pollTests, selectTests]
        if not hasattr(select, 'poll'):
            tests.pop(0)
        suite = unittest.TestSuite(tests)
        unittest.TextTestRunner().run(suite)

if __name__ == '__main__':
    main()
