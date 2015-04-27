""" Handles ZChars/Zascii and the general text processing part of the Z-Machine """

class ZTextException(Exception):
    """ Thrown when ztext is invalid in some way """
    pass

class ZTextState(object):
    DEFAULT                         = 0 # Default state
    WAITING_FOR_ABBREVIATION        = 1 # Waiting for an abbreviation. Triggered by zchars 1-3
    GETTING_10BIT_ZCHAR_CHAR1       = 2 # See 3.4. Zchar 6 uses next two chars to make a 10-bit character
    GETTING_10BIT_ZCHAR_CHAR2       = 3 # Second char for 2-character zchar

class ZText(object):
    """ Abstraction for handling Z-Machine text. """
    ZCHARS    = [['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'],
                 ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'],
                 [' ', '\n', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.', ',', '!', '?', '_', '#', "'", '"', '/', '\\', '-', ':', '(', ')']]
    ZCHARS_V1 = [['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'],
                 ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'],
                 [' ', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.', ',', '!', '?', '_', '#', "'", '"', '/', '\\', '<', '-', ':', '(', ')']]
    ZASCII_UNICODE = ['ae', 'oe', 'ue', 'Ae', 'Oe', 'Ue', 'ss', '>>', '<<', 'e', 'i', 'y', 'E', 'I', 'a', 'e', 'i', 'o', 'u', 'y', 'A', 'E', 'I', 'O', 
                      'U', 'Y', 'a', 'e', 'i', 'o', 'u', 'A', 'E', 'I', 'O', 'U', 'a', 'e', 'i', 'o', 'u', 'A', 'E', 'I', 'O', 'U', 'a', 'A', 'o', 'O', 
                      'a', 'n', 'o', 'A', 'N', 'O', 'ae', 'AE', 'c', 'C', 'th', 'th', 'Th', 'Th', 'L', 'oe', 'OE', '!', '?']

    def __init__(self,version,screen,get_abbrev_f):
        self.version = version
        self.screen = screen
        self.get_abbrev_f = get_abbrev_f
        self.reset()

    def reset(self):
        self._current_alphabet = 0
        self._shift_alphabet = None
        self.state = ZTextState.DEFAULT
        self._previous_zchar = None

    def to_ascii(self, memory,start_at,length_in_bytes):
        """ Convert the ztext starting at start_at in memory to an ascii string.
            If length_in_bytes > 0, convert that many bytes. Otherwise convert until the end of 
            string word is found """
        if length_in_bytes < 1:
            l = 100000000000
        else:
            l = min(len(memory),start_at+length_in_bytes)
        idx = start_at
        chars = []
        while idx < l:
            zchars,is_last_char = self.get_zchars_from_memory(memory,idx)
            for zchar in zchars:
                ascii_char = self.handle_zchar(zchar)
                if ascii_char:
                    chars.append(ascii_char)
            idx+=2
            if length_in_bytes < 1 and is_last_char:
                break
        return ''.join(chars)
        
    def encrypt(self,text):
        """ Encrypt a string for dictionary matching to a six-zchar string, returned as a
            bytearray. See 3.7
            I'm not 100% sure I've implemented this correctly due to the shift characters
            and 3.7.1
            """
        if text == None: text = ''
        text = text.lower()
        results = [5] * 6
        i = 0
        idx = 0
        mapping = ZText.ZCHARS
        if self.version == 1:
            mapping = ZText.ZCHARS_V1
        previous_alphabet = 0
        while i < min(len(text),6):
            c = text[i]
            for alphabet in (0,1,2):
                try:
                    pos = mapping[alphabet].index(c)
                    if alphabet == 2:
                        # 3.7.1
                        if self.version < 3 and previous_alphabet == alphabet:
                            results[idx-2] = 4
                        else:
                            results[idx]=3 # Shift
                            idx+=1
                    results[idx] = pos+6
                    previous_alphabet = alphabet
                except ValueError:
                   pass 
            i+=1
            idx+=1
        return bytearray(results)

    def handle_zchar(self,zchar):
        """ Handle the given zcode based on our state and other information. 
            Returns an ASCII char to print, or None if no print should cocur
        """
        try:
            if self.state == ZTextState.WAITING_FOR_ABBREVIATION:
                return self._waiting_for_abbreviation(zchar)
            if self.state == ZTextState.GETTING_10BIT_ZCHAR_CHAR1:
                self.state = ZTextState.GETTING_10BIT_ZCHAR_CHAR2
                return None
            if self.state == ZTextState.GETTING_10BIT_ZCHAR_CHAR2:
                zchar = (self._previous_zchar << 5) | zchar                
                self.state = ZTextState.DEFAULT
                return self._map_zscii(zchar)

            if zchar >= 1 and zchar < 4:
                if self.get_abbrev_f == None:
                    raise ZTextException('Attempt to print abbreviation text that contains abbreviation') 
                if self.version < 2:
                    return zchar
                if zchar == 1 or self.version > 2:
                    self.state = ZTextState.WAITING_FOR_ABBREVIATION        
            elif zchar == 6:
                self.state = ZTextState.GETTING_10BIT_ZCHAR_CHAR1
            else:
                return self._map_zchar(zchar)
        finally:
            self._previous_zchar = zchar

    def _map_zchar(self,zchar):
        """ Map a zchar code to an ASCII code (only valid for a subrange of zchars """
        # 3.5.1
        if zchar == 0:
            return ' '
        # 3.5.2
        if zchar == 1 and self.version == 1:
            return '\n'
        # 3.5.3
        if zchar >= 6 and zchar < 32:
            mapping = ZText.ZCHARS
            if self.version == 1:
                mapping = ZText.ZCHARS_V1
            return mapping[self.alphabet][zchar-6]

        return ''

    def _map_zscii(self,zascii):
        """ Map a zasii code to an ascii code. ZAscii is referenced by zchar 6 
            followed by two more 5-bit units to form the code """
        if zascii == 0:
            return ''
        if zascii == 13:
            return '\r'
        if zascii >= 32 and zascii <= 126:
            return chr(zascii)
        if zascii >= 155 and zascii < 155+len(ZText.ZASCII_UNICODE):
            return ZText.ZASCII_UNICODE[zascii - 155]

        raise ZTextException('Character %d invalid for ZSCII output' % zascii)


    def _waiting_for_abbreviation(self,zchar):
        ztext = ZText(version=self.version,screen=self.screen,get_abbrev_f=None)
        self.state = ZTextState.DEFAULT
        return ztext.to_ascii(self.get_abbrev_f((32 * self._previous_zchar-1) + zchar),0,0)

    @property
    def alphabet(self):
        if self._shift_alphabet != None:    
            return self._shift_alphabet
        return self._current_alphabet

    def get_zchars_from_memory(self,memory,idx):    
        """ Return the three zchars at the word at index idx of memory, as well
            as whether or not this has the end bit set.

            Each word has 3 5-bit zchars, starting at bit E.
            Bit   F E D C B A 9 8 7 6 5 4 3 2 1 0
            ZChar   1 1 1 1 1 2 2 2 2 2 3 3 3 3 3
            """
        b0 = memory[idx]
        b1 = memory[idx+1]

        # Use masks and shifts to filter out the three 5-bit chars we want, as well as whether
        # end bit is set
        return ((b0 & 0x7C)>>2,((0x03 & b0) << 3) | ((0xE0 & b1)>>5), int(b1 & 0x1F)), (b0 & 0x80) == 0x80

    def shift(self,reverse=False,permanent=False):
        """ Shift the current alphabet. 0 shifts it "right" (A0->A1->A2)
            and 1 shifts left (A2->A0->A1). Permanent will store the new alphabet,
            and is only used for versions 1 and 2 """
        if reverse:
            self._shift_alphabet = self._current_alphabet - 1
            if self._shift_alphabet < 0:
                self._shift_alphabet = 2
        else:
            self._shift_alphabet = self._current_alphabet + 1
            if self._shift_alphabet > 2:
                self._shift_alphabet = 0
        if permanent:
            self._current_alphabet = self._shift_alphabet
            self._shift_alphabet = None

