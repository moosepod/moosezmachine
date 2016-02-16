import curses
from curses import wrapper

import argparse
import time

from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams

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

class DebuggerWindow(object):
    def __init__(self, zmachine, window):
        self.zmachine = zmachine
        self.window = window

    def status(self,msg):
        self.window.move(2,10)
        self.window.addstr(msg)
        self.window.refresh()
    
    def quit(self):
        raise QuitException()
    
    def reset(self):
        raise ResetException()
    
    def step(self):
        self.zmachine.step()
        self.redraw()
    
    def show_vars(self):
        self.status('VARS')

    def show_header(self):
        self.status('HEADER')

    def show_dictionary(self):
        self.status('DICTIONARY')

    def show_objects(self):
        self.status('OBJECTS')
    
    def key_pressed(self,key):  
        """ Key pressed while debugger active """
        ch = chr(key).lower()
        if ch == 'q':
            self.quit()
        elif ch == 'r':
            self.reset()
        elif ch == 's':
            self.step()
        elif ch == 'v':
            self.show_vars()
        elif ch == 'h':
            self.show_header()
        elif ch == 'd':
            self.show_dictionary()
        elif ch == 'o':
            self.show_objects()

    def redraw(self):
        self.window.clear()
        self.window.addstr(0,0,"(Q)uit (R)eset (S)tep (V)ars (H)eader (D)ictionary (O)bjects",curses.A_REVERSE)
        
        self.window.move(2,0)
        
        for i,inst_t in enumerate(self.zmachine.instructions(5)):
            if i == 0:
                prefix = " >>> "
            else:
                prefix = "     "
            instruction, idx = inst_t 
            self.window.addstr("%04x %s\n" % (idx,instruction.bytestr))
            self.window.addstr("%s%s:%s\n\n" % (prefix,instruction.instruction_type,instruction.handler.description))  
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
        zmachine.reset()

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
