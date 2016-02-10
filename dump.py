#
# Dump the header for a ZCode file
#

import sys
import argparse
from zmachine.interpreter import ZMachine,StoryFileException
from zmachine.text import ZTextException
from zmachine.memory import Memory

class DumpScreen(object):
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.string = []

    def print_ascii(self,msg):
        self.string.append(msg)

    def done(self):
        print(''.join(self.string))
        self.reset()

def dump_memory(data,zmachine,start_address,):
    data.dump(start_address=start_address)

def load(path):
    with open(path,'rb') as f:
        zmachine = ZMachine()
        try:
            zmachine.raw_data = f.read()
        except StoryFileException as e:
            print('Unable to load story file. %s' % e)
            return None
    return zmachine

def dump(path,abbrevs=False,dictionary=False,start_address=0):
        zmachine = load(path)
        if not zmachine:
            return

        header = zmachine.header
       
        print('Version:                  %d' % (header.version))
        print('Himem address:            0x%04x' % (header.himem_address))
        print('PC Address:               0x%04x' % (header.program_counter_address))
        print('Dictionary address:       0x%04x' % (header.dictionary_address))
        print('Object table address:     0x%04x' % (header.object_table_address))
        print('Global variables address: 0x%04x' % (header.global_variables_address))
        print('Static memory address:    0x%04x' % (header.static_memory_address))
        print('Abbrev table address:     0x%04x' % (header.abbrev_address))
        print('File length:              0x%08x' % (header.file_length))
        print('Checksum:                 0x%08x' % (header.checksum))
        print('Revision number:          0x%04x' % (header.revision_number))
        print('Flags:')
        if header.flag_status_line_type == 0: print('   score/turns')
        if header.flag_status_line_type == 1: print('   hours:mins')
        if header.flag_story_two_disk: print('   two disk')
        if header.flag_status_line_not_available: print('   no status line')
        if header.flag_screen_splitting_available: print('   screen split available')
        if header.flag_variable_pitch_default: print('  variable pitch is default')

        print('')
        print('Raw memory\n---------\n')
        header.dump()
        print('')

        print('Current instruction\n--------\n')
        print(zmachine.current_instruction())
        print('')
        
        if start_address:
            print('')
            print('Dumping from 0x%x' % start_address)
            data = zmachine.get_memory(start_address,start_address+(16*10))
            dump_memory(data,zmachine,start_address)

        ztext = zmachine.get_ztext()
        if abbrevs:
            print('')
            print('Abbreviations\n------------\n')
            data = zmachine.get_memory(header.abbrev_address,header.object_table_address)
            dump_memory(data,zmachine,header.abbrev_address,)


        if dictionary:
            print ('')
            print ('Dictionary\n--------------\n')
            dictionary = zmachine.dictionary
        
            print ('Entries       : %d' % len(dictionary))
            print ('Entry length  : %d' % dictionary.entry_length)
            print ('Keyboard codes:\n %s' % '\n '.join([ztext._map_zscii(x) for x in dictionary.keyboard_codes]))
            for i in range(0,len(dictionary)):
                try:
                    ztext.reset()
                    text = ztext.to_ascii(Memory(dictionary[i]), 0,4)
                except ZTextException as e:  
                    print('Error. %s' % e)
                print(' %d: %.2X %.2X %.2X %.2X (%s)' % (i, 
                                        dictionary[i][0],
                                        dictionary[i][1],
                                        dictionary[i][2],
                                        dictionary[i][3],
                                         text))
def usage() :
    print('Usage: python dump.py [--abbrevs] path_to_story_file')
    return 

def main():
    dictionary = False
    abbrevs = False
    parser = argparse.ArgumentParser()
    parser.add_argument('--dictionary',action='store_true')
    parser.add_argument('--abbrevs',action='store_true')
    parser.add_argument('--address')
    parser.add_argument('--file')
    data = parser.parse_args()
    abbrevs = data.abbrevs
    dictionary  = data.dictionary
    filename = data.file
    addr_tmp = data.address or '0x00'
    start_address=0
    if addr_tmp and not addr_tmp.startswith('0x'):
        print('address must start with 0x')
        return 
    try:
        start_address = int(addr_tmp,0)
    except ValueError:
        print('address must starat with 0x and be a valid hex address')
    dump(filename, abbrevs=abbrevs,dictionary=dictionary,start_address=start_address)

if __name__ == "__main__":
    main()
