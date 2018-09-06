import pygame
from pygame_terp.window import TextWindow

from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream



BLACK_COLOR = (0,0,0)
WHITE_COLOR = (255,255,255)
BLUE_COLOR = (0,0,100)

class PygameUI(InputStream,OutputStream):
    """ Acts as an interface to our pygame UI. 
    
        Implements both InputStream and OutputStream directly.

        All IO from the interpreter occurs (with the exception of special commands like save/load)
        is mediated by TextWindow objects (which support the ZMachine spec screen model)

        The status window is its own special instance of a window.

        The UI maintains an input window and an output window. 
        
        If the input window is None, the cursor is inactive. If an input window is active, 
        the cursor will be activated in that window.

        Any text printed by the terp goes to the output window (if selected).

        The interpreter itself needs to call tick() on this wrapper object regularly. This runs
        the game loop. It will return True if processing should continue, False if a UI-level
        event cancels    
    """

    def __init__(self,settings):
        """ Initialize the UI. This will open an OS window, create the child text windows,
            and peform general initialization.
        """
        pygame.init()
        self.char_dimensions = settings['char_dimensions']
        self.screen = pygame.display.set_mode(settings['dimensions'])

        # Use built-in mono font
        self.font =  pygame.font.Font("pygame_terp/VeraMono.ttf", 12)

        # Record last char pressed, if any
        self.last_char_pressed = None
        self.status_width = self.char_dimensions[0]

        # For inputstream
        self.waiting_for_line=False
        self.line_done=False

        # For outputstream
        self.buffer = ''

        # All Zmachine output is handled through windows
        self.status_line_window = TextWindow("Status",
                    self.screen,
                    self.font,
                    (0,0),
                    (settings['char_dimensions'][0], 1),
                    WHITE_COLOR,
                    BLACK_COLOR)
        self.main_window = TextWindow("Main",
                    self.screen,
                    self.font,
                    (0,1),
                    settings['char_dimensions'],
                    BLACK_COLOR,
                    WHITE_COLOR)

        # Start with no input window, main window as output window
        self.input_window = None
        self.output_window = self.main_window
        self.entered_text_buffer = ''

    def tick(self):
        """ Run tick of game loop. Return False if game should quit, True if keep running """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if self.input_window:
                    # Window will handle keypress and update the internal buffer
                    # If not return/enter char, returns True. Otherwise False.
                    # On success, store the entered line which will then be returned in 
                    # a subsequent call to readline
                    if not self.input_window.handle_keypress(event.unicode):
                        self.entered_text_buffer = self.input_window.entered_text_buffer
                        self.waiting_for_line=False

        self.screen.fill(WHITE_COLOR)
        pygame.display.flip()

        return True

    def wait_for_line(self):
        """ Enable the cursor and start reading text """
        self.waiting_for_line=True
        self.input_window = self.main_window
        self.input_window.enable_keypress()
        self.entered_text_buffer = ''

    def stop_waiting_for_line(self):
        """ Disable cursor and stop reading text from the keyboard """
        self.waiting_for_line = False
        self.entered_text_buffer = None
        if self.input_window:
            self.input_window.disable_keypress()
            self.input_window = None
            
    
    def print_str(self,txt):
        """ Print the text (as unicode) to the selected output window. If no window selected,
            prints nothing """
        if self.output_window:
            self.output_window.print_text(txt)
            self.refresh()

    def new_line(self):
        """ Print a newline to the current output window. If no window selected, does nothing """
        if self.output_window:
            self.main_window.new_line()
            self.refresh()

    def print_char(self,txt):
        self.print_str(txt)

    def readline(self):
        return_text = None

        if self.entered_text_buffer:
            return_text = self.entered_text_buffer
            self.stop_waiting_for_line()
        else:
            self.wait_for_line()
        
        return return_text
    
    def char_pressed(self,char):
        """ Pass a character (as an int) through to the selected input window. If no input window, do nothing """
        if self.input_window:
            self.main_window.print_text(char)
        
    def refresh(self):
        """ Redraw this screen """
        if self.output_window:
            self.output_window.draw()

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        if score_mode:
            right_string = 'Score: %s Moves: %s' % (score or 0,turns or 0)
        else:
            right_string = '%02d:%02d' % (hours,minutes)

        status_format = '{:%d}{:>%d}' % (self.status_width-len(right_string)-1,len(right_string))
        status_message = status_format.format(room_name,right_string)

        self.status_line_window.draw()
        self.status_line_window.set_text(status_message)