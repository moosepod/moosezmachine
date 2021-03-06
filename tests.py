""" Tests for zmachine """
import unittest
import os
import inspect
import json

from zmachine.interpreter import Interpreter,StoryFileException,MemoryAccessException,\
                                 OutputStream,OutputStreams,SaveHandler,RestoreHandler,Story,\
                                InterpreterException,QuitException,RestartException,Header,\
                                InvalidSaveDataException,InputStream,InputStreams
from zmachine.text import ZText,ZTextState,ZTextException
from zmachine.memory import Memory
from zmachine.dictionary import Dictionary
from zmachine.instructions import InstructionForm,InstructionType,OperandType,OPCODE_HANDLERS,\
                                  read_instruction,extract_opcode,create_instruction,\
                                  process_operands, extract_literal_string, extract_branch_offset,\
                                  format_description,convert_to_unsigned,\
                                  JumpRelativeAction,CallAction,NextInstructionAction,OperandTypeHint,QuitAction,ReturnAction,\
                                  InstructionException,RestoreAction,RestartAction,SaveAction
import zmachine.instructions as instructions

class TestOutputStream(OutputStream):
    def __init__(self,*args,**kwargs):
        super(TestOutputStream,self).__init__(*args,**kwargs)
        self.new_line_called = False
        self.printed_string = ''
        self.status_shown=False

    def new_line(self):
        self.new_line_called = True

    def print_str(self,msg):
        self.printed_string += msg

    def show_status(self, msg, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        self.status_shown=True

class TestSaveHandler(SaveHandler):
    pass

class TestRestoreHandler(RestoreHandler):
    pass

class TestScreen(object):
    def __init__(self):
        self.top_window_size = 0
        self.window_id = 0

    def split_window(self,lines):
        self.top_window_size = lines

    def set_window(self,window_id):
        self.window_id = window_id

    def supports_screen_splitting(self):
        return True

class TestOutputStreams(OutputStreams):
    def __init__(self):
        super(TestOutputStreams,self).__init__(TestOutputStream(),TestOutputStream())

class TodoTests(unittest.TestCase):
    @unittest.skip('Implement')
    def test_fix_abbrevs(self):
        self.fail('Current abbrevs function for ztext is a hack. Fix!')
    
class InstructionTests(unittest.TestCase):
    def test_create_instruction(self):
        mem = create_instruction(InstructionType.twoOP, 1,[(OperandType.small_constant,0),(OperandType.small_constant,17)],branch_to=0x19)
        self.assertEqual('0100118019', str(mem))

        mem = create_instruction(InstructionType.twoOP, 1,[(OperandType.large_constant,0),(OperandType.small_constant,17)])
        self.assertEqual('c11f000011', str(mem))


    def test_extract_opcode(self):
        # je
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory(b'\x01\x00\x11\x8d\x19'),0)
        self.assertEqual(InstructionForm.long_form, instruction_form)
        self.assertEqual(InstructionType.twoOP,instruction_type)
        self.assertEqual(1, opcode_number)
        self.assertEqual([OperandType.small_constant,OperandType.small_constant], operands)

        # je with multiple
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory(b'\xc1\x57\x05\x04\x05\x01\x16'),0)
        self.assertEqual(InstructionForm.variable_form, instruction_form)
        self.assertEqual(InstructionType.twoOP,instruction_type)
        self.assertEqual(1, opcode_number)
        self.assertEqual([OperandType.small_constant,OperandType.small_constant,OperandType.small_constant,OperandType.omitted], operands)

        # jl
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(Memory(b'\x22\xb2\x14\xe4\x5d'),0)
        self.assertEqual(InstructionForm.long_form, instruction_form)
        self.assertEqual(InstructionType.twoOP,instruction_type)
        self.assertEqual(2, opcode_number)
        self.assertEqual([OperandType.small_constant,OperandType.variable], operands)

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
        self.assertEqual([OperandType.large_constant,OperandType.variable,OperandType.omitted, OperandType.omitted], operands)

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
        self.assertEqual([178,20],[x[0] for x in operands])

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
        self.assertEqual([(2,OperandTypeHint.unsigned),(0x00,OperandTypeHint.signed)], operands)

        # mul
        mem = Memory(b'\xd6\x2f\x03\xe8\x02\x00')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        handler = OPCODE_HANDLERS.get((instruction_type, opcode_number))
        address, operands = process_operands(operands, handler, mem, address,3)
        self.assertEqual([(1000,OperandTypeHint.signed),(2,OperandTypeHint.signed_variable)],operands)

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
        self.assertEqual(36,branch_offset)

    def test_extract_literal_string(self):
        mem = Memory(b'\xb2\x11\xaa\x46\x34\x16\x45\x9c\xa5')
        address,instruction_form, instruction_type,  opcode_number,operands = extract_opcode(mem,0)
        address, literal_string = extract_literal_string(mem, address, ZText(version=3,get_abbrev_f=lambda x: Memory([0x80,0])))
        self.assertEqual("Hello.\n", literal_string)

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
        self.assertEqual('zeroOP:print (Hello.\\n)',description)


class TestStoryMixin(object):
    def __init__(self,*args,**kwargs):
        super(TestStoryMixin,self).__init__(*args,**kwargs)    
        path = 'testdata/test.z3'
        if not os.path.exists(path):
            self.fail('Could not find test file test.z3')
        with open(path, 'rb') as f:
            self.data = f.read()

    def setUp(self):
        self._load_zmachine()

    def _load_zmachine(self,version=3):
        self.story = Story(self.data)
        self.zmachine = Interpreter(self.story,TestOutputStreams(),None,TestSaveHandler(),TestRestoreHandler())
        self.zmachine.screen = TestScreen()
        self.zmachine.reset(force_version=version)
        self.screen = TestOutputStream()
        self.zmachine.output_streams.set_screen_stream(self.screen)


class ObjectTableTests(TestStoryMixin,unittest.TestCase):
    def __init__(self,*args,**kwargs):
        super(ObjectTableTests,self).__init__(*args,**kwargs)    
        path = 'testdata/test.z3'
        if not os.path.exists(path):
            self.fail('Could not find test file test.z3')
        with open(path, 'rb') as f:
            self.story = Story(f.read())
            self.zmachine = Interpreter(self.story,TestOutputStreams(),None,TestSaveHandler(),TestRestoreHandler())

    def test_default_properties(self):
        self.assertEqual([0x0000] * 31, self.story.object_table.property_defaults)

    def test_set_and_test_attribute(self):
        table = self.story.object_table
        self.assertTrue(table.test_attribute(1,26))
        self.assertFalse(table.test_attribute(1,0))

        obj = self.story.object_table[1]
        self.assertEqual('00000000000000000000000000100000',str(obj['attributes']))
        table.set_attribute(1,0,True)
        table.set_attribute(1,8,True)
        table.set_attribute(1,16,True)
        table.set_attribute(1,24,True)
        obj = self.story.object_table[1]
        self.assertEqual('10000000100000001000000010100000',str(obj['attributes']))
        table.set_attribute(1,0,False)
        obj = self.story.object_table[1]
        self.assertEqual('00000000100000001000000010100000',str(obj['attributes']))

        for i in range(0,32):
            self.assertFalse(table.test_attribute(10,i))
            table.set_attribute(10,i,True)
            self.assertTrue(table.test_attribute(10,i))
            table.set_attribute(10,i,False)
            self.assertFalse(table.test_attribute(10,i))

    def test_object_in(self):
        table = self.story.object_table
        self.assertTrue(table.is_child_of(1,11))
        self.assertFalse(table.is_child_of(8,5))
        self.assertFalse(table.is_child_of(1,1))

    def test_object_is_sibling(self):
        table = self.story.object_table
        self.assertFalse(table.is_sibling_of(7,5))
        self.assertFalse(table.is_sibling_of(8,5))
        self.assertFalse(table.is_sibling_of(1,1))

    def test_insert_obj(self):
        table = self.story.object_table
        self.assertTrue(1,table[11]['child'])
        self.assertTrue(table.is_child_of(1,11))

        table.insert_obj(7,11)
        self.assertTrue(table.is_child_of(7,11))
        self.assertTrue(table.is_sibling_of(1,7))
        self.assertTrue(7,table[11]['child'])
        self.assertTrue(table.is_child_of(1,11))
        
        # Ensure child relationship of old parent correct
        table.insert_obj(7,2)
        self.assertTrue(table.is_child_of(7,2))
        self.assertFalse(table.is_child_of(7,11))
        self.assertEqual(2,table.get_parent(7))
        self.assertEqual(7,table.get_child(2))
        self.assertEqual(1,table.get_child(11))
        self.assertEqual(11,table.get_parent(1))

        # Setup so we can test that inserting an object correctly preserves old sibling
        # After these inserts, children of 2 are 5,4,3,7
        table.insert_obj(3,2)
        table.insert_obj(4,2)
        table.insert_obj(5,2)

        # After the insert below, children should be 5,4,7
        table.insert_obj(3,6)
        child_id = table.get_child(2)
        self.assertEqual(5,child_id)
        child_id = table.get_sibling(child_id)
        self.assertEqual(4,child_id)
        child_id = table.get_sibling(child_id)
        self.assertEqual(7,child_id)
        self.assertEqual(0, table.get_sibling(child_id))

        self.assertEqual(3, table.get_child(6))
        self.assertEqual(0, table.get_sibling(3))

        # Verify removing first child. After this children should be 4,7
        table.insert_obj(5,6)
        child_id = table.get_child(2)
        self.assertEqual(4,child_id)
        child_id = table.get_sibling(child_id)
        self.assertEqual(7,child_id)
        self.assertEqual(0, table.get_sibling(child_id))
        
        self.assertEqual(5, table.get_child(6))
        self.assertEqual(3, table.get_sibling(5))
        self.assertEqual(0, table.get_sibling(3))

    def test_remove_obj(self):
        table = self.story.object_table
        self.assertEqual(11,table[1]['parent'])
        table.remove_obj(1)
        self.assertEqual(0,table[1]['parent'])

        self.assertEqual(0,table[11]['parent'])
        table.remove_obj(11)
        self.assertEqual(0,table[11]['parent'])

    def test_get_property(self):
        obj = self.story.object_table[1]
        self.assertEqual({}, obj['properties'])
        self.assertEqual(0, obj['child'])
        self.assertEqual(0, obj['sibling'])
        self.assertEqual(11, obj['parent'])
        self.assertEqual('The first room',self.zmachine.get_ztext().to_ascii(obj['short_name_zc'])[0])
        self.assertEqual('00000000000000000000000000100000',str(obj['attributes']))

        obj = self.story.object_table[10]
        self.assertEqual(0, obj['child'])
        self.assertEqual(0, obj['sibling'])
        self.assertEqual(0, obj['parent'])
        self.assertEqual('',self.zmachine.get_ztext().to_ascii(obj['short_name_zc'])[0])
        self.assertEqual('00000000000000000000000000000000',str(obj['attributes']))
        self.assertEqual({16: {'data': bytearray(b'\xff'), 'address': 558, 'size': 1}, 
            17: {'data': bytearray(b'\x00\x02'), 'address': 555, 'size': 2}, 
            10: {'data': bytearray(b'\x00\n'), 'address': 574, 'size': 2}, 
            11: {'data': bytearray(b'\x00\x00'), 'address': 571, 'size': 2}, 
            12: {'data': bytearray(b'\x00\x00'), 'address': 568, 'size': 2}, 
            13: {'data': bytearray(b'\n'), 'address': 566, 'size': 1}, 
            14: {'data': bytearray(b'\x00\x00'), 'address': 563, 'size': 2}, 
            15: {'data': bytearray(b'\x00\x00'), 'address': 560, 'size': 2}},
            obj['properties'])

        obj = self.story.object_table[11]
        self.assertEqual({}, obj['properties'])
        self.assertEqual(1, obj['child'])
        self.assertEqual(0, obj['sibling'])
        self.assertEqual(0, obj['parent'])
        self.assertEqual('',self.zmachine.get_ztext().to_ascii(obj['short_name_zc'])[0])
        self.assertEqual('00000000000011111111111111111111',str(obj['attributes']))

    def test_get_next_prop(self):
        table = self.story.object_table
        self.assertEqual(19, table.get_next_prop(2,0))
        self.assertEqual(18, table.get_next_prop(2,19))
        self.assertEqual(0, table.get_next_prop(2,18))

    def test_get_property_address(self):
        table = self.zmachine.story.object_table
        self.assertEqual(508, table.get_property_address(2,18))
        self.assertEqual(503, table.get_property_address(2,19))
        self.assertEqual(0, table.get_property_address(2,3))

    def test_get_property_lengths(self):
        table = self.zmachine.story.object_table
        self.assertEqual(2, table.get_property_length(table.get_property_address(2,18)))
        self.assertEqual(4, table.get_property_length(table.get_property_address(2,19)))
        self.assertEqual(0, table.get_property_length(table.get_property_address(2,0)))

    def test_get_default(self):
        table = self.zmachine.story.object_table
        table.property_defaults[0] = 0xff
        table = self.story.object_table
        self.assertEqual(0x00ff, table.get_default_property(1))

class InterpreterStepTests(TestStoryMixin,unittest.TestCase):
    def test_next_address(self):
        old_pc = self.zmachine.pc
        NextInstructionAction(old_pc+10).apply(self.zmachine)
        self.assertEqual(old_pc+10,self.zmachine.pc)

    def test_call_and_return(self):
        self.assertEqual(1,len(self.zmachine.routines))
        old_pc = self.zmachine.pc
        routine = self.zmachine.current_routine()
        routine.local_variables = [1,2,3,4,5,6]
        
        CallAction(0x1000,5,old_pc+10,[]).apply(self.zmachine)
        self.assertEqual(2,len(self.zmachine.routines))
        routine = self.zmachine.current_routine()
        self.assertEqual(0x1009,self.zmachine.pc)
        self.assertEqual(5,routine.store_to)
        self.assertEqual(old_pc + 10, routine.return_to_address)

        ReturnAction(111).apply(self.zmachine)
        routine = self.zmachine.current_routine()
        self.assertEqual(old_pc + 10, self.zmachine.pc)
        self.assertEqual(111,routine[5])
        self.assertEqual(1,len(self.zmachine.routines))

    def test_call_with_locals(self):
        self.assertEqual(1,len(self.zmachine.routines))
        old_pc = self.zmachine.pc
        routine = self.zmachine.current_routine()
        
        CallAction(0x1000,5,old_pc+10,[1,2,3]).apply(self.zmachine)
        self.assertEqual(2,len(self.zmachine.routines))
        routine = self.zmachine.current_routine()
        self.assertEqual(4105   ,self.zmachine.pc)
        self.assertEqual(5,routine.store_to)
        self.assertEqual(old_pc + 10, routine.return_to_address)
        self.assertEqual(1, routine[1])
        self.assertEqual(2, routine[2])
        self.assertEqual(3, routine[3])

    def test_jump_relative(self):
        old_pc = self.zmachine.pc
        JumpRelativeAction(10,old_pc+4).apply(self.zmachine)
        self.assertEqual(old_pc+12,self.zmachine.pc)

    def test_quit(self):
        self.assertRaises(QuitException, QuitAction(self.zmachine.pc).apply,self.zmachine)

    def test_restart(self):
        self.zmachine.story.header.set_flag(Header.FLAGS_2,0,1)
        self.zmachine.story.header.set_flag(Header.FLAGS_2,1,1)
        try:
            RestartAction().apply(self.zmachine)
            self.fail('Should have thrown restart error')
        except RestartException as e:
            self.assertEqual((True,True),e.restart_flags)

        self.zmachine.story.header.set_flag(Header.FLAGS_2,0,0)
        self.zmachine.story.header.set_flag(Header.FLAGS_2,1,1)
        try:
            RestartAction().apply(self.zmachine)
            self.fail('Should have thrown restart error')
        except RestartException as e:
            self.assertEqual((False,True), e.restart_flags)


class ObjectInstructionsTests(TestStoryMixin,unittest.TestCase):
    def test_insert_obj(self):
        object_table = self.zmachine.story.object_table
        self.assertTrue(object_table.is_child_of(1,11))
        self.assertFalse(object_table.is_child_of(2,11))
        self.assertFalse(object_table.is_sibling_of(1,2))

        memory = create_instruction(InstructionType.twoOP,14,[(OperandType.small_constant,2),(OperandType.small_constant,11)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:insert_obj 2 11',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))

        self.assertTrue(object_table.is_child_of(1,11))
        self.assertTrue(object_table.is_child_of(2,11))
        self.assertTrue(object_table.is_sibling_of(1,2))

    def test_tst_attr(self):
        memory = create_instruction(InstructionType.twoOP,10,[(OperandType.small_constant,1),(OperandType.small_constant,26)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:test_attr 1 26 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(29,result.branch_offset)

        self.zmachine.current_routine()[200] = 0
        memory = create_instruction(InstructionType.twoOP,10,[(OperandType.small_constant,1),(OperandType.variable,200)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:test_attr 1 Gb8 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

    def test_set_attr(self):
        object_table = self.zmachine.story.object_table
        self.assertFalse(object_table.test_attribute(2,0))
        memory = create_instruction(InstructionType.twoOP,11,[(OperandType.small_constant,2),(OperandType.small_constant,0)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:set_attr 2 0',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(3,result.next_address)
        self.assertTrue(object_table.test_attribute(2,0))

        self.assertFalse(object_table.test_attribute(2,10))
        self.zmachine.current_routine()[200] = 10
        memory = create_instruction(InstructionType.twoOP,11,[(OperandType.small_constant,2),(OperandType.variable,200)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:set_attr 2 Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(3,result.next_address)
        self.assertTrue(object_table.test_attribute(2,10))

    def test_clear_attr(self):
        object_table = self.zmachine.story.object_table
        self.assertTrue(object_table.test_attribute(1,26))
        memory = create_instruction(InstructionType.twoOP,12,[(OperandType.small_constant,1),(OperandType.small_constant,26)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:clear_attr 1 26',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(3,result.next_address)
        self.assertFalse(object_table.test_attribute(1,26))

        object_table.set_attribute(2,10,True)
        self.zmachine.current_routine()[200] = 10
        memory = create_instruction(InstructionType.twoOP,12,[(OperandType.small_constant,2),(OperandType.variable,200)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:clear_attr 2 Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(3,result.next_address)
        self.assertFalse(object_table.test_attribute(2,10))

    def test_jin(self):
        # Object 1 is in object 11 (11 is parent of 1)
        memory = create_instruction(InstructionType.twoOP,6,[(OperandType.small_constant,1),(OperandType.small_constant,11)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jin 1 11 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(29,result.branch_offset)

        # Object 11 is not object 1 (11 is parent of 1)
        memory = create_instruction(InstructionType.twoOP,6,[(OperandType.small_constant,11),(OperandType.small_constant,1)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jin 11 1 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))

        # Verify var support
        self.zmachine.current_routine().local_variables = [1,11]
        memory = create_instruction(InstructionType.twoOP,6,[(OperandType.variable,1),(OperandType.variable,2)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jin L00 L01 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(29,result.branch_offset)

    def test_get_sibling(self):
        routine = self.zmachine.current_routine()
        table = self.zmachine.story.object_table
        table.insert_obj(7,11)
        memory = create_instruction(InstructionType.oneOP,1,[(OperandType.small_constant,7)],branch_to=0x1d,store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:get_sibling 7 -> Gb8 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(0x1d,result.branch_offset)
        self.assertEqual(1,routine[200])

        memory = create_instruction(InstructionType.oneOP,1,[(OperandType.small_constant,11)],branch_to=0x1d,store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:get_sibling 11 -> Gb8 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[200])

    def test_get_child(self):
        routine = self.zmachine.current_routine()
        table = self.zmachine.story.object_table
        memory = create_instruction(InstructionType.oneOP,2,[(OperandType.small_constant,11)],branch_to=0x1d,store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:get_child 11 -> Gb8 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(0x1d,result.branch_offset)
        self.assertEqual(1,routine[200])

        memory = create_instruction(InstructionType.oneOP,2,[(OperandType.small_constant,1)],branch_to=0x1d,store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:get_child 1 -> Gb8 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[200])

        memory = create_instruction(InstructionType.oneOP,2,[(OperandType.small_constant,1)],branch_to=0x1d,branch_if_true=False,store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:get_child 1 -> Gb8 ?!001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(0x1d,result.branch_offset)
        self.assertEqual(0,routine[200])

    def test_get_parent(self):
        routine = self.zmachine.current_routine()
        table = self.zmachine.story.object_table
        memory = create_instruction(InstructionType.oneOP,3,[(OperandType.small_constant,1)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:get_parent 1 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(11,routine[200])

        memory = create_instruction(InstructionType.oneOP,3,[(OperandType.small_constant,11)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:get_parent 11 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[200])

    def test_get_prop_len(self):
        routine = self.zmachine.current_routine()
        table = self.zmachine.story.object_table
        addr = table.get_property_address(2,18)
        memory = create_instruction(InstructionType.oneOP,4,[(OperandType.large_constant,addr)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:get_prop_len %s -> Gb8' % addr,description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(2,routine[200])

        addr = table.get_property_address(2,100)
        memory = create_instruction(InstructionType.oneOP,4,[(OperandType.large_constant,addr)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:get_prop_len %s -> Gb8' % addr,description)
        result = handler_f(self.zmachine)
        self.assertEqual(0,routine[200])

    def test_get_prop_addr(self):
        routine = self.zmachine.current_routine()
        table = self.zmachine.story.object_table
        memory = create_instruction(InstructionType.twoOP,0x12,[(OperandType.small_constant,2),(OperandType.small_constant,18)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:get_prop_addr 2 18 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(508,routine[200])

        memory = create_instruction(InstructionType.twoOP,0x12,[(OperandType.small_constant,2),(OperandType.small_constant,20)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:get_prop_addr 2 20 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[200])

    def test_remove_obj(self):
        routine = self.zmachine.current_routine()
        table = self.zmachine.story.object_table
        self.assertEqual(11, table[1]['parent'])
        memory = create_instruction(InstructionType.oneOP,9,[(OperandType.small_constant,1)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:remove_obj 1',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0, table[1]['parent'])

        memory = create_instruction(InstructionType.oneOP,9,[(OperandType.small_constant,11)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:remove_obj 11',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0, table[11]['parent'])

    def test_print_obj(self):
        memory = create_instruction(InstructionType.oneOP,0x0A,[(OperandType.small_constant,1)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:print_obj 1',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual('The first room',self.screen.printed_string)

        memory = create_instruction(InstructionType.oneOP,0x0A,[(OperandType.large_constant,300)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:print_obj 300',description)
        self.assertRaises(InstructionException, handler_f, self.zmachine)

    def test_put_prop(self):
        routine = self.zmachine.current_routine()
        object_table = self.zmachine.story.object_table
        memory = create_instruction(InstructionType.varOP,3,[(OperandType.small_constant,10),(OperandType.small_constant,16),(OperandType.large_constant,0xffff)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('varOP:put_prop 10 16 65535' ,description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(bytearray(b'\xff'),object_table[10]['properties'][16]['data'])

        memory = create_instruction(InstructionType.varOP,3,[(OperandType.small_constant,10),(OperandType.small_constant,17),(OperandType.large_constant,0xffff)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('varOP:put_prop 10 17 65535',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(bytearray(b'\xff\xff'),object_table[10]['properties'][17]['data'])

        memory = create_instruction(InstructionType.varOP,3,[(OperandType.small_constant,2),(OperandType.small_constant,19),(OperandType.large_constant,0xffff)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('varOP:put_prop 2 19 65535' ,description)
        self.assertRaises(InterpreterException, handler_f, self.zmachine)

    def test_get_prop(self):
        routine = self.zmachine.current_routine()
        memory = create_instruction(InstructionType.twoOP,0x11,[(OperandType.small_constant,10),(OperandType.small_constant,16)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:get_prop 10 16 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0xff,routine[200])

        memory = create_instruction(InstructionType.twoOP,0x11,[(OperandType.small_constant,10),(OperandType.small_constant,17)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:get_prop 10 17 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0x0002,routine[200])

        memory = create_instruction(InstructionType.twoOP,0x11,[(OperandType.small_constant,2),(OperandType.small_constant,19)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:get_prop 2 19 -> Gb8',description)
        self.assertRaises(InstructionException, handler_f, self.zmachine)

        self.zmachine.story.object_table.property_defaults[17] = 0xff
        memory = create_instruction(InstructionType.twoOP,0x11,[(OperandType.small_constant,10),(OperandType.small_constant,18)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:get_prop 10 18 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertEqual(0x00ff,routine[200])

    def test_get_next_prop(self):
        routine = self.zmachine.current_routine()
        table = self.zmachine.story.object_table
        memory = create_instruction(InstructionType.twoOP,0x13,[(OperandType.small_constant,2),(OperandType.small_constant,19)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:get_next_prop 2 19 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(18,routine[200])

        memory = create_instruction(InstructionType.twoOP,0x13,[(OperandType.small_constant,2),(OperandType.small_constant,18)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:get_next_prop 2 18 -> Gb8' ,description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[200])

        memory = create_instruction(InstructionType.twoOP,0x13,[(OperandType.small_constant,2),(OperandType.small_constant,20)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:get_next_prop 2 20 -> Gb8',description)
        self.assertRaises(InterpreterException, handler_f, self.zmachine)

class RoutineInstructionsTests(TestStoryMixin,unittest.TestCase):
    def test_ret(self):
        memory = create_instruction(InstructionType.oneOP,0x0b,[(OperandType.small_constant,178)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:ret 178',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,ReturnAction))
        self.assertEqual(178,result.result)

    def test_ret_popped(self):
        self.zmachine.push_game_stack(0xfa)
        self.zmachine.push_game_stack(0xff)
        memory = create_instruction(InstructionType.zeroOP,8,[])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('zeroOP:ret_popped',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,ReturnAction))
        self.assertEqual(0xff,result.result)
        self.assertEqual(0xfa, self.zmachine.peek_game_stack())

    def test_rtrue(self):
        memory = Memory(b'\xb0\x00')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('zeroOP:rtrue',description)
        result = handler_f(self.zmachine)

        self.assertTrue(isinstance(result,ReturnAction))
        self.assertEqual(1,result.result)

    def test_rfalse(self):
        memory = Memory(b'\xb1\x00')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('zeroOP:rfalse',description)
        result = handler_f(self.zmachine)

        self.assertTrue(isinstance(result,ReturnAction))
        self.assertEqual(0,result.result)

    def test_jump(self):
        memory = Memory(b'\x8c\x00\x07')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:jump 7',description)
        result = handler_f(self.zmachine)

        # Offset is relative. Formula is next address + offset - 2
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(7,result.branch_offset)

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
        memory = create_instruction(InstructionType.twoOP,2,[(OperandType.small_constant,178),(OperandType.small_constant,200)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jl 178 200 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(29,result.branch_offset)

        # Gt, don't jump
        memory = create_instruction(InstructionType.twoOP,2,[(OperandType.small_constant,20),(OperandType.small_constant,1)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jl 20 1 ?001d',description)
        result = handler_f(self.zmachine)    
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

        # equal, don't jump
        memory = create_instruction(InstructionType.twoOP,2,[(OperandType.small_constant,178),(OperandType.small_constant,178)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jl 178 178 ?001d',description)
        result = handler_f(self.zmachine)    
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

        # Test inverse
        memory = create_instruction(InstructionType.twoOP,2,[(OperandType.small_constant,1),(OperandType.small_constant,20)],branch_to=0x1d,branch_if_true=False)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jl 1 20 ?!001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

        # Test signed
        memory = create_instruction(InstructionType.twoOP,2,[(OperandType.small_constant,1),(OperandType.large_constant,-2)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jl 1 -2 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(7  ,result.next_address)

    def test_jg(self):
        # Item is greater than, so jump
        memory = create_instruction(InstructionType.twoOP,3,[(OperandType.small_constant,20),(OperandType.small_constant,1)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jg 20 1 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(29,result.branch_offset)

        # less than, don't jump
        memory = create_instruction(InstructionType.twoOP,3,[(OperandType.small_constant,20),(OperandType.small_constant,178)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jg 20 178 ?001d',description)
        result = handler_f(self.zmachine)    
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

        # equal, don't jump
        memory = create_instruction(InstructionType.twoOP,3,[(OperandType.small_constant,178),(OperandType.small_constant,178)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jg 178 178 ?001d',description)
        result = handler_f(self.zmachine)    
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,result.next_address)

        # Test inverse
        memory = create_instruction(InstructionType.twoOP,3,[(OperandType.small_constant,20),(OperandType.small_constant,178)],branch_to=0x1d,branch_if_true=False)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jg 20 178 ?!001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(29,result.branch_offset)

        # Test signed
        memory = create_instruction(InstructionType.twoOP,3,[(OperandType.large_constant,-2),(OperandType.small_constant,1)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:jg -2 1 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(7  ,result.next_address)

    def test_jz(self):
        # Item is not 0 so don't jump
        memory = create_instruction(InstructionType.oneOP,0,[(OperandType.small_constant,20)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:jz 20 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4,result.next_address)

        # Zero, jump
        memory = create_instruction(InstructionType.oneOP,0,[(OperandType.small_constant,0)],branch_to=0x1d)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:jz 0 ?001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(29,result.branch_offset)

        # Test inverse
        memory = create_instruction(InstructionType.oneOP,0,[(OperandType.small_constant,0)],branch_to=0x1d,branch_if_true=False)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:jz 0 ?!001d',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4,result.next_address)

        # Test variant
        memory=Memory(b'\x90\x00\xc0')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:jz 0 RFALSE',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,ReturnAction))
        self.assertEqual(0,result.result)


    def test_call(self):
        memory=Memory(b'\xe0\x3f\x16\x34\x00')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('varOP:call 11368 -> (SP)',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,CallAction))
        self.assertEqual(5,result.return_to)
        self.assertEqual(11368,result.routine_address)
        self.assertEqual(0,result.store_to)
        self.assertEqual([], result.local_vars)

        self.zmachine.current_routine()[200] = 3
        memory = create_instruction(InstructionType.varOP,0,[(OperandType.large_constant,987),(OperandType.small_constant,1),(OperandType.small_constant,2),(OperandType.variable,200)],store_to=150)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('varOP:call 1974 1 2 Gb8 -> G86',description)
        result = handler_f(self.zmachine)
        self.assertEqual(8,result.return_to)
        self.assertEqual(1974,result.routine_address)
        self.assertEqual(150,result.store_to)
        self.assertEqual([1,2,3], result.local_vars)

class ArithmaticInstructionsTests(TestStoryMixin,unittest.TestCase):
    def test_add(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [1,2]

        # Test unsigned
        memory = create_instruction(InstructionType.twoOP,20,[(OperandType.small_constant,0x12),(OperandType.small_constant,0)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:add 18 0 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(18,routine[200])

        # Test signed
        memory = create_instruction(InstructionType.twoOP,20,[(OperandType.large_constant,0xffff),(OperandType.small_constant,0)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:add -1 0 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0xffff,routine[200])

        # Test vars
        routine[202] = 10
        memory = create_instruction(InstructionType.twoOP,20,[(OperandType.small_constant,5),(OperandType.variable,202)],store_to=0)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:add 5 Gba -> (SP)',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(15,routine[0])

    def test_sub(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [1,2]

        # Test unsigned
        memory = create_instruction(InstructionType.twoOP,21,[(OperandType.small_constant,0x12),(OperandType.small_constant,0)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:sub 18 0 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(18,routine[200])

        # Test signed
        memory = create_instruction(InstructionType.twoOP,21,[(OperandType.small_constant,0),(OperandType.small_constant,1)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:sub 0 1 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0xffff,routine[200])

        # Test vars
        routine[202] = 10
        memory = create_instruction(InstructionType.twoOP,21,[(OperandType.small_constant,15),(OperandType.variable,202)],store_to=0)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:sub 15 Gba -> (SP)',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5,routine[0])

    def test_div(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [1,2]

        # Test unsigned
        memory = create_instruction(InstructionType.twoOP,23,[(OperandType.small_constant,0x12),(OperandType.small_constant,1)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:div 18 1 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(18,routine[200])

        # Test signed
        memory = create_instruction(InstructionType.twoOP,23,[(OperandType.large_constant,0xffff),(OperandType.small_constant,1)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:div -1 1 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0xffff,routine[200])

        # Test vars
        routine[202] = 5
        memory = create_instruction(InstructionType.twoOP,23,[(OperandType.small_constant,15),(OperandType.variable,202)],store_to=0)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:div 15 Gba -> (SP)',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(3,routine[0])

        # Test round
        memory = create_instruction(InstructionType.twoOP,23,[(OperandType.small_constant,1),(OperandType.small_constant,2)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:div 1 2 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[200])

        # Test exception
        memory = create_instruction(InstructionType.twoOP,23,[(OperandType.small_constant,1),(OperandType.small_constant,0)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:div 1 0 -> Gb8',description)
        self.assertRaises(InstructionException, handler_f,self.zmachine)

    def test_mod(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [1,2]

        # Test unsigned
        memory = create_instruction(InstructionType.twoOP,24,[(OperandType.small_constant,0x12),(OperandType.small_constant,1)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:mod 18 1 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[200])

        # Test signed
        memory = create_instruction(InstructionType.twoOP,24,[(OperandType.large_constant,0xffff),(OperandType.small_constant,1)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:mod -1 1 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[200])

        # Test vars
        routine[202] = 5
        memory = create_instruction(InstructionType.twoOP,24,[(OperandType.small_constant,15),(OperandType.variable,202)],store_to=0)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:mod 15 Gba -> (SP)',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[0])

        # Test remainder
        memory = create_instruction(InstructionType.twoOP,24,[(OperandType.small_constant,1),(OperandType.small_constant,2)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:mod 1 2 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(1,routine[200])

        # Test exception
        memory = create_instruction(InstructionType.twoOP,24,[(OperandType.small_constant,1),(OperandType.small_constant,0)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:mod 1 0 -> Gb8',description)
        self.assertRaises(InstructionException, handler_f,self.zmachine)

        # Test negative
        routine[201] = convert_to_unsigned(-13)
        routine[202] = convert_to_unsigned(5)
        memory = create_instruction(InstructionType.twoOP,24,[(OperandType.variable,201),(OperandType.variable,202)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        result = handler_f(self.zmachine)
        self.assertEqual('twoOP:mod Gb9 Gba -> Gb8',description)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(convert_to_unsigned(-3),routine[200])

    def test_inc(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [0xffff,10]

        memory = create_instruction(InstructionType.oneOP,5,[(OperandType.small_constant,1)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:inc 1',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[1])

        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:inc 1',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(1,routine[1])

    def test_dec(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [1,10]

        memory = create_instruction(InstructionType.oneOP,6,[(OperandType.small_constant,1)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:dec 1',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0,routine[1])

        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:dec 1',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0xffff,routine[1])

    def test_inc_chk(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [0,1,2,3,4,5]

        # Increment and branch
        memory=Memory([0x05,0x02,0x00,0xd4])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:inc_chk 2 0 ?0014',description)

        self.assertEqual(1,self.zmachine.current_routine()[2])
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(20,result.branch_offset)
        self.assertEqual(2,self.zmachine.current_routine()[2])

        # Increment and don't branch
        memory=Memory([0x05,0x02,0x06,0xd4])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:inc_chk 2 6 ?0014',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(3,self.zmachine.current_routine()[2])

        # Invert
        memory=Memory([0x05,0x02,0x00,0x54])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:inc_chk 2 0 ?!0014',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4,self.zmachine.current_routine()[2])

        # Negative 
        routine[100] = 0xFFFA
        memory = create_instruction(InstructionType.twoOP,5,[(OperandType.small_constant,100),(OperandType.large_constant,1000)],branch_to=0x14)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:inc_chk 100 1000 ?0014',description)
        result = handler_f(self.zmachine)
        self.assertEqual(0xFFFB, routine[100])
        self.assertTrue(isinstance(result,NextInstructionAction))

    def test_dec_chk(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [0,3,2,3,4,5]

        # Decrement and branch
        memory=Memory([0x04,0x02,0x06,0xd4])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:dec_chk 2 6 ?0014',description)

        self.assertEqual(3,self.zmachine.current_routine()[2])
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(20,result.branch_offset)
        self.assertEqual(2,self.zmachine.current_routine()[2])

        # Decrement and don't branch
        memory=Memory([0x04,0x02,0x00,0xd4])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:dec_chk 2 0 ?0014',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(1,self.zmachine.current_routine()[2])

        # Invert
        memory=Memory([0x04,0x06,0x05,0x54])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:dec_chk 6 5 ?!0014',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4,self.zmachine.current_routine()[6])

        # Negative 
        routine[100] = 0XFFFF
        memory = create_instruction(InstructionType.twoOP,4,[(OperandType.small_constant,100),(OperandType.large_constant,-1)],branch_to=0x14)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:dec_chk 100 -1 ?0014',description)
        result = handler_f(self.zmachine)
        self.assertEqual(0xFFFE, routine[100])
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(0x14,result.branch_offset)

    def test_mul(self):
        routine = self.zmachine.current_routine()
        routine.local_variables = [1,2]

        # Test unsigned
        memory=Memory(b'\xd6\x2f\x03\xe8\x02\x00')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:mul 1000 L01 -> (SP)',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(2000,routine[0])

        # Test signed
        memory=Memory(b'\xd6\x2f\xff\xff\x01\x30')
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:mul -1 L00 -> G20',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(convert_to_unsigned(-1),routine[48])

class ScreenInstructionsTests(TestStoryMixin,unittest.TestCase):
    def test_sread(self):
        called = {}
        def stub_read_and_process(text_buffer_addr, parse_buffer_addr,called=called):
            self.assertEqual(text_buffer_addr,2222)
            self.assertEqual(parse_buffer_addr,1111)
            called['called'] = True

        memory = create_instruction(InstructionType.varOP,228,[(OperandType.large_constant,2222),(OperandType.large_constant,1111)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('varOP:sread 2222 1111',description)
        self.zmachine.read_and_process = stub_read_and_process
        result = handler_f(self.zmachine)        
        self.assertTrue(called.get('called'))

    def test_set_window(self):
        self.assertEqual(0, self.zmachine.screen.window_id)
        memory = create_instruction(InstructionType.varOP,11,[(OperandType.small_constant,1)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('varOP:set_window 1',description)
        result = handler_f(self.zmachine)        
        self.assertEqual(1, self.zmachine.screen.window_id)

    def test_split_window(self):
        self.assertEqual(0, self.zmachine.screen.top_window_size)
        memory = create_instruction(InstructionType.varOP,10,[(OperandType.small_constant,10)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('varOP:split_window 10',description)
        result = handler_f(self.zmachine)        
        self.assertEqual(10, self.zmachine.screen.top_window_size)

    @unittest.skip('To be implemented')
    def test_output_stream(self):
        self.fail('Still need to implment stream 3')

    def test_input_stream(self):
        input_streams = self.zmachine.input_streams = InputStreams(InputStream(), InputStream())
        input_streams.select_stream(InputStreams.KEYBOARD)
        self.assertEqual(input_streams.active_stream, input_streams.keyboard_stream)
        memory = create_instruction(InstructionType.varOP,244,[(OperandType.small_constant,1)])
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('varOP:input_stream 1',description)
        result = handler_f(self.zmachine)        
        self.assertEqual(input_streams.active_stream, input_streams.command_file_stream)

    def test_print(self):
        memory=Memory(b'\xb2\x11\xaa\x46\x34\x16\x45\x9c\xa5')
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('zeroOP:print (Hello.\\n)',description)

        self.assertEqual('',self.screen.printed_string)
        result = handler_f(self.zmachine)        
        self.assertEqual('Hello.\n',self.screen.printed_string)

    def test_print_ret(self):
        memory = create_instruction(InstructionType.zeroOP,3,[],literal_string_bytes=[0x16,0x45,0x94,0xA5])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('zeroOP:print_ret (.)',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,ReturnAction))
        self.assertEqual(result.result, 1)
        self.assertEqual('.\n',self.screen.printed_string)

    def test_print_char(self):
        memory = create_instruction(InstructionType.varOP,5,[(OperandType.small_constant,65)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('varOP:print_char 65',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual('A',self.screen.printed_string)

    def test_print_paddr(self):
        self.story.game_memory[0x0820] = 0x16
        self.story.game_memory[0x0821] = 0x45
        self.story.game_memory[0x0822] = 0x94
        self.story.game_memory[0x0823] = 0xA5
        self.zmachine.current_routine().local_variables=[0,0,0]
        self.zmachine.current_routine()[3] = 0x0410

        memory = Memory(b'\xad\x03')
        self.assertEqual('',self.screen.printed_string)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('oneOP:print_paddr L02', description)
        handler_f(self.zmachine)
        self.assertEqual('.',self.screen.printed_string)
   
    def test_print_addr(self):
        memory = Memory(b'\xa7\xff')
        self.story.game_memory[0x0820] = 0x16
        self.story.game_memory[0x0821] = 0x45
        self.story.game_memory[0x0822] = 0x94
        self.story.game_memory[0x0823] = 0xA5
        self.zmachine.current_routine()[255] = 0x0820
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('oneOP:print_addr Gef',description)
        
        self.assertEqual('',self.screen.printed_string)
        handler_f(self.zmachine)
        self.assertEqual('.',self.screen.printed_string)

    def test_new_line(self):
        memory = Memory(b'\xbb\x00')
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('zeroOP:new_line',description)
        
        self.assertFalse(self.screen.new_line_called)
        result = handler_f(self.zmachine)        
        self.assertTrue(self.screen.new_line_called)

    def test_print_num(self):
        memory = Memory(b'\xe6\xbf\x11')
        self.zmachine.current_routine()[17] = 20
        self.assertEqual('',self.screen.printed_string)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('varOP:print_num G01',description)
        result = handler_f(self.zmachine)        
        self.assertEqual('20',self.screen.printed_string)

        # Test signed
        self.screen.printed_string=''
        self.zmachine.current_routine()[17] = 0xffff
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        result = handler_f(self.zmachine)        
        self.assertEqual('-1',self.screen.printed_string)

class MiscInstructionsTests(TestStoryMixin,unittest.TestCase):
    def test_random(self):
        rng = self.zmachine.story.rng
        rng.enter_predictable_mode(1)
        old_seed = rng.seed
        current_routine = self.zmachine.current_routine()
        memory = create_instruction(InstructionType.varOP,7,[(OperandType.small_constant,0x12)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('varOP:random 18 -> Gb8',description)
        result = handler_f(self.zmachine)        
        self.assertEqual(5, current_routine[200])
        self.assertEqual(old_seed, rng.seed)

        # Range of 0 should randomize seed
        memory = create_instruction(InstructionType.varOP,7,[(OperandType.small_constant,0)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('varOP:random 0 -> Gb8',description)
        result = handler_f(self.zmachine)        
        self.assertNotEqual(old_seed, rng.seed)

        # Negative range should set random to that seed
        memory = create_instruction(InstructionType.varOP,7,[(OperandType.large_constant,0xffff)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('varOP:random -1 -> Gb8',description)
        result = handler_f(self.zmachine)        
        self.assertEqual(0, current_routine[200])
        self.assertEqual(0xffff, rng.seed)


    def test_push(self):
        self.assertEqual(None,self.zmachine.peek_game_stack())
        memory = create_instruction(InstructionType.varOP,8,[(OperandType.small_constant,0x12)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('varOP:push 18',description)
        result = handler_f(self.zmachine)        
        self.assertEqual(0x12,self.zmachine.peek_game_stack())

        self.zmachine.current_routine()[200] = 0x18
        memory = create_instruction(InstructionType.varOP,8,[(OperandType.variable,200)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('varOP:push Gb8',description)
        result = handler_f(self.zmachine)        
        self.assertEqual(0x18,self.zmachine.pop_game_stack())
        self.assertEqual(0x12,self.zmachine.pop_game_stack())
        self.assertRaises(InterpreterException, self.zmachine.pop_game_stack)

    def test_pull(self):
        current_routine = self.zmachine.current_routine()
        self.zmachine.push_game_stack(0x23)
        self.assertEqual(0,current_routine[199])
        memory = create_instruction(InstructionType.varOP,9,[(OperandType.small_constant,199)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('varOP:pull 199',description)
        result = handler_f(self.zmachine)        
        self.assertEqual(0x23,current_routine[199])

        self.assertRaises(InterpreterException, handler_f,self.zmachine)

    def test_pop(self):
        current_routine = self.zmachine.current_routine()
        self.zmachine.push_game_stack(0x23)
        self.zmachine.push_game_stack(0x32)
        memory = create_instruction(InstructionType.zeroOP,9,[])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('zeroOP:pop',description)
        result = handler_f(self.zmachine)        
        self.assertEqual(0x23,self.zmachine.pop_game_stack())

        self.assertRaises(InterpreterException, handler_f,self.zmachine)

    def test_show_status(self):
        self.zmachine.current_routine().set_nth_global(0,11)
        memory = create_instruction(InstructionType.zeroOP,0x0C,[])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        result = handler_f(self.zmachine)
        self.assertEqual('zeroOP:show_status',description)
        self.assertTrue(self.zmachine.output_streams[0].status_shown)

    def test_verify(self):
        memory = create_instruction(InstructionType.zeroOP,0x0D,[],branch_to=0x02)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        result = handler_f(self.zmachine)
        self.assertEqual('zeroOP:verify ?0002',description)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(2,result.branch_offset)

        self.zmachine.story._checksum  = 0xff
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))

    def test_storew(self):
        self.assertNotEqual(0xff,self.zmachine.story.game_memory.word(0x500))
        memory = create_instruction(InstructionType.varOP,1,[(OperandType.large_constant,0x500),(OperandType.small_constant,0),(OperandType.large_constant,0xffff)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        result = handler_f(self.zmachine)
        self.assertEqual('varOP:storew 1280 0 65535',description)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0xffff,self.zmachine.story.game_memory.word(0x500))

        self.assertNotEqual(0xff,self.zmachine.story.game_memory.word(0x501))
        memory = create_instruction(InstructionType.varOP,1,[(OperandType.large_constant,0x500),(OperandType.small_constant,1),(OperandType.large_constant,0xfffc)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        result = handler_f(self.zmachine)
        self.assertEqual('varOP:storew 1280 1 65532',description)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0xfffc,self.zmachine.story.game_memory.word(0x502))

        memory = create_instruction(InstructionType.varOP,1,[(OperandType.large_constant,self.story.header.himem_address),(OperandType.small_constant,1),(OperandType.large_constant,0xfffc)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertRaises(MemoryAccessException, handler_f, self.zmachine)


    def test_storeb(self):
        self.assertNotEqual(0xff,self.zmachine.story.game_memory[0x500])
        memory = create_instruction(InstructionType.varOP,2,[(OperandType.large_constant,0x500),(OperandType.small_constant,0),(OperandType.small_constant,0xff)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        result = handler_f(self.zmachine)
        self.assertEqual('varOP:storeb 1280 0 255',description)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0xff,self.zmachine.story.game_memory[0x500])

        self.assertNotEqual(0xff,self.zmachine.story.game_memory[0x501])
        memory = create_instruction(InstructionType.varOP,2,[(OperandType.large_constant,0x500),(OperandType.small_constant,1),(OperandType.small_constant,0xfc)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        result = handler_f(self.zmachine)
        self.assertEqual('varOP:storeb 1280 1 252',description)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0xfc,self.zmachine.story.game_memory[0x501])

        # Test memory range check
        memory = create_instruction(InstructionType.varOP,2,[(OperandType.large_constant,self.story.header.himem_address),(OperandType.small_constant,1),(OperandType.small_constant,0xfc)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertRaises(MemoryAccessException, handler_f, self.zmachine)

    def test_loadb(self):
        routine = self.zmachine.current_routine()
        self.assertEqual(0, routine[200])

        memory = create_instruction(InstructionType.twoOP,16,[(OperandType.small_constant,0x12),(OperandType.small_constant,0)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        result = handler_f(self.zmachine)
        self.assertEqual('twoOP:loadb 18 0 -> Gb8',description)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0x31, routine[200])

        memory = create_instruction(InstructionType.twoOP,16,[(OperandType.small_constant,0x12),(OperandType.small_constant,1)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        result = handler_f(self.zmachine)
        self.assertEqual('twoOP:loadb 18 1 -> Gb8',description)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(53, routine[200])

    def test_loadw(self):
        routine = self.zmachine.current_routine()
        self.assertEqual(0, routine[200])

        memory = create_instruction(InstructionType.twoOP,15,[(OperandType.small_constant,0x12),(OperandType.small_constant,0)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('twoOP:loadw 18 0 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0x3135, routine[200])

        memory = create_instruction(InstructionType.twoOP,15,[(OperandType.small_constant,0x12),(OperandType.small_constant,1)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('twoOP:loadw 18 1 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(12340, routine[200])


    def test_store(self):
        routine = self.zmachine.current_routine()
        self.assertEqual(0, routine[200])

        memory = create_instruction(InstructionType.twoOP,13,[(OperandType.small_constant,200),(OperandType.small_constant,0xFF)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('twoOP:store 200 255',description)
        result = handler_f(self.zmachine)        
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(255, routine[200])

        routine[199] = 5
        memory = create_instruction(InstructionType.twoOP,13,[(OperandType.small_constant,200),(OperandType.variable,199)])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('twoOP:store 200 Gb7',description)
        result = handler_f(self.zmachine)        
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5, routine[200])

    def test_quit(self):
        memory = Memory(b'\xba\x00')
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('zeroOP:quit',description)
        result = handler_f(self.zmachine)        
        self.assertTrue(isinstance(result,QuitAction))

    def test_nop(self):
        memory = Memory(b'\x00\x03\x61')
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('twoOP:nop 3 97',description)
        result = handler_f(self.zmachine)        
        self.assertTrue(isinstance(result,NextInstructionAction))

    def test_load(self):
        routine = self.zmachine.current_routine()
        routine[200] = 0x31
        routine[150] = 0
        memory = create_instruction(InstructionType.oneOP,0x0E,[(OperandType.small_constant,200)],store_to=150)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        result = handler_f(self.zmachine)
        self.assertEqual('oneOP:load 200 -> G86',description)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(0x31, routine[150])

    def test_save(self):
        memory = create_instruction(InstructionType.zeroOP,5,[],branch_to=0x10)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('zeroOP:save ?0010',description)
        result = handler_f(self.zmachine)        
        self.assertTrue(isinstance(result,SaveAction))
        self.assertEqual(0x10, result.branch_offset)
        self.assertEqual(next_address, result.next_address)

    def test_restore(self):
        memory = create_instruction(InstructionType.zeroOP,6,[],branch_to=0x10)
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('zeroOP:restore ?0010',description)
        result = handler_f(self.zmachine)        
        self.assertTrue(isinstance(result,RestoreAction))
        self.assertEqual(0x10, result.branch_offset)
        self.assertEqual(next_address, result.next_address)

    def test_restart(self):
        memory = create_instruction(InstructionType.zeroOP,7,[])
        handler_f, description, next_address = read_instruction(memory,0,3,self.zmachine.get_ztext())
        self.assertEqual('zeroOP:quit',description)
        result = handler_f(self.zmachine)        
        self.assertTrue(isinstance(result,RestartAction))

class BitwiseInstructionsTests(TestStoryMixin,unittest.TestCase):
    def test_not(self):
        memory = create_instruction(InstructionType.oneOP,0x0F,[(OperandType.small_constant,0)],store_to=150)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:not 0 -> G86',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(3  ,result.next_address)
        self.assertEqual(0xffff, self.zmachine.current_routine()[150])

        memory = create_instruction(InstructionType.oneOP,0x0F,[(OperandType.large_constant,0xffff)],store_to=150)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:not 65535 -> G86',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4  ,result.next_address)
        self.assertEqual(0x0000, self.zmachine.current_routine()[150])

        memory = create_instruction(InstructionType.oneOP,0x0F,[(OperandType.large_constant,43690)],store_to=150)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('oneOP:not 43690 -> G86',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4  ,result.next_address)
        self.assertEqual(21845, self.zmachine.current_routine()[150])
        

    def test_or(self):
        memory = create_instruction(InstructionType.twoOP,8,[(OperandType.small_constant,0x00),(OperandType.small_constant,0xFF)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:or 0 255 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4  ,result.next_address)
        self.assertEqual(0xff, self.zmachine.current_routine()[200])

        memory = create_instruction(InstructionType.twoOP,8,[(OperandType.small_constant,0xff),(OperandType.small_constant,0x00)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:or 255 0 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4  ,result.next_address)
        self.assertEqual(0xff, self.zmachine.current_routine()[200])

    def test_and(self):
        memory = create_instruction(InstructionType.twoOP,9,[(OperandType.small_constant,0x00),(OperandType.small_constant,0xFF)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:and 0 255 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4  ,result.next_address)
        self.assertEqual(0, self.zmachine.current_routine()[200])

        memory = create_instruction(InstructionType.twoOP,9,[(OperandType.small_constant,0xff),(OperandType.small_constant,0xff)],store_to=200)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:and 255 255 -> Gb8',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(4  ,result.next_address)
        self.assertEqual(0xff, self.zmachine.current_routine()[200])

    def test_test(self):
        memory = create_instruction(InstructionType.twoOP,7,[(OperandType.small_constant,0xFF),(OperandType.small_constant,0xFF)],branch_to=0x02)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:test 255 255 ?0002',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(2,result.branch_offset)

        memory = create_instruction(InstructionType.twoOP,7,[(OperandType.small_constant,0xFF),(OperandType.small_constant,0xFF)],branch_to=0x02,branch_if_true=False)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:test 255 255 ?!0002',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5  ,result.next_address)

        memory = create_instruction(InstructionType.twoOP,7,[(OperandType.small_constant,0x01),(OperandType.small_constant,0x10)],branch_to=0x02)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:test 1 16 ?0002',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,NextInstructionAction))
        self.assertEqual(5  ,result.next_address)

        memory = create_instruction(InstructionType.twoOP,7,[(OperandType.small_constant,0x11),(OperandType.small_constant,0x10)],branch_to=0x02)
        handler_f, description, next_address = read_instruction(memory,0,3,None)
        self.assertEqual('twoOP:test 17 16 ?0002',description)
        result = handler_f(self.zmachine)
        self.assertTrue(isinstance(result,JumpRelativeAction))
        self.assertEqual(2,result.branch_offset)

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

    def test_to_zchars(self):
        ztext = ZText(version=3,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual((0,),ztext.to_zchars(' '))
        self.assertEqual((6,),ztext.to_zchars('a'))
        self.assertEqual((4,6),ztext.to_zchars('A'))
        self.assertEqual((5,8),ztext.to_zchars('0'))

    def test_shift_v1(self):
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

    def test_v1(self):
        # In v1: char 0 is space
        # 1 is newline
        # 2/3 are single char shifts
        # 4/5 are shift locks
        # Char 7 A2 is 0, not ^
        ztext = ZText(version=1,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(' \nBb0bBBbb', ''.join(ztext._handle_zchars([0,1,2,7,7,3,7,7,4,7,7,5,7,7])))

    def test_v2(self):
        # In v2: char 0 is space
        # 1 is abbrev
        # 2/3 are single char shifts
        # 4/5 are shift locks
        ztext = ZText(version=2,get_abbrev_f=lambda x: b'\x11\xaa\x46\x34\x16\x45\x9c\xa5')
        self.assertEqual(' HELLOm\nBb\nbBBbb', ''.join(ztext._handle_zchars([0,1,1,2,7,7,3,7,7,4,7,7,5,7,7])))

    def test_v3(self):
        # In v3: char 0 is space
        # 1-3 is abbrev
        # 4/5 are single char shifts
        # 6 uses next to chars for lookup if in A2
        ztext = ZText(version=3,get_abbrev_f=lambda x: b'\x11\xaa\x46\x34\x16\x45\x9c\xa5')
        self.assertEqual(' Hello.\nHello.\nbHello.\nbBb\nbaA[b', ''.join(ztext._handle_zchars([0,1,1,2,7,7,3,7,7,4,7,7,5,7,7,6,4,6,5,6,2,27,7])))

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
        s,offset = ztext.to_ascii(data,0,0)
        self.assertEqual('      ',s)
        
        # Check explicit length
        s,offset = ztext.to_ascii(data,0,2)
        self.assertEqual('   ',s)
    
    def test_to_ascii_shift(self):
        ztext = ZText(version=3,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual('.',ztext.to_ascii(Memory([0x16,0x45,0x94,0xA5]),0,4)[0])
   
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
        self.assertEqual(bytearray(b'8\xa5\x94\xa5'), ztext.encrypt('i'))
        self.assertEqual(bytearray([0x18,0xF4,0xEB,0x25]),ztext.encrypt('about'))
        self.assertEqual(bytearray([0x5d,0x55,0xd2,0xf9]),ztext.encrypt('report'))
        self.assertEqual(bytearray([0x16,0x65,0x94,0xA5]),ztext.encrypt(','))
        # This was throwing an exception due to the shifts. NOte that the shifts for v3 
        # means much of the buffer ends up thrown away
        self.assertEqual(bytearray([21,37,172,189]),ztext.encrypt('13:43')) 

    def test_encrypt_text_v1(self):
        # See 3.7.1 and 3.5.4
        ztext = ZText(version=1,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(bytearray(bytearray(b'8\x87\xa0\xa5')), ztext.encrypt('i01'))
        
    def test_encrypt_text_v2(self):
        ztext = ZText(version=2,get_abbrev_f=self.get_abbrev_f)
        self.assertEqual(bytearray(bytearray(b'8\x88\xa4\xa5')), ztext.encrypt('i01'))

class DictionaryTests(unittest.TestCase):
    def setUp(self):
        self.dictionary = Dictionary(Memory([0x01,0x01,0x02,0x00,0x03,0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07]),0,None)
    
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

    def test_restart_data(self):
        # Verify that a story reset with restart data correctly sets
        # the flags
        self.story.game_memory.set_flag(Header.FLAGS_2,0,0)        
        self.story.game_memory.set_flag(Header.FLAGS_2,1,0)

        self.story.reset(restart_flags=(True,True))        

        self.assertTrue(self.story.game_memory.flag(Header.FLAGS_2,0))
        self.assertTrue(self.story.game_memory.flag(Header.FLAGS_2,1))

    def test_header(self):
        self.story.game_memory.set_flag(0x10,0,1)        
        self.story.game_memory.set_flag(0x10,1,1)        
        self.story.game_memory.set_flag(0x10,2,1)

        self.story.game_memory.set_flag(0x10,3,1)
        self.story.game_memory.set_flag(0x10,4,1)
        self.story.game_memory.set_flag(0x10,5,1)
        self.story.game_memory.set_flag(0x10,6,1)
        self.story.game_memory.set_flag(0x10,7,1)

        self.assertRaises(MemoryAccessException, self.story.game_memory.set_flag,0x10,3,1,check_bounds=True)
        self.assertRaises(MemoryAccessException, self.story.game_memory.set_flag,0x10,4,1,check_bounds=True)
        self.assertRaises(MemoryAccessException, self.story.game_memory.set_flag,0x10,5,1,check_bounds=True)
        self.assertRaises(MemoryAccessException, self.story.game_memory.set_flag,0x10,6,1,check_bounds=True)
        self.assertRaises(MemoryAccessException, self.story.game_memory.set_flag,0x10,7,1,check_bounds=True)

    def test_highmem_access(self):
        self.story.game_memory.restrict_access=True
        himem_address = self.story.header.himem_address
        for i in range(0,2):
            memory = self.story.game_memory
            try:
                memory.set_byte(himem_address+i,1,check_bounds=True)
                self.fail('Should have thrown exception')
            except MemoryAccessException:
                pass
    

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
        
        for version in (0x04,0x05,0x06,0x07,0x08):
            raw_data[0] = version
            try:
                Story(raw_data).reset()
                self.fail('Should throw error for unsupported version')
            except StoryFileException as e:
                # Should throw exception as our object table points at bad data
                self.assertEqual('Story file version %d is not supported.' % version,str(e))

        for version in (0x01,0x02,0x03):
            raw_data[0] = version
            Story(raw_data).reset()
            

class SampleFileTests(unittest.TestCase):
    def setUp(self):
        path = 'testdata/test.z3'
        if not os.path.exists(path):
            self.fail('Could not find test file test.z3')
        with open(path, 'rb') as f:
            self.story = Story(f.read())
            self.zmachine = Interpreter(self.story,TestOutputStreams(),None,TestSaveHandler(),TestRestoreHandler())
            self.zmachine.reset()

    def test_save_and_restore_basic(self):
        # Save and restore without changing anything. Ensure data is the same before/after
        old_memory = Memory(self.zmachine.story.raw_data)
        
        data = self.zmachine.to_save_data()
        self.assertEqual(1,data['version'])
        self.assertEqual('0031F3',data['checksum'])
        self.zmachine.restore_from_save_data(json.dumps(data))

        self.assertEqual(self.zmachine.story.raw_data._raw_data, old_memory._raw_data)

    def test_invalid_restore(self):
        old_memory = Memory(self.zmachine.story.raw_data)
        data = self.zmachine.to_save_data()
        data['version'] = 2
        self.assertRaises(InvalidSaveDataException, self.zmachine.restore_from_save_data,json.dumps(data))
        
        data['version'] = 1
        old_checksum = data['checksum']
        data['checksum'] = '123456'
        self.assertRaises(InvalidSaveDataException, self.zmachine.restore_from_save_data,json.dumps(data))

        data['checksum'] = old_checksum
        self.zmachine.restore_from_save_data(json.dumps(data))

    def test_save_and_restore(self):
        # Run until command prompt to set up some memory.
        count = 0
        while self.zmachine.state == Interpreter.RUNNING_STATE and count < 100:
            self.zmachine.step()

        # Set flags 2 so that we can verify it's preserved on reset
        self.zmachine.story.raw_data[Header.FLAGS_2] = 0xFF

        old_memory = self.zmachine.story.raw_data._raw_data
        old_routines = [x.to_dict() for x in self.zmachine.routines]
        old_state = self.zmachine.state

        data = self.zmachine.to_save_data()
    
        self.zmachine.story.raw_data[Header.FLAGS_2] = 0x00
        self.assertEqual(0x00,  self.zmachine.story.raw_data[Header.FLAGS_2])

        self.zmachine.restore_from_save_data(json.dumps(data))

        self.assertEqual(0x00,  self.zmachine.story.raw_data[Header.FLAGS_2])
        self.assertEqual(len(self.zmachine.routines),len(old_routines))
        self.assertEqual(old_state, self.zmachine.state)
        for old_routine, routine in zip(old_routines,self.zmachine.routines):
            self.assertEqual(old_routine, routine.to_dict())         

        new_mem = self.zmachine.story.raw_data._raw_data
        self.assertEqual(len(new_mem),len(old_memory))

        for idx in range(0,len(new_mem)):
            self.assertEqual(new_mem[idx],old_memory[idx],'Differs at index %d' % idx)

    def test_dictionary_split(self):
        # Test file has delimeters . and , and " (and default space)
        ztext = self.zmachine.get_ztext()
        dictionary = self.zmachine.story.dictionary
        self.assertEqual([], dictionary.split([]))
        self.assertEqual([(0,[116, 101, 115, 116])], dictionary.split([ztext.to_zscii(c) for c in 'test']))
        self.assertEqual([(1,[102, 114, 101, 100]), (5,[44]), (7,[103, 111]), (10,[102, 105, 115, 104, 105, 110, 103])], 
                    dictionary.split([ztext.to_zscii(c) for c in ' fred, go fishing ']))
        self.assertEqual([(0,[97]), (1,[46]), (2,[44]), (3,[34]), (4,[102, 111, 111]), (7,[34])], dictionary.split([ztext.to_zscii(c) for c in 'a.,"foo"']))

    def test_dictionary_lookup(self):
        ztext = self.zmachine.get_ztext()
        dictionary = self.zmachine.story.dictionary
        self.assertEqual(None, dictionary.lookup([],ztext))
        self.assertEqual(2220, dictionary.lookup([ztext.to_zscii('d')],ztext))
        self.assertEqual(2290, dictionary.lookup([ztext.to_zscii(c) for c in 'examin'],ztext))

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
        self.assertEqual(4, routine[21]) # Check default value from story file
        routine[22] = 0xFFFF
        self.assertEqual(0xFFFF,routine[22])
        routine[17] = 0x12
        self.assertEqual(0x12,routine[17])
        # Verify stored in right place in memory
        self.assertEqual(0x0012,self.zmachine.story.game_memory.word(self.zmachine.story.header.global_variables_address+(17-0x10)*2))


if __name__ == '__main__':
    unittest.main()
