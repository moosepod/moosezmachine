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

    def tick(self,waiting_for_text=False):
        """ Run tick of game loop. Return False if game should quit, True if keep running """
        self.last_char_pressed = None # Reset key each time
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                self.last_char_pressed = ord(event.unicode) 

        self.screen.fill(WHITE_COLOR)
        self.status_line_window.draw()
        self.main_window.draw(waiting_for_text)
        pygame.display.flip()

        return True
    
    def print(self,txt):
        self.main_window.print_text(txt)

    def print_new_line(self):
        self.main_window.new_line()

    def readline(self):
        self.waiting_for_line=True
    
    def char_pressed(self,char):
        self.main_window.print_text(char)
        
    def refresh(self):
        """ Redraw this screen """
        pass

    def new_line(self):
        #self.buffer += '\n'
        self.print_new_line()
        
    def print_str(self,txt):
        #self.buffer += txt
        self.print(txt)

    def print_char(self,txt):
        #self.buffer += txt
        self.print(txt)

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        if score_mode:
            right_string = 'Score: %s Moves: %s' % (score or 0,turns or 0)
        else:
            right_string = '%02d:%02d' % (hours,minutes)

        status_format = '{:%d}{:>%d}' % (self.status_width-len(right_string)-1,len(right_string))
        status_message = status_format.format(room_name,right_string)

        self.status_line_window.set_text(status_message)