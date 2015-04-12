""" Support classes around working with virtual "memory" in the ZMachine VM """

class Memory(object):
    ZCHARS = [['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'],
              ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'],
              [' ', '^', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.', ',', '!', '?', '_', '#', "'", '"', '/', '\\', '-', ':', '(', ')']]

    def __init__(self, data):
        """ This can take an array of chars, or an list of ints. Either way it will store internally
            as a list of ints """
        try:
            self._raw_data = [int(x) for x in data]
        except ValueError, e:
            if u'invalid literal for int()' in unicode(e):
                self._raw_data = [ord(x) for x in data]
            else:
                raise e

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

    def integer(self,idx):
        """ Return the two-byte integer at the given index """
        return self.address(idx)

    def address(self, idx):
        """ Return the two-byte address (as an unsigned int) at the given index """
        return (self[idx]*256) + self[idx+1]

    def _zchar_to_zscii(self, zchar,alphabet=0):
        if (alphabet < 0 or alphabet > 2):
            raise Exception('Alphabet must be between 0 and 2')
        return Memory.ZCHARS[alphabet][zchar-6]

    def __len__(self):
        return len(self._raw_data)

    def __getitem__(self,idx):
        return self._raw_data[idx]

    def __setitem__(self,idx,val):
        self._raw_data[idx] = val

    def dump(self, width=16):
        """ Dump all memory in a convienient format """
        counter = 0
        length = len(self)
        while counter < length:
            row = []
            if width + counter > length:
                width = length-counter
            for i in range(0,width):
                row.append('%.2x' % self[counter+i])
            print '%s %s' % ('%.8x' % counter, ' '.join(row))
            counter += width

       
                
                       
        

