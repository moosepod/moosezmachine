import pygame

SETTINGS = {'dimensions': (640,480),
            'font_name': 'courier',
            'font_size': 12}


def initialize(settings):
    """ Initialize and open the window """
    pygame.init()
    screen = pygame.display.set_mode(settings['dimensions'])
    font = pygame.font.SysFont("courier", 12)
    return screen, font

def loop(screen,font):
    """ Main game loop """
    done = False
    text = font.render("Hello, World", True, (0, 128, 0))

    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                done = True
    
        screen.fill((255, 255, 255))
        screen.blit(text,(20,20))
        pygame.display.flip()

if __name__ == "__main__":
    screen, font = initialize(SETTINGS)
    loop(screen,font)