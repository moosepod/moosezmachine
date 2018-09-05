import pygame
import textwrap

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

        self.lines = ['' * self.size[1]]
        self.buffer = ''

        self.cursor_row = 0
        self.cursor_col = 0

        # Assume a monospace font and use 0 as the placeholder
        self.text_width,self.text_height = self.font.size("0" * self.size[1])
        self.text_width /= self.size[1] # Average size

        self.bounds = pygame.Rect(margin_left + (self.text_width*self.position[0]),
                                  margin_top + (self.text_height*self.position[1]),
                                  (self.text_width*self.size[0]),
                                  (self.text_height*self.size[1]))

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

    def _add_row(self):
        self.cursor_row += 1
        if self.cursor_row >= len(self.lines):
            self.lines.append('')

    def flush(self):
        """ Flush the text buffer and display it as a series of lines, wrapping where necessary """
        lines = []

        width = self.size[0]

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

    def _get_x_y_from_pos(self, col,row):
        """ Given a column and row, return the x/y location """ 
        return (self.margin_left+(self.text_width*col),
                self.margin_top+(self.text_height*row))

    def draw(self,show_cursor=False):
        pygame.draw.rect(self.screen, self.background_color, self.bounds)
        for idx,line in enumerate(self.lines):
            text = self.font.render(line, True, self.foreground_color)
            x,y = self._get_x_y_from_pos(self.position[0], self.position[1]+idx)
            self.screen.blit(text,(x,y))
        
        if show_cursor:
            x,y = self._get_x_y_from_pos(len(self.lines[-1])+1, len(self.lines))
            cursor_rect = pygame.Rect(x,y,
                                     self.text_width,self.text_height)
            pygame.draw.rect(self.screen, self.foreground_color, cursor_rect)
        
