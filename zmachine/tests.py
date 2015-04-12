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
        self.assertEquals(3,self.zmachine.header.version)

if __name__ == '__main__':
    unittest.main()
