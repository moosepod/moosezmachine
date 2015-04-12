#
# Dump the header for a ZCode file
#

import sys
from zmachine import ZMachine

def dump(path):
    with open(path,'rb') as f:
        zmachine = ZMachine()
        zmachine.raw_data = f.read()
        header = zmachine.header
       
        print 'Version:                  %d' % (header.version)


def main():
    if len(sys.argv) < 2:
        print 'Usage: python dump_header.py path_to_story_file'
        return
    dump(sys.argv[1])

if __name__ == "__main__":
    main()
