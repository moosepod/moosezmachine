""" Object representation of opcodes, and classes to handle the actual instructions 

    Using OOP for the intructions is very inefficient but makes writing the reference implementation easy. 

    See http://inform-fiction.org/zmachine/standards/z1point0/sect04.html
"""
import re
from enum import Enum
from zmachine.text import ZText
from zmachine.memory import Memory

MIN_SIGNED= -32768
MAX_SIGNED = 32767
MIN_UNSIGNED = 0
MAX_UNSIGNED = 0xffff

### Constants and utilities
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

class OperandTypeHint(Enum):
    """ Declared with opcode handlers to give hints on how to handle/display operands """
    unsigned = 1
    signed = 2
    address = 3
    packed_address = 4
    variable = 5
    signed_variable = 6
    packed_address_variable = 7

def convert_to_signed(val):
    if val > 0x7fff:
        return -1 * ((val ^ 0xffff) + 1)
    return val

def convert_to_unsigned(val):
    if val < 0:
        return -1 * ((val ^ 0xffff) + 1)
    return val

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


### Passed in memory, address of next instruction, and some context info, return
### a handler function (taking an interpreter) and a description of this instruction
def read_instruction(memory,address,version,ztext):
    """ Read the instruction at the given address, and return a handler function and summary """
    # If top two bits are 11, variable form. If 10, short. 
    # If opcode is BE, form is extended. Otherwise long.
    start_address=address

    branch_offset = 0 # Offset, in bytes, to move PC
    store_to = None # Variable # to store the resulting value to
    zchars = [] # If this instruction works with zcodes, store them here
    literal_string = None # Ascii version of zchars, if any

    address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(memory,address)
    
    # Find opcode handler
    handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
    if not handler:
        raise InstructionException('Unknown opcode %s, %s' % (instruction_type, opcode_number)) 

    address, operands = process_operands(operands, handler,memory,address,version)

    if handler.get('literal_string'):
        address,literal_string = extract_literal_string(memory,address,ztext)
        
    # 4.6
    if handler.get('store'):
        store_to = memory[address]            
        address+=1

    # 4.7
    branch_if_true=False
    if handler.get('branch'):
        address, branch_offset,branch_if_true = extract_branch_offset(memory,address)
    next_address = address

    # Create the handler function for this instruction
    handler_f = lambda interpreter: handler['handler'](interpreter, operands, next_address,store_to,branch_offset,branch_if_true, literal_string)

    # Setup text version for debuggging
    description = format_description(instruction_type, handler, operands, store_to, branch_offset, branch_if_true, literal_string)
    
    return handler_f,description,next_address

def extract_opcode(memory,address):
    """ Handle section 4.3 """
    b1 = memory[address]
    b2 = memory[address+1]
    address+=1
    opcode_byte=b1

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
        # If bit 6 is 1, first operand is variable. If bit 5 is 1, second operand is variable.
        if b1 & 0x40: operands[0] = OperandType.variable
        if b1 & 0x20: operands[1] = OperandType.variable
    
    return address,instruction_form, instruction_type,  opcode_number,operands

def unpack_address(val,version):
    if version > 3:
        return val * 4
    return val * 2

def process_operand_type_hint(val, hint,version):
    """ Use the hint to perform any processing on the operand value (such as signing) """
    if val < MIN_UNSIGNED or val > MAX_UNSIGNED:
        raise InstructionException('Operand out of 0 <= op => 0xffff range')

    if hint == OperandTypeHint.signed:
        # Signed numbers are stored twos compliment. See 2.2.
        return convert_to_signed(val)
    elif hint == OperandTypeHint.packed_address:
        return unpack_address(val,version)
    elif hint == OperandTypeHint.variable:
        return val
    return val 

def process_operands(operands, handler,memory, address,version):
    """ Handle section 4.5 """
    tmp = []
    for i,optype in enumerate(operands):
        val = 0
        if len(handler.get('types',[])) > i:
            hint = handler['types'][i]
        else:
            hint = None
        if optype == OperandType.small_constant:
            val = process_operand_type_hint(memory[address],hint,version)
            address+=1
        elif optype == OperandType.large_constant:
            val = process_operand_type_hint(memory.word(address),hint,version)
            address+=2
        elif optype == OperandType.variable:
            val = memory[address]
            if hint == OperandTypeHint.signed:
                hint = OperandTypeHint.signed_variable
            elif hint == OperandTypeHint.packed_address:
                hint = OperandTypeHint.packed_address_variable
            else:
                hint = OperandTypeHint.variable
            address+=1
        elif optype == OperandType.omitted:
            # 4.4.3
            # Omit any vars after an ommitted type
            break
        tmp.append((val,hint))
    return address, tmp

def extract_literal_string(memory,address,ztext):
    """ Extract the literal string from the given memory/address and return the new address + string """
    zchar_start_address = address
    zchars = []
    done = False
    while not done:
        zchars_tmp,done = ztext.get_zchars_from_memory(memory,address)
        address+=2
        zchars.extend(list(zchars_tmp))            
    return address, ztext.to_ascii(memory,zchar_start_address,0)   

def extract_branch_offset(memory,address):
    """ Handle section 4.7 """
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
    return address, branch_offset, branch_if_true

def format_description(instruction_type, handler, operands, store_to, branch_offset, branch_if_true, literal_string):
    """ Create a text description of this instruction """
    description = "%s:%s" % (instruction_type.name, handler['name'])
    for operand,hint in operands:
        if hint in (OperandTypeHint.variable,OperandTypeHint.signed_variable,OperandTypeHint.packed_address_variable):
            description += ' var%s' % operand
        else:
            description += ' %s' % operand
    if literal_string:
        description += ' (%s)' % repr(literal_string).strip("'")
    if store_to:
        description += ' -> %s' % store_to
    if branch_offset:
        if not branch_if_true:
            branch_invert = '!'
        else:
            branch_invert = ''
        description += ' ?%s%04x' % (branch_invert,branch_offset)
    return description

### For testing purposes. Pass in params and make the memory that represents this instruction
def create_instruction(instruction_type, opcode_number, operands, store_to=None, branch_to=None, branch_if_true=True):
    bytes = []

    if instruction_type == InstructionType.twoOP:
        variables = 0
        if operands[0][0] == OperandType.large_constant or operands[1][0] == OperandType.large_constant:
            instruction_form = InstructionForm.variable_form
            bytes.append(0xC0 | opcode_number)
        else:
            instruction_form = InstructionForm.long_form
            if operands[0][0] == OperandType.variable:
                variables = variables | 0x40
            if operands[1][0] == OperandType.variable:
                variables = variables | 0x20
            bytes.append(0x00 | opcode_number | variables)
        if instruction_form == InstructionForm.variable_form:
            variable_types = 0x0F

            opt = operands[0][0]
            if opt  == OperandType.variable:
                variable_types = variable_types | 0x80 # 10
            elif opt == OperandType.small_constant:
                variable_types = variable_types | 0x40 # 01

            opt = operands[1][0]
            if opt  == OperandType.variable:
                variable_types = variable_types | 0x20 # 10
            elif opt == OperandType.small_constant:
                variable_types = variable_types | 0x10 # 01    

            bytes.append(variable_types)        

        for optype, operand in operands:
            if operand < 0:
                operand = convert_to_unsigned(operand)
                bytes.append(operand >> 8)
                bytes.append(operand & 0x00FF)
            elif optype == OperandType.large_constant:
                bytes.append(operand >> 8)
                bytes.append(operand & 0x00FF)
            else:
                bytes.append(operand)
    else:
        raise Exception('Not supporting that type yet')

    if store_to:
        bytes.append(store_to)

    if branch_to:
        if branch_if_true:
            bytes.append(0x80)
            bytes.append(branch_to)
        else:
            bytes.append(0x00)
            bytes.append(branch_to)     
    return Memory(bytes)

### Interpreter actions, returned at end of each instruction to tell interpreter how to proceed
class NextInstructionAction(object):
    """ Interpreter should proceed to next instruction, address provided """
    def __init__(self, next_address):
        self.next_address = next_address

    def apply(self,interpreter):
        interpreter.pc = self.next_address

class CallAction(object):
    """ Interpreter should call the routine with the provide info """
    def __init__(self, routine_address, store_to, return_to):
        self.routine_address = routine_address
        self.store_to = store_to
        self.return_to = return_to

    def apply(self,interpreter):
        interpreter.call_routine(self.routine_address,self.return_to,self.store_to)

class ReturnAction(object):
    """ Interpreter should return from the current routine with the given result """
    def __init__(self, result):
        self.result = result

    def apply(self,interpreter):
        interpreter.return_from_current_routine(self.result)

class JumpRelativeAction(object):
    """ Interpreter should jump relative to the current program counter """
    def __init__(self, branch_offset, next_address):
        self.branch_offset = branch_offset
        self.next_address = next_address

    def apply(self,interpreter):
        interpreter.pc = self.next_address + self.branch_offset - 2

class QuitAction(object):
    def __init__(self, next_address):
        self.next_address = next_address

    def apply(self,interpreter):
        interpreter.quit()


###
### All handlers are passed in an interpreter and information about the given instruction
### and return an action object telling interpreter how to proceed
###

def dereference_variables(operand, interpreter):
    val, hint = operand
    if hint == OperandTypeHint.variable:
        return interpreter.current_routine()[val]
    elif hint == OperandTypeHint.signed_variable:
        return convert_to_signed(interpreter.current_routine()[val])   
    elif hint == OperandTypeHint.packed_address_variable:
        return unpack_address(interpreter.current_routine()[val], interpreter.story.header.version)  
    return val

## Text

def op_newline(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    interpreter.output_streams.new_line()
    return NextInstructionAction(next_address)

def op_print(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    interpreter.output_streams.print_str(literal_string)
    return NextInstructionAction(next_address)

def op_print_paddr(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    addr = dereference_variables(operands[0],interpreter)
    interpreter.output_streams.print_str(interpreter.get_ztext().to_ascii(interpreter.story.game_memory, addr))
    return NextInstructionAction(next_address)

def op_print_addr(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    addr = dereference_variables(operands[0],interpreter)
    interpreter.output_streams.print_str(interpreter.get_ztext().to_ascii(interpreter.story.game_memory, addr))
    return NextInstructionAction(next_address)

def op_print_num(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    val = dereference_variables(operands[0],interpreter)
    interpreter.output_streams.print_str(str(val))
    return NextInstructionAction(next_address)

def op_print_ret(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_sread(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_print_char(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_split_window(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_set_window(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_output_stream(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_input_stream(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

## Branching
def op_call(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    address,hint = operands[0]  
    return CallAction(address, store_to,next_address)

def op_ret(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_ret_popped(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_rtrue(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return ReturnAction(1)

def op_rfalse(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return ReturnAction(0)

def op_je(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    do_branch = False
    a = dereference_variables(operands[0],interpreter)
    for operand in operands[1:]:
        b = dereference_variables(operand,interpreter)
        if a == b:
            do_branch = True
            break

    if not branch_if_true:
        do_branch = not do_branch

    if do_branch:
        return JumpRelativeAction(branch_offset,next_address)

    return NextInstructionAction(next_address)

def op_jl(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    do_branch = False
    a = dereference_variables(operands[0],interpreter)
    for operand in operands[1:]:
        b = dereference_variables(operand,interpreter)
        if a < b:
            do_branch = True
            break

    if not branch_if_true:
        do_branch = not do_branch

    if do_branch:
        return JumpRelativeAction(branch_offset,next_address)

    return NextInstructionAction(next_address)

def op_jg(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    do_branch = False
    a = dereference_variables(operands[0],interpreter)
    for operand in operands[1:]:
        b = dereference_variables(operand,interpreter)
        if a > b:
            do_branch = True
            break

    if not branch_if_true:
        do_branch = not do_branch

    if do_branch:
        return JumpRelativeAction(branch_offset,next_address)

    return NextInstructionAction(next_address)

def op_jz(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_return(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_jump(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    offset = dereference_variables(operands[0],interpreter)
    return JumpRelativeAction(offset,next_address)
    

def op_inc_chk(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    routine = interpreter.current_routine()
    var_num,hint = operands[0]
    comp_to = dereference_variables(operands[1],interpreter)

    var = routine[var_num]
    var += 1
    routine[var_num] = var

    branch = var > comp_to
    if not branch_if_true:
        branch = not branch

    if branch:
        return JumpRelativeAction(branch_offset,next_address)

    return NextInstructionAction(next_address)

def op_dec_chk(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    routine = interpreter.current_routine()
    var_num,hint = operands[0]
    comp_to = dereference_variables(operands[1],interpreter)
    var = routine[var_num]
    var -= 1
    routine[var_num] = var

    branch = var < comp_to
    if not branch_if_true:
        branch = not branch

    if branch:
        return JumpRelativeAction(branch_offset,next_address)

    return NextInstructionAction(next_address)

## Memory/Variables
def op_store(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

## Objects
def op_put_prop(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_insert_obj(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_get_sibling(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_get_child(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_get_parent(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_get_prop_len(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_remove_obj(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_print_obj(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_jin(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    a = dereference_variables(operands[0],interpreter)
    b = dereference_variables(operands[1],interpreter)

    obj = interpreter.story.object_table[a]
    if obj['parent'] == b:
        return JumpRelativeAction(branch_offset,next_address)

    return NextInstructionAction(next_address)

## Math
def op_mul(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    v1 = dereference_variables(operands[0],interpreter)
    v2 = dereference_variables(operands[1],interpreter)
    result = v1 * v2
    if result < MIN_SIGNED or result > MAX_SIGNED:
        raise Interpreter('Overflow in mul of %s * %s: %s' % (v1,v2,result))
    interpreter.current_routine()[int(store_to)] = result

    return NextInstructionAction(next_address)

def op_inc(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_dec(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_add(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_sub(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_div(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_mod(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_mul(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

## Properties
def op_get_prop(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_get_prop_addr(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_get_next_prop(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_test_attr(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    object_number = dereference_variables(operands[0],interpreter)
    attribute_number = dereference_variables(operands[1],interpreter)

    if interpreter.story.object_table.test_attribute(object_number, attribute_number):
        return JumpRelativeAction(branch_offset,next_address)

    return NextInstructionAction(next_address)

def op_set_attr(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    object_number = dereference_variables(operands[0],interpreter)
    attribute_number = dereference_variables(operands[1],interpreter)

    interpreter.story.object_table.set_attribute(object_number, attribute_number,True)

    return NextInstructionAction(next_address)

def op_clear_attr(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    object_number = dereference_variables(operands[0],interpreter)
    attribute_number = dereference_variables(operands[1],interpreter)

    interpreter.story.object_table.set_attribute(object_number, attribute_number,False)

    return NextInstructionAction(next_address)

## Misc
def op_quit(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return QuitAction(next_address)

def op_nop(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_store(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_storeb(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_storew(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_load(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_loadw(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_loadb(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_save(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_restore(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_restart(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_pop(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_show_status(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_verify(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_random(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_push(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

def op_pull(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)

### Bitwise
def op_not(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    return NextInstructionAction(next_address)    

def op_test(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    bitmap = dereference_variables(operands[0],interpreter)
    flags = dereference_variables(operands[1],interpreter)

    if bitmap & flags == flags:
        return JumpRelativeAction(branch_offset,next_address)

    return NextInstructionAction(next_address)    

def op_or(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    v1 = dereference_variables(operands[0],interpreter)
    v2 = dereference_variables(operands[1],interpreter)

    interpreter.current_routine()[store_to] = v1 | v2

    return NextInstructionAction(next_address)   

def op_and(interpreter,operands,next_address,store_to,branch_offset,branch_if_true,literal_string):
    v1 = dereference_variables(operands[0],interpreter)
    v2 = dereference_variables(operands[1],interpreter)

    interpreter.current_routine()[store_to] = v1 & v2

    return NextInstructionAction(next_address)   

### 14.1
OPCODE_HANDLERS = {
(InstructionType.zeroOP,0):  {'name': 'rtrue', 'handler': op_rtrue},
(InstructionType.zeroOP,1):  {'name': 'rfalse', 'handler': op_rfalse},
(InstructionType.zeroOP,2):  {'name': 'print', 'literal_string': True,'handler': op_print},
(InstructionType.zeroOP,3):  {'name': 'print_ret', 'literal_string': True,'handler': op_print_ret},
(InstructionType.zeroOP,4):  {'name': 'nop', 'handler': op_nop},
(InstructionType.zeroOP,5):  {'name': 'save','branch':True, 'handler': op_save},
(InstructionType.zeroOP,6):  {'name': 'restore','branch':True, 'handler': op_restore},
(InstructionType.zeroOP,7):  {'name': 'quit','restart': op_restart},
(InstructionType.zeroOP,8):  {'name': 'ret_popped','restart': op_ret_popped},
(InstructionType.zeroOP,8):  {'name': 'pop','restart': op_pop},
(InstructionType.zeroOP,10): {'name': 'quit','handler': op_quit},

(InstructionType.zeroOP,11): {'name': 'new_line','handler': op_newline},
(InstructionType.zeroOP,12): {'name': 'show_status','handler': op_show_status},
(InstructionType.zeroOP,13): {'name': 'verify','branch': True, 'handler': op_verify},

(InstructionType.oneOP, 0):  {'name': 'jz','branch': True, 'types': (OperandTypeHint.address,), 'handler': op_jz},
(InstructionType.oneOP, 1):  {'name': 'get_sibling','branch': True, 'store': True, 'types': (OperandTypeHint.unsigned,), 'handler': op_get_sibling},
(InstructionType.oneOP, 2):  {'name': 'get_child','branch': True, 'store': True, 'types': (OperandTypeHint.unsigned,), 'handler': op_get_child},
(InstructionType.oneOP, 3):  {'name': 'get_parent', 'store': True, 'types': (OperandTypeHint.unsigned,), 'handler': op_get_parent},
(InstructionType.oneOP, 4):  {'name': 'get_prop_len', 'store': True, 'types': (OperandTypeHint.address,), 'handler': op_get_prop_len},
(InstructionType.oneOP, 5):  {'name': 'inc', 'types': (OperandTypeHint.signed,), 'handler': op_inc},
(InstructionType.oneOP, 6):  {'name': 'dec', 'types': (OperandTypeHint.signed,), 'handler': op_inc},
(InstructionType.oneOP, 7):  {'name': 'print_addr','types': (OperandTypeHint.address,), 'handler': op_print_addr},
(InstructionType.oneOP, 9):  {'name': 'remove_obj','types': (OperandTypeHint.unsigned,), 'handler': op_remove_obj},

(InstructionType.oneOP, 10):  {'name': 'print_obj','types': (OperandTypeHint.unsigned,), 'handler': op_print_obj},
(InstructionType.oneOP, 11):  {'name': 'ret','types': (OperandTypeHint.unsigned,), 'handler': op_ret},
(InstructionType.oneOP, 12):  {'name': 'jump','handler': op_jump,'types': (OperandTypeHint.signed,) },
(InstructionType.oneOP, 13):  {'name': 'print_paddr','types': (OperandTypeHint.packed_address,), 'handler': op_print_paddr},
(InstructionType.oneOP, 14):  {'name': 'load','store': True, 'types': (OperandTypeHint.unsigned,), 'handler': op_load},
(InstructionType.oneOP, 15):  {'name': 'not','store': True, 'types': (OperandTypeHint.unsigned,), 'handler': op_not},

(InstructionType.twoOP,0):   {'name': 'nop','handler': op_nop},
(InstructionType.twoOP,1):   {'name': 'je','branch': True,'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_je},
(InstructionType.twoOP,2):   {'name': 'jl','branch': True,'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_jl},
(InstructionType.twoOP,3):   {'name': 'jg','branch': True,'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_jg},
(InstructionType.twoOP,4):   {'name': 'dec_chk','branch': True,'types': (OperandTypeHint.variable,OperandTypeHint.unsigned,),'handler': op_dec_chk},
(InstructionType.twoOP,5):   {'name': 'inc_chk','branch': True,'types': (OperandTypeHint.variable,OperandTypeHint.unsigned,),'handler': op_inc_chk},
(InstructionType.twoOP,6):   {'name': 'jin','branch': True,'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_jin},
(InstructionType.twoOP,7):   {'name': 'test','branch': True,'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_test},
(InstructionType.twoOP,8):   {'name': 'or','store': True,'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_or},
(InstructionType.twoOP,9):   {'name': 'and','store': True,'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_and},
(InstructionType.twoOP,10):  {'name': 'test_attr','branch': True,'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_test_attr},

(InstructionType.twoOP,11):  {'name': 'set_attr','types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_set_attr},
(InstructionType.twoOP,12):  {'name': 'clear_attr','types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_clear_attr},
(InstructionType.twoOP,13):  {'name': 'store','types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_store},
(InstructionType.twoOP,14):  {'name': 'insert_obj','types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_insert_obj},
(InstructionType.twoOP,15):  {'name': 'loadw','store':True,'types': (OperandTypeHint.address,OperandTypeHint.address,),'handler': op_loadw},
(InstructionType.twoOP,16):  {'name': 'loadb','store':True,'types': (OperandTypeHint.address,OperandTypeHint.address,),'handler': op_loadb},
(InstructionType.twoOP,17):  {'name': 'get_prop','store': True, 'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_get_prop},
(InstructionType.twoOP,18):  {'name': 'get_prop_addr','store': True, 'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_get_prop_addr},
(InstructionType.twoOP,19):  {'name': 'get_next_prop','store': True, 'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_get_next_prop},

(InstructionType.twoOP,20):  {'name': 'add','store': True, 'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_add},
(InstructionType.twoOP,21):  {'name': 'sub','store': True, 'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_sub},
(InstructionType.twoOP,22):  {'name': 'mul','store': True, 'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_mul},
(InstructionType.twoOP,23):  {'name': 'div','store': True, 'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_div},
(InstructionType.twoOP,24):  {'name': 'mod','store': True, 'types': (OperandTypeHint.signed,OperandTypeHint.signed,),'handler': op_mod},

(InstructionType.twoOP,31):  {'name': 'nop','handler': op_nop},


(InstructionType.varOP,0):   {'name': 'call','store': True,
                              'types': (OperandTypeHint.packed_address,OperandTypeHint.unsigned,OperandTypeHint.unsigned,
                                        OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_call},
(InstructionType.varOP,1):   {'name': 'storew',
                              'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,OperandTypeHint.unsigned),'handler': op_storew},
(InstructionType.varOP,2):   {'name': 'storeb',
                              'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,OperandTypeHint.unsigned),'handler': op_storeb},
(InstructionType.varOP,3):   {'name': 'put_prop',
                              'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,OperandTypeHint.unsigned),'handler': op_put_prop},
(InstructionType.varOP,4):   {'name': 'sread',
                              'types': (OperandTypeHint.unsigned,OperandTypeHint.unsigned,),'handler': op_sread},
(InstructionType.varOP,5):   {'name': 'print_char',
                              'types': (OperandTypeHint.unsigned,),'handler': op_print_char},

(InstructionType.varOP,6):   {'name': 'print_num',
                              'types': (OperandTypeHint.signed,),
                              'handler': op_print_num},
(InstructionType.varOP,7):   {'name': 'random',
                              'types': (OperandTypeHint.unsigned,),'handler': op_random},
(InstructionType.varOP,8):   {'name': 'push',
                              'types': (OperandTypeHint.unsigned,),'handler': op_push},
(InstructionType.varOP,9):   {'name': 'pull','store':True,
                              'types': (OperandTypeHint.unsigned,),'handler': op_pull},

(InstructionType.varOP,10):   {'name': 'split_window',
                              'types': (OperandTypeHint.unsigned,),'handler': op_split_window},
(InstructionType.varOP,11):   {'name': 'set_window',
                              'types': (OperandTypeHint.unsigned,),'handler': op_set_window},
(InstructionType.varOP,19):   {'name': 'output_stream',
                              'types': (OperandTypeHint.unsigned,),'handler': op_output_stream},
(InstructionType.varOP,20):   {'name': 'input_stream',
                              'types': (OperandTypeHint.unsigned,),'handler': op_input_stream},

}

