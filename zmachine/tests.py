""" Tests for zmachine """

import unittest
import os

from interpreter import ZMachine,StoryFileException,MemoryAccessException
from memory import Memory

class MemoryTests(unittest.TestCase):
    def test_from_integers(self):
        mem = Memory([1,2,3])
        self.assertEquals(3, len(mem))
        self.assertEquals(1,mem[0])
        self.assertEquals(2,mem[1])
        self.assertEquals(3,mem[2])     
        self.assertEquals([1,2], mem[0:2])

    def test_from_chars(self):
        mem = Memory('\x01\x02\x03')
        self.assertEquals(3, len(mem))
        self.assertEquals(1,mem[0])
        self.assertEquals(2,mem[1])
        self.assertEquals(3,mem[2])

    def test_address(self):
        mem = Memory([0,1])
        self.assertEquals(0x00, mem[0])
        self.assertEquals(0x01,mem[1])
        self.assertEquals(0x01,mem.address(0))

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

class GameMemoryTests(unittest.TestCase):
    def setUp(self):
        path = 'testdata/test.z3'
        if not os.path.exists(path):
            self.fail('Could not find test file test.z3')
        with open(path, 'rb') as f:
            self.zmachine = ZMachine()
            self.zmachine.raw_data = f.read()

    def test_header(self):
        self.zmachine.game_memory[0]
        try:
            self.zmachine.game_memory[0] = 1
            self.fail('Should have thrown exception')
        except MemoryAccessException:
            pass
        self.zmachine.game_memory.set_flag(0x10,0,1)        
        self.zmachine.game_memory.set_flag(0x10,1,1)        
        self.zmachine.game_memory.set_flag(0x10,2,1)        
        self.assertRaises(MemoryAccessException, self.zmachine.game_memory.set_flag,0x10,3,1)
        self.assertRaises(MemoryAccessException, self.zmachine.game_memory.set_flag,0x10,4,1)
        self.assertRaises(MemoryAccessException, self.zmachine.game_memory.set_flag,0x10,5,1)
        self.assertRaises(MemoryAccessException, self.zmachine.game_memory.set_flag,0x10,6,1)
        self.assertRaises(MemoryAccessException, self.zmachine.game_memory.set_flag,0x10,7,1)

    def test_highmem_access(self):
        himem_address = self.zmachine.header.himem_address
        for i in range(0,2):
            memory = self.zmachine.game_memory
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
        static_address = self.zmachine.header.static_memory_address
        for i in range(0,2):
            memory = self.zmachine.game_memory
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
        zmachine = ZMachine()
        try:
            zmachine.raw_data = ''
            self.fail('Should have thrown exception')
        except StoryFileException, e:
            self.assertEquals(u'Story file is too short', unicode(e))

    def test_version(self):
        zmachine = ZMachine()
        raw_data =['\x00'] * 1000
        for version in (0x01,0x02,0x03):
            raw_data[0] = version
            zmachine.raw_data = raw_data
        for version in (0x04,0x05,0x06,0x07,0x08):
            raw_data[0] = version
            try:
                zmachine.raw_data = raw_data
                self.fail('Should have thrown exception.')
            except StoryFileException, e:
                self.assertEquals('This story file version is not supported.',unicode(e))
            

class SampleFileTests(unittest.TestCase):
    def setUp(self):
        path = 'testdata/test.z3'
        if not os.path.exists(path):
            self.fail('Could not find test file test.z3')
        with open(path, 'rb') as f:
            self.zmachine = ZMachine()
            self.zmachine.raw_data = f.read()

    def test_header(self):
        header = self.zmachine.header
        self.assertEquals(3,header.version)
        self.assertEquals(0x0cd4,header.himem_address)
        self.assertEquals(0x0cd5,header.program_counter_address)
        self.assertEquals(0x0835,header.dictionary_address)
        self.assertEquals(0x0146,header.object_table_address)
        self.assertEquals(0x0102,header.global_variables_address)
        self.assertEquals(0x0835,header.static_memory_address)
        self.assertEquals(0x0042,header.abbrev_address)
        self.assertEquals(0x0326a,header.file_length)
        self.assertEquals(0xf3a4,header.checksum)

        self.assertEquals(0,header.flag_status_line_type)
        self.assertFalse(header.flag_story_two_disk)
        self.assertFalse(header.flag_status_line_not_available)
        self.assertFalse(header.flag_screen_splitting_available)
        self.assertFalse(header.flag_variable_pitch_default)

    def test_checksum(self):
        self.assertEquals(0xf3a4,self.zmachine.calculate_checksum())

if __name__ == '__main__':
    unittest.main()
