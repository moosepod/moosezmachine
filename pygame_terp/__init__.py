import pygame
from pygame_terp.window import TextWindow

from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream



BLACK_COLOR = (0,0,0)
WHITE_COLOR = (255,255,255)
BLUE_COLOR = (0,0,100)

class PygameWrapper(object):
    def __init__(self,settings):
        """ Initialize and open the window """
        pygame.init()
        self.char_dimensions = settings['char_dimensions']
        self.screen = pygame.display.set_mode(settings['dimensions'])
        self.font = pygame.font.SysFont("courier", 14)
        
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
    
    def tick(self):
        """ Run tick of game loop. Return False if game should quit, True if keep running """
        text = self.font.render("Hello, World", True, (0, 128, 0))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False

        self.screen.fill(WHITE_COLOR)
        self.status_line_window.draw()
        self.main_window.draw()
        pygame.display.flip()

        return True

class PygameInputStream(InputStream):
    def __init__(self):
        self.waiting_for_line=False

class PygameOutputStream(OutputStream):
    def __init__(self,pygame_wrapper):
        super(PygameOutputStream,self).__init__()
        self.pygame_wrapper = pygame_wrapper
        self.buffer = ''
        self.status_width = pygame_wrapper.char_dimensions[0]
        
    def refresh(self):
        """ Redraw this screen """
        pass

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
        status_message = status_format.format(room_name,right_string)

        self.pygame_wrapper.status_line_window.set_text(status_message)