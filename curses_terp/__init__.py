from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream

import curses
import curses.ascii
import textwrap

BACKSPACE_CHAR = '\x7f'

class CursesInputStream(object):
    """ Input stream for reading commands within a curses window """
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

    def reset(self):
        self.waiting_for_line = False
        self.line_done = False
        self.text = ''
        curses.curs_set(0) # Set cursor to hidden
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
            self.reset()
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

    def flush(self):
        lines = []

        for block in self.buffer.split('\n'):
            # If the line fits, just add it as is. Otherwise use the textwrap
            # tool to wrap. We don't use textwrap on every line because it will strip trailing spaces
            if len(block) < self.width:
                lines.append(block)
            else:
                for line in textwrap.wrap(block,self.width-1): # Formatting works better with a 1-character buffer on right
                    lines.append(line)

        first_line=True
        for line in lines:
            if not first_line:
                self.window.addstr('\n')
            self.window.addstr(line.encode('ascii','replace')) # Strip out unicode that won't behave properly in curses
            first_line=False

        if self.buffer.endswith('\n') and first_line:
            self.window.addstr('\n')

        self.buffer=''

    def new_line(self):
        self.buffer += '\n'
        
    def print_str(self,txt):
        self.buffer += txt

    def print_char(self,txt):
        self.buffer += txt

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        if score_mode:
            right_string = 'Score: %s Moves: %s' % (score or 0,turns or 0)
        else:
            right_string = '%02d:%02d' % (hours,minutes)

        status_format = '{:%d}{:>%d}' % (self.status_width-len(right_string)-1,len(right_string))
        status_msg = status_format.format(room_name,right_string)

        self.status_window.addstr(0,0,status_msg,curses.A_REVERSE)
        self.status_window.refresh()
        self.flush()

