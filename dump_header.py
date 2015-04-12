#
# Dump the header for a ZCode file
#

import sys
from zmachine.interpreter import ZMachine

def dump(path):
    with open(path,'rb') as f:
        zmachine = ZMachine()
        zmachine.raw_data = f.read()
        header = zmachine.header
       
        print 'Version:                  %d' % (header.version)
        print 'Himem adddress:           0x%04x' % (header.himem_address)
        print 'PC Address:               0x%04x' % (header.program_counter_address)
        print 'Dictionary address:       0x%04x' % (header.dictionary_address)
        print 'Object table address:     0x%04x' % (header.object_table_address)
        print 'Global variables address: 0x%04x' % (header.global_variables_address)
        print 'Static memory address:    0x%04x' % (header.static_memory_address)

def main():
    if len(sys.argv) < 2:
        print 'Usage: python dump_header.py path_to_story_file'
        return
    dump(sys.argv[1])

if __name__ == "__main__":
    main()
