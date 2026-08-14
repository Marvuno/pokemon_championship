import pygame as pg


class Button:
    def __init__(self, text, width, height, pos, elevation):
        self.pressed = False
        self.elevation = elevation
        self.dynamic_elevation = elevation
        self.original_y_pos = pos[1]
        self.font = pg.font.SysFont('Trebuchet MS', 24, bold=True)

        # top rectangle
        self.top_rect = pg.Rect(pos, (width, height))
        self.top_color = '#475F77'

        # bottom rectangle
        self.bottom_rect = pg.Rect(pos, (width, height))
        self.bottom_color = '#354B5E'
        # text
        self.text_surf = self.font.render(text, True, '#FFFFFF')
        self.text_rect = self.text_surf.get_rect(center=self.top_rect.center)

    def draw(self):
        # elevation logic
        self.top_rect.y = self.original_y_pos - self.dynamic_elevation
        self.text_rect.center = self.top_rect.center

        self.bottom_rect.midtop = self.top_rect.midtop
        self.bottom_rect.height = self.top_rect.height + self.dynamic_elevation

        pg.draw.rect(screen, self.bottom_color, self.bottom_rect, border_radius=12)
        pg.draw.rect(screen, self.top_color, self.top_rect, border_radius=12)
        screen.blit(self.text_surf, self.text_rect)
        self.check_click()

    def check_click(self):
        mouse_pos = pg.mouse.get_pos()
        if self.top_rect.collidepoint(mouse_pos):
            self.top_color = '#D74B4B'
            if pg.mouse.get_pressed()[0]:
                self.dynamic_elevation = 0
                self.pressed = True
            else:
                self.dynamic_elevation = self.elevation
                if self.pressed:
                    print('click')
                    self.pressed = False
        else:
            self.dynamic_elevation = self.elevation
            self.top_color = '#475F77'


# init
pg.init()
pg.font.init()



screen = pg.display.set_mode((1536, 864))
pg.display.set_caption("Pokemon Championship")
pg.display.set_icon(pg.image.load('../../Assets/image/icon.png'))

# background
background = pg.image.load('../../Assets/image/menu.png')
screen.blit(background, (0, 0))

new_game_button = Button('New Game', 200, 40, (200, 250), 5)

# game loop
while True:
    events = pg.event.get()
    for event in events:
        if event.type == pg.QUIT:
            pg.quit()

    new_game_button.draw()

    pg.display.update()