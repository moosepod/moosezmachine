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

class OperandType(Enum):
    large_constant = 1
    small_constant = 2
    variable = 3
    omitted = 4

def operand_from_bitfield(bf):
    # 4.2
    if bf == 3:
        return OperandType.omitted
    elif bf == 2:
        return OperandType.variable
    elif bf == 1:
        return OperandType.small_constant
    elif bf == 0:
        return OperandType.large_constant
    return None

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
        idx = 1
        b1 = memory[0]
        b2 = memory[1]
        self.opcode_byte=b1
        self.operands = [] # List of operands (if any)
        self.offset = 0 # Offset, in bytes, to move PC
        self.store_to = None # Variable # to store the resulting value to
        self.zchars = [] # If this instruction works with zcodes, store them here
        
        # 4.3
        if b1 == 0xbe and version >= 5:
            # 4.3.4 (Extended form)
            self.instruction_form = InstructionForm.extended_form
            self.instruction_type = InstructionType.varOP
            self.opcode_number = b2
            # 4,4,3
            idx+=1
            b2 = mem[idx]
            idx+=1
            self.operands = [
                operand_from_bitfield((b2 & 0xC0) >> 6),
                operand_from_bitfield((b2 & 0x30) >> 4),
                operand_from_bitfield((b2 & 0x0C) >> 2),
                operand_from_bitfield(b2 & 0x03)
            ]
        elif b1 >> 6 == 3:
            # 4.3.3 (Variable form)
            self.instruction_form = InstructionForm.variable_form
            if (b1 & 0x20) >> 4 == 1: 
                self.instruction_type = InstructionType.varOP
            else:
                self.instruction_type = InstructionType.twoOP
            self.opcode_number = b1 & 0x1F
            # 4,4,3
            idx+=1
            self.operands = [
                operand_from_bitfield((b2 & 0xC0) >> 6),
                operand_from_bitfield((b2 & 0x30) >> 4),
            ]
            if self.instruction_type == InstructionType.varOP:
                self.operands.extend([
                    operand_from_bitfield((b2 & 0x0C) >> 2),
                    operand_from_bitfield(b2 & 0x03)         
                ])
        elif b1 >> 6 == 2:
            # 4.3.1 (Short form)
            self.instruction_form = InstructionForm.short_form
            bf45 = (b1 & 0x30) >> 4 # Bits 4 & 5
            if bf45  == 3: 
                self.instruction_type = InstructionType.zeroOP
            else:
                self.instruction_type = InstructionType.oneOP
            self.opcode_number = b1 & 0x0F
            # 4.4.1
            self.operands = [operand_from_bitfield(bf45)]  
        else:
            # 4.3.2 (Long form)
            self.instruction_form = InstructionForm.long_form
            self.instruction_type = InstructionType.twoOP
            self.opcode_number = b1 & 0x1F # Bottom 5 bits are opcode #        
            self.operands = [OperandType.small_constant,OperandType.small_constant]
            # 4.4.2
            # If bit 6 is 1, first operand is large. If bit 5 is 1, second operand is large.
            if b1 & 0x40: self.operands[0] = OperandType.large_constant
            if b1 & 0x20: self.operands[1] = OperandType.large_constant
        
        # Find opcode handler
        self.handler = OPCODE_HANDLERS.get((self.instruction_type, self.opcode_number),
                                            OpcodeHandler(self.opcode_number,str(self.opcode_number),False,False))

        # 4.5
        tmp = []
        for i,optype in enumerate(self.operands):
            val = 0
            if optype == OperandType.small_constant:
                val = memory[idx]
                idx+=1
            elif optype == OperandType.large_constant:
                val = memory.word(idx)
                idx+=2
            elif optype == OperandType.variable:
                val = memory[idx]
                idx+=1
            elif optype == OperandType.omitted:
                # 4.4.3
                # Omit any vars after an ommitted type
                break
            tmp.append(val)
        self.operands=tmp
        # 4.6
        if self.handler.is_store:
            self.store_to = memory[idx]
            idx+=1

        # Set our offset to the current memory idx
        self.bytestr = ' '.join('%02x' % b for b in memory[0:idx])
        self.bytestr += ' (%s)' % bin(memory[0])
        self.offset = idx

    def __str__(self):
        st = self.bytestr
        st += '\n'
        st += "%s:%s" % (self.instruction_type, self.handler.description)
        if self.operands:
            st += ' [%s]' % ' '.join(['%02x' % x for x in self.operands])
        if self.store_to:
            st += ' -> %s' % self.store_to
        st += ' (%02x)' % self.offset
        return st

class OpcodeHandler(object):
    def __init__(self, name, description, is_break, is_store):
        self.name = name
        self.description = description
        self.is_break = is_break
        self.is_store = is_store

# 14.1
OPCODE_HANDLERS = {(InstructionType.twoOP, 22): OpcodeHandler('mul','mul a b -> (result)',False,True)}

