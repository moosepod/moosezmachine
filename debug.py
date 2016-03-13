import sys

import logging
import curses
import curses.ascii
from curses import wrapper

import argparse
import time

from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream
from zmachine.text import ZTextException
from zmachine.memory import BitArray,MemoryException
from zmachine.instructions import InstructionException

# Window constants
STORY_TOP_MARGIN = 1
STORY_BOTTOM_MARGIN = 1 
STATUS_BAR_HEIGHT = 1
STORY_WINDOW_WIDTH = 80 
STORY_RIGHT_MARGIN = 1

BACKSPACE_CHAR = '\x7f'

class DebugQuitException(Exception):
    pass

class ResetException(Exception):
    pass

class CursesInputStream(object):
    def __init__(self,window):
        super(CursesInputStream,self).__init__()
        self.window = window
        self.text = ''
        self.waiting_for_line = False
        self.line_done = False

    def char_pressed(self,char):
        if char == '\n' or char == '\r':
            self.line_done = True
        elif char == BACKSPACE_CHAR:
            if self.text:
                self.text = self.text[0:-1]
                y,x = self.window.getyx()
                self.window.move(y,x-1)
                self.window.clrtoeol()
                self.window.refresh()
        else:
            self.text += char
            self.window.addstr(char)
            self.window.refresh()

    def readline(self):
        # Note that we're currently waiting for text from the keyboard
        if not self.waiting_for_line:
            self.waiting_for_line = True
            self.line_done = False
            curses.curs_set(2) # Set cursor to very visible
            self.window.refresh()

        if self.line_done:
            text = self.text
            self.waiting_for_line = True
            self.line_done = False
            self.text = ''
            curses.curs_set(0) # Set cursor to hidden
            self.window.refresh()
            return text

        return None

class CursesOutputStream(OutputStream):
    def __init__(self,window,status_window):
        super(CursesOutputStream,self).__init__()
        self.window = window
        self.height,self.width = window.getmaxyx()
        self.status_height,self.status_width = status_window.getmaxyx()
        self.window.move(self.height-1,0)
        self.window.scrollok(True)
        self.buffer = ''
        self.status_window = status_window

    def refresh(self):
        """ Redraw this screen """
        self.window.refresh()

    def _print_buffer_msg(self,msg):
        # Break message up so it wraps nicely on word breaks
        self.buffer = msg
        lines = []
        target_width = self.width-1
        for line in msg.split('\n'):
            while len(line) >= target_width:
                new_line, line = line[0:target_width],line[target_width:]
                for i in range(len(new_line)-1,0,-1):
                    if new_line[i] in (' ','.',',',':',';'):
                        new_line = new_line[0:i]
                        lines.append(new_line)
                        break
                    else:
                        line = '%s%s' % (new_line[i],line)
            lines.append(line)
        first_line=True
        for line in lines:
            if not first_line:
                self.window.addstr('\n')
            else:
                first_line = False
            self.window.addstr(line)
            
    def _println(self,msg):
        self._print_buffer_msg(msg)
        self.window.addstr('\n')
        self.refresh()

    def _print(self,msg):
        self._print_buffer_msg(msg)
        self.refresh()

    def new_line(self):
        self._println('')
        
    def print_str(self,txt):
        self._print(txt)

    def print_char(self,txt):
        self._print(txt)

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        if score_mode:
            right_string = 'Score: %s Moves: %s' % (score or 0,turns or 0)
        else:
            right_string = '{:02}:{:02}' % (hours,minutes)

        status_format = '{:%d}{:>%d}' % (self.status_width-len(right_string)-1,len(right_string))
        status_msg = status_format.format(room_name,right_string)

        self.status_window.addstr(0,0,status_msg,curses.A_REVERSE)
        self.status_window.refresh()

class FileTranscriptStream(OutputStream):
    def __init__(self,path):
        super(FileTranscriptStream,self).__init__()
        self.path = path

        # Clear the transcript on starting the stream
        with open(self.path, 'w') as f:
            f.write('')

    def refresh(self):
        pass
            
    def _println(self,msg):
        self._print(msg + '\n')

    def _print(self,msg):
        with open(self.path, 'a') as f:
            f.write(msg)

    def new_line(self):
        self._println('')
        
    def print_str(self,txt):
        self._print(txt)

    def print_char(self,txt):
        self._print(txt)

    def show_status(self, msg, time=None, score=None):
        pass

class StepperWindow(object):
    def next_line(self):
        return False

    def previous_line(self):
        return False
    
    def redraw(self,window,zmachine,height):
        idx = zmachine.pc
        try:
            i = 0
            while i < 10:
                handler, description,next_address = zmachine.instruction_at(idx)
                if i == 0:
                    prefix = " >>> "
                else:
                    prefix = "     "
                window.addstr('%04x: %s\n' %(idx,' '.join(['%02x' % x for x in zmachine.story.raw_data[idx:next_address]])))
                window.addstr("%s%s\n\n" % (prefix,description,))  
                idx = next_address
                i+=1
        except InstructionException as e:
            window.addstr('%04x: %s\n' %(idx,' '.join(['%02x' % x for x in zmachine.story.raw_data[idx:idx+8]])))
            window.addstr('%04x: %s\n' %(idx,e))


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

class ObjectsWindow(object):
    def __init__(self,max_obj):
        self.obj_index = 1
        self.max_obj = max_obj

    def next_line(self):
        self.obj_index += 1
        if self.obj_index > self.max_obj:
            self.obj_index = self.max_obj

        return True

    def previous_line(self):
        self.address -= 1
        if self.address < 0:
            self.address = 0
        return True
    
    def redraw(self,window,zmachine,height):
        ztext = zmachine.get_ztext()
        for i in range(self.obj_index,min(self.max_obj, height-self.obj_index)):
            obj = zmachine.story.object_table[i]
            zc = obj['short_name_zc']
            window.addstr('%d: %s\n' % (i,ztext.to_ascii(zc,0,len(zc))))
            if obj['parent']:
                window.addstr('   child of: %d\n' % (obj['parent']))
            if obj['child']:
                window.addstr('   child is: %d\n' % (obj['child']))
            if obj['sibling']:
                window.addstr('   sibling is: %d\n' % (obj['sibling']))
            for number,data in obj['properties'].items():
                window.addstr('   %s: %s \n' % (number,''.join(['%02x' % x for x in data['data']])))

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

class AbbreviationWindow(object):
    def __init__(self):
        self.abbrev_index = 0

    def next_line(self):
        self.abbrev_index += 1
        return True

    def previous_line(self):
        self.abbrev_index -= 1
        if self.abbrev_index < 0:
            self.abbrev_index = 0
        return True
    
    def redraw(self,window,zmachine,height):
        ztext = zmachine.get_ztext()

        window.addstr('Use , and . to scroll abbrevs\n\n')
        y,x = window.getyx()
        zchar=1
        max_val = 32*3
        if zmachine.story.header.version == 2:
            max_val = 32
        for i in range(0,min(height-y,max_val - self.abbrev_index)): 
            idx = self.abbrev_index + i
            try:
                ztext.reset()
                text = ztext.to_ascii(zmachine.get_abbrev(idx),0,0)
                if text:
                    window.addstr('%d: %s\n' % (idx,text))
                else:
                    window.addstr('%d\n' % (idx))
            except ZTextException as e: 
                window.addstr('%d/%d: ztext error\n' % (zchar,i))

class VariablesWindow(object):
    def __init__(self):
        self.vars_index= 0

    def next_line(self):
        self.vars_index += 1
        return True

    def previous_line(self):
        self.vars_index -= 1
        if self.vars_index < 0:
            self.vars_index = 0
        return True
    
    def redraw(self,window,zmachine,height):
        routine = zmachine.current_routine()
        for i in range(self.vars_index,min(height+self.vars_index,255)):
            if i == 0:
                val = routine.peek_stack()
            else:
                val = routine[i]
            window.addstr('%d) %.4x\n' % (i,val or 0)) 

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
                                'v': VariablesWindow(),
                                'a': AbbreviationWindow(),
                                'o': ObjectsWindow(zmachine.story.object_table.estimate_number_of_objects()),
                                'd': DictionaryWindow()}
        self.current_handler = self.window_handlers['s']
        self.window_height,self.window_width = window.getmaxyx()
        self.is_running = True
        self.is_running_slow = False
        self.is_active =True

    def status(self,msg):
        self.window.move(2,10)
        self.window.addstr(msg)
        self.window.refresh()
    
    def quit(self):
        raise DebugQuitException()
    
    def reset(self):
        raise ResetException()

    def _run_fast(self):
        self.is_running = True
        self.is_running_slow = False
        self.window.timeout(1)

    def _run_slow(self):
        self.is_running = True
        self.is_running_slow = True
        self.window.timeout(100)
    
    def key_pressed(self,key):  
        """ Key pressed while debugger active """
        ch = chr(key).lower()
        if ch == 'q':
            self.quit()
        elif ch == 'r':
            self.reset()
        elif ch == 'i':
            self.current_handler = self.window_handlers['s']
            self.redraw()
        elif ch == 's':
            self.is_running=False            
            self.current_handler = self.window_handlers['s']
            self.zmachine.step()
            self.redraw()
        elif ch == 'g':
            self.current_handler = self.window_handlers['s']
            if self.is_running:
                self._run_fast()
            else:
                self._run_slow()
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
        if self.is_active:
            self.window.addstr(0,0,"(Q)uit (R)eset (M)em (H)eader (D)ict (A)bbr (V)ars (O)bjs (I)nstr (S)tep (G)o",curses.A_REVERSE)
        else:
            self.window.addstr(0,0,"Hit ESC for control",curses.A_REVERSE)
        
        self.window.move(2,0)
        if self.current_handler:
            self.current_handler.redraw(self.window, self.zmachine, self.window_height-3) # 3 is height of header + buffer
        self.window.refresh()

class ErrorWindow(object):
    def __init__(self,window):
        self.window = window

    def error(self,msg):
        self.window.addstr(0, 0, msg, curses.A_REVERSE)
        self.window.refresh()

class MainLoop(object):
    def __init__(self,zmachine,breakpoint,breakattext,transcript):
        self.zmachine = zmachine
        self.breakpoint = breakpoint
        self.is_running_slow = False
        self.is_running = True
        self.breakattext = breakattext
        self.transcript = transcript
        self.curses_input_stream = None

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
        status.addstr(0,0,"",curses.A_REVERSE)
        status.refresh()

        # The story window
        story = curses.newwin(screen_height-(STORY_TOP_MARGIN+STORY_BOTTOM_MARGIN+STATUS_BAR_HEIGHT),
                              STORY_WINDOW_WIDTH,
                              STATUS_BAR_HEIGHT+STORY_TOP_MARGIN,
                              0)
        story.refresh()
        curses_output_stream = CursesOutputStream(story,status)
        self.zmachine.output_streams.set_screen_stream(curses_output_stream)
        if self.transcript:
            self.zmachine.output_streams[OutputStreams.TRANSCRIPT] = FileTranscriptStream(self.transcript)
            self.zmachine.output_streams.select_stream(OutputStreams.TRANSCRIPT)

        self.curses_input_stream = CursesInputStream(story)
        self.zmachine.input_streams.keyboard_stream = self.curses_input_stream
        self.zmachine.input_streams.select_stream(0)

        # The debugger window
        debugger = DebuggerWindow(self.zmachine,
                                curses.newwin(screen_height-2,
                                 screen_width-STORY_WINDOW_WIDTH-STORY_RIGHT_MARGIN,
                                 0,
                                 STORY_WINDOW_WIDTH+STORY_RIGHT_MARGIN))
        debugger.redraw()
        debugger.window.timeout(100)

        debugger_selected = True

        # Area for error messages
        error_window = ErrorWindow(curses.newwin(2,
                                screen_width-STORY_WINDOW_WIDTH-STORY_RIGHT_MARGIN,
                                screen_height-2,
                                STORY_WINDOW_WIDTH+STORY_RIGHT_MARGIN))

        if self.breakattext or self.breakpoint:
            debugger.window.timeout(1)
            debugger.is_running = True
            debugger.is_running_slow=False
        else:
            # Default running at full speed
            debugger._run_fast()
        control_mode = True
        while True:
            try:
                if debugger.is_running:
                    if self.breakpoint and self.zmachine.pc == int(self.breakpoint,16):
                        debugger.is_running = False
                        debugger.redraw()
                        self.breakpoint = None
                    elif self.breakattext and self.breakattext in curses_stream.buffer:
                        debugger.is_running = False
                        debugger.redraw()
                        self.breakattext = None
                    else:
                        self.zmachine.step()
                        if debugger.is_running_slow:
                            debugger.redraw()

                ch = debugger.window.getch()
                if ch != curses.ERR:
                    if ch == curses.ascii.ESC:
                        control_mode = not control_mode
                        if control_mode:
                            debugger.is_active=True
                        else:
                            debugger.is_active=False
                        debugger.redraw()
                    elif self.curses_input_stream.waiting_for_line and not control_mode:
                        debugger.is_active=False
                        debugger.redraw()
                        self.curses_input_stream.char_pressed('%s' % chr(ch))
                    elif debugger_selected :
                        debugger.key_pressed(ch)
                        control_mode = False
            except InstructionException as e:
                error_window.error('%s at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction))
                debugger.is_running=False
            except MemoryException as e:
                error_window.error('%s at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction))
                debugger.is_running=False
            except MemoryAccessException as e:
                error_window.error('%s at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction))
                debugger.is_running=False
            except ZTextException as e:
                error_window.error('%s at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction))
                debugger.is_running=False
            except StoryFileException as e:
                error_window.error('%s at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction))
                debugger.is_running=False
            except InterpreterException as e:
                error_window.error('%s at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction))
                debugger.is_running=False
            except QuitException as e:
                error_window.error('Request to quit at at PC 0x%04x [%s]' % (self.zmachine.pc,self.zmachine.last_instruction))
                debugger.is_running=False
            except Exception as e:
                raise Exception('Unhandled exception "%s" at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction),e)

def load_zmachine(filename):
    with open(filename,'rb') as f:
        story = Story(f.read())
        outputs = OutputStreams(OutputStream(),OutputStream())
        inputs = InputStreams(InputStream(),InputStream())
        zmachine = Interpreter(story,outputs,inputs,None,None)
        zmachine.reset()
        zmachine.story.header.set_debug_mode()

    return zmachine

def main():
    if sys.version_info[0] < 3:
        raise Exception("Moosezmachine requires Python 3.")

    parser = argparse.ArgumentParser()
    parser.add_argument('--file')
    parser.add_argument('--breakpoint')
    parser.add_argument('--transcript')
    parser.add_argument('--breakattext')
    data = parser.parse_args()
    filename = data.file
    breakpoint = data.breakpoint
    breakattext = data.breakattext
    transcript = data.transcript
    if breakpoint and not breakpoint.startswith('0x'):
        breakpoint = '0x' + breakpoint
    try:
        while True:
            try:
                start(filename,breakpoint,breakattext,transcript)    
            except ResetException:
                print("Resetting...")
                time.sleep(1)
    except QuitException:
        print("Thanks for playing!")

def start(filename,breakpoint,breakattext,transcript):
    zmachine = load_zmachine(filename)
    loop = MainLoop(zmachine,breakpoint,breakattext,transcript)
    wrapper(loop.loop)

if __name__ == "__main__":
    main()
