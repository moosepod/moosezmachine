""" Given a set of byte (as hex), print the zchars and ascii """

import sys
from zmachine.text import ZText
from zmachine.memory import Memory

def main():
    args = sys.argv[1:]
    if len(args) < 1:
        print 'Usage: python zprint.py 00 [more hex]'
        return
    
    ztext = ZText(1,lambda x: None)
    memory = Memory([int('0x%s' % x,16) for x in args])
    i = 0
    word = []
    while i < len(memory):
        chars, end = ztext.get_zchars_from_memory(memory,i)
        word.extend(chars)
        i+=2
    print 'ZChars : %s' % ' '.join([str(x) for x in word])
    print 'ASCII  : %s' % ''.join([ztext._map_zchar(x) for x in word])

if __name__ == "__main__":
    main()
