""" Support classes around working with virtual "memory" in the ZMachine VM """

class MemoryException(Exception):
    pass

class Memory(object):
    SIGNED_INT_MIN = -32768
    SIGNED_INT_MAX = 32767

    def __init__(self, data):
        self._raw_data = bytearray(data) 

    def signed_int(self,idx):
        """ Return the memory value at IDX as a signed integer. Per spec, this means
            values > 32767 are stored as 65536 (0x10000) - n """
        d = self.word(idx)
        if d > Memory.SIGNED_INT_MAX:
            return -1 * (0x10000 - d)
        return d

    def set_signed_int(self,idx,val):
        if val < Memory.SIGNED_INT_MIN or val > Memory.SIGNED_INT_MAX:
            raise MemoryException('Storing too large signed int %d to %d' % (val, idx))      
        if val < 0:
            self.set_word(idx, 0x10000 + val)
        else:
            self.set_word(idx, val)

    def flag(self,idx,bit):
        """ Return True or False based on the bit at the given index """
        data = self[idx]
        data = data >> bit
        return data & 0x00000001 == 1
        
    def set_flag(self,idx,bit,value):
        data = self[idx]
        new_data = 0x1 << bit
        if value:
            self[idx] = data | new_data        
        else:
            self[idx] = (~new_data) & data

    def packed_address(self,idx,multiplier):
        """ Packed addresses are stored as multiplier * idx. Multiplier varies
            based on version """
        return self.word(idx*multiplier)

    def word(self, idx):
        """ Return the word at the provided address """
        return (self[idx]*256) + self[idx+1]

    def set_word(self,idx,val):
        """ Set the two-byte word at the given index to the (unsigned) integer value """
        self[idx] = (val & 0xFF00) >> 8
        self[idx+1] = val & 0x00FF

    def _zchar_to_zscii(self, zchar,alphabet=0):
        if (alphabet < 0 or alphabet > 2):
            raise Exception('Alphabet must be between 0 and 2')
        return Memory.ZCHARS[alphabet][zchar-6]

    def __len__(self):
        return len(self._raw_data)

    def __getitem__(self,idx):
        """ Return byte at the provided address """
        return self._raw_data[idx]

    def __setitem__(self,idx,val):
        """ Set byte at provided address """
        self._raw_data[idx] = val

    def dump(self, width=16,start_address=0):
        """ Dump all memory in a convienient format """
        counter = 0
        length = len(self)
        while counter < length:
            row = []
            if width + counter > length:
                width = length-counter
            for i in range(0,width):
                row.append('%.2x' % self[counter+i])
            print('%s %s' % ('%.8x' % (counter+start_address), ' '.join(row)))
            counter += width
       
                
                       
        

