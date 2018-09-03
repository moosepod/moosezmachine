import pygame

from pygame_terp.window import TextWindow

SETTINGS = {'dimensions': (640,480),
            'char_dimensions': (60,14),
            'font_name': 'courier',
            'font_size': 12}

BLACK_COLOR = (0,0,0)
WHITE_COLOR = (255,255,255)
BLUE_COLOR = (0,0,100)

def initialize(settings):
    """ Initialize and open the window """
    pygame.init()
    screen = pygame.display.set_mode(settings['dimensions'])
    font = pygame.font.SysFont("courier", 12)
    return screen, font

def loop(screen,font,settings):
    """ Main game loop """
    done = False
    text = font.render("Hello, World", True, (0, 128, 0))

    status_line_window = TextWindow("Status",
               screen,
                font,
                (0,0),
                (settings['char_dimensions'][0], 1),
                WHITE_COLOR,
                BLACK_COLOR)
    main_window = TextWindow("Main",
                screen,
                font,
                (0,1),
                settings['char_dimensions'],
                BLACK_COLOR,
                BLUE_COLOR)

    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                done = True

        screen.fill(WHITE_COLOR)
        status_line_window.draw()
        main_window.draw()
        pygame.display.flip()

if __name__ == "__main__":
    screen, font = initialize(SETTINGS)
    loop(screen,font,SETTINGS)