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
    SPACE = 32

    def __init__(self,version,get_abbrev_f,debug=False):
        self.version = version
        self.get_abbrev_f = get_abbrev_f
        self.debug=debug
        self.reset()

    def reset(self):
        self._current_alphabet = 0
        self._shift_alphabet = None
        self.state = ZTextState.DEFAULT
        self._previous_zchar = None

    def to_ascii(self, memory,start_at=0,length_in_bytes=0):
        """ Convert the ztext starting at start_at in memory to an ascii string.
            If length_in_bytes > 0, convert that many bytes. Otherwise convert until the end of 
            string word is found """
        chars = self._extract_zchars(memory,start_at,length_in_bytes)
        output_chars = self._handle_zchars(chars)
        if self.debug:
            print('-- end')

        return ''.join(output_chars)

    def _extract_zchars(self,memory,start_at,length_in_bytes):
        if length_in_bytes < 1:
            l = 100000000000
        else:
            l = min(len(memory),start_at+length_in_bytes)
        idx = start_at
        chars = []
        if self.debug:
            print('-- start to_ascii:')
        while idx < l:
            zchars,is_last_char = self.get_zchars_from_memory(memory,idx)
            chars.extend(zchars)
            idx+=2
            if length_in_bytes < 1 and is_last_char:
                break
        return chars

    def _handle_zchars(self,zchars):
        chars = []
        for zchar in zchars:
            ascii_char = self.handle_zchar(zchar)
            if ascii_char:
                chars.append(ascii_char)
            if self.debug:
                print('   %d,%s' % (zchar,ascii_char))
        return chars

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
        # Compress the 6 characters into 4 bytes
        b1 = (results[0] << 2 & 0xff) | (results[1] >> 3)
        b2 = (results[1] << 5 & 0xff) | results[2]
        b3 = (results[3] << 2 & 0xff) | (results[4] >> 3) | 0x80 # End flag always set on terminating word
        b4 = (results[4] << 5 & 0xff) | results[5]
        return bytearray([b1,b2,b3,b4])

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
                self._shift_alphabet=None
                return self._map_zscii(zchar)

            if zchar > 0 and zchar < 6:
                if self.version < 3:
                    return self._handle_1_5_zchar_pre3(zchar)
                else:
                    return self._handle_1_5_zchar(zchar)
            elif zchar == 6 and self.alphabet == 2:
                self.state = ZTextState.GETTING_10BIT_ZCHAR_CHAR1
            else:
                result = self._map_zchar(zchar)
                if self._shift_alphabet:
                    self._shift_alphabet = None
                return result
        finally:
            self._previous_zchar = zchar
        return ''

    def _handle_1_5_zchar_pre3(self,zchar):
        # ZChar logic for versions 1 and 2 for zcharts 1 through 5
        if zchar == 1:
            # 3.5.2
            if self.version == 1:
                return '\n'
            else:
                # 3.3
                if self.get_abbrev_f == None:
                    raise ZTextException('Attempt to print abbreviation text that contains abbreviation') 
                self.state = ZTextState.WAITING_FOR_ABBREVIATION        
        if zchar == 2:
            self.shift(False,False)
        elif zchar == 3:
            self.shift(True,False)
        elif zchar == 4:
            self.shift(False,True)
        elif zchar == 5:
            self.shift(True,True)
        return ''

    def _handle_1_5_zchar(self,zchar):
        # ZChar logic for 3 and u[2 for zcharts 1 through 5
        if zchar >= 1 and zchar < 4:
            # 3.3
            if self.get_abbrev_f == None:
                raise ZTextException('Attempt to print abbreviation text that contains abbreviation') 
            if self.version < 2:
                return zchar
            if zchar == 1 or self.version > 2:
                self.state = ZTextState.WAITING_FOR_ABBREVIATION        
        elif zchar == 4:
            # 3.2.3
            self._shift_alphabet = 1
        elif zchar == 5:
            # 3.2.3
            self._shift_alphabet = 2
        return ''

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
        if zascii < 1023:
            return 'UNDEFINED'
        raise ZTextException('Character %d invalid for ZSCII output' % zascii)


    def _waiting_for_abbreviation(self,zchar):
        ztext = ZText(version=self.version,get_abbrev_f=None)
        self.state = ZTextState.DEFAULT
        return ztext.to_ascii(self.get_abbrev_f((32 * (self._previous_zchar-1)) + zchar),0,0)

    @property
    def alphabet(self):
        if self._shift_alphabet != None:    
            return self._shift_alphabet
        return self._current_alphabet

    def to_zscii(self,chr):
        """ Convert an ascii/unicode char to zscii. Filter it to standard ascii chars """
        c = ord(chr)
        if c < 32 or c > 126:
            return ord(' ')
        return c

    def zscii_to_ascii(self,zscii):
        if zscii < 32 or zscii > 126:
            return ' '
        return chr(zscii)

    def to_zchars(self,char):
        """ Convert a unicode char to one or more zchars """
        if self.version == 1:
            raise Exception('Version 1 zchar reading not yet supported')
        if char == ' ':
            return (0,) 

        if self.version == 2:
            shift_up, shift_down = 2,3
        else:
            shift_up, shift_down = 4,5

        for alphabet_id, alphabet in enumerate(ZText.ZCHARS):
            for char_idx, c in enumerate(alphabet):
                if c == char:
                    if alphabet_id == 0:
                        return (char_idx+6,)
                    elif alphabet_id == 1:
                        return (shift_up,char_idx+6)
                    else:
                        return (shift_down,char_idx+6)

        # Return spaces for any unknown chars
        return (0,)

    def write_zchars_to_memory(self,zchars,memory,idx):
        """ Given a list of zchars, write them to memory starting at idx, 0 terminated """
        pass

    def get_zchars_from_memory(self,memory,idx):    
        """ Return the three zchars at the word at index idx of memory, as well
            as whether or not this has the end bit set.

            Each word has 3 5-bit zchars, starting at bit E.
            Bit   F E D C B A 9 8 7 6 5 4 3 2 1 0
            ZChar   1 1 1 1 1 2 2 2 2 2 3 3 3 3 3
            """
        try:
            b0 = memory[idx]
            b1 = memory[idx+1]

            # Use masks and shifts to filter out the three 5-bit chars we want, as well as whether
            # end bit is set
            return ((b0 & 0x7C)>>2,((0x03 & b0) << 3) | ((0xE0 & b1)>>5), int(b1 & 0x1F)), (b0 & 0x80) == 0x80
        except IndexError:
            return (6,6,6,),True

    def shift(self,reverse=False,permanent=False):
        """ Shift the current alphabet. 0 shifts it "right" (A0->A1->A2)
            and 1 shifts left (A2->A0->A1). Permanent will store the new alphabet,
            and is only used for versions 1 and 2 """
        if self.debug:
            print('   shifting from %d - %s,%s' % (self._current_alphabet, reverse,permanent))
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

