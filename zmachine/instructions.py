""" Object representation of opcodes, and classes to handle the actual instructions 

    Using OOP for the intructions is very inefficient but makes writing the reference implementation easy. 

    See http://inform-fiction.org/zmachine/standards/z1point0/sect04.html
"""

from enum import Enum

class InstructionType(Enum):
    zeroOP = 1
    oneOP  = 2
    twoOP  = 3
    varOP  = 4

class InstructionForm(Enum):
    long_form     = 1
    extended_form = 2
    short_form    = 3
    variable_form = 4

class Instruction(object):
    def __init__(self,memory=None):
        if memory:
            self.init_from_memory(memory)
        else:
            self.instruction_type = None
            self.opcode = 0
            self.opcode_byte = 0
            self.instruction_form = None
            self.opcode_number = 0
            self.operands = []
            
    def init_from_memory(self,memory,version=3):
        """ Init this instruction object from the provided block of memory. Assume byte 0 is the first byte of the instruction
            Note number of bytes varies based on instruction """ 
        # If top two bits are 11, variable form. If 10, short. 
        # If opcode is BE, form is extended. Otherwise long.
        b1 = memory[0]
        b2 = memory[1]
        self.opcode_byte=b1

        self.operands = [] # List of operands (if any)
        self.offset = 0 # Offset, in bytes, to move PC
        self.store_to = None # Variable # to store the resulting value to

        # 4.3
        if b1 == 0xbe and version >= 5:
            # 4.3.4
            self.instruction_form = InstructionForm.extended_form
            self.instruction_type = InstructionType.varOP
            self.opcode_number = b2
        elif b1 >> 6 == 3:
            # 4.3.3
            self.instruction_form = InstructionForm.variable_form
            if (b1 & 0x20) >> 4 == 1: 
                self.instruction_type = InstructionType.varOP
            else:
                self.instruction_type = InstructionType.twoOP
            self.opcode_number = b1 & 0x1F  
        elif b1 >> 6 == 2:
            # 4.3.1 
            self.instruction_form = InstructionForm.short_form
            if (b1 & 0x30) >> 4  == 3: 
                self.instruction_type = InstructionType.zeroOP
            else:
                self.instruction_type = InstructionType.oneOP
            self.opcode_number = b1 & 0x1F 
        else:
            # 4.3.2
            self.instruction_form = InstructionForm.long_form
            self.instruction_type = InstructionType.twoOP
            self.opcode_number = b1 & 0x1F # Bottom 5 bits are opcode #        
    def __str__(self):
        str = u'Opcode byte: %x\n' % self.opcode_byte
        str += u'Instruction form: %s' % self.instruction_form 
        return str
