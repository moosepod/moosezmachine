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
            self.window.addstr('\n')
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
            self.waiting_for_line = False
            self.line_done = False
            self.text = ''
            curses.curs_set(0) # Set cursor to hidden
            self.window.refresh()
            return text

        return None

class FileStreamEmptyException(Exception):
    """ Thrown when a file input stream runs out of commands """
    pass

class FileInputStream(object):
    """ Input stream for handling commands stored in a file """
    def __init__(self,output_stream=None):
        self.commands = []
        self.index = 0
        self.output_stream=output_stream
        self.waiting_for_line = False

    def load_from_path(self,path):
        with open(path,'r') as f:
            for line in f:
                self.commands.append(line.strip())

    def readline(self):
        self.index += 1
        try:
            command = self.commands[self.index] 
            if self.output_stream:
                self.output_stream.print_str(command)
                self.output_stream.new_line()
        except IndexError:
            raise FileStreamEmptyException()

        return command

    def char_pressed(self,char):
        pass

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
            for line in textwrap.wrap(block,self.width):
                lines.append(line)
        first_line=True
        for line in lines:
            if not first_line:
                self.window.addstr('\n')
            self.window.addstr(line.encode('ascii','replace')) # Strip out unicode that won't behave properly in curses
            first_line=False

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

class STDOUTOutputStream(OutputStream):
    def __init__(self,window,status_window):
        super(STDOUTOutputStream,self).__init__()
        self.buffer = ''
        self.status_height,self.status_width=0,0        

    def refresh(self):
        pass

    def new_line(self):
        print('')
        
    def print_str(self,txt):
        print(txt,end='')

    def print_char(self,txt):
        print(txt,end='')

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        pass


class FileOutputStream(OutputStream):
    def __init__(self,path):
        super(FileOutputStream,self).__init__()
        self.buffer = ''
        self.path = path


    def flush(self):
        with open(self.path,'a') as f:
            f.write(str(self.buffer.encode('ascii','replace'),'ascii'))
        self.buffer = ''

    def new_line(self):
        self.buffer += '\n'
        
    def print_str(self,txt):
        self.buffer += str(txt)

    def print_char(self,txt):
        self.buffer += str(txt)

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        pass

class StringIOOutputStream(OutputStream):
    def __init__(self,io_stream):
        self.io_stream = io_stream
        super(StringIOOutputStream,self).__init__()

    def refresh(self):
        pass

    def new_line(self):
        self.io_stream.write('\n')
    
    def print_str(self,txt):
        self.io_stream.write(txt)

    def print_char(self,ch):
        self.io_stream.write(ch)

    def show_status(self,room_name,score_mode=True,hours=0,minutes=0,score=0,turns=0):
        pass