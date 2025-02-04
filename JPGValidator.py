# coding=utf-8
import struct
from abc import ABCMeta


class Validator(object):
    """
    Abstract class that defines the Validator Interface.
    """
    __metaclass__ = ABCMeta

    def __init__(self):
        """
        Setting the behaviour for most validators. All validators are expected to have is_valid,
        eof, and bytes_last_valid attributes.
        """
        self.is_valid = False
        self.eof = False
        self.bytes_last_valid = -1
        self.end = False
        self.fd = None

    def GetDetails(self):
        """
        Returns a dictionary with detailed validator-specific information.
        """
        return {}

    def GetStatus(self):
        """
        Returns the status of the validator.
        """
        return self.is_valid, self.eof, self.bytes_last_valid, self.end

    def Validate(self, fd):
        """
        Validates a file-like object.
        """
        pass

    def _Read(self, length):
        data = self.fd.read(length)
        if len(data) < length:
            self.eof = True
        return data

    def _CountValidBytes(self, bytes_read):
        """
        Tracks the number of valid bytes.
        """
        if self.is_valid and not self.eof:
            self.bytes_last_valid += bytes_read

    def _SetValidBytes(self, value):
        """
        Sets the count of valid bytes.
        """
        if self.is_valid:
            self.bytes_last_valid = value


class JPGValidator(Validator):
    """
    Class that validates an object to determine if it is a valid JPG file.
    """

    def __init__(self):
        """
        Calls Validator.__init__() and sets some internal attributes for the validation process.
        """
        super(JPGValidator, self).__init__()
        self.converter = struct.Struct(">H")
        self._chunksize = 2048
        self.markers = {
            b'\xff\xc0', b'\xff\xc1', b'\xff\xc2', b'\xff\xc3', b'\xff\xc4', b'\xff\xc5',
            b'\xff\xc6', b'\xff\xc7', b'\xff\xc8', b'\xff\xc9', b'\xff\xca', b'\xff\xcb',
            b'\xff\xcc', b'\xff\xcd', b'\xff\xce', b'\xff\xcf', b'\xff\xd0', b'\xff\xd1',
            b'\xff\xd2', b'\xff\xd3', b'\xff\xd4', b'\xff\xd5', b'\xff\xd6', b'\xff\xd7',
            b'\xff\xd9', b'\xff\xda', b'\xff\xdb', b'\xff\xdc', b'\xff\xdd', b'\xff\xde',
            b'\xff\xdf', b'\xff\xe0', b'\xff\xe1', b'\xff\xe2', b'\xff\xe3', b'\xff\xe4',
            b'\xff\xe5', b'\xff\xe6', b'\xff\xe7', b'\xff\xe8', b'\xff\xe9', b'\xff\xea',
            b'\xff\xeb', b'\xff\xec', b'\xff\xed', b'\xff\xee', b'\xff\xef', b'\xff\xf0',
            b'\xff\xf1', b'\xff\xf2', b'\xff\xf3', b'\xff\xf4', b'\xff\xf5', b'\xff\xf6',
            b'\xff\xf7', b'\xff\xf8', b'\xff\xf9', b'\xff\xfa', b'\xff\xfb', b'\xff\xfc',
            b'\xff\xfd', b'\xff\xfe'
        }
        self.restart_markers = {
            b'\xff\x00', b'\xff\xd0', b'\xff\xd1', b'\xff\xd2', b'\xff\xd3', b'\xff\xd4',
            b'\xff\xd5', b'\xff\xd6', b'\xff\xd7'
        }
        self.min_size = 135
        self.eoi_marker = False
        self.markers_found = []
        self.data = b""
        self.pos = 0

    def _ConvertBytes(self, value):
        return self.converter.unpack(value)[0]

    def _Read(self, length):
        ret = self.data[self.pos: self.pos + length]
        if len(ret) < length:
            self.eof = True
        self.pos += length
        return ret

    def GetDetails(self):
        return {
            "segments": self.markers_found,
            'extensions': ['.jpg'],
        }

    def Validate(self, fd):
        valid_markers = self.markers
        valid_restart_markers = self.restart_markers

        if isinstance(fd, str):
            self.data = fd.encode()
        elif hasattr(fd, "read"):
            self.data = fd.read()
        else:
            raise Exception("Argument must be either a file or a string.")

        self.pos = 0
        self.is_valid = True
        self.eof = False
        self.end = False
        self._SetValidBytes(0)
        self.markers_found = []

        first_read = self._Read(4)
        header_marker = first_read[:2]
        current_marker = first_read[2:4]

        self.is_valid = header_marker == b'\xff\xd8' and (current_marker in valid_markers)
        if self.is_valid and not self.eof:
            self.markers_found.append(('ffd8', self.pos - 4, 2))

        self._CountValidBytes(4)
        is_eoi_marker = current_marker == b'\xff\xd9'

        while not self.eof and not is_eoi_marker and self.is_valid:
            if current_marker == b'\xff\xd9':
                is_eoi_marker = True
                break

            if current_marker == b'\xff\xdd':
                payload_length = 4
            else:
                payload_length = self._Read(2)
                self._CountValidBytes(2)
                if not self.eof:
                    payload_length = self._ConvertBytes(payload_length) - 2
                else:
                    payload_length = 0

            if self.is_valid and not self.eof:
                self.markers_found.append((current_marker.hex(), self.pos - 4, payload_length + 4))

            data = self._Read(payload_length)
            self._CountValidBytes(payload_length)

            file_tell = self.pos
            adjust_offset = 0
            bytestring = self.data[self.pos:]
            eof = len(bytestring) < self._chunksize
            seek_marker = True
            pos = bytestring.find(b"\xff")

            while seek_marker and pos >= 0:
                potential_marker = bytestring[pos: pos + 2]
                if not (potential_marker in valid_restart_markers):
                    current_marker = potential_marker
                    seek_marker = False
                    self._SetValidBytes(file_tell + pos + 2)
                    self.pos = file_tell + pos + 2
                else:
                    adjust_offset += 2
                    self._CountValidBytes(adjust_offset)
                    seek_marker = b"\xff" in bytestring
                pos = bytestring.find(b"\xff", pos + 1)

            current_marker = self._Read(2)
            self.is_valid = current_marker in valid_markers
            self._CountValidBytes(2)
            is_eoi_marker = current_marker == b'\xff\xd9'

        if is_eoi_marker:
            self._SetValidBytes(self.bytes_last_valid - 2)
            self.end = True
            self.markers_found.append(('ffd9', self.pos - 2, 2))

        if self.bytes_last_valid < self.min_size:
            self.is_valid = False

        return self.is_valid
