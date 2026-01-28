import sys

import pygame


def main():
    pygame.init()

    screen = pygame.display.set_mode((640, 480))
    pygame.display.set_caption("Distributed SMB - Setup Test")

    clock = pygame.time.Clock()

    print("Setup completed with success.")
    print("Use the window 'X' to close the test.")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        screen.fill((40, 44, 52))

        pygame.display.flip()

        clock.tick(60)


if __name__ == "__main__":
    main()
