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

    def lookup(self,word,ztext):
        """ Take a word (as a list of ZSCII) and look it up in the dictionary. Return byte address if present,
            None otherwise. ztext is a ZText reference. """
        # Convert our zscii to a string
        word_str = ''.join([ztext.zscii_to_ascii(c) for c in word])
        zchar_word = ztext.encrypt(word_str)
        for idx in range(0,len(self)):
            if self[idx] == zchar_word:
                return self._get_item_address(idx)

        return None

    def split(self,chars):
        """ Split the text into a list of words and indexes of their location in the string per 13.5.1. 
            Text is array of ZSCII """
        words = []
        word = []
        index=0
        word_start=0
        for c in chars:
            index+=1
            if c == ZText.SPACE:
                if word:
                    words.append((word_start,word))
                    word = []
                word_start=index
            elif c in self.keyboard_codes:
                if word:
                    words.append((word_start,word))
                    word = []
                    word_start=index-1
                words.append((word_start,[c]))
                word_start=index
            else:
                word.append(c)
        if word:
            words.append((word_start,word))

        return words

    def _get_item_address(self, item_idx):
        if item_idx < 0 or item_idx >= self.number_of_entries:
            raise IndexError('%d out of range for dictionary.' % (item_idx))
        return self._addr + (self.entry_length * item_idx)

    # Allow this to be treated as a list, where word 0 is the first word in 
    # the dictionary. Will return 4 bytes as a bytearray
    def __len__(self):
        return self.number_of_entries

    def __getitem__(self,item_idx):
        address = self._get_item_address(item_idx)
        return bytearray(self._memory[address:address+4])        

