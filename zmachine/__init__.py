#
# See http://inform-fiction.org/zmachine/standards/z1point1/index.html for a definition of the Z-Machine
#
# This module abstracts out the Z-Machine generic code.
#

class Header(object):
    """ Represents the header of a ZCode file, bytes 0x00 through 0x36. The usage of the data will vary
        based on the version of the file. Most of the memory is read-only for a game. Some of the remainder
        is set by the game, other by the interpreter itself. """
    def __init__(self):
        self.raw_data = []

class ZMachine(object):
    """ Contains the entirity of the state of the interpreter. It does not initialize in a valid state,
        as it requires a story file to be loaded into it. For clarity the single block of memory in the spec
        is divided into multiple objects """
    def __init__(self):
        self.header = Header()
        self.global_variables = None
        self.dictionary = None
        self.object_tree = None
        self.program_counter = 0 # Address of the current routine.
        self.stack = []          # Global stack, represented as a list

