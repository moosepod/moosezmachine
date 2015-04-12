#
# See http://inform-fiction.org/zmachine/standards/z1point1/index.html for a definition of the Z-Machine
#
# See README.md for a summary of architecture 
#

class Header(object):
    """ Represents the header of a ZCode file, bytes 0x00 through 0x36. The usage of the data will vary
        based on the version of the file. Most of the memory is read-only for a game. Some of the remainder
        is set by the game, other by the interpreter itself. """
    def __init__(self,raw_data):
        self._raw_data = raw_data

    @property
    def version(self):
        """ Return the version of the story file, stored at location 0 """
        return ord(self._raw_data[0])

class ZMachine(object):
    """ Contains the entirity of the state of the interpreter. It does not initialize in a valid state,
        is divided into multiple objects """
    def __init__(self):
        self.header = None
        self.global_variables = None
        self.dictionary = None
        self.object_tree = None
        self.program_counter = 0 # Address of the current routine.
        self.stack = []          # Global stack, represented as a list
        self._raw_data = []

    @property
    def raw_data(self):
        """ Return the raw data for the currently loaded story file """
        return self._raw_data

    @raw_data.setter
    def raw_data(self,value):
        """ Set the story data for this file. This will reset the header. """
        self._raw_data = bytearray(value)
        if len(value) < 36:
            raise Exception('Story file is too short')
        self.header = Header(value[0:36])


