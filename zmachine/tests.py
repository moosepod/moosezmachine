""" Tests for zmachine """

import unittest
import os

from interpreter import ZMachine

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
