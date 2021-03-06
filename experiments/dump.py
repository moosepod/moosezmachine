#
# Dump the header for a ZCode file
#

import sys
import argparse
from zmachine.interpreter import Interpreter,Story,StoryFileException
from zmachine.text import ZTextException
from zmachine.memory import Memory
from zmachine.instructions import InstructionException

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
        story = Story(f.read())
        try:
            zmachine = Interpreter(story,None,None,None,None,None)
            zmachine.reset()
        except StoryFileException as e:
            print('Unable to load story file. %s' % e)
            return None
    return zmachine

def dump(path,abbrevs=False,dictionary=False,objects=False,instructions=False,start_address=0):
        zmachine = load(path)
        if not zmachine:
            return

        header = zmachine.story.header
       
        print('Version:                  %d' % (header.version))
        print('Himem address:            0x%04x' % (header.himem_address))
        print('Main routine address:     0x%04x' % (header.main_routine_addr))
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

        if instructions:
            print('Current instruction\n--------\n')
            idx = zmachine.pc
            try:
                for t in range(1,30):
                    t = zmachine.instruction_at(idx)
                    (f,description,next_address) = t
                    print('%04x: %s [%04x]' %(idx,' '.join(['%02x' % x for x in zmachine.story.raw_data[idx:next_address]]),next_address))
                    print('      %s' %(description,))
                    idx=next_address
            except InstructionException as e:
                print(e)
            print('')
        
        if objects:
            ztext = zmachine.get_ztext()
            print('Object Table Defaults\n--------\n')
            for i,val in enumerate(zmachine.story.object_table.property_defaults):
                print('%d) %04x' % (i,val))

            obj_count = zmachine.story.object_table.estimate_number_of_objects()
            print('Object Tables (%d estimated)\n--------\n' % obj_count)
            for i in range(1,obj_count+1):
                obj = zmachine.story.object_table[i]
                zc = obj['short_name_zc']
                try:
                    obj['short_name'],offset = ztext.to_ascii(zc,0,len(zc))
                except ZTextException:
                    obj['short_name'] = '(ZTEXT ERROR)'
                print('%d) %s' % (i,obj))

        if start_address:
            print('')
            print('Dumping from 0x%x' % start_address)
            data = zmachine.get_memory(start_address,start_address+(16*10))
            dump_memory(data,zmachine,start_address)

        if abbrevs:
            print('')
            print('Abbreviations\n------------\n')
            data = zmachine.get_memory(header.abbrev_address,header.object_table_address)
            dump_memory(data,zmachine,header.abbrev_address,)


        if dictionary:
            print ('')
            print ('Dictionary\n--------------\n')
            dictionary = zmachine.story.dictionary
        
            print ('Entries       : %d' % len(dictionary))
            print ('Entry length  : %d' % dictionary.entry_length)
            print ('Keyboard codes:\n %s' % '\n '.join([ztext._map_zscii(x) for x in dictionary.keyboard_codes]))
            for i in range(0,len(dictionary)):
                try:
                    ztext.reset()
                    text,offset = ztext.to_ascii(Memory(dictionary[i]), 0,4)
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
    if sys.version_info[0] < 3:
        raise Exception("Moosezmachine requires Python 3.")

    dictionary = False
    abbrevs = False
    parser = argparse.ArgumentParser()
    parser.add_argument('--dictionary',action='store_true')
    parser.add_argument('--abbrevs',action='store_true')
    parser.add_argument('--objects',action='store_true')
    parser.add_argument('--instructions',action='store_true')    
    parser.add_argument('--address')
    parser.add_argument('--file')
    data = parser.parse_args()
    abbrevs = data.abbrevs
    dictionary  = data.dictionary
    filename = data.file
    instructions = data.instructions
    objects = data.objects
    addr_tmp = data.address or '0x00'
    start_address=0
    if addr_tmp and not addr_tmp.startswith('0x'):
        print('address must start with 0x')
        return 
    try:
        start_address = int(addr_tmp,0)
    except ValueError:
        print('address must starat with 0x and be a valid hex address')
    dump(filename, abbrevs=abbrevs,dictionary=dictionary,start_address=start_address,objects=objects,instructions=instructions)

if __name__ == "__main__":
    main()
