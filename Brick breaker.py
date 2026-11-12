import array
import math
import os
import random

import pygame

# Mixer harus di-set sebelum pygame.init() agar format suara konsisten
pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()

# ----------------------------------------------------------------------
# Pengaturan dasar
# ----------------------------------------------------------------------
WIDTH, HEIGHT = 800, 600
FPS = 60
HUD_H = 46        # tinggi bar atas (juga dinding atas area main)
BOSS_EVERY = 3    # boss muncul setiap kelipatan level ini (3, 6, 9, ...)

# Kenaikan kecepatan seiring waktu bermain (bola terbang):
TEMPO_MAX_BONUS = 0.8     # kecepatan maksimal = x1.8
TEMPO_FULL_SECONDS = 150  # detik yang dibutuhkan untuk mencapai maksimal
MAX_BALL_SPEED = 15.0

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Block Breaker - Animal Edition")
clock = pygame.time.Clock()

HIGHSCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "highscore.txt")


def make_font(size, bold=False):
    return pygame.font.SysFont("segoeui,arial,helvetica", size, bold=bold)


FONT_S = make_font(16)
FONT_M = make_font(22, True)
FONT_L = make_font(34, True)
FONT_XL = make_font(64, True)

# Warna
WHITE = (240, 244, 255)
CYAN = (80, 210, 255)
PINK = (255, 90, 150)
YELLOW = (255, 214, 90)
GREEN = (110, 235, 150)
ORANGE = (255, 170, 90)
FIRE = (255, 120, 60)
PURPLE = (170, 140, 255)
ROW_COLORS = [
    (255, 90, 110), (255, 150, 80), (255, 214, 90), (110, 235, 150),
    (80, 210, 255), (160, 130, 255), (255, 120, 210), (120, 160, 255),
]

# Tema latar (berganti tiap level supaya tidak monoton)
THEMES = [
    ((12, 14, 36), (38, 16, 62)),
    ((8, 30, 40), (12, 64, 74)),
    ((40, 14, 30), (84, 30, 62)),
    ((16, 36, 24), (30, 74, 52)),
]
BOSS_THEME = ((40, 8, 12), (96, 14, 30))

# Pola susunan balok (r = baris, c = kolom, R = jumlah baris, C = jumlah kolom)
PATTERNS = [
    lambda r, c, R, C: True,                                   # penuh
    lambda r, c, R, C: (r + c) % 2 == 0,                       # papan catur
    lambda r, c, R, C: abs(c - (C - 1) / 2) <= (r + 1) * 0.9,  # piramida
    lambda r, c, R, C: r % 2 == 0,                             # garis
    lambda r, c, R, C: (abs(r - (R - 1) / 2) / max(1, (R - 1) / 2)
                        + abs(c - (C - 1) / 2) / ((C - 1) / 2)) <= 1.05,  # berlian
    lambda r, c, R, C: r in (0, R - 1) or c in (0, C - 1) or (r + c) % 3 == 0,  # bingkai