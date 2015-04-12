""" Support classes around working with virtual "memory" in the ZMachine VM """

class Memory(object):
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

    def address(self, idx):
        """ Return the two-byte address (as an unsigned int) at the given index """
        return (self[idx]*256) + self[idx+1]

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

       
                
                       
        

