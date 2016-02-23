""" Tests for zmachine """
import unittest
import os
import inspect

from zmachine.interpreter import Interpreter,StoryFileException,MemoryAccessException,\
                                 OutputStream,OutputStreams,SaveHandler,RestoreHandler,Story,\
                                InterpreterException
from zmachine.text import ZText,ZTextState,ZTextException
from zmachine.memory import Memory
from zmachine.dictionary import Dictionary
from zmachine.instructions import InstructionForm,InstructionType,OperandType,OPCODE_HANDLERS,\
                                  read_instruction,extract_opcode,\
                                  process_operands, extract_literal_string, extract_branch_offset,\
                                  format_description,convert_to_unsigned,\
                                  JumpRelativeAction,CallAction,NextInstructionAction,OperandTypeHint

class TestOutputStream(OutputStream):
    def __init__(self,*args,**kwargs):
        super(TestOutputStream,self).__init__(*args,**kwargs)
        self.new_line_called = False
        self.printed_string = ''

    def new_line(self):
        self.new_line_called = True

    def print_str(self,msg):
        self.printed_string += msg

class TestSaveHandler(SaveHandler):
    pass

class TestRestoreHandler(RestoreHandler):
    pass

class TestOutputStreams(OutputStreams):
    def __init__(self):
        super(TestOutputStreams,self).__init__(TestOutputStream(),TestOutputStream())

class InstructionTests(unittest.TestCase):
    def test_extract_opcode(self):
        # je
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory(b'\x01\x00\x11\x8d\x19'),0)
        self.assertEqual(InstructionForm.long_form, instruction_form)
        self.assertEqual(InstructionType.twoOP,instruction_type)
        self.assertEqual(1, opcode_number)
        self.assertEqual([OperandType.small_constant,OperandType.small_constant], operands)

        # jl
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory(b'\x22\xb2\x14\xe4\x5d'),0)
        self.assertEqual(InstructionForm.long_form, instruction_form)
        self.assertEqual(InstructionType.twoOP,instruction_type)
        self.assertEqual(2, opcode_number)
        self.assertEqual([OperandType.small_constant,OperandType.large_constant], operands)

        # call
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory(b'\xe0\x3f\x16\x34\x00'),0)
        self.assertEqual(InstructionForm.variable_form, instruction_form)
        self.assertEqual(InstructionType.varOP,instruction_type)
        self.assertEqual(0, opcode_number)
        self.assertEqual([OperandType.large_constant,OperandType.omitted,OperandType.omitted,OperandType.omitted], operands)

        # call_1n
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory([0x8f,0x01,0x56]),0)
        self.assertEqual(InstructionForm.short_form, instruction_form)
        self.assertEqual(InstructionType.oneOP,instruction_type)
        self.assertEqual(15, opcode_number)
        self.assertEqual([OperandType.large_constant], operands)

        # inc_chk
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory([0x05,0x02,0x00,0xd4]),0)
        self.assertEqual(InstructionForm.long_form, instruction_form)
        self.assertEqual(InstructionType.twoOP,instruction_type)
        self.assertEqual(5, opcode_number)
        self.assertEqual([OperandType.small_constant,OperandType.small_constant], operands)

        # mul
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory(b'\xd6\x2f\x03\xe8\x02\x00'),0)
        self.assertEqual(InstructionForm.variable_form, instruction_form)
        self.assertEqual(InstructionType.twoOP, instruction_type)
        self.assertEqual(22, opcode_number)
        self.assertEqual([OperandType.large_constant,OperandType.variable], operands)

        # print
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory(b'\xb2\x11\xaa\x46\x34\x16\x45\x9c\xa5'),0)
        self.assertEqual(InstructionForm.short_form, instruction_form)
        self.assertEqual(InstructionType.zeroOP, instruction_type)
        self.assertEqual(2, opcode_number)

        # new_line
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory(b'\xbb\x00'),0)
        self.assertEqual(InstructionForm.short_form, instruction_form)
        self.assertEqual(InstructionType.zeroOP, instruction_type)
        self.assertEqual(11, opcode_number)

    def test_process_operands(self):
        # je
        mem = Memory(b'\x01\x00\x11\x8d\x19')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler,mem, address,3)
        self.assertEqual([0,17], [x[0] for x in operands])

        # jl
        mem = Memory(b'\x22\xb2\x14\xe4\x5d')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler,mem, address,3)
        self.assertEqual([178,5348],[x[0] for x in operands])

        # call
        mem = Memory(b'\xe0\x3f\x16\x34\x00')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler,mem, address,3)
        self.assertEqual([11368], [x[0] for x in operands])

        # inc_chk
        mem = Memory([0x05,0x02,0x00,0xd4])
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler, mem, address,3)
        self.assertEqual([(2,OperandTypeHint.variable),(0x00,OperandTypeHint.unsigned)], operands)

        # mul
        mem = Memory(b'\xd6\x2f\x03\xe8\x02\x00')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler, mem, address,3)
        self.assertEqual([(1000,OperandTypeHint.signed),(2,OperandTypeHint.variable)],operands)

        # print
        mem = Memory(b'\xb2\x11\xaa\x46\x34\x16\x45\x9c\xa5')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler, mem, address,3)
        self.assertEqual([], [x[0] for x in operands])

        # new_line
        mem = Memory(b'\xbb\x00')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler, mem, address,3)
        self.assertEqual([],[x[0] for x in operands])

    def test_extract_branch_offset(self):
        # je
        mem = Memory(b'\x01\x00\x11\x8d\x19')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler,mem, address,3)
        address, branch_offset, branch_if_true = extract_branch_offset(mem,address)
        self.assertEqual(3353,branch_offset)

        # jl
        mem = Memory(b'\x22\xb2\x14\xe4\x5d')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler,mem, address,3)
        address, branch_offset, branch_if_truet = extract_branch_offset(mem,address)
        self.assertEqual(29,branch_offset)

    def test_extract_literal_string(self):
        mem = Memory(b'\xb2\x11\xaa\x46\x34\x16\x45\x9c\xa5')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        address, literal_string = extract_literal_string(mem, address, ZText(version=3,get_abbrev_f=lambda x: Memory([0x80,0])))
        self.assertEqual("HELLO.\n", literal_string)

    def test_format_description(self):
        # je
        mem = Memory(b'\x01\x00\x11\x8d\x19')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler,mem, address,3)
        address, branch_offset, branch_if_true = extract_branch_offset(mem,address)
        description = format_description(instruction_type, handler, operands, None, branch_offset, branch_if_true, None)
        self.assertEqual('twoOP:je 0 17 ?0d19',description)

        # print
        mem = Memory(b'\xb2\x11\xaa\x46\x34\x16\x45\x9c\xa5')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, literal_string = extract_literal_string(mem, address, ZText(version=3,get_abbrev_f=lambda x: Memory([0x80,0])))
        description = format_description(instruction_type, handler, [], None, None, False, literal_string)
        self.assertEqual('zeroOP:print (HELLO.\\n)',description)

class InstructionTestsMixin(object):
    # Took examples from end of http://inform-fiction.org/zmachine/standards/z1point0/sect04.html
    def __init__(self,*args,**kwargs):
        super(InstructionTestsMixin,self).__init__(*args,**kwargs)    
        path = 'testdata/test.z3'
        if not os.path.exists(path):
            self.fail('Could not find test file test.z3')
        with open(path, 'rb') as f:
            self.story = Story(f.read())
            self.zmachine = Interpreter(self.story,TestOutputStreams(),TestSaveHandler(),TestRestoreHandler())

    def setUp(self):
        self.zmachine.reset()
        self.screen = TestOutputStream()
        self.zmachine.output_streams.set_screen_stream(self.screen)
    

class RoutineInstructionsTests(InstructionTestsMixin,unittest.TestCase):
    def test_je(self):
        memory = Memory(b'\x01\x00\x11\x8d\x19')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:je 0 17 ?0d19',description)
        result = handler_f(self.zmachine)

        # Items not equal, don't jump
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

        # Items equal, jump
        memory = Memory(b'\x01\x11\x11\x8d\x19')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:je 17 17 ?0d19',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(3353,result.branch_offset)

        # Flip branch if true, reverse logic
        memory = Memory(b'\x01\x11\x11\x0d\x19')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:je 17 17 ?!0d19',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

    def test_jl(self):
        # Item is less than, so jump
        memory = Memory(b'\x22\xb2\x14\xe4\xdd')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jl 178 5348 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(29,result.branch_offset)

        # Gt, don't jump
        memory = Memory(b'\x22\x14\x00\x01\xdd')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jl 20 1 ?001d',description)
        result = handler_f(self.zmachine)    
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

        # equal, don't jump
        memory = Memory(b'\x22\xb2\x00\xb2\xdd')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jl 178 178 ?001d',description)
        result = handler_f(self.zmachine)    
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

        # Test inverse
        memory = Memory(b'\x22\xb2\x14\xe4\x5d')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jl 178 5348 ?!001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

        # Test signed
        memory = Memory(b'\x22\xb2\xff\xff\xdd')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jl 178 -1 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

    def test_call(self):
        memory=Memory(b'\xe0\x3f\x16\x34\x00')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('varOP:call 11368',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,CallAction))
        self.assertEqual(5,result.return_to)
        self.assertEqual(11368,result.routine_address)
        self.assertEqual(0,result.store_to)

class ArithmaticInstructionsTests(InstructionTestsMixin,unittest.TestCase):
    def test_inc_chk(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [0,1,2,3,4,5]

        # Increment and branch
        memory=Memory([0x05,0x02,0x00,0xd4])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:inc_chk var2 0 ?0014',description)

        self.assertEqual(1,self.zmachine.current_routine()[2])
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(20,result.branch_offset)
        self.assertEqual(2,self.zmachine.current_routine()[2])

        # Increment and don't branch
        memory=Memory([0x05,0x02,0x06,0xd4])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:inc_chk var2 6 ?0014',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(3,self.zmachine.current_routine()[2])

        # Invert
        memory=Memory([0x05,0x02,0x00,0x54])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:inc_chk var2 0 ?!0014',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4,self.zmachine.current_routine()[2])

    def test_mul(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [1,2]

        # Test unsigned
        memory=Memory(b'\xd6\x2f\x03\xe8\x02\x00')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:mul 1000 var2',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(2000,routine[0])

        # Test signed
        memory=Memory(b'\xd6\x2f\xff\xff\x01\x30')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:mul -1 var1 -> 48',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(convert_to_unsigned(-1),routine[48])

class ScreenInstructionsTests(InstructionTestsMixin,unittest.TestCase):
    def test_print(self):
        memory=Memory(b'\xb2\x11\xaa\x46\x34\x16\x45\x9c\xa5')
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('zeroOP:print (HELLO.\\n)',description)

        self.assertEqual('',self.screen.printed_string)
        result = handler_f(self.zmachine)        
        self.assertEqual('HELLO.\n',self.screen.printed_string)
    
    def test_new_line(self):
        memory = Memory(b'\xbb\x00')
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('zeroOP:new_line',description)
        
        self.assertFalse(self.screen.new_line_called)
        result = handler_f(self.zmachine)        
        self.assertTrue(self.screen.new_line_called)

class MemoryTests(unittest.TestCase):
    def test_from_integers(self):
        mem = Memory([1,2,3])
        self.assertEqual(3, len(mem))
        self.assertEqual(1,mem[0])
        self.assertEqual(2,mem[1])
        self.assertEqual(3,mem[2])     
        self.assertEqual(bytearray([1,2]), mem[0:2])

    def test_from_chars(self):
        mem = Memory(b'\x01\x02\x03')
        self.assertEqual(3, len(mem))
        self.assertEqual(1,mem[0])
        self.assertEqual(2,mem[1])
        self.assertEqual(3,mem[2])

    def test_address(self):
        mem = Memory([0,1])
        self.assertEqual(0x00, mem[0])
        self.assertEqual(0x01,mem[1])
        self.assertEqual(0x01,mem.word(0))

    def test_flag(self):
        mem = Memory([1])
        self.assertTrue(mem.flag(0,0))
        self.assertFalse(mem.flag(0,1))
        self.assertFalse(mem.flag(0,2))

    def test_set_flag(self):
        mem = Memory([0])
        self.assertFalse(mem.flag(0,1))
        mem.set_flag(0,1,1)
        self.assertTrue(mem.flag(0,1))
        mem.set_flag(0,1,0)
        self.assertFalse(mem.flag(0,1))
    
    def test_set_word(self):
        mem = Memory([0,0])
        self.assertEqual(0,mem.word(0))
        self.assertEqual(0, mem[0])
        self.assertEqual(0, mem[1])

        mem.set_word(0,0xFFFF)
        self.assertEqual(0xFFFF,mem.word(0))
        self.assertEqual(0xFF, mem[0])
        self.assertEqual(0xFF, mem[1])

        mem.set_word(0,0xFF00)
        self.assertEqual(0xFF00,mem.word(0))
        self.assertEqual(0xFF,mem[0])
        self.assertEqual(0,mem[1])

    def test_packed(self):
        mem = Memory([1,2,3,4])
        self.assertEqual(mem.word(2),mem.packed_address(1,2))

    def test_signed_int(self):
        mem = Memory([0,0])
        self.assertEqual(0, mem.signed_int(0))
        mem[1] = 1
        self.assertEqual(1, mem.signed_int(0))
        mem[1] = 0xFF
        mem[0] = 0x7F
        self.assertEqual(32767, mem.signed_int(0))
        mem[0] = 0xFF
        self.assertEqual(-1, mem.signed_int(0))

    def test_set_signed_int(self):
        mem = Memory([0,0])
        mem.set_signed_int(0,0)
        self.assertEqual(0, mem.word(0))
        mem.set_signed_int(0,1)
        self.assertEqual(1, mem.word(0))
        mem.set_signed_int(0,-1)
        self.assertEqual(65535, mem.word(0))

class ScreenStub(object):
    def __init__(self):
        self.reset()
    
    def done(self):
        pass

    def reset(self):
        self.print_called = False
        self.printed_string = ''

    def print_ascii(self,msg_ascii):
        self.printed_string = self.printed_string + msg_ascii
        self.print_called = True

class ZTextTests(unittest.TestCase):
    def setUp(self):
        self.screen = ScreenStub()
        self.get_abbrev_f = lambda x: Memory([0x80,0]) # Empty end char

    def test_shift(self):
        ztext = ZText(version=1,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(0,ztext._current_alphabet)
        self.assertEqual(None,ztext._shift_alphabet)
        self.assertEqual(0,ztext.alphabet)

        ztext.shift()
        self.assertEqual(0,ztext._current_alphabet)
        self.assertEqual(1,ztext._shift_alphabet)
        self.assertEqual(1,ztext.alphabet)

        ztext.shift(reverse=False,permanent=True)
        self.assertEqual(1,ztext._current_alphabet)
        self.assertEqual(None,ztext._shift_alphabet)
        self.assertEqual(1,ztext.alphabet)

        ztext.shift(reverse=True)
        self.assertEqual(1,ztext._current_alphabet)
        self.assertEqual(0,ztext._shift_alphabet)
        self.assertEqual(0,ztext.alphabet)

    def test_zchars(self):
        ztext = ZText(version=1,get_abbrev_f=self.get_abbrev_f)
        memory = Memory([0,0,0,0])
        self.assertEqual(((0,0,0),False), ztext.get_zchars_from_memory(memory,0))
        memory.set_word(0,0xFFFF)
        self.assertEqual(((31,31,31),True), ztext.get_zchars_from_memory(memory,0))
        memory.set_word(2,0xFFF0)
        self.assertEqual(((31, 31,16),True), ztext.get_zchars_from_memory(memory,2))

    def test_map_zscii(self):       
        ztext = ZText(version=2,get_abbrev_f=self.get_abbrev_f)
        correct_mapping = {0: '', 
                           13: '\r'}
        chars = ' !"#$%&\'()*+,-./0123456789:;<=>?' + \
                      '@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_' + \
                      '`abcdefghijklmnopqrstuvwxyz{|}~'

        unicode_chars = ('ae oe ue Ae Oe Ue ss >> << e i y E I a e i o u y A E I O U Y ' +
                         'a e i o u A E I O U a e i o u A E I O U a A o O a n o A N O ae AE ' +
                         'c C th th Th Th L oe OE ! ?').split(' ')

        for i in range(0,len(chars)):
            correct_mapping[i+32] = chars[i]
        for i in range(0, len(unicode_chars)):
            correct_mapping[155+i] = unicode_chars[i]
        
        for i in range(0,255):
            if correct_mapping.get(i) != None:
                self.assertEqual(correct_mapping[i],ztext._map_zscii(i))
            else:
                self.assertRaises(ZTextException, ztext._map_zscii,i)
    
    def test_map_zchar(self):
        ztext = ZText(version=2,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(' ', ztext._map_zchar(0))
        for i in range(1,6):
            self.assertEqual('',ztext._map_zchar(i))
        for i in range(6,32):
            self.assertEqual(chr(ord('a') + (i-6)), ztext._map_zchar(i))
        ztext.shift(permanent=True)
        for i in range(6,32):
            self.assertEqual(chr(ord('A') + (i-6)), ztext._map_zchar(i))
        ztext.shift(permanent=True)
        target_chars = '       \n0123456789.,!?_#\'"/\-:()'
        for i in range(7,32):   
            # Skip char 6 of alphabet 2, it is special case, see 3.4
            self.assertEqual(target_chars[i],ztext._map_zchar(i))

    def test_map_zchar_v1(self):
        ztext = ZText(version=1,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual('\n',ztext._map_zchar(1))
        ztext.shift(permanent=True)
        ztext.shift(permanent=True)
        target_chars='       0123456789.,!?_#\'"/\<-:()'
        for i in range(7,32):
            # Skip char 6 of alphabet 2, it is special case, see 3.4
            self.assertEqual(target_chars[i],ztext._map_zchar(i))


    def test_to_ascii(self):
        ztext = ZText(version=1,get_abbrev_f=self.get_abbrev_f)
        # Check that we terminate the output when we hit an end character
        data = Memory([0,0,0x80,0x00,0,0])
        s = ztext.to_ascii(data,0,0)
        self.assertEqual('      ',s)
        
        # Check explicit length
        s = ztext.to_ascii(data,0,2)
        self.assertEqual('   ',s)
    
    def test_to_ascii_shift(self):
        ztext = ZText(version=3,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual('.',ztext.to_ascii(Memory([0x16,0x45,0x94,0xA5]),0,4))
   
    def test_handle_zchar_v1(self):
        # V1 does not handle abbreviations
        ztext = ZText(version=1,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(ZTextState.DEFAULT,ztext.state)
        for i in range(1,4):
            ztext.handle_zchar(i,)          
            self.assertEqual(ZTextState.DEFAULT, ztext.state)

    def test_handle_zchar_v2(self): 
        ztext = ZText(version=2,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(ZTextState.DEFAULT,ztext.state)
        ztext.handle_zchar(1)
        self.assertEqual(ZTextState.WAITING_FOR_ABBREVIATION, ztext.state)
        ztext.reset()

        for i in range(2,4):
            ztext.handle_zchar(i)          
            self.assertEqual(ZTextState.DEFAULT, ztext.state)
        
    def test_handle_zchar_v3(self):
        ztext = ZText(version=3,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(ZTextState.DEFAULT,ztext.state)
        for i in range(1,4):
            ztext.reset()
            self.screen.reset()
            ztext.handle_zchar(i)          
            self.assertEqual(ZTextState.WAITING_FOR_ABBREVIATION, ztext.state)
            ztext.handle_zchar(5)   

    def test_handle_zchar_6(self):
        # Zchar 6 in alphabet 2 means the next two chars are used to make a single 10-bit char
        ztext = ZText(version=3,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(ZTextState.DEFAULT,ztext.state)
        ztext.handle_zchar(6)
        self.assertEqual(ZTextState.DEFAULT,ztext.state)
        
        ztext.reset()
        ztext.shift(True,False)
        ztext.handle_zchar(6)
        self.assertEqual(ZTextState.GETTING_10BIT_ZCHAR_CHAR1,ztext.state)
        ztext.handle_zchar(1)
        self.assertEqual(ZTextState.GETTING_10BIT_ZCHAR_CHAR2,ztext.state)
        c = ztext.handle_zchar(1)
        self.assertEqual('!',c)
        self.assertEqual(ZTextState.DEFAULT,ztext.state)

    def test_encrypt_text(self):
        # Note this isn't any kind of real encryption, it's simply converting input text
        # to match against dictionary
        ztext = ZText(version=3,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(bytearray([14,5,5,5,5,5]), ztext.encrypt('i'))
        self.assertEqual(bytearray([14,15,16,17,18,19]), ztext.encrypt('ijkLMN'))
        self.assertEqual(bytearray([14,3,8,3,9,5]), ztext.encrypt('i01'))

    def test_encrypt_text_v1(self):
        # See 3.7.1 and 3.5.4
        ztext = ZText(version=1,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(bytearray([14,4,7,8,5,5]), ztext.encrypt('i01'))
        
    def test_encrypt_text_v2(self):
        ztext = ZText(version=2,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(bytearray([14,4,8,9,5,5]), ztext.encrypt('i01'))

class DictionaryTests(unittest.TestCase):
    def setUp(self):
        self.dictionary = Dictionary(Memory([0x01,0x01,0x02,0x00,0x03,0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07]),0)
    
    def test_header(self):
        self.assertEqual([1], self.dictionary.keyboard_codes)
        self.assertEqual(2, self.dictionary.entry_length)
        self.assertEqual(3, self.dictionary.number_of_entries)

    def test_index(self):
        self.assertEqual(3, len(self.dictionary))
        self.assertEqual(bytearray([0,1,2,3]), self.dictionary[0])
        try:    
            self.dictionary[4]
            self.fail('Should have raised an IndexError')
        except IndexError:
            pass # What we expect

class GameMemoryTests(unittest.TestCase):
    def setUp(self):
        path = 'testdata/test.z3'
        if not os.path.exists(path):
            self.fail('Could not find test file test.z3')
        with open(path, 'rb') as f:
            self.story = Story(f.read())
            self.story.reset()

    def test_header(self):
        self.story.game_memory[0]
        try:
            self.story.game_memory[0] = 1
            self.fail('Should have thrown exception')
        except MemoryAccessException:
            pass
        self.story.game_memory.set_flag(0x10,0,1)        
        self.story.game_memory.set_flag(0x10,1,1)        
        self.story.game_memory.set_flag(0x10,2,1)        
        self.assertRaises(MemoryAccessException, self.story.game_memory.set_flag,0x10,3,1)
        self.assertRaises(MemoryAccessException, self.story.game_memory.set_flag,0x10,4,1)
        self.assertRaises(MemoryAccessException, self.story.game_memory.set_flag,0x10,5,1)
        self.assertRaises(MemoryAccessException, self.story.game_memory.set_flag,0x10,6,1)
        self.assertRaises(MemoryAccessException, self.story.game_memory.set_flag,0x10,7,1)

    def test_highmem_access(self):
        himem_address = self.story.header.himem_address
        for i in range(0,2):
            memory = self.story.game_memory
            try:
                memory[himem_address+i]
                self.fail('Should have thrown exception')
            except MemoryAccessException:
                pass
    
            try:
                memory[himem_address+i] = 1
                self.fail('Should have thrown exception')
            except MemoryAccessException:
                pass
    
            self.assertRaises(MemoryAccessException, memory.flag,himem_address+1,1)
            self.assertRaises(MemoryAccessException, memory.set_flag,himem_address+1,1,1)

    def test_static_memory_access(self):
        static_address = self.story.header.static_memory_address
        for i in range(0,2):
            memory = self.story.game_memory
            memory[static_address+i]

            try:
                memory[static_address+i] = 1
                self.fail('Should have thrown exception')
            except MemoryAccessException:
                pass

            memory.flag(static_address+i,2)
            self.assertRaises(MemoryAccessException, memory.set_flag,static_address+1,1,1)


class ValidationTests(unittest.TestCase):
    def test_size(self):
        story = Story(b'')
        try:
            story.reset()
            self.fail('Should have thrown exception')
        except StoryFileException as e:
            self.assertEqual(u'Story file is too short',str(e))

    def test_version(self):
        raw_data = bytearray([0] * 1000)
        
        for version in (0x01,0x02,0x03):
            raw_data[0] = version
            Story(raw_data).reset()
        for version in (0x04,0x05,0x06,0x07,0x08):
            raw_data[0] = version
            try:
                Story(raw_data).reset()
                self.fail('Should have thrown exception.')
            except StoryFileException as e:
                self.assertEqual('Story file version %d is not supported.' % version,str(e))
            

class SampleFileTests(unittest.TestCase):
    def setUp(self):
        path = 'testdata/test.z3'
        if not os.path.exists(path):
            self.fail('Could not find test file test.z3')
        with open(path, 'rb') as f:
            self.story = Story(f.read())
            self.zmachine = Interpreter(self.story,TestOutputStreams(),TestSaveHandler(),TestRestoreHandler())
            self.zmachine.reset()

    def test_randomizer(self):
        # This really isn't a "unit" test. It's more of a smoke test,
        # just to see if the RNG is totally failing
        rng = self.zmachine.story.rng
        for i in range(0,100):
            x = rng.randint(i+1)
            self.assertTrue(x >= 1)
            self.assertTrue(x <= i+1)

        # In predictable mode, should return same value
        rng.enter_predictable_mode(0)
        x = rng.randint(100)
        rng.enter_predictable_mode(0)
        self.assertEqual(x, rng.randint(100))

        # Reset should enter random mode
        self.assertEqual(0,rng.seed)        
        self.zmachine.reset()
        self.assertFalse(rng.seed == 0)

    def test_header(self):
        header = self.zmachine.story.header
        self.assertEqual(3,header.version)
        self.assertEqual(0x0cd4,header.himem_address)
        self.assertEqual(0x0cd5,header.main_routine_addr)
        self.assertEqual(0x0835,header.dictionary_address)
        self.assertEqual(0x0146,header.object_table_address)
        self.assertEqual(0x0102,header.global_variables_address)
        self.assertEqual(0x0835,header.static_memory_address)
        self.assertEqual(0x0042,header.abbrev_address)
        self.assertEqual(0x0326a,header.file_length)
        self.assertEqual(0xf3a4,header.checksum)

        self.assertEqual(0,header.flag_status_line_type)
        self.assertFalse(header.flag_story_two_disk)
        self.assertFalse(header.flag_status_line_not_available)
        self.assertFalse(header.flag_screen_splitting_available)
        self.assertFalse(header.flag_variable_pitch_default)

    def test_checksum(self):
        self.assertEqual(0xf3a4,self.zmachine.story.calculate_checksum())

    def test_dictionary(self):
        dictionary = self.zmachine.story.dictionary
        self.assertEqual([0x2e,0x2c,0x22], dictionary.keyboard_codes)
        self.assertEqual(7,dictionary.entry_length)
        self.assertEqual(0x62,dictionary.number_of_entries)

    def test_vars_stack(self):
        routine = self.zmachine.current_routine()
        try:
            routine[0] # Popping empty stack should throw error
            self.fail()
        except InterpreterException:
            pass
        routine[0]=0x0000
        routine[0]=0xFFFF
        self.assertEqual(0xFFFF,routine[0])
        self.assertEqual(0x0000,routine[0])

    def test_vars_local(self):
        routine = self.zmachine.current_routine()
        routine.local_variables=[3,0x0000,0xFFFF]
        self.assertEqual(3,routine[1])
        self.assertEqual(0x0000,routine[2])
        self.assertEqual(0xFFFF,routine[3])
        self.assertEqual(0,routine[15])

        routine[3] = 4
        self.assertEqual(4,routine[3])

        try:
            routine[4]=5
            self.fail('Should throw exception on assign')
        except InterpreterException:
            pass

    def test_vars_global(self):
        routine = self.zmachine.current_routine()
        self.assertEqual(0x026d, routine[22]) # Check default value from story file
        routine[22] = 0xFFFF
        self.assertEqual(0xFFFF,routine[22])
if __name__ == '__main__':
    unittest.main()
