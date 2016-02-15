""" See http://inform-fiction.org/zmachine/standards/z1point1/index.html for a definition of the Z-Machine
    See README.md for a summary of architecture 
"""
import random
import os

from zmachine.memory import Memory
from zmachine.text import ZText
from zmachine.dictionary import Dictionary
from zmachine.instructions import Instruction

class StoryFileException(Exception):
    """ Thrown in cases where a story file is invalid """
    pass

class MemoryAccessException(Exception):
    """ Thrown in cases where a game attempts to access memory it shouldn't """
    pass

class RNG(object):
    """ The random number generator, as specced in section 2.4
        Note that it toggles between a predicatable and random mode """
    def __init__(self):
        self.enter_random_mode()
        self.seed = 0

    def enter_random_mode(self):
        self.seed = os.urandom(8)
        self._reseed()

    def enter_predictable_mode(self, seed):
        self.seed = seed
        self._reseed()

    def _reseed(self):
        random.seed(self.seed)

    def randint(self,n):       
        """ Return random integer r such that 1 <= r <= n """
        return random.randint(1,n)

class Screen(object):
    """ Abstraction of a screen for display """
    def print_ascii(self,msg):
        """ Print the given ASCII string to the screen """
        print(msg)

class Header(Memory):
    VERSION = 0x00
    FLAGS_1 = 0x01
    FLAGS_2 = 0x10
    FLAGS_2_1 = 0x11
    HIMEM = 0x04
    MAIN_ROUTINE = 0x06
    DICTIONARY = 0x08
    OBJECT_TABLE = 0x0A
    GLOBAL_VARIABLES = 0x0C
    STATIC_MEMORY = 0x0E
    ABBREV_TABLE = 0x18
    FILE_LENGTH = 0x1A
    CHECKSUM    = 0x1C
    INTERPRETER_NUMBER = 0x1E
    INTERPRETER_VERSION = 0x1F
    REVISION_NUMBER = 0x32

    HEADER_SIZE = 0x40
    MAX_VERSION = 0x03   # Max ZCode version we support

    """ Represents the header of a ZCode file, bytes 0x00 through 0x40. The usage of the data will vary
        based on the version of the file. Most of the memory is read-only for a game. Some of the remainder
        is set by the game, other by the interpreter itself. """
    def __init__(self,data):
        super(Header,self).__init__(data)
        if self.version > Header.MAX_VERSION:
            raise StoryFileException('Story file version %d is not supported.' % self.version)

    @property
    def version(self):
        return self[Header.VERSION]

    @property
    def himem_address(self):
        return self.word(Header.HIMEM)

    @property
    def main_routine_addr(self): 
        return self.word(Header.MAIN_ROUTINE)

    @property
    def dictionary_address(self):
        return self.word(Header.DICTIONARY)

    @property
    def object_table_address(self):
        return self.word(Header.OBJECT_TABLE)

    @property
    def global_variables_address(self):
        return self.word(Header.GLOBAL_VARIABLES)

    @property
    def static_memory_address(self):
        return self.word(Header.STATIC_MEMORY)

    @property
    def abbrev_address(self):
        return self.word(Header.ABBREV_TABLE)

    @property
    def file_length(self):
        # This length is divided by a constant that varies based on version. V1-3 has a constant of 2
        return self.word(Header.FILE_LENGTH)*2

    @property 
    def checksum(self):
        return self.word(Header.CHECKSUM)

    @property
    def revision_number(self):
        return self.word(Header.REVISION_NUMBER)

    @property
    def flag_status_line_type(self):
        """ Return 0 if score/turn, 1 if hours:mins """
        return self.flag(Header.FLAGS_1, 1)

    @property
    def flag_story_two_disk(self):
        """ Is this story file on two disks? """
        return self.flag(Header.FLAGS_1,2)

    @property
    def flag_status_line_not_available(self):
        return self.flag(Header.FLAGS_1,4)
    
    @property
    def flag_screen_splitting_available(self):
        return self.flag(Header.FLAGS_1,5)
    
    @property
    def flag_variable_pitch_default(self):
        """ Return True if a variable pitch font is default """
        return self.flag(Header.FLAGS_1,6)
 
    def reset(self):
        """ Reset appropriate flags after an initialization or load """
        self.set_flag(Header.FLAGS_1,4,0) # Status line is available
        self.set_flag(Header.FLAGS_1,5,0) # Screen splitting not available
        self.set_flag(Header.FLAGS_1,6,0) # Font is not variable width
        
        self.set_flag(Header.FLAGS_2,0,0) # Transcripting is off
        self.set_flag(Header.FLAGS_2,1,0) # Fixed-pitch printing off
        self.set_flag(Header.FLAGS_2,2,0) # Screen redraw flag off
        self.set_flag(Header.FLAGS_2,3,0) # Game requests pictures
        self.set_flag(Header.FLAGS_2,4,0) # Game requests UNDO
        self.set_flag(Header.FLAGS_2,5,0) # Game requests mouse
        self.set_flag(Header.FLAGS_2,7,0) # Game requests sound
        self.set_flag(Header.FLAGS_2_1,0,0) # Game requests menu
    
        # We aren't fully implementing the zcode spec yet, so set to 0, as per spec
        self[Header.INTERPRETER_NUMBER] = 0
        self[Header.INTERPRETER_VERSION] = 0

class GameMemory(Memory):
    """ Wrapper around the memory that restricts access to valid locations """
    def __init__(self,memory, static_address,himem_address):
        self._raw_data = memory._raw_data
        self._himem_address = himem_address
        self._static_address = static_address
        self.header = None
    
    def __getitem__(self,idx):
        if idx >= self._himem_address:
            raise MemoryAccessException('Index %d in himem not readable' % idx)
        return super(GameMemory,self).__getitem__(idx)

    def __setitem__(self,idx,value):
        if idx >= self._static_address or (idx < Header.HEADER_SIZE and idx != Header.FLAGS_2):
            raise MemoryAccessException('Index %d in header not writeable to game' % idx)
        super(GameMemory,self).__setitem__(idx,value)        

    def set_flag(self,idx,bit,value):
        if idx == Header.FLAGS_2 and bit > 2:
            raise MemoryAccessException('Bit %d of index %d not writeable to game' % (bit,idx))
        super(GameMemory,self).set_flag(idx,bit,value)

class Routine(object):
    """ Context for a routine in memory """
    def __init__(self,memory,idx,version,nolocals=False):
        """ Initialize this routine from location idx at the memory passed in """
        self.routine_start = idx
        self.version=version
        if not nolocals:
            var_count = memory[idx]
            if var_count < 0 or var_count > 15:
                raise Exception('Invalid number %s of local vars for routine at index %s' % (var_count,idx))
            # 5.2.1
            idx+=1
            self.local_vars = [0] * var_count
            if version < 5:
                for i in range(0,var_count):
                    self.local_vars = memory.word(idx)
                    idx+=2
        self.memory = memory
        self.idx = idx  

    def instruction(self,idx):
        """ Return the current instruction pointed to by the given index"""
        return Instruction(self.memory,idx,self.version)

    def current_instruction(self):
        """ Return the current instruction pointed to by this routine """
        return self.instruction(self.idx)

class OutputStream(object):
    """ See section 8 """
    def __init__(self):
        # 7.2 Buffered streams word wrap
        self.is_active = False
        self.is_buffered = False

    def print_str(self,txt):
        """ Print ascii to the stream """
        pass

    def new_line(self):
        """ Output a newline to the stream """
        pass

    def print_char(self,chr):
        """ Output ZSCII char """
        pass

    def set_buffer(self,b):
        """ Set buffering on/off """
        self.is_buffered = b == True

class OutputStreams(object):
    """ See section 8. Wraps the various output streams """
    SCREEN = 0
    TRANSCRIPT = 1
    ZMACHINE = 2
    SCRIPT = 3

    def __init__(self,screen,transcript,zmachine,script=None):
        self.streams = [screen,transcript]
        if zmachine.header.version > 3:
            self.streams.append(ZMachineStream(zmachine))
            self.streams.append(script)

    def set_screen_stream(self,stream):
        self.streams[OutputStreams.SCREEN] = stream

class ZMachine(object):
    """ Contains the entirity of the state of the interpreter. It does not initialize in a valid state,
        is divided into multiple objects """
    MIN_FILE_SIZE = 64  # Minimum size of a story file, in bytes

    def __init__(self):
        self.header = None
        self.global_variables = None
        self.dictionary = None
        self.object_tree = None
        self.program_counter = 0   # Address of the current routine.
        self.stack = []            # Global stack, represented as a list
        self._raw_data = []
        self.game_memory = None # Protected memory interface for use by game
        self.himem_address = 0
        self.rng = RNG()
        self.output_streams=None
        self.reset()

    def reset(self):
        self.rng.enter_random_mode()
        if self.header:
            self.header.reset()

    @property
    def raw_data(self):
        """ Return the raw data for the currently loaded story file """
        return self._raw_data

    @raw_data.setter
    def raw_data(self,value):
        """ Set the story data for this file. This will reset the header. """
        self._raw_data = Memory(value)
        if len(value) < ZMachine.MIN_FILE_SIZE:
            raise StoryFileException('Story file is too short')
        self.header = Header(self._raw_data[0:ZMachine.MIN_FILE_SIZE])
        self.header.reset()
        self.dictionary = Dictionary(self.raw_data, self.header.dictionary_address)
        self.game_memory = GameMemory(self._raw_data,
                                      self.header.static_memory_address,
                                      self.header.himem_address)
        # Program counter default points to first routine. 
        if self.header.version == 6:   
            self.routines = [Routine(self._raw_data,
                    self.header.main_routine_addr * self._packed_address_multiplier()
                    ,self.header.version)]
        else:
            self.routines =[Routine(self._raw_data,
                    self.header.main_routine_addr,
                    self.header.version,
                    nolocals=True)]
        # some early files have no checksum -- skip the check in that case
        if self.header.checksum and self.header.checksum != self.calculate_checksum():
            raise StoryFileException('Checksum of %.8x does not match %.8x' % (self.header.checksum, self.calculate_checksum()))

    def set_streams(self,screen_stream,transcript_stream,script_stream):
        # Initialize our output streams with the provided streams        
        self.output_streams = OutputStreams(screen_stream,transcript_stream,self,script_stream)
    
    def initialize(self,data,screen_stream,transcript_stream,script_stream):
        """ Initialize this Zmachine with all information ready to play the game """
        self.raw_data = data
        self.set_streams(screen_stream,transcript_stream,script_stream)

    def calculate_checksum(self):
        """ Return the calculated checksum, which is the unsigned sum, mod 65536
            of all bytes past 0x0040 """
        return sum(self._raw_data[0x40:]) % 65536

    def get_ztext(self):
        """ Return the a ztext processor for this interpreter """
        return ZText(version=self.header.version,get_abbrev_f=lambda x:Memory([0x80,0]))

    def get_memory(self,start_addr,end_addr):
        """ Return a chunk of memory """
        if end_addr < start_addr:
            raise ZMachineException('get_memory called with end_addr %s smaller than start_addr %s' % (end_addr,start_addr))
        return Memory(self._raw_data[start_addr:end_addr])

    def _packed_address_multiplier(self):
        if self.header.version > 3:
            return 4
        return 2

    def packed_address(self,idx):
        return self._raw_data.packed_address(idx,self._packed_address_multiplier())
    
    def current_routine(self):
        """ Return the routine at the top of the stack """
        return self.routines[-1]
    
    def instructions(self):
        instructions = []
        routine = self.current_routine()
        offset = routine.idx
        
        for i in range(0,5):
            instruction = routine.instruction(offset)
            instructions.append((instruction,offset))
            offset += instruction.offset
        
        return instructions
 
    def step(self):
        """ Execute the intruction at the PC in the current routine context, then move PC based on returned offset """
        pass
