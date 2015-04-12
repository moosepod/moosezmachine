""" See http://inform-fiction.org/zmachine/standards/z1point1/index.html for a definition of the Z-Machine
    See README.md for a summary of architecture 
"""

### These helper methods are for working with "memory" as bytes. There is probably a better/existing
### way of doing this
def get_byte_as_int(data, index):
    # Support string or int versions of data
    try:
        return ord(data[index])
    except TypeError, e:
        return int(data[index])

def get_address(data,index):
    return ord(data[index])*256 + ord(data[index+1])

class StoryFileException(Exception):
    """ Thrown in cases where a story file is invalid """
    pass

class Header(object):
    VERSION = 0x00
    HIMEM = 0x04
    PROGRAM_COUNTER = 0x06
    DICTIONARY = 0x08
    OBJECT_TABLE = 0x0A
    GLOBAL_VARIABLES = 0x0C
    STATIC_MEMORY = 0x0E

    MAX_VERSION = 0x03   # Max ZCode version we support

    """ Represents the header of a ZCode file, bytes 0x00 through 0x36. The usage of the data will vary
        based on the version of the file. Most of the memory is read-only for a game. Some of the remainder
        is set by the game, other by the interpreter itself. """
    def __init__(self,raw_data):
        self._raw_data = raw_data
        if self.version > Header.MAX_VERSION:
            raise StoryFileException('This story file version is not supported.')
    @property
    def version(self):
        return get_byte_as_int(self._raw_data, Header.VERSION)

    @property
    def himem_address(self):
        return get_address(self._raw_data,Header.HIMEM)

    @property
    def program_counter_address(self):
        return get_address(self._raw_data,Header.PROGRAM_COUNTER)

    @property
    def dictionary_address(self):
        return get_address(self._raw_data,Header.DICTIONARY)

    @property
    def object_table_address(self):
        return get_address(self._raw_data,Header.OBJECT_TABLE)

    @property
    def global_variables_address(self):
        return get_address(self._raw_data,Header.GLOBAL_VARIABLES)

    @property
    def static_memory_address(self):
        return get_address(self._raw_data,Header.STATIC_MEMORY)

 
        
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
            raise StoryFileException('Story file is too short')
        self.header = Header(value[0:36])
    

