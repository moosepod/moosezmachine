""" Tests for zmachine """

import unittests
import os

class TestSampleFile(unittests.TestCase):
    def setUp(self
        if not os.path.exists('testdata/test.z8'):
            self.fail('Could not fild test file test.z8')
