import pygame

class TextWindow(object):
    def __init__(self,name, screen, font, 
                    position, size,
                     foreground_color, background_color,
                     margin_top=5,margin_left=5,
                     debug=True):
        """ Width/height is in characters """
        self.screen = screen
        self.name = name
        self.position = position
        self.size = size
        self.font = font
        self.foreground_color = foreground_color
        self.background_color = background_color
        self.margin_top = margin_top
        self.margin_left = margin_left
        self.window_text = ''

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
        self.window_text = text

    def draw(self):
        pygame.draw.rect(self.screen, self.background_color, self.bounds)
        text = self.font.render(self.window_text, True, self.foreground_color)
        self.screen.blit(text,(self.margin_left+(self.text_width*self.position[0]),
                               self.margin_top+(self.text_height*self.position[1])))
