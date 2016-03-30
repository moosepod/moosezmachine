import sys
from enum import Enum

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

from curses_terp import CursesInputStream,CursesOutputStream,FileTranscriptStream

# Window constants
STORY_TOP_MARGIN = 1
STORY_BOTTOM_MARGIN = 1 
STATUS_BAR_HEIGHT = 1
STORY_WINDOW_WIDTH = 80 
STORY_RIGHT_MARGIN = 1


class DebugQuitException(Exception):
    pass

class ResetException(Exception):
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
        self.width=20

    def next_line(self):
        self.obj_index += 1
        if self.obj_index > self.max_obj:
            self.obj_index = self.max_obj

        return True

    def previous_line(self):
        self.obj_index -= 1
        if self.obj_index < 0:
            self.obj_index = 0
        return True

    def _safe_add_str(self,msg,window):
        msg = msg.replace('\n','')
        if len(msg) > self.width:
            msg = msg[0:self.width]
        window.addstr(msg)
        window.addstr('\n')
    
    def redraw(self,window,zmachine,height):
        ztext = zmachine.get_ztext()
        obj_index = self.obj_index
        obj = zmachine.story.object_table[obj_index]
        zc = obj['short_name_zc']
        self._safe_add_str('%d: %s' % (obj_index,ztext.to_ascii(zc,0,len(zc))),window)
        if obj['parent']:
            self._safe_add_str('   child of: %d' % (obj['parent']),window)
        if obj['child']:
            self._safe_add_str('   child is: %d' % (obj['child']),window)
        if obj['sibling']:
            self._safe_add_str('   sibling is: %d' % (obj['sibling']),window)
        for number,data in obj['properties'].items():
            self._safe_add_str('   %s: %s' % (number,''.join(['%02x' % x for x in data['data']])),window)

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
                window.addstr('%d) %s\n' % (i,routine.stack or 0)) 
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
    def __init__(self, zmachine,window):
        self.zmachine = zmachine
        self.is_active=False
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

    def status(self,msg):
        self.window.move(2,10)
        self.window.addstr(msg)
        self.window.refresh()
    
    def quit(self):
        raise DebugQuitException()
    
    def reset(self):
        raise ResetException()

    def key_pressed(self,key,terp):  
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
            terp.zmachine.step()           
            self.current_handler = self.window_handlers['s']
            self.redraw()
        elif ch == 'g':
            self.current_handler = self.window_handlers['s']
            terp.run()           
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

    def activate(self):
        self.is_active=True
        self.redraw()

    def deactivate(self):
        self.is_active=False
        self.redraw()

    def redraw(self):
        curses.curs_set(0) # Hide cursor
        self.window.clear()
        if self.is_active:
            self.window.addstr(0,0,"PAUSED: (Q)uit (R)eset (M)em (H)eader (D)ict (A)bbr (V)ars (O)bjs (I)nstr (S)tep (G)o",curses.A_REVERSE)
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

class RunState(Enum):
    RUNNING                  = 0
    PAUSED                   = 1
    RUN_UNTIL_BREAKPOINT = 2

class Terp(object):
    def __init__(self,zmachine,debugger):
        self.state = RunState.RUNNING
        self.zmachine = zmachine
        self.breakpoint = None
        self.breakattext = None
        self.debugger = debugger

    def run(self):
        if self.state != RunState.RUNNING:
            self.state = RunState.RUNNING
            self.debugger.deactivate()

    def pause(self):
        if self.state != RunState.PAUSED:
            self.state = RunState.PAUSED
            self.debugger.activate()

    def run_until(self,breakpoint=None,breakattext=None):
        if self.state != RunState.RUN_UNTIL_BREAKPOINT:
            self.breakpoint=breakpoint
            self.breakattext = breakattext
            self.state = RunState.RUN_UNTIL_BREAKPOINT
            self.debugger.deactivate()

    def idle(self):
        """ Called if no key is pressed """
        if self.state == RunState.RUNNING:
            self.zmachine.step()
        elif self.state == RunState.RUN_UNTIL_BREAKPOINT:
            if ((self.breakpoint and self.zmachine.pc == int(self.breakpoint,16) or
                (self.breakattext and len(self.breakattext) and self.breakattext in curses_output_stream.buffer))):
                    self.pause()
            else:
                self.zmachine.step()

    def key_pressed(self,ch,curses_input_stream):
        if self.state == RunState.RUNNING or self.state == RunState.RUN_UNTIL_BREAKPOINT:
            if ch == curses.ascii.ESC:
                self.pause()
            elif curses_input_stream.waiting_for_line:
                curses_input_stream.char_pressed('%s' % chr(ch))
                #if curses_input_stream.line_done:
                #    self.pause() # Pause after each command
        elif self.state == RunState.PAUSED:
            self.debugger.key_pressed(ch,self)

class MainLoop(object):
    def __init__(self,zmachine,breakpoint,breakattext,transcript):
        self.zmachine = zmachine
        self.breakpoint = breakpoint
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
        debugger.window.timeout(1)

        terp = Terp(self.zmachine,debugger)
        if self.breakpoint or self.breakattext:
            terp.run_until(breakpoint=self.breakpoint,breakattext=self.breakattext)
        else:
            terp.run()

        # Area for error messages
        error_window = ErrorWindow(curses.newwin(2,
                                screen_width-STORY_WINDOW_WIDTH-STORY_RIGHT_MARGIN,
                                screen_height-2,
                                STORY_WINDOW_WIDTH+STORY_RIGHT_MARGIN))

        while True:
            try:
                ch = debugger.window.getch()
                if ch == curses.ERR:
                    terp.idle()
                else:
                    terp.key_pressed(ch,self.curses_input_stream)
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
