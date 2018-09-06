import pygame
import textwrap

COLS=0
ROWS=1

BACKSPACE_KEY = 8
RETURN_KEY = 13

class TextWindow(object):
    def __init__(self,name, screen, font, 
                    position, size,
                     foreground_color, background_color,
                     margin_top=5,margin_left=5,
                     debug=False):
        """ Width/height is in characters.
        
            We maintain a line buffer of all text for scrolling. This should be capped at some point """
        self.screen = screen
        self.name = name
        self.position = position
        self.size = size
        self.font = font
        self.foreground_color = foreground_color
        self.background_color = background_color
        self.margin_top = margin_top
        self.margin_left = margin_left

        self.lines = ['' * self.size[COLS]]
        self.buffer = ''

        self.scroll_window_top = 0
        self.scroll_window_bottom = len(self.lines)
        self.scroll_window_lines = []

        self.cursor_row = 0
        self.cursor_col = 0

        # used for text entry
        self.cursor_visible = False
        self.cursor_absolute_position = 0
        self.cursor_min_length = 0 # When text reading starts, represents place we can't backspace past
        self.entered_text_buffer = ''

        # Assume a monospace font and use 0 as the placeholder
        self.text_width,self.text_height = self.font.size("0" * self.size[COLS])
        self.text_width /= self.size[COLS] # Average size

        self.bounds = pygame.Rect(margin_left + (self.text_width*self.position[0]),
                                  margin_top + (self.text_height*self.position[1]),
                                  (self.text_width*self.size[COLS]),
                                  (self.text_height*self.size[ROWS]))

        if debug:
            print("""Initializing window %s
Position:    %s
Size:        %s
Foreground:  %s
Background:  %s
Top Margin:  %s
Left margin: %s
Text width:  %s
Text height: %s
Bounds:      %s
""" % (name, position, size, 
       foreground_color, background_color, margin_top, margin_left, 
       self.text_width, self.text_height,self.bounds))

    def set_text(self, text):
        self.lines[0] = text
        self.cursor_col = len(text)
        self.cursor_row = 0

    def print_text(self,txt):
        self.buffer += txt
        self.flush()

    def new_line(self):
        self.buffer += '\n'
        self.flush()

    def enable_keypress(self):
        """ Start this window accepting user input """
        # Add a space after the prompt -- we'll start collecting text after this point
        self.lines[-1] += ' '
        # Setup cursor
        self.cursor_visible = True
        self.cursor_min_length = sum([len(l) for l in self.lines])
        self.cursor_absolute_position = self.cursor_min_length
        self.entered_text_buffer = ''

        

    def disable_keypress(self):
        """ Stop window from handling user input """
        self.cursor_visible = True

    def handle_keypress(self,key):
        """ Handle a key typed to this window. Return True if we should keep processing, False if a line has been completed. """
        if len(key) == 0:
            return True
        
        # Whenever we start typing scroll to the bottom
        self.scroll_bottom() 

        if self.cursor_visible:
            if ord(key) == BACKSPACE_KEY: # If backspace and we aren't at start point of buffer, remove one char
                if self.cursor_absolute_position > self.cursor_min_length:
                    self.lines[-1] = self.lines[-1][0:-1]
                    self.entered_text_buffer = self.entered_text_buffer[0:-1]
                    self.cursor_absolute_position-=1
            elif ord(key) == RETURN_KEY:
                # Hit return, count it as an entered command and return
                return False 
            else:
                self.print_text(key)
                self.cursor_absolute_position+=1
                self.entered_text_buffer += key

            return True

    def _add_row(self):
        self.cursor_row += 1
        if self.cursor_row >= len(self.lines):
            self.lines.append('')
            self.scroll_window_bottom+=1
            self.scroll_window_top = max(0,self.scroll_window_bottom-self.size[ROWS])

    def scroll_up(self):
        if self.scroll_window_top > 0:
            self.scroll_window_top -= 1
            self.scroll_window_bottom -= 1
            self.draw()
    
    def scroll_down(self):
        if self.scroll_window_bottom < len(self.lines):
            self.scroll_window_top += 1
            self.scroll_window_bottom += 1
            self.draw()

    def scroll_top(self):
        self.scroll_window_top=0
        self.scroll_window_bottom=self.scroll_window_top+self.size[ROWS]
        self.draw()

    def scroll_bottom(self):
        self.scroll_window_bottom=len(self.lines)
        self.scroll_window_top=self.scroll_window_bottom-self.size[ROWS]
        self.draw()

    def flush(self):
        """ Flush the text buffer and display it as a series of lines, wrapping where necessary """
        lines = []

        width = self.size[COLS]

        for block in self.buffer.split('\n'):
            # If the line fits, just add it as is. Otherwise use the textwrap
            # tool to wrap. We don't use textwrap on every line because it will strip trailing spaces
            if len(block) < width:
                lines.append(block)
            else:
                for line in textwrap.wrap(block,width-1): # Formatting works better with a 1-character buffer on right
                    lines.append(line)

        first_line=True
        for line in lines:
            if not first_line:
                self._add_row()
            first_line=False
            self.lines[self.cursor_row] += line

        if self.buffer.endswith('\n') and first_line:
            self.add_row()
        self.buffer=''
        self.draw()

    def _get_x_y_from_pos(self, col,row):
        """ Given a column and row, return the x/y location """ 
        return (self.margin_left+(self.text_width*col),
                self.margin_top+(self.text_height*row))

    def draw(self):
        """ Call to draw this text window to the ui window """
        pygame.draw.rect(self.screen, self.background_color, self.bounds)
        line_window = self.lines[self.scroll_window_top:self.scroll_window_bottom]
        for idx,line in enumerate(line_window):
            text = self.font.render(line, True, self.foreground_color)
            x,y = self._get_x_y_from_pos(self.position[0], self.position[1]+idx)
            self.screen.blit(text,(x,y))
        
        if self.cursor_visible and self.scroll_window_bottom == len(self.lines):
            x,y = self._get_x_y_from_pos(len(line_window[-1]), len(line_window))
            cursor_rect = pygame.Rect(x,y,
                                     self.text_width,self.text_height)
            pygame.draw.rect(self.screen, self.foreground_color, cursor_rect)
        
