import curses
import curses.wrapper

# Window constants
STORY_TOP_MARGIN = 1
STORY_BOTTOM_MARGIN = 1 
STATUS_BAR_HEIGHT = 1
STORY_WINDOW_WIDTH = 80 
STORY_RIGHT_MARGIN = 1
 
def main():
    curses.wrapper(loop)

def loop(x):
    # Disable automatic echo
    curses.noecho()
    
    # Use unbufferd input
    curses.cbreak()

    # THe main screen
    screen = curses.initscr()
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

if __name__ == "__main__":
    main()
