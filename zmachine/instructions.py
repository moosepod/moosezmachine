""" Object representation of opcodes, and classes to handle the actual instructions 

    Using OOP for the intructions is very inefficient but makes writing the reference implementation easy. 

    See http://inform-fiction.org/zmachine/standards/z1point0/sect04.html
"""

from enum import Enum
from zmachine.text import ZText

class InstructionType(Enum):
    zeroOP = '0OP'
    oneOP  = '1OP'
    twoOP  = '2OP'
    varOP  = 'VAR'

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
    def __init__(self,memory,idx,version):
        """ Init this instruction object from the provided block of memory. """
        # If top two bits are 11, variable form. If 10, short. 
        # If opcode is BE, form is extended. Otherwise long.
        start_idx=idx
        b1 = memory[idx]
        b2 = memory[idx+1]
        idx+=1
        self.opcode_byte=b1
        self.operands = [] # List of operands (if any)
        self.offset = 0 # Offset, in bytes, to move PC
        self.store_to = None # Variable # to store the resulting value to
        self.zchars = [] # If this instruction works with zcodes, store them here
        self.literal_string = None # Ascii version of zchars, if any

        # 4.3
        if b1 == 0xbe and version >= 5:
            # 4.3.4 (Extended form)
            self.instruction_form = InstructionForm.extended_form
            self.instruction_type = InstructionType.varOP
            self.opcode_number = b2
            # 4,4,3
            b2 = memory[idx]
            idx+=1
            self.operands = [
                operand_from_bitfield((b2 & 0xC0) >> 6),
                operand_from_bitfield((b2 & 0x30) >> 4),
                operand_from_bitfield((b2 & 0x0C) >> 2),
                operand_from_bitfield(b2 & 0x03)
            ]
        elif (b1 & 0xC0 )>> 6 == 3:
            # 4.3.3 (Variable form)
            self.instruction_form = InstructionForm.variable_form
            if (b1 & 0x20) >> 5 == 1: 
                self.instruction_type = InstructionType.varOP
            else:
                self.instruction_type = InstructionType.twoOP
            self.opcode_number = b1 & 0x1F
            idx+=1
            # 4,4,3
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
                                            OpcodeHandler(self.opcode_number,str(self.opcode_number),False,False,False))

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
       
        if self.handler.literal_string:
            zchar_start_idx = idx
            ztext = ZText(version=version,get_abbrev_f=lambda x: [6,6,6])
            self.zchars = []
            done = False
            while not done:
                zchars_tmp,done = ztext.get_zchars_from_memory(memory,idx)
                idx+=2
                self.zchars.extend(list(zchars_tmp))            
            self.literal_string = ztext.to_ascii(memory,zchar_start_idx,0)

        # 4.6
        if self.handler.is_store:
            self.store_to = memory[idx]            
            idx+=1

        # 4.7
        self.next_instruction = idx
        if self.handler.is_branch:
            b = memory[idx]
            idx+=1
            if (b & 0x80) >> 7:
                branch_if_true = True
            else:
                branch_if_true = False
            if (b & 0x40) >> 6:
                # Bit 6 set, offset is bottom 6 bits of byte
                self.offset = b & 0x3F
            else:
                # Bit 6 not set, offset is bottom 6 bits + next byte
                next_byte = memory[idx]
                idx += 1
                self.offset = ((b & 0x3f) << 8) | next_byte 
        
        # Store the bytes used in this instruction for debugging
        self.bytestr = ' '.join('%02x' % b for b in memory[start_idx:idx])

    def execute(self,routine):
        self.handler.execute(routine)

    def __str__(self):
        st = '%s\n' % self.bytestr
        st += "%s:%s" % (self.instruction_type, self.handler.description)
        if self.operands:
            st += ' [%s]' % ' '.join(['%02x' % x for x in self.operands])
        if self.store_to:
            st += ' -> %s' % self.store_to
        if self.literal_string:
            st += '"%s"' % self.literal_string
        st += '\n'
        return st

class OpcodeHandler(object):
    def __init__(self, name, description, is_branch, is_store,literal_string):
        self.name = name
        self.description = description
        self.is_branch = is_branch
        self.is_store = is_store
        self.literal_string = literal_string

    def execute(self, routine):
        """ Execute this instruction in the context of the provided routine """
        pass

# 14.1
OPCODE_HANDLERS = {
(InstructionType.twoOP, 22): OpcodeHandler('mul','mul a b -> (result)',False,True,False),
(InstructionType.twoOP,5):   OpcodeHandler('inc_chk','inc_chk (variable) value ?(label)',True,False,False),

(InstructionType.zeroOP,2):  OpcodeHandler('print', 'print (literal-string)',False,False,True),
(InstructionType.zeroOP,11): OpcodeHandler('new_line','new_line',False,False,False),

(InstructionType.varOP,0): OpcodeHandler('call','call routine ...0 to 3 args... -> (result)',False,True,False)
}

