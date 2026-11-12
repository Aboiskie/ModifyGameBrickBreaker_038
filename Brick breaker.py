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
]

# ----------------------------------------------------------------------
# Data karakter (hewan)
# stats = (lebar, kecepatan, nyawa, skor), skala 1-5 (untuk tampilan)
# ----------------------------------------------------------------------
CHARACTERS = [
    {"name": "Kucing", "animal": "cat", "color": ORANGE, "width": 95,
     "speed": 13, "lives": 3, "ball": 1.05, "score": 1.5, "power": 1.0,
     "desc": ["Lincah, paddle kecil,", "skor dikali 1.5"],
     "stats": (2, 4, 3, 5)},
    {"name": "Capybara", "animal": "capy", "color": CYAN, "width": 150,
     "speed": 7, "lives": 4, "ball": 0.9, "score": 1.0, "power": 1.0,
     "desc": ["Paddle lebar, 4 nyawa,", "bola lebih lambat"],
     "stats": (5, 2, 4, 3)},
    {"name": "Landak", "animal": "hedgehog", "color": GREEN, "width": 115,
     "speed": 10, "lives": 3, "ball": 1.0, "score": 1.0, "power": 1.5,
     "desc": ["Seimbang, durasi", "power-up 1.5x lebih lama"],
     "stats": (3, 3, 3, 3)},
]
STAT_LABELS = ("Lebar", "Gerak", "Nyawa", "Skor")


# ----------------------------------------------------------------------
# Sound effect (dibuat lewat kode, tanpa file audio)
# ----------------------------------------------------------------------
class Sfx:
    def __init__(self):
        self.enabled = True
        self.sounds = {}
        info = pygame.mixer.get_init()
        self.ok = bool(info) and info[1] == -16
        if self.ok:
            self.rate, _, self.channels = info
            pygame.mixer.set_num_channels(16)
            self.build()

    @staticmethod
    def P(freq, dur, wave="square", slide=0.0):
        return (freq, dur, wave, slide)

    def synth(self, freq, dur, vol, wave, slide):
        n = int(self.rate * dur)
        buf = array.array("h")
        phase = 0.0
        for i in range(n):
            t = i / n
            phase += (freq + slide * t) / self.rate
            if wave == "noise":
                s = random.uniform(-1, 1)
            elif freq <= 0:
                s = 0.0                      # jeda
            elif wave == "square":
                s = 1.0 if (phase % 1) < 0.5 else -1.0
            elif wave == "saw":
                s = 2 * (phase % 1) - 1
            else:
                s = math.sin(math.tau * phase)
            env = 1 - t                      # volume mengecil
            if i < 150:
                env *= i / 150               # attack singkat anti-klik
            buf.append(int(s * env * vol * 32767))
        return buf

    def make(self, parts, vol=0.3):
        buf = array.array("h")
        for freq, dur, wave, slide in parts:
            buf.extend(self.synth(freq, dur, vol, wave, slide))
        if self.channels == 2:
            stereo = array.array("h")
            for s in buf:
                stereo.append(s)
                stereo.append(s)
            buf = stereo
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def build(self):
        P = self.P
        defs = {
            "launch":  ([P(380, .12, "sine", 500)], .35),
            "paddle":  ([P(240, .06, "square", -40)], .30),
            "wall":    ([P(170, .04, "sine")], .30),
            "hard":    ([P(330, .07, "square")], .28),
            "brick":   ([P(600, .05), P(880, .07)], .25),
            "bomb":    ([P(0, .25, "noise"), P(120, .2, "saw", -60)], .35),
            "laser":   ([P(900, .06, "square", -500)], .15),
            "powerup": ([P(523, .07, "sine"), P(659, .07, "sine"),
                         P(784, .12, "sine")], .35),
            "lose":    ([P(320, .35, "saw", -220)], .30),
            "hurt":    ([P(0, .12, "noise"), P(180, .2, "saw", -100)], .30),
            "win":     ([P(523, .1), P(659, .1), P(784, .1),
                         P(1046, .28)], .25),
            "gameover": ([P(400, .2, "saw"), P(300, .2, "saw"),
                          P(200, .55, "saw", -80)], .28),
            "warn":    ([P(660, .18), P(0, .06), P(660, .18), P(0, .06),
                         P(660, .35)], .25),
            "boss_shoot": ([P(700, .15, "saw", -420)], .20),
            "boss_hit": ([P(0, .07, "noise"), P(150, .1, "saw")], .35),
            "boss_die": ([P(0, .9, "noise"), P(200, .5, "saw", -150)], .40),
            "select":  ([P(700, .05, "sine")], .30),
            "confirm": ([P(600, .06, "sine"), P(900, .12, "sine")], .35),
        }
        for name, (parts, vol) in defs.items():
            self.sounds[name] = self.make(parts, vol)

    def play(self, name):
        if self.ok and self.enabled and name in self.sounds:
            self.sounds[name].play()

    def toggle(self):
        self.enabled = not self.enabled
        if self.ok and not self.enabled:
            pygame.mixer.stop()


sfx = Sfx()


