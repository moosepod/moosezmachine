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
            self.instruction_type = InstructionType.zeroOP
            self.opcode = 0
            self.opcode_byte = 0
            self.iform = InstructionForm.long_form

    def init_from_memory(self,memory):
        """ Init this instruction object from the provided block of memory. Assume byte 0 is the first byte of the instruction
            Note number of bytes varies based on instruction """ 
        # If top two bits are 11, variable form. If 10, short. 
        # If opcode is BE, form is extended. Otherwise long.
        b1 = memory[0]
        self.opcode_byte=b1
        if b1 == 0xbe:
            self.instruction_form = InstructionForm.extended_form
        elif b1 >> 6 == 3: # 0x11 top bits
            self.instruction_form = InstructionForm.variable_form
        elif b1 >> 6 == 2 : # 0x10 top bits
            self.instruction_form = InstructionForm.short_form
        else:
            self.instruction_form = InstructionForm.long_form
                 
    def __str__(self):
        str = u'Opcode byte: %x\n' % self.opcode_byte
        str += u'Instruction form: %s' % self.instruction_form 
        return str
