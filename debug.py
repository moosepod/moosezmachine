import curses
from curses import wrapper
import argparse

from zmachine.interpreter import ZMachine

# Window constants
STORY_TOP_MARGIN = 1
STORY_BOTTOM_MARGIN = 1 
STATUS_BAR_HEIGHT = 1
STORY_WINDOW_WIDTH = 80 
STORY_RIGHT_MARGIN = 1
 
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
        story.addstr(0,0,"This is the story window")
        story.refresh()

        # The debugger window
        debugger = curses.newwin(screen_height,
                                 screen_width-STORY_WINDOW_WIDTH-STORY_RIGHT_MARGIN,
                                 0,
                                 STORY_WINDOW_WIDTH+STORY_RIGHT_MARGIN)
        debugger.addstr(0,0,"^Quit | ^Reset | ^Step | ^Vars | ^PC | ^Header | ^Dictionary | ^Objects",curses.A_REVERSE)
        debugger.refresh()

        while True:
            pass

def load_zmachine(filename):
    zmachine = ZMachine()
    with open(filename,'rb') as f:
        zmachine.raw_data = f.read()
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
