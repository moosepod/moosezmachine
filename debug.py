import curses
from curses import wrapper
import argparse

from zmachine.interpreter import ZMachine,OutputStream

# Window constants
STORY_TOP_MARGIN = 1
STORY_BOTTOM_MARGIN = 1 
STATUS_BAR_HEIGHT = 1
STORY_WINDOW_WIDTH = 80 
STORY_RIGHT_MARGIN = 1

class CursesStream(OutputStream):
    def __init__(self,window):
        super(CursesStream,self).__init__()
        self.window = window

class DebuggerWindow(object):
    def __init__(self, zmachine, window):
        self.zmachine = zmachine
        self.window = window

    def redraw(self):
        self.window.clear()
        self.window.addstr(0,0,"^Quit | ^Reset | ^Step | ^Vars | ^PC | ^Header | ^Dictionary | ^Objects",curses.A_REVERSE)
        
        self.window.move(2,0)

        for i,inst in enumerate(self.zmachine.instructions()):
            instruction, idx = inst
            self.window.addstr("%04x %s\n" % (idx,instruction.bytestr))
            self.window.addstr("    %s:%s\n\n" % (instruction.instruction_type,instruction.handler.description))  
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

        while True:
            pass

def load_zmachine(filename):
    zmachine = ZMachine()
    with open(filename,'rb') as f:
        zmachine.initialize(f.read(),OutputStream(),OutputStream(),OutputStream())
        if not zmachine:
            raise Exception('Unable to load zmachine %s' % filename)
    return zmachine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file')
    data = parser.parse_args()
    filename = data.file
    
    zmachine = load_zmachine(filename)
    loop = MainLoop(zmachine)
    wrapper(loop.loop)

if __name__ == "__main__":
    main()
