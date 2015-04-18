""" Tests for zmachine """

import unittest
import os

from interpreter import ZMachine,StoryFileException,MemoryAccessException,ZText
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
        self.assertEquals(0x01,mem.word(0))

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

    def test_packed(self):
        mem = Memory([1,2,3,4])
        self.assertEquals(mem.word(2),mem.packed_address(1,2))

    def test_signed_int(self):
        mem = Memory([0,0])
        self.assertEquals(0, mem.signed_int(0))
        mem[1] = 1
        self.assertEquals(1, mem.signed_int(0))
        mem[1] = 0xFF
        mem[0] = 0x7F
        self.assertEquals(32767, mem.signed_int(0))
        mem[0] = 0xFF
        self.assertEquals(-1, mem.signed_int(0))

    def test_set_signed_int(self):
        mem = Memory([0,0])
        mem.set_signed_int(0,0)
        self.assertEquals(0, mem.word(0))
        mem.set_signed_int(0,1)
        self.assertEquals(1, mem.word(0))
        mem.set_signed_int(0,-1)
        self.assertEquals(65535, mem.word(0))

class ZTextTests(unittest.TestCase):
    def test_shift(self):
        ztext = ZText()
        self.assertEquals(0,ztext._current_alphabet)
        self.assertEquals(None,ztext._shift_alphabet)
        self.assertEquals(0,ztext.alphabet)

        ztext.shift()
        self.assertEquals(0,ztext._current_alphabet)
        self.assertEquals(1,ztext._shift_alphabet)
        self.assertEquals(1,ztext.alphabet)

        ztext.shift(reverse=False,permanent=True)
        self.assertEquals(1,ztext._current_alphabet)
        self.assertEquals(None,ztext._shift_alphabet)
        self.assertEquals(1,ztext.alphabet)

        ztext.shift(reverse=True)
        self.assertEquals(1,ztext._current_alphabet)
        self.assertEquals(0,ztext._shift_alphabet)
        self.assertEquals(0,ztext.alphabet)



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

    def test_packed(self):
        self.assertEquals(self.zmachine._raw_data[3],self.zmachine.packed_address(1))

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
    
    def test_randomizer(self):
        # This really isn't a "unit" test. It's more of a smoke test,
        # just to see if the RNG is totally failing
        rng = self.zmachine.rng
        for i in range(0,100):
            x = rng.randint(i+1)
            self.assertTrue(x >= 1)
            self.assertTrue(x <= i+1)

        # In predictable mode, should return same value
        rng.enter_predictable_mode(0)
        x = rng.randint(100)
        rng.enter_predictable_mode(0)
        self.assertEquals(x, rng.randint(100))

        # Reset should enter random mode
        self.assertEquals(0,rng.seed)        
        self.zmachine.reset()
        self.assertFalse(rng.seed == 0)
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
