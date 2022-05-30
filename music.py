import os

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

pygame.init()
pygame.mixer.init()
pygame.mixer.music.set_volume(0.5)


def music(*, audio, loop):
    pygame.mixer.music.load(audio)
    pygame.mixer.music.play(-1) if loop else pygame.mixer.music.play()


def sound(*, audio):
    pygame.mixer.Sound.play(pygame.mixer.Sound(audio))