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

class MessageLength(object):
    """
    Class implementing serialization / deserialization of message size headers.

    Note: The size is serialized as a series of bytes, where the first bit acts as a bitflag, and the remaining 7 bits
          are included in the size calculation.  It was done this way, as it allows us to not require specifying a
          maximum message size, and it also prevents us from having to have a header specifying the length of the size
          header. (a message size header size header, if you will. meta.).  This will be more efficient than dedicating
          a complete byte to storing the size of the message headers up until a message of size 2**56 is sent.  Since
          we expect most of our messages to be well below that threshold, doing it this way shouldn't cost us any
          additional bytes.
    """

    # Deserialization state variables.
    # Because deserialization can occur in increments we record the state of the current deserialization as
    # class attributes
    _msgLength = 0      # Constructed Message length
    _completed = False  # Boolean indicating whether we are done deserializing the message length
    _shift = 1          # Integer recording the current amount of bits we need to shift in order to add the next value

    # API Functions

    def get(self):
        """ Returns the calculated message length, if we've found one - else None. """

        if self._completed:
            return self._msgLength


    def reset(self):
        """ Resets the state variables in self so it can be used to deserialize another message size header. """

        self._msgLength = 0
        self._completed = False
        self._shift = 1


    @staticmethod
    def serialize(length):
        """
        Serializes the length of a message to send as a string which can be parsed by the other endpoint.
        Uses 7 bits out of a char in order to serialize variable length'd messages without requiring a message
        size limit.

        Inputs: length - The length (integer) to serialize as a string.

        Outputs: A string format of the length of the message we are to send.
        """

        chars = []

        while length:
            chars.append(length & 127)
            length >>= 7

        chars[-1] |= 128

        toReturn = "".join(chr(c) for c in chars)

        if type(toReturn) != bytes:
            toReturn = toReturn.encode('latin1')
        return toReturn


    def deserialize(self, st):
        """
        Deserializes the length of a message from a string into an integer,
        and updates self._iBufferLen and self._iBuffer accordingly.

        Inputs: st - The message received from which we are to parse out the size header.

        Outputs: Whether or not we have successfully parsed the entire message size header.
        """

        # If we've finished deserializing the length already, return
        if self._completed:
            return True

        for i, char in enumerate(st):
            # Python2/3 support
            if type(char) != int:
                char = ord(char)

            self._msgLength += self._shift * (char & 127)

            # If the first bit on this char is set, stop processing further bytes
            if char & 128:
                self._completed = True

                return True

            self._shift <<= 7

        return False


