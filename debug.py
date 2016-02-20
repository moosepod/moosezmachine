import curses
from curses import wrapper

import argparse
import time

from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory
from zmachine.text import ZTextException

# Window constants
STORY_TOP_MARGIN = 1
STORY_BOTTOM_MARGIN = 1 
STATUS_BAR_HEIGHT = 1
STORY_WINDOW_WIDTH = 80 
STORY_RIGHT_MARGIN = 1

class QuitException(Exception):
    pass

class ResetException(Exception):
    pass

class CursesStream(OutputStream):
    def __init__(self,window):
        super(CursesStream,self).__init__()
        self.window = window
        self.height,self.width = window.getmaxyx()
        self.window.move(self.height-1,0)
        self.window.scrollok(True)

    def refresh(self):
        """ Redraw this screen """
        self.window.refresh()
            
    def _println(self,msg):
        self.window.addstr(msg)
        self.window.addstr('\n')
        self.refresh()

    def _print(self,msg):
        self.window.addstr(msg)
        self.refresh()

    def new_line(self):
        self._println('')
        
    def print_str(self,txt):
        self._print(txt)

class StepperWindow(object):
    def next_line(self):
        return False

    def previous_line(self):
        return False
    
    def redraw(self,window,zmachine,height):
        for i,inst_t in enumerate(zmachine.instructions(10)):
            if i == 0:
                prefix = " >>> "
            else:
                prefix = "     "
            instruction, idx = inst_t 
            window.addstr("%04x %s\n" % (idx,instruction.bytestr))
            extra = ''
            if instruction.operands:
                extra = ' %s' % instruction.operands
            if instruction.handler.is_branch:
                extra += ' br->%s' % instruction.branch_to
            if instruction.handler.is_store:
                extra += ' st->%s' % instruction.store_to
            window.addstr("%s%s:%s %s\n\n" % (prefix,instruction.instruction_type,instruction.handler.description,extra))  

class MemoryWindow(object):
    def __init__(self):
        self.address = 0

    def next_line(self):
        self.address += 0x10
        return True

    def previous_line(self):
        self.address -= 0x10
        if self.address < 0:
            self.address = 0
        return True
    
    def redraw(self,window,zmachine,height):
        for i in range(0,height-1):
            addr = self.address + (0x10 * i)
            s = '%.4x ' % addr
            s += str(' '.join(['%.2x' % x for x in zmachine.story.raw_data[addr:addr+16]]))
            s += '\n'
            window.addstr(s)   
        
class DictionaryWindow(object):
    def __init__(self):
        self.dictionary_index = 0

    def next_line(self):
        self.dictionary_index += 1
        return True

    def previous_line(self):
        self.dictionary_index -= 1
        if self.dictionary_index < 0:
            self.dictionary_index = 0
        return True
    
    def redraw(self,window,zmachine,height):
        dictionary = zmachine.story.dictionary
        ztext = zmachine.get_ztext()

        window.addstr('Use , and . to scroll dictionary\n\n')
        window.addstr('Entries       : %d\n' % len(dictionary))
        window.addstr('Entry length  : %d\n' % dictionary.entry_length)
        window.addstr('Keyboard codes: %s' % '  '.join(['"%s"' % ztext._map_zscii(x) for x in dictionary.keyboard_codes]))
        window.addstr('\n\n')
        y,x = window.getyx()
        for i in range(0,min(height-y,len(dictionary) - self.dictionary_index)): 
            try:
                idx = i + self.dictionary_index
                ztext.reset()
                text = ztext.to_ascii(Memory(dictionary[idx]), 0,4)
            except ZTextException as e:  
                window.addstr('Error. %s\n' % e)
            window.addstr(' %d: %.2X %.2X %.2X %.2X (%s)\n' % (idx, 
                                    dictionary[idx][0],
                                    dictionary[idx][1],
                                    dictionary[idx][2],
                                    dictionary[idx][3],
                                     text))
class HeaderWindow(object):
    def next_line(self):
       return False

    def previous_line(self):
        return False

    def redraw(self,window,zmachine,height):
        header = zmachine.story.header
       
        window.addstr('Version:                  %d\n' % (header.version))
        window.addstr('Himem address:            0x%04x\n' % (header.himem_address))
        window.addstr('Main routine address:     0x%04x\n' % (header.main_routine_addr))
        window.addstr('Dictionary address:       0x%04x\n' % (header.dictionary_address))
        window.addstr('Object table address:     0x%04x\n' % (header.object_table_address))
        window.addstr('Global variables address: 0x%04x\n' % (header.global_variables_address))
        window.addstr('Static memory address:    0x%04x\n' % (header.static_memory_address))
        window.addstr('Abbrev table address:     0x%04x\n' % (header.abbrev_address))
        window.addstr('File length:              0x%08x\n' % (header.file_length))
        window.addstr('Checksum:                 0x%08x\n' % (header.checksum))
        window.addstr('Revision number:          0x%04x\n' % (header.revision_number))
        window.addstr('Flags:')
        if header.flag_status_line_type == 0: window.addstr('   score/turns\n')
        if header.flag_status_line_type == 1: window.addstr('   hours:mins\n')
        if header.flag_story_two_disk: window.addstr('   two disk\n')
        if header.flag_status_line_not_available: window.addstr('   no status line\n')
        if header.flag_screen_splitting_available: window.addstr('   screen split available\n')
        if header.flag_variable_pitch_default: window.addstr('  variable pitch is default\n')

class DebuggerWindow(object):
    def __init__(self, zmachine, window):
        self.zmachine = zmachine
        self.window = window
        self.window_handlers = {'s': StepperWindow(),
                                'h': HeaderWindow(),
                                'm': MemoryWindow(),
                                'd': DictionaryWindow()}
        self.current_handler = self.window_handlers['s']
        self.window_height,self.window_width = window.getmaxyx()

    def status(self,msg):
        self.window.move(2,10)
        self.window.addstr(msg)
        self.window.refresh()
    
    def quit(self):
        raise QuitException()
    
    def reset(self):
        raise ResetException()
    
    def key_pressed(self,key):  
        """ Key pressed while debugger active """
        ch = chr(key).lower()
        if ch == 'q':
            self.quit()
        elif ch == 'r':
            self.reset()
        elif ch == 's':
            self.current_handler = self.window_handlers['s']
            self.zmachine.step()
            self.redraw()
        elif ch == '.' or ch == '>':
            if self.current_handler.next_line():
                self.redraw()
        elif ch == ',' or ch == '<':
            if self.current_handler.previous_line():
                self.redraw()
        else:
            h = self.window_handlers.get(ch)
            if h:
                self.current_handler = h
                self.redraw()

    def redraw(self):
        curses.curs_set(0) # Hide cursor
        self.window.clear()
        self.window.addstr(0,0,"(Q)uit (R)eset (S)tep (M)emory (H)eader (D)ictionary (O)bjects",curses.A_REVERSE)
        
        self.window.move(2,0)
        if self.current_handler:
            self.current_handler.redraw(self.window, self.zmachine, self.window_height-3) # 3 is height of header + buffer
        
        self.window.refresh()

class MainLoop(object):
    def __init__(self,zmachine):
        self.zmachine = zmachine

    def loop(self,screen):
        # Disable automatic echo
        curses.noecho()
        
        # Use unbufferd input
        curses.cbreak()

        # THe main screen
        screen_height,screen_width = screen.getmaxyx()
        if screen_width < 120:
            print('Terminal must be at least 120 characters wide')
            return
        if screen_height < 20:
            print('Terminal must be at least 20 characters in height')
            return     

        # The status bar
        status = curses.newwin(STATUS_BAR_HEIGHT,STORY_WINDOW_WIDTH,0,0)
        status.addstr(0,0,"Status bar",curses.A_REVERSE)
        status.refresh()

        # The story window
        story = curses.newwin(screen_height-(STORY_TOP_MARGIN+STORY_BOTTOM_MARGIN+STATUS_BAR_HEIGHT),
                              STORY_WINDOW_WIDTH,
                              STATUS_BAR_HEIGHT+STORY_TOP_MARGIN,
                              0)
        story.refresh()
        self.zmachine.output_streams.set_screen_stream(CursesStream(story))

        # The debugger window
        debugger = DebuggerWindow(self.zmachine,
                                curses.newwin(screen_height,
                                 screen_width-STORY_WINDOW_WIDTH-STORY_RIGHT_MARGIN,
                                 0,
                                 STORY_WINDOW_WIDTH+STORY_RIGHT_MARGIN))
        debugger.redraw()

        debugger_selected = True

        while True:
            ch = story.getch()
            if debugger_selected:
                debugger.key_pressed(ch)

def load_zmachine(filename):
    with open(filename,'rb') as f:
        story = Story(f.read())
        outputs = OutputStreams(OutputStream(),OutputStream())
        zmachine = Interpreter(story,outputs,None,None)
        zmachine.reset(force_version=3)

    return zmachine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file')
    data = parser.parse_args()
    filename = data.file
    
    try:
        while True:
            try:
                start(filename)    
            except ResetException:
                print("Resetting...")
                time.sleep(1)
    except QuitException:
        print("Thanks for playing!")

def start(filename):
    zmachine = load_zmachine(filename)
    loop = MainLoop(zmachine)
    wrapper(loop.loop)

if __name__ == "__main__":
    main()
