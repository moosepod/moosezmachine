""" See http://inform-fiction.org/zmachine/standards/z1point1/index.html for a definition of the Z-Machine
    See README.md for a summary of architecture 
"""
import random
import os

from zmachine.memory import Memory,BitArray
from zmachine.text import ZText
from zmachine.dictionary import Dictionary
from zmachine.instructions import read_instruction

# First global variable in the variable numbering system
GLOBAL_VAR_START = 0x10

class StoryFileException(Exception):
    """ Thrown in cases where a story file is invalid """
    pass

class MemoryAccessException(Exception):
    """ Thrown in cases where a game attempts to access memory it shouldn't """
    pass

class InterpreterException(Exception):
    """ General exception in handling by the interpreter """
    pass

class QuitException(Exception):
    """ Thrown when its time to quit the game """
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
    def split_window(self,lines):
        raise Exception('split_window is not implemented')

    def set_window(self,window_id):
        raise Exception('set_window is not implemented')

    def supports_screen_splitting(self):
        return False

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
    def __init__(self,data,force_version=0):
        self.force_version = force_version
        super(Header,self).__init__(data)
        if self.version > Header.MAX_VERSION:
            raise StoryFileException('Story file version %d is not supported.' % self.version)

    @property
    def version(self):
        if self.force_version:
            return self.force_version
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
    
    @flag_screen_splitting_available.setter
    def flag_screen_splitting_available(self,val):
        return self.set_flag(Header.FLAGS_1,5,val)

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
    
        self[Header.INTERPRETER_NUMBER] = 1
        self[Header.INTERPRETER_VERSION] = ord('0')

    def set_debug_mode(self):
        """ Force the version number in the header and some other flags. Used when running against czech or other
            test files """
        self[Header.REVISION_NUMBER] = 1
        self[Header.REVISION_NUMBER+1] = 0
        self.set_flag(Header.FLAGS_1,5,1) # Screen splitting not available
        self.set_flag(Header.FLAGS_1,6,1) # Font is not variable width

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
    def __init__(self,memory,globals_address,routine_start,return_to_address,store_to,version,local_vars):
        """ Initialize this routine from location idx at the memory passed in """
        self.routine_start = routine_start
        self.version=version
        self.globals_address = globals_address
        self.local_variables = []
        idx = self.routine_start
        if local_vars != None: 
            # First "routine" in earlier story file versions has no locals
            var_count = memory[idx] or len(local_vars)
            if var_count < 0 or var_count > 15:
                raise Exception('Invalid number %s of local vars for routine at index %s' % (var_count,idx))
            # 5.2.1
            idx+=1
            self.local_variables = [0] * var_count
            if version < 5:
                for i in range(0,var_count):
                    self.local_variables[i] = memory.word(idx)
                    idx+=2
            for i,val in enumerate(local_vars):
                self.local_variables[i] = val

        self.store_to = store_to
        self.return_to_address = return_to_address
        self.stack = []
        self.memory = memory
        self.code_starts_at = idx

    def __len__(self):
        # Always return 255 possible variables
        return 255

    def __getitem__(self,key):
        """ Return the value of the numbered variable. 16->255 are globals, 1-15 are the current routine's locals,
            and 0 is push/pull on the stack """
        key = int(key)
        if key < 0 or key > 255:
            raise InterpreterException('Var %d is out of range 0 to x to 255' % key)
        if key == 0:
            return self.pop_from_stack()
        elif key < GLOBAL_VAR_START:
            local_var = key - 1
            if local_var >= len(self.local_variables):
                return 0
            return self.local_variables[local_var]
        else:
            return self.memory.word(self.globals_address+((key-GLOBAL_VAR_START)*2))
        return None

    def __setitem__(self,key,val):
        """ Write a byte to the var with the given number. See get_var """
        key = int(key)
        if key < 0 or key > 255:
            raise InterpreterException('Var %d is out of range 0 to x to 255' % key)
        if key == 0:
            self.push_to_stack(val)
        elif key < GLOBAL_VAR_START:
            local_var = key - 1
            if local_var >= len(self.local_variables):
                raise InterpreterException('Reference to local var %d when only %d local vars' % (local_var,len(self.local_variables)))
            self.local_variables[local_var] = val
        else:
            self.memory.set_word(self.globals_address+((key-GLOBAL_VAR_START)*2), val)

    def peek_stack(self):
        if len(self.stack):
            return self.stack[-1]
        return None

    def get_nth_global(self,global_id):
        """ Return the 0-based global. """
        return self[GLOBAL_VAR_START+global_id]

    def set_nth_global(self,global_id,val):
        """ Set the 0-based global. """
        self[GLOBAL_VAR_START+global_id] = val

    def push_to_stack(self,val):
        self.stack.append(val)

    def set_stack(self,val):
        # Set last element of stack to the value
        self.stack[-1] = val

    def pop_from_stack(self):
        try:
            return self.stack.pop()
        except IndexError:
            raise InterpreterException('Cannot pop from empty stack')

class ObjectTableManager(object):
    """ Handles the object table (see section 12.1). Note that requests to the table pass through, since we don't
        know for sure where the object table ends.

        This abstraction needs to be refactored. The original intent was to organize the data in python dicts/lists,
        but enough of the instructions work directly on addresses this proved messy to work around. 
        """
    PROPERTY_ADDRESS_OFFSET=7
    PARENT_OFFSET=4
    SIBLING_OFFSET=5
    CHILD_OFFSET=6

    def __init__(self,story):
        self.version = story.header.version
        self.game_memory = story.game_memory
        self.object_table_address = story.header.object_table_address
        self.reset()

    def reset(self):
        self.objects_start_address = self.object_table_address
        self._load_defaults()

    def _load_defaults(self):
        """ Load the property defaults table. See 12.2 """
        if self.version < 4:
            num_words = 31
        else:
            num_words = 63
        self.property_defaults = []
        for i in range(0,num_words):
            self.property_defaults.append(self.game_memory.word(self.objects_start_address))
            self.objects_start_address+=2

    def get_default_property(self,property_number):
        return self.property_defaults[property_number-1]

    def _object_record_size(self):
        if self.version < 4:
            return 9
        return None

    def estimate_number_of_objects(self):
        """ Grab the first object and use its property table start as the assumed end of the
            object table, the work backwards. No gurantee to work! """
        first_obj = self[1]
        addr = first_obj['property_address']
        count = (addr - self.objects_start_address)/self._object_record_size()
        if count > 255 and self.version < 4:
            return 0 # Something's wrong, just return no objects
        return int(count)

    def _find_attribute_start_byte(self,object_number,attribute_number):
        """ Given a start address and an attribute number, return the byte address and relative
            attribute number. For example, attribute 0 will return start_addr,0 while attribute 8 will
            return start_addr+1,0 """
        address = self._obj_start_addr(object_number)
        if attribute_number > 31:
            raise StoryFileException('Request to test invalid attribute number %s on object %s' % (attribute_number,object_number))

        while attribute_number > 7:
            address+=1
            attribute_number -= 8

        return address,attribute_number

    def test_attribute(self,object_number,attribute_number):
        """ Return true if attribute # attr_number is set on object number object_number """
        address,attribute_number = self._find_attribute_start_byte(object_number,attribute_number)
        val = self.game_memory[address]
        return (val >> (7-attribute_number)) & 0x01 == 1
 
    def set_attribute(self,object_number,attribute_number,new_val):
        """ Set # attr_number is set on object number object_number to new_val (True/False)"""
        address,attribute_number = self._find_attribute_start_byte(object_number,attribute_number)
        val = self.game_memory[address]
        if new_val:
            val = val |  (0x80 >> attribute_number)
        else:
            val = val & ((0x80 >> attribute_number) ^ 0xff)
        self.game_memory[address] = val

    def is_sibling_of(self,sibling_obj_id,obj_id):
        """ Return True of obj is the sibling of obj """
        obj = self[obj_id]
        return obj['sibling'] == sibling_obj_id

    def is_child_of(self,child_obj_id,parent_obj_id):
        """ Return True if child_obj is child of parent_obj """
        obj = self[child_obj_id]
        return obj['parent'] == parent_obj_id

    def remove_obj(self,obj_id):
        """ Remove this objects from its parent (leaving its children) """
        obj_start_addr = self._obj_start_addr(obj_id)
        
        # need to identify this object's previous sibling, if any, and link to next sibling
        obj = self[obj_id]
        parent_obj = obj['parent']
        if not parent_obj:
            return
        parent_obj_start_addr = self._obj_start_addr(obj_id)
        child_obj_id = self[parent_obj]['child']
        if child_obj_id == obj_id:
            self.game_memory[parent_obj_start_addr+ObjectTableManager.CHILD_OFFSET] = obj['sibling']
        else:
           previous_obj_id = None
           while child_obj_id:
            if child_obj_id == obj_id:
                addr = self._obj_start_addr(previous_obj_id)
                self.game_memory[addr+ObjectTableManager.SIBLING_OFFSET] = obj['sibling']
                break
            else:
                previous_obj_id = child_obj_id
                child_obj_id = self[child_obj_id]['sibling']

        # Now remove this obj from parent
        self.game_memory[obj_start_addr+ObjectTableManager.PARENT_OFFSET] = 0
        self.game_memory[obj_start_addr+ObjectTableManager.SIBLING_OFFSET] = 0


    def insert_obj(self,obj_id,parent_id):
        """ Insert the obj obj_id at the front of parent_id """
        obj = self[parent_id]
        if obj['child']:
            old_child_id = obj['child']
        else:
            old_child_id = 0

        start_addr = self._obj_start_addr(obj_id)
        self.game_memory[start_addr+ObjectTableManager.PARENT_OFFSET] = parent_id
        self.game_memory[start_addr+ObjectTableManager.SIBLING_OFFSET] = old_child_id

        start_addr = self._obj_start_addr(parent_id)
        self.game_memory[start_addr+ObjectTableManager.CHILD_OFFSET] = obj_id

    def get_next_prop(self,obj_id, property_id):
        """ Find the property after the identified property. If 0, first property. If property
            is last property, return 0. If no such property, error """
        obj = self[obj_id]

        if property_id == 0:
            return obj['property_ids_ordered'][0]

        if property_id and not obj['properties'].get(property_id):
            raise InterpreterException('No property %d for object id %d' % (property_id, obj_id))

        return_next = False
        for i,tmp_id in enumerate(obj['property_ids_ordered']):
            if return_next:
                return tmp_id
            if tmp_id == property_id:
                return_next = True

        return 0

    def get_property_address(self,obj_id, property_id):
        """ Return the address of the given property """
        obj = self[obj_id]
        start_addr = 0
        try:
            start_addr = obj['properties'][property_id]['address']
        except KeyError:
            start_addr = 0

        return start_addr

    def get_property_length(self, prop_addr):
        """ Return the length of the property starting at the given address """
        size = 0
        if prop_addr == 0:
            return 0
        # Note -- the property length will be one byte _behind_ the property address
        property_number,property_size = self._extract_property_info(prop_addr-1)
        return property_size

    def _extract_property_info(self,prop_addr):
        """ Return the property number and size extracted from size byte at location """
        size_byte = self.game_memory[prop_addr]
        property_number = size_byte & 0x1F
        property_size = ((size_byte & 0xE0) >> 5) + 1 

        return property_number,property_size

    def put_prop(self,obj_id, property_id,value):
        """ Store a property in the property table """
        prop_addr = self.get_property_address(obj_id, property_id)
        if not prop_addr:
            raise InterpreterException("Request to set non-existent property %s of obj %s to %s." % (obj_id, property_id, value))
        prop_len = self.get_property_length(prop_addr)
        prop_addr+=1 # Skip size byte
        if prop_len > 2:
            raise InterpreterException("Request to set non-existent property %s of obj %s to %s for property greater than 2 bytes." % (obj_id, property_id, value))
        elif prop_len == 2:
            self.game_memory.set_word(prop_addr,value)
        else:
            self.game_memory[prop_addr] = value & 0xFF

    def _get_properties(self, start_addr):
        """ Return the properties at the given address """
        properties = {}
        property_ids_ordered = []

        # 12.4
        text_length = self.game_memory[start_addr]
        start_addr+=1
        short_name_zc = self.game_memory._raw_data[start_addr:start_addr+(text_length*2)]

        start_addr+=text_length*2
        size_byte_addr = start_addr
        size_byte = self.game_memory[size_byte_addr]
        while size_byte:
            start_addr+=1
            property_number,property_size = self._extract_property_info(size_byte_addr)
            data = self.game_memory._raw_data[start_addr:start_addr+property_size]
            # NOte that the property address is the start of the property -- the size byte will be one previous
            properties[property_number] = {'data': data, 'size': property_size, 'address': size_byte_addr+1}
            property_ids_ordered.append(property_number)
            start_addr+=property_size
            size_byte = self.game_memory[start_addr]
            size_byte_addr = start_addr

        return properties,property_ids_ordered,short_name_zc

    def _obj_start_addr(self, object_number):
        return self.objects_start_address + (self._object_record_size() * (object_number-1))

    def is_valid_object_id(self,obj_id):
        if obj_id < 0 or obj_id > 255:
            return False
        return True

    def __getitem__(self,key):
        """ Get the nth object """
        if self.version > 3:
            raise InterpreterException("object table references need to be reworked for later versions, see 12.32")
        
        # 0th object is nothing, we should return no data
        if key == 0:
            return None

        if key > 255:
            return None

        # 12.3.1
        start_addr = self._obj_start_addr(key)  

        property_address = self.game_memory.word(start_addr+ObjectTableManager.PROPERTY_ADDRESS_OFFSET)
        properties,property_ids_ordered,short_name_zc = self._get_properties(property_address)
        obj = {'attributes': BitArray(self.game_memory._raw_data[start_addr:start_addr+4]),
              'parent': self.game_memory[start_addr+ObjectTableManager.PARENT_OFFSET], 
              'sibling': self.game_memory[start_addr+ObjectTableManager.SIBLING_OFFSET], 
              'child': self.game_memory[start_addr+ObjectTableManager.CHILD_OFFSET], 
              'property_address': property_address,
              'short_name_zc': short_name_zc,
              'properties': properties,
              'property_ids_ordered': property_ids_ordered
              }
        return obj

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

    def print_zchar(self,chr):
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

    def __init__(self,screen,transcript,script=None):
        self.screen = screen
        self.transcript = transcript
         
    def reset(self,zmachine,ztext):
        self.ztext = ztext 
        self.streams = [self.screen,self.transcript]
        if zmachine.story.header.version > 3:
            self.streams.append(ZMachineStream(zmachine))
            self.streams.append(script)

    def select_stream(self,stream_num):
        if stream_num >= 0 and stream_num < len(self.streams):
            self.streams[stream_num].is_active = True

    def set_screen_stream(self,stream):
        """ Assign the screen stream, setting it active by default """
        self.streams[OutputStreams.SCREEN] = stream
        stream.is_active=True

    def new_line(self):
        """ Pass a new_line call down to all active streams """
        for stream in (s for s in self.streams if s.is_active):
            stream.new_line()

    def print_str(self,txt):
        """ Print the (ascii) string to all active streams """
        for stream in (s for s in self.streams if s.is_active):
            stream.print_str(txt)
 
    def print_zchar(self,ch):
        """ Print the zchar to all active streams """
        text = self.ztext._map_zchar(ch)
        for stream in (s for s in self.streams if s.is_active):
            stream.print_str(text)

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        if self[OutputStreams.SCREEN].is_active:
            self[OutputStreams.SCREEN].show_status(room_name,score_mode=score_mode,hours=hours,minutes=minutes, score=score,turns=turns)
            
    def __getitem__(self,idx):
        return self.streams[idx]

    def __setitem__(self,idx,val):
        self.streams[idx] = val

class InputStream(object):
    def readline(self):
        return None

class InputStreams(object):
    """ See section 10. Handles input """
    KEYBOARD = 0
    FILE = 1

    def __init__(self,keyboard_stream,command_file_stream):
        self.keyboard_stream = keyboard_stream
        self.command_file_stream = command_file_stream
        self.active_stream = None
         
    def reset(self):
        self.active_stream = self.keyboard_stream

    def select_stream(self,stream_id):
        if stream_id == InputStreams.KEYBOARD:
            self.active_stream = self.keyboard_stream
        else:
            self.active_stream = self.command_file_stream

    def readline(self,ztext):
        # Note this expects that the returned characters will be unicode
        zchars = []
        line = self.active_stream.readline()
        if not line:
            return None

        for char in line.lower():
            # Convert unicode to zscii
            zchars.append(ztext.to_zscii(char))

        return zchars
        
class Story(object):
    """ Full copy of the (a) original story file data and (b) current (possibly modifed) memory.
        Provides wrapper interfaces to subsets of the memory, such as the dictionary, header,
        or objects """
    MIN_FILE_SIZE = 64  # Minimum size of a story file, in bytes
    
    def __init__(self,data):
        """ Initalize with story data. Data is not loaded and validated until reset() is called """
        self.header = None
        self.dictionary = None
        self.game_memory = None # Protected memory interface for use by game
        self.object_table = None
        self.himem_address = 0

        # Initial data, stored to allow for resets
        self.story_data = data

        # Raw bytes of memory as a Memory object
        self.raw_data = None
    
        # Will contain the wrapped game memory that provides memory access validation
        self.game_memory = None
        self.rng = RNG()

    def reset(self,force_version=0):
        """ Reset/initialize the game state from the raw game data. Will raise StoryFileException on validation issues. 
            If force version is set, pretend this file is that version.
         """
        self.raw_data = Memory(self.story_data)
        if len(self.story_data) < Story.MIN_FILE_SIZE:
            raise StoryFileException('Story file is too short')
        self._checksum = sum(self.raw_data[0x40:]) % 65536 # Store checksum at this point, since data will change post-load
        self.header = Header(self.raw_data[0:Story.MIN_FILE_SIZE],force_version=force_version)
        self.header.reset()
        self.dictionary = Dictionary(self.raw_data, self.header.dictionary_address)
        self.game_memory = GameMemory(self.raw_data,
                                      self.header.static_memory_address,
                                      self.header.himem_address)

        self.object_table = ObjectTableManager(self)

        # Default mode for RNG is random (see 2.4)
        self.rng.enter_random_mode()

    def calculate_checksum(self):
        """ Return the calculated checksum, which is the unsigned sum, mod 65536
            of all bytes past 0x0040. """
        return self._checksum


class GameState(object):
    def __init__(self,story):
        self.story = story           
    
class SaveHandler(object):
    pass

class RestoreHandler(object):
    pass

class Interpreter(object):
    """ Main interface to the game. Combines Story, GameState, OutputScreens, SaveHandler,
        RestoreHandler. Call reset to start the interpreter. 
    """
    RUNNING_STATE = 0
    WAITING_FOR_LINE_STATE = 1

    def __init__(self,story, output_streams, input_streams, save_handler, restore_handler,screen=None):
        self.story = story
        self.output_streams = output_streams
        self.input_streams = input_streams
        self.save_handler = save_handler
        self.restore_handler = restore_handler
        self.initialized = False
        self.pc = 0 # program counter
        self.state = Interpreter.RUNNING_STATE
        self.screen = screen or Screen()

    def reset(self,force_version=0):
        """ Start/restart the interpreter. Set force_version to make it act like the story file
            is that version
         """
        self.initialized = True
        self.story.reset(force_version=force_version)
        self.pc = self.story.header.main_routine_addr
        self.last_instruction = None
        if self.output_streams:
            self.output_streams.reset(self,self.get_ztext())
        if self.input_streams:
            self.input_streams.reset()
        self.routines = []
        self.state = Interpreter.RUNNING_STATE
        self.call_routine(self.pc,self.pc,None,None)
        if self.screen.supports_screen_splitting():
            self.story.header.flag_screen_splitting_available = 1
        else:
            self.story.header.flag_screen_splitting_available = 0

    def call_routine(self, routine_address, next_address,  store_var,  local_vars):
        """ Add a routine call to the stack from the current program counter """
        new_routine = Routine(self.story.raw_data, 
                                    self.story.header.global_variables_address,
                                    routine_address,
                                    next_address,
                                    store_var,
                                    self.story.header.version,
                                    local_vars)
        self.routines.append(new_routine)
        self.pc = new_routine.code_starts_at 

    def return_from_current_routine(self,return_val):
        """ Pop the call stack and set the return_to variable to return_val. If stack is on last routine,
            throw exception """
        if len(self.routines) == 0:
            raise InterpreterException('Request to return from empty routine at addr %04x' % self.pc)

        return_from_routine = self.routines.pop()
        store_to = return_from_routine.store_to
        self.current_routine()[store_to] = return_val
        self.pc = return_from_routine.return_to_address
    
    def get_ztext(self):
        """ Return the a ztext processor for this interpreter """
        self._check_initialized()
        version = self.story.header.version
        abbrev_address = self.story.header.abbrev_address
        return ZText(version=version,get_abbrev_f=self.get_abbrev)

    def get_abbrev(self, index):
        # 3.3, 1.2.2 (word address = address / 2)
        abbrev_address = self.story.raw_data.word(self.story.header.abbrev_address + (index*2))*2
        return self.story.raw_data[abbrev_address:abbrev_address+20]

    def get_memory(self,start_addr,end_addr):
        """ Return a chunk of memory """
        self._check_initialized()
        if end_addr < start_addr:
            raise InterpreterException('get_memory called with end_addr %s smaller than start_addr %s' % (end_addr,start_addr))
        return Memory(self.story.raw_data[start_addr:end_addr])
        
    def _check_initialized(self):
        if not self.initialized:
            raise InterpreterException('Interpreter is not yet initialized')

    def instruction_at(self,address):
        """ Return the current instruction pointed to by the given address """
        try:    
            return read_instruction(self.story.raw_data,
                            address,
                            self.story.header.version,
                            self.get_ztext())
        except IndexError:
            # Requested instruction past end of memory.
            raise Exception('Request to look for instruction past end of memory at 0x%.4x' % address)
            
    def current_instruction(self):
        """ Return the current instruction """
        return self.instruction_at(self.pc)

    def current_routine(self):
        """ Return the currently running routine (at top of routine stack) """
        return self.routines[-1]

    def step(self):
        """ If in running state, execute the current instruction then increment the program counter.
        If waiting for text, query the input streams for the next line """
        if self.state == Interpreter.WAITING_FOR_LINE_STATE:
            if self._handle_input():
                self.state = Interpreter.RUNNING_STATE

        if self.state == Interpreter.RUNNING_STATE:
            handler_f,description,next_address = self.current_instruction()
            self.last_instruction=description
            result = handler_f(self)
            result.apply(self)

        return self.state

    def instructions(self,how_many):
        """ Return how_many instructions starting at the current instruction """
        instructions = []
        address = self.pc

        for i in range(0,how_many):
            handler_f,description,next_address = self.instruction_at(address)
            instructions.append((description,next_address))
            address = next_address
        
        return instructions
 
    def packed_address_to_address(self,address):
        if self.story.header.version > 3:
            return address * 4
        return address * 2

    def play_sound(self,number,effect,volume,routine):
        # No sound currently supported
        raise Exception('Sound not currently supported')

    def read_and_process(self,text_buffer_addr, parse_buffer_addr):
        if self.story.header.version < 4:
            self.show_status()
        self.state = Interpreter.WAITING_FOR_LINE_STATE
        self._text_buffer_addr = text_buffer_addr
        self._parse_buffer_addr = parse_buffer_addr

    def _handle_input(self):
        ztext = self.get_ztext()

        ### Switch to ZSCII
        # Line will be array of ZASCII chars. Or none if not a complete line yet
        line = self.input_streams.readline(ztext)
        if not line:
            return False

        text_buffer_addr, parse_buffer_addr = self._text_buffer_addr, self._parse_buffer_addr

        # Cap at the number of letters provided in first byte of dest text buffer
        max_letters = self.story.game_memory[text_buffer_addr]-1
        if len(line) > max_letters:
            line = line[0:max_letters]

        # Write our ZSCII to the address, zero terminated
        idx = text_buffer_addr+1
        for zchar in line:
            self.story.game_memory._raw_data[idx] = zchar
            idx+=1
        self.story.game_memory._raw_data[idx] = 0

        # Draw a newline
        self.output_streams.new_line() 

        # Handle parse data
        max_words = self.story.game_memory[parse_buffer_addr]
        idx = parse_buffer_addr+1

        # Tokenize words using separators
        dictionary = self.story.dictionary
        words = dictionary.split(line)

        # write number of words in byte 1
        self.story.game_memory[idx] = len(words)

        # for each word up to max, write
        # (a) two bytes w/ addr of word (0 is missing)
        # (b) byte containing word length then 
        # (c) byte containing index of first letter of this word in the text buffer
        # (d) empty byte
        idx+=1
        for offset, word in words:
            addr = dictionary.lookup(word,ztext)
            if not addr:
                addr = 0
            self.story.game_memory.set_word(idx, addr)
            idx+=2
            self.story.game_memory[idx] = len(word)+1
            idx+=1
            self.story.game_memory[idx] = offset+1
            idx+=1

        return True

    def show_status(self):
        """ Update the statushow_statuss line with our current status """
        # 8.2.2
        routine = self.current_routine()
        current_obj_id = routine.get_nth_global(0)
        if not self.story.object_table.is_valid_object_id(current_obj_id):
            room_name = 'INVALID OBJECT'
        else:
            current_obj = self.story.object_table[current_obj_id]
            room_name = self.get_ztext().to_ascii(current_obj['short_name_zc'])

        if self.story.header.flag_status_line_type == 0:
            # 8.2.3.1
            self.output_streams.show_status(room_name,score_mode=True,score=routine.get_nth_global(1),turns=routine.get_nth_global(2))
        else:
            # 8.2.3.2
            self.output_streams.show_status(room_name,score_mode=False,hours=routine.get_nth_global(1),minutes=routine.get_nth_global(2))

    def quit(self):
        raise QuitException()

    def restart(self):
        raise InterpreterException('Restart not implemented')

    def save(self,branch_offset,next_address):
        """ Handle a save. Branch info is used to move pc post save """
        raise InterpreterException('Save not implemented')

    def debug(self,msg):
        """ Debug logging """
        self.output_streams.print_str('>>> %s\n' % msg)

    def restore(self,branch_offset,next_address):
        """ Handle a restore. Branch info is passed in but ignored in version 3 """
        raise InterpreterException('Restore not implemented')

    def push_game_stack(self,val):
        self.current_routine().push_to_stack(val)

    def pop_game_stack(self):
        return self.current_routine().pop_from_stack()

    def peek_game_stack(self):
        return self.current_routine().peek_stack() 
