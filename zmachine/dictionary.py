""" Class for handling a zcode story's dictionary.
    See http://inform-fiction.org/zmachine/standards/z1point0/sect13.html
"""

class Dictionary(object):
    def __init__(self,data,start_address):
        self._memory = data
        self._start_address = start_address
        self._addr = start_address
        self._load_header()

    def _increment_addr(self,amount=1):
        self._addr+=1
    
    def _load_header(self):
        # See 13.2
        self.keyboard_codes = []
        num_codes = self._memory[self._addr]
        self._increment_addr()
        for i in range(0,num_codes):
            self.keyboard_codes.append(self._memory[self._addr])
            self._increment_addr()
        self.entry_length = self._memory[self._addr]
        self._increment_addr()
        self.number_of_entries = self._memory.word(self._addr)
        self._increment_addr(2)
