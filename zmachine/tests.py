""" Tests for zmachine """

import unittest
import os

from interpreter import ZMachine,StoryFileException
from memory import Memory

class TestMemory(unittest.TestCase):
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

class TestValidation(unittest.TestCase):
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
            

class TestSampleFile(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()
