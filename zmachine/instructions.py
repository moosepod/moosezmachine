""" Object representation of opcodes, and classes to handle the actual instructions 

    Using OOP for the intructions is very inefficient but makes writing the reference implementation easy. 

    See http://inform-fiction.org/zmachine/standards/z1point0/sect04.html
"""

from enum import Enum
from zmachine.text import ZText

class InstructionException(Exception):
    pass

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

class IntepreterAction(Enum):
    next_instruction = 1 # Jump to next instruction
    return_val       = 2 # Return from the current routine. Next val in tuple is return value
    jump_abs         = 3 # Jump to an absolute address. Next val in tuple is address
    call             = 4 # Call routine. Next val in tuple is value.

class OperandTypeHint(Enum):
    """ Declared with opcode handlers to give hints on how to handle/display operands """
    unsigned = 1
    signed = 2
    address = 3
    packed_address = 4
    variable = 5

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

def extract_opcode(memory,address):
    # Section 4.3
    b1 = memory[address]
    b2 = memory[address+1]
    address+=1
    opcode_byte=b1
    operands = [] # List of operands (if any)

    if b1 == 0xbe and version >= 5:
        # 4.3.4 (Extended form)
        instruction_form = InstructionForm.extended_form
        instruction_type = InstructionType.varOP
        opcode_number = b2
        # 4,4,3
        b2 = memory[address]
        address+=1
        operands = [
            operand_from_bitfield((b2 & 0xC0) >> 6),
            operand_from_bitfield((b2 & 0x30) >> 4),
            operand_from_bitfield((b2 & 0x0C) >> 2),
            operand_from_bitfield(b2 & 0x03)
        ]
    elif (b1 & 0xC0 )>> 6 == 3:
        # 4.3.3 (Variable form)
        instruction_form = InstructionForm.variable_form
        if (b1 & 0x20) >> 5 == 1: 
            instruction_type = InstructionType.varOP
        else:
            instruction_type = InstructionType.twoOP
        opcode_number = b1 & 0x1F
        address+=1
        # 4,4,3
        operands = [
            operand_from_bitfield((b2 & 0xC0) >> 6),
            operand_from_bitfield((b2 & 0x30) >> 4),
        ]
        if instruction_type == InstructionType.varOP:
            operands.extend([
                operand_from_bitfield((b2 & 0x0C) >> 2),
                operand_from_bitfield(b2 & 0x03)         
            ])
    elif b1 >> 6 == 2:
        # 4.3.1 (Short form)
        instruction_form = InstructionForm.short_form
        bf45 = (b1 & 0x30) >> 4 # Bits 4 & 5
        if bf45  == 3: 
            instruction_type = InstructionType.zeroOP
        else:
            instruction_type = InstructionType.oneOP
        opcode_number = b1 & 0x0F
        # 4.4.1
        operands = [operand_from_bitfield(bf45)]  
    else:
        # 4.3.2 (Long form)
        instruction_form = InstructionForm.long_form
        instruction_type = InstructionType.twoOP
        opcode_number = b1 & 0x1F # Bottom 5 bits are opcode #        
        operands = [OperandType.small_constant,OperandType.small_constant]
        # 4.4.2
        # If bit 6 is 1, first operand is large. If bit 5 is 1, second operand is large.
        if b1 & 0x40: operands[0] = OperandType.large_constant
        if b1 & 0x20: operands[1] = OperandType.large_constant
    
    return address,instruction_form, instruction_type,  opcode_number,operands

def process_operands(operands, handler):
    # Section 4.5
    tmp = []
    for i,optype in enumerate(operands):
        val = 0
        if optype == OperandType.small_constant:
            val = memory[address]
            address+=1
        elif optype == OperandType.large_constant:
            val = memory.word(address)
            address+=2
        elif optype == OperandType.variable:
            val = -1 * memory[address]
            address+=1
        elif optype == OperandType.omitted:
            # 4.4.3
            # Omit any vars after an ommitted type
            break
        tmp.append(val)
    return address, tmp

def extract_literal_string(memory,address):
    zchar_start_address = address
    ztext = ZText(version=version,get_abbrev_f=lambda x: [6,6,6])
    zchars = []
    done = False
    while not done:
        zchars_tmp,done = ztext.get_zchars_from_memory(memory,address)
        address+=2
        zchars.extend(list(zchars_tmp))            
    return address, ztext.to_ascii(memory,zchar_start_address,0)   

def extract_branch_offset(memory,address):
    b = memory[address]
    address+=1
    if (b & 0x80) >> 7:
        branch_if_true = True
    else:
        branch_if_true = False
    if (b & 0x40) >> 6:
        # Bit 6 set, offset is bottom 6 bits of byte
        branch_offset = b & 0x3F
    else:
        # Bit 6 not set, offset is bottom 6 bits + next byte
        next_byte = memory[address]
        address += 1
        branch_offset = ((b & 0x3f) << 8) | next_byte 
    return address, branch_offset

def read_instruction(self,memory,address,version):
    """ Read the instruction at the given address, and return a handler function and summary """
    # If top two bits are 11, variable form. If 10, short. 
    # If opcode is BE, form is extended. Otherwise long.
    start_address=address

    offset = 0 # Offset, in bytes, to move PC
    store_to = None # Variable # to store the resulting value to
    zchars = [] # If this instruction works with zcodes, store them here
    literal_string = None # Ascii version of zchars, if any

    address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(memory,address)
    
    # Find opcode handler
    handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
    if not handler:
        raise InstructionException('Unknown opcode %s, %s' % (instruction_type, opcode_number)) 

    operands = process_operands(operands, handler)
   
    if handler.get('literal_string'):
        address,literal_string = extract_literal_string(memory,address)
        
    # 4.6
    if handler.get('store'):
        store_to = memory[address]            
        address+=1

    # 4.7
    branch_offset = None
    if handler.get.('branch'):
        address, branch_offset = extract_branch(memory,address)

        branch_offset+=start_address
    next_address = address

    # Store the bytes used in this instruction for debugging
    bytestr = ' '.join('%02x' % b for b in memory[start_address:address])

    # Create the execution function for this instruction
    f = lambda interpreter: self.handler.execute(interpreter, operands, next_address,store_to,store_to,branch_if_true)

    # Setup text version for debuggging
    st = '%s\n' % self.bytestr
    st += "%s:%s" % (self.instruction_type, self.handler.description)
    if self.operands:
        st += ' [%s]' % ' '.join(['%02x' % x for x in self.operands])
    if self.store_to:
        st += ' -> %s' % self.store_to
    if self.literal_string:
        st += '"%s"' % self.literal_string
    st += '\n'
    
    return f, bytestr, st

### Text

def op_newline(interpreter,operands,next_address,store_to,branch_offset,branch_if_true):
    interpreter.output_streams.new_line()
    return HandlerResult.next_instruction,None

def op_print(interpreter,operands,next_address,store_to,branch_offset,branch_if_true):
    interpreter.output_streams.print_str(instruction.literal_string)
    return HandlerResult.next_instruction,None

### Branching
def op_call(interpreter,operands,next_address,store_to,branch_offset,branch_if_true):n:
   routine_address = interpreter.packed_address_to_address(instruction.operands[0])
    return HandlerResult.call,{'routine_address': routine_address, 'store_to': store_to})

def op_je(interpreter,operands,next_address,store_to,branch_offset,branch_if_true):
    a = instruction.operands[0]
    for b in instruction.operands[1:]:
        if a == b:
            return HandlerResult.jump_abs, {'branch_offset': branch_offset} # Branch address will have been set on instruction initialize
    
    # Don't branch, not equal
    return HandlerResult.next_instruction,None

def op_jl(interpreter,operands,next_address,store_to,branch_offset,branch_if_true):
    a = operands[0]
    for b in operands[1:]:
        if a < b:
            return HandlerResult.jump_abs, {'branch_offset': branch_offset} # Branch address will have been set on instruction initialize
    
    # Don't branch, not equal
    return HandlerResult.next_instruction,None

def op_inc_chk(interpreter,operands,next_address,store_to,branch_offset,branch_if_true):
    return HandlerResult.next_instruction,None

### Memory/Variables
def op_store(interpreter,operands,next_address,store_to,branch_offset,branch_if_true):
    return HandlerResult.next_instruction,None

### Objects
def op_insert_obj(interpreter,operands,next_address,store_to,branch_offset,branch_if_true):
    return HandlerResult.next_instruction,None

### Math
def op_mul(interpreter,operands,next_address,store_to,branch_offset,branch_if_true):
    return HandlerResult.next_instruction,None

### 14.1
OPCODE_HANDLERS = {
(InstructionType.oneOP, 0):  {'name': 'jz','branch': True, 'types': (OperandTypeHint.address,), 'handler': op_jz},

(InstructionType.twoOP,1):  {'name': 'je','je a b ?(label)','branch': True,'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_je},
(InstructionType.twoOP,2):  {'name': 'jl','jl a b ?(label)','branch': True,'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_jz},
(InstructionType.twoOP,5):   {'name': 'inc_chk','branch': True,'types': (OperandTypeHint.variable,OperandTypeHint.unsigned,),'handler': op_inc_chk},
(InstructionType.twoOP,13):  {'name': 'store','types': (OperandTypeHint.variable,OperandTypeHint.unsigned,),'handler': op_inc_chk},
(InstructionType.twoOP,14):  {'name': 'insert_obj','types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_insert_obj},
(InstructionType.twoOP, 22): {'name': 'mul','store': True, 'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_mul},

(InstructionType.zeroOP,2):  {'name': 'print', 'print (literal-string)','literal_string': True,'handler': op_print},
(InstructionType.zeroOP,11): {'name': 'new_line','handler': op_newline},

(InstructionType.varOP,0): {'name': 'call','store': True,
                            'types': (OperandTypeHint.PACKED_ADDRESS,OperandTypeHint.unsigned,OperandTypeHint.unsigned,
                                        OperandTypeHint.unsigned,OperandTypeHint.unsigned,}'handler': op_call}
}

