""" Class for handling a zcode story's dictionary.
    See http://inform-fiction.org/zmachine/standards/z1point0/sect13.html
"""

from zmachine.text import ZText

class Dictionary(object):
    def __init__(self,data,start_address):
        self._memory = data
        self._start_address = start_address
        self._addr = start_address
        self._load_header()

    def _increment_addr(self,amount=1):
        self._addr+=amount
    
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

    def split(self,chars):
        """ Split the text into a list of words per 13.5.1. Text is array of ZSCII """
        words = []
        word = []
        for c in chars:
            if c == ZText.SPACE:
                if word:
                    words.append(word)
                    word = []
            elif c in self.keyboard_codes:
                if word:
                    words.append(word)
                    word = []
                words.append([c])
            else:
                word.append(c)
        if word:
            words.append(word)
        return words

    # Allow this to be treated as a list, where word 0 is the first word in 
    # the dictionary. Will return 4 bytes as a bytearray
    def __len__(self):
        return self.number_of_entries

    def __getitem__(self,item_idx):
        if item_idx < 0 or item_idx >= self.number_of_entries:
            raise IndexError('%d out of range for dictionary.' % (item_idx))
        address = self._addr + (self.entry_length * item_idx)
        return bytearray(self._memory[address:address+4])        

