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


# ----------------------------------------------------------------------
# Fungsi bantu
# ----------------------------------------------------------------------
def load_highscore():
    try:
        with open(HIGHSCORE_FILE, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def save_highscore(value):
    try:
        with open(HIGHSCORE_FILE, "w") as f:
            f.write(str(value))
    except OSError:
        pass


def make_background(top, bottom):
    bg = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        pygame.draw.line(bg, color, (0, y), (WIDTH, y))
    return bg


def make_glow(radius, color):
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        alpha = int(110 * (1 - r / radius) ** 2)
        pygame.draw.circle(surf, (*color, alpha), (radius, radius), r)
    return surf


BULLET_GLOW = make_glow(18, (255, 100, 60))


def lighten(color, amount=40):
    return tuple(min(255, c + amount) for c in color)


def darken(color, amount=40):
    return tuple(max(0, c - amount) for c in color)


def draw_text(surf, text, font, color, center, shadow=True):
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        surf.blit(sh, sh.get_rect(center=(center[0] + 2, center[1] + 2)))
    img = font.render(text, True, color)
    surf.blit(img, img.get_rect(center=center))


def draw_heart(surf, cx, cy, size, color):
    pts = []
    for deg in range(0, 360, 10):
        t = math.radians(deg)
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t)
              - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * size / 32, cy + y * size / 32))
    pygame.draw.polygon(surf, color, pts)


def R(x, y, w, h):
    return pygame.Rect(int(x), int(y), max(1, int(w)), max(1, int(h)))


def circ(surf, color, x, y, rad):
    pygame.draw.circle(surf, color, (int(x), int(y)), max(1, int(rad)))


def draw_animal(surf, kind, cx, cy, r):
    """Gambar wajah hewan dari bentuk dasar. r = jari-jari kepala."""
    lw = max(1, int(r * 0.07))
    if kind == "cat":
        fur, dark, pink = (255, 170, 90), (190, 100, 40), (255, 150, 170)
        for s in (-1, 1):
            pygame.draw.polygon(surf, fur, [(cx + s * r * 0.95, cy - r * 0.2),
                                            (cx + s * r * 0.85, cy - r * 1.35),
                                            (cx + s * r * 0.2, cy - r * 0.75)])
            pygame.draw.polygon(surf, pink, [(cx + s * r * 0.8, cy - r * 0.35),
                                             (cx + s * r * 0.75, cy - r * 1.0),
                                             (cx + s * r * 0.4, cy - r * 0.7)])
        pygame.draw.ellipse(surf, fur, R(cx - r, cy - r * 0.85, 2 * r, 1.7 * r))
        for dx in (-0.3, 0, 0.3):
            pygame.draw.line(surf, dark, (cx + dx * r, cy - r * 0.8),
                             (cx + dx * r, cy - r * 0.45), lw)
        for s in (-1, 1):
            circ(surf, (30, 20, 20), cx + s * r * 0.42, cy - r * 0.05, r * 0.17)
            circ(surf, WHITE, cx + s * r * 0.46, cy - r * 0.1, r * 0.06)
            for ey in (0.18, 0.4):
                pygame.draw.line(surf, (255, 245, 235),
                                 (cx + s * r * 0.55, cy + r * 0.28),
                                 (cx + s * r * 1.3, cy + r * ey), 1)
        pygame.draw.polygon(surf, pink, [(cx - r * 0.12, cy + r * 0.2),
                                         (cx + r * 0.12, cy + r * 0.2),
                                         (cx, cy + r * 0.34)])
        pygame.draw.line(surf, dark, (cx, cy + r * 0.34),
                         (cx - r * 0.18, cy + r * 0.5), lw)
        pygame.draw.line(surf, dark, (cx, cy + r * 0.34),
                         (cx + r * 0.18, cy + r * 0.5), lw)

    elif kind == "capy":
        brown, light, dark = (165, 115, 75), (198, 150, 108), (70, 45, 30)
        for s in (-1, 1):
            circ(surf, (130, 88, 58), cx + s * r * 0.75, cy - r * 0.72, r * 0.26)
        pygame.draw.ellipse(surf, brown, R(cx - r * 1.05, cy - r * 0.8,
                                           2.1 * r, 1.65 * r))
        pygame.draw.ellipse(surf, light, R(cx - r * 0.6, cy - r * 0.05,
                                           1.2 * r, 0.8 * r))
        for s in (-1, 1):
            circ(surf, dark, cx + s * r * 0.55, cy - r * 0.3, r * 0.1)
            circ(surf, dark, cx + s * r * 0.22, cy + r * 0.28, r * 0.08)
        # jeruk di kepala (ciri khas capybara)
        circ(surf, (255, 150, 40), cx + r * 0.1, cy - r * 0.95, r * 0.3)
        pygame.draw.line(surf, (80, 190, 90), (cx + r * 0.1, cy - r * 1.22),
                         (cx + r * 0.25, cy - r * 1.35), lw)

    elif kind == "hedgehog":
        spike, body = (85, 60, 48), (140, 100, 72)
        beige = (245, 215, 175)
        for a in range(170, 371, 14):
            rad, half = math.radians(a), math.radians(9)
            pygame.draw.polygon(surf, spike, [
                (cx + math.cos(rad - half) * r * 0.95,
                 cy + math.sin(rad - half) * r * 0.95),
                (cx + math.cos(rad) * r * 1.5, cy + math.sin(rad) * r * 1.5),
                (cx + math.cos(rad + half) * r * 0.95,
                 cy + math.sin(rad + half) * r * 0.95)])
        circ(surf, body, cx, cy, r)
        for s in (-1, 1):
            circ(surf, (110, 78, 56), cx + s * r * 0.8, cy - r * 0.4, r * 0.22)
        pygame.draw.ellipse(surf, beige, R(cx - r * 0.78, cy - r * 0.2,
                                           1.56 * r, 1.05 * r))
        for s in (-1, 1):
            circ(surf, (30, 20, 20), cx + s * r * 0.35, cy + r * 0.08, r * 0.1)
        circ(surf, (20, 15, 15), cx, cy + r * 0.42, r * 0.14)


def draw_paddle_shape(surf, rect, color):
    """Dipakai oleh paddle di game dan pratinjau di menu karakter."""
    pygame.draw.rect(surf, darken(color, 40), rect, border_radius=10)
    top = pygame.Rect(rect.x + 3, rect.y + 2, rect.w - 6, rect.h // 2 - 1)
    pygame.draw.rect(surf, lighten(color, 50), top, border_radius=7)


# ----------------------------------------------------------------------
# Objek game
# ----------------------------------------------------------------------
class Paddle:
    def __init__(self, char):
        self.kind = char["animal"]
        self.base_w = float(char["width"])
        self.w = self.base_w
        self.target_w = self.base_w
        self.speed = char["speed"]
        self.color = char["color"]
        self.h = 20
        self.x = WIDTH / 2 - self.w / 2
        self.y = HEIGHT - 50
        self.wide_timer = 0
        self.laser_timer = 0

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), int(self.w), self.h)

    def set_center(self, cx):
        self.x = cx - self.w / 2
        self.clamp()

    def move(self, direction, tempo=1.0):
        self.x += direction * self.speed * (1 + (tempo - 1) * 0.6)
        self.clamp()

    def clamp(self):
        self.x = max(0, min(WIDTH - self.w, self.x))

    def update(self):
        center = self.x + self.w / 2
        self.w += (self.target_w - self.w) * 0.15
        self.x = center - self.w / 2
        self.clamp()
        if self.wide_timer > 0:
            self.wide_timer -= 1
            if self.wide_timer == 0:
                self.target_w = self.base_w
        if self.laser_timer > 0:
            self.laser_timer -= 1

    def draw(self, surf):
        r = self.rect
        glow_col = PURPLE if self.laser_timer > 0 else self.color
        glow = pygame.Surface((r.w + 40, r.h + 40), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*glow_col, 55), glow.get_rect(),
                         border_radius=22)
        surf.blit(glow, (r.x - 20, r.y - 20))
        draw_paddle_shape(surf, r, self.color)
        # Wajah hewan di tengah paddle
        draw_animal(surf, self.kind, r.centerx, r.centery - 1, 10)
        if self.laser_timer > 0:  # moncong laser di kedua ujung
            for x in (r.x + 8, r.right - 8):
                pygame.draw.rect(surf, PURPLE, (x - 2, r.y - 5, 4, 6))


class Ball:
    def __init__(self):
        self.r = 8
        self.x = WIDTH / 2
        self.y = HEIGHT / 2
        self.vx = 0.0
        self.vy = 0.0
        self.base_speed = 6.0
        self.stuck = True
        self.slow_timer = 0
        self.fire_timer = 0
        self.trail = []
        self.glow = make_glow(26, WHITE)
        self.glow_fire = make_glow(30, FIRE)

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.r), int(self.y - self.r),
                           self.r * 2, self.r * 2)

    def stick_to(self, paddle):
        self.stuck = True
        self.vx = self.vy = 0.0
        self.x = paddle.x + paddle.w / 2
        self.y = paddle.y - self.r - 1
        self.trail.clear()

    def launch(self):
        angle = math.radians(random.uniform(-25, 25))
        self.vx = self.base_speed * math.sin(angle)
        self.vy = -self.base_speed * math.cos(angle)
        self.stuck = False

    def normalize(self, tempo):
        """Jaga kecepatan sesuai tempo & hindari pantulan terlalu horizontal."""
        target = min(MAX_BALL_SPEED, self.base_speed * tempo)
        if self.slow_timer > 0:
            target *= 0.7
        min_vy = target * 0.25
        if abs(self.vy) < min_vy:
            self.vy = min_vy if self.vy >= 0 else -min_vy
        mag = math.hypot(self.vx, self.vy) or 1.0
        self.vx *= target / mag
        self.vy *= target / mag

    def draw(self, surf):
        fire = self.fire_timer > 0
        base_col = FIRE if fire else CYAN
        for i, (tx, ty) in enumerate(self.trail):
            frac = (i + 1) / max(1, len(self.trail))
            rad = max(1, int(self.r * frac * 0.8))
            col = tuple(int(c * (0.25 + 0.5 * frac)) for c in base_col)
            pygame.draw.circle(surf, col, (int(tx), int(ty)), rad)
        if fire:
            surf.blit(self.glow_fire, (self.x - 30, self.y - 30))
        else:
            surf.blit(self.glow, (self.x - 26, self.y - 26))
        pygame.draw.circle(surf, (255, 210, 120) if fire else WHITE,
                           (int(self.x), int(self.y)), self.r)
        pygame.draw.circle(surf, (255, 255, 255),
                           (int(self.x - 2), int(self.y - 2)), 3)


class Brick:
    def __init__(self, x, y, w, h, color, hp, kind="normal"):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = color
        self.hp = hp
        self.max_hp = hp
        self.kind = kind  # normal / bomb

    def draw(self, surf):
        r = self.rect
        strong = self.hp > 1
        if self.kind == "bomb":
            body = (235, 80, 60)
        else:
            body = (185, 190, 215) if strong else self.color
        pygame.draw.rect(surf, darken(body, 50), r.move(0, 3), border_radius=6)
        pygame.draw.rect(surf, body, r, border_radius=6)
        shine = pygame.Rect(r.x + 3, r.y + 3, r.w - 6, r.h // 3)
        pygame.draw.rect(surf, lighten(body, 45), shine, border_radius=4)
        if strong:
            pygame.draw.rect(surf, self.color, r, width=3, border_radius=6)
        if self.kind == "bomb":
            pygame.draw.rect(surf, YELLOW, r, width=2, border_radius=6)
            circ(surf, (40, 20, 20), r.centerx, r.centery + 1, 6)
            circ(surf, YELLOW, r.centerx + 3, r.centery - 5, 2)


class Particle:
    def __init__(self, x, y, color, power=1.0):
        ang = random.uniform(0, math.tau)
        sp = random.uniform(1.0, 5.0) * power
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(ang) * sp, math.sin(ang) * sp - 1
        self.life = self.max_life = random.randint(22, 42)
        self.size = random.uniform(2, 5) * (1 + 0.4 * (power - 1))
        self.color = color

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.15
        self.life -= 1

    def draw(self, surf):
        rad = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), rad)


class FloatText:
    def __init__(self, x, y, text, color):
        self.x, self.y, self.text, self.color = x, y, text, color
        self.life = 40

    def update(self):
        self.y -= 1
        self.life -= 1

    def draw(self, surf):
        draw_text(surf, self.text, FONT_S, self.color, (self.x, self.y))


class PowerUp:
    KINDS = {
        "W": ("Paddle Lebar", CYAN),
        "S": ("Bola Lambat", YELLOW),
        "L": ("Nyawa +1", PINK),
        "F": ("Bola Api!", FIRE),
        "Z": ("Laser!", PURPLE),
    }

    def __init__(self, x, y, kind):
        self.kind = kind
        self.color = self.KINDS[kind][1]
        self.rect = pygame.Rect(0, 0, 34, 20)
        self.rect.center = (x, y)
        self.fy = float(self.rect.y)

    def update(self, tempo=1.0):
        self.fy += 3 * (1 + (tempo - 1) * 0.5)
        self.rect.y = int(self.fy)

    def draw(self, surf):
        pygame.draw.rect(surf, darken(self.color, 70), self.rect.move(0, 2),
                         border_radius=10)
        pygame.draw.rect(surf, self.color, self.rect, border_radius=10)
        pygame.draw.rect(surf, WHITE, self.rect, width=2, border_radius=10)
        label = FONT_S.render(self.kind, True, (20, 20, 40))
        surf.blit(label, label.get_rect(center=self.rect.center))


class Laser:
    def __init__(self, x, y):
        self.rect = pygame.Rect(int(x) - 2, int(y), 4, 14)

    def update(self):
        self.rect.y -= 12

    def draw(self, surf):
        pygame.draw.rect(surf, (230, 210, 255), self.rect, border_radius=2)
        pygame.draw.rect(surf, PURPLE, self.rect, width=1, border_radius=2)


# ----------------------------------------------------------------------
# Boss
# ----------------------------------------------------------------------
class BossBullet:
    r = 7

    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.r), int(self.y - self.r),
                           self.r * 2, self.r * 2)

    def update(self):
        self.x += self.vx
        self.y += self.vy

    def draw(self, surf):
        surf.blit(BULLET_GLOW, (self.x - 18, self.y - 18))
        pygame.draw.circle(surf, (255, 120, 70), (int(self.x), int(self.y)),
                           self.r)
        pygame.draw.circle(surf, (255, 240, 200), (int(self.x), int(self.y)),
                           self.r - 3)


class Boss:
    PHASE_COLORS = {1: (150, 80, 220), 2: (240, 150, 60), 3: (240, 70, 80)}
    SHOOT_DELAY = {1: 110, 2: 85, 3: 65}

    def __init__(self, number):
        self.number = number
        self.w, self.h = 170, 80
        self.max_hp = 25 + 12 * number
        self.hp = self.max_hp
        self.x = WIDTH / 2 - self.w / 2
        self.target_y = HUD_H + 40
        self.y = float(-self.h - 10)
        self.dir = random.choice((-1, 1))
        self.shoot_timer = 100.0
        self.hit_cd = 0      # jeda agar 1 benturan tidak dihitung berkali-kali
        self.flash = 0

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    @property
    def ready(self):
        return self.y >= self.target_y

    @property
    def phase(self):
        ratio = self.hp / self.max_hp
        return 1 if ratio > 0.66 else (2 if ratio > 0.33 else 3)

    def enter_step(self):
        self.y = min(self.target_y, self.y + 3)

    def take_damage(self):
        """Return True jika kena damage (bukan saat cooldown)."""
        if self.hit_cd > 0:
            return False
        self.hp -= 1
        self.hit_cd = 8
        self.flash = 8
        return True

    def update(self, paddle, tempo=1.0):
        if self.hit_cd > 0:
            self.hit_cd -= 1
        if self.flash > 0:
            self.flash -= 1

        speed = (1.8 + self.phase * 0.8 + self.number * 0.2) \
            * (1 + (tempo - 1) * 0.7)
        self.x += self.dir * speed
        if self.x <= 10:
            self.x, self.dir = 10, 1
        elif self.x + self.w >= WIDTH - 10:
            self.x, self.dir = WIDTH - 10 - self.w, -1
        if self.phase == 3 and random.random() < 0.008:
            self.dir *= -1

        self.shoot_timer -= tempo
        if self.shoot_timer <= 0:
            self.shoot_timer = self.SHOOT_DELAY[self.phase]
            return self.shoot(paddle, tempo)
        return []

    def shoot(self, paddle, tempo=1.0):
        sx, sy = self.x + self.w / 2, self.y + self.h - 5
        base = math.atan2(paddle.y - sy, paddle.x + paddle.w / 2 - sx)
        speed = (4.2 + 0.25 * self.number + 0.4 * (self.phase - 1)) \
            * (1 + (tempo - 1) * 0.5)
        offsets = {1: [0], 2: [-0.3, 0, 0.3],
                   3: [-0.5, -0.25, 0, 0.25, 0.5]}[self.phase]
        return [BossBullet(sx, sy, math.cos(base + o) * speed,
                           math.sin(base + o) * speed) for o in offsets]

    def draw(self, surf, paddle):
        r = self.rect
        base = self.PHASE_COLORS[self.phase]
        body = WHITE if (self.flash > 0 and self.flash % 2 == 0) else base
        dark = (25, 12, 35)

        pygame.draw.rect(surf, darken(body, 70), r.move(0, 5), border_radius=18)
        pygame.draw.rect(surf, body, r, border_radius=18)
        pygame.draw.rect(surf, lighten(body, 45),
                         (r.x + 10, r.y + 6, r.w - 20, r.h // 5),
                         border_radius=10)

        # Mata mengikuti paddle
        for k, sign in ((0.3, 1), (0.7, -1)):
            ex, ey = int(r.x + r.w * k), r.y + r.h // 2 - 8
            pygame.draw.circle(surf, WHITE, (ex, ey), 15)
            dx, dy = paddle.x + paddle.w / 2 - ex, paddle.y - ey
            d = math.hypot(dx, dy) or 1
            pygame.draw.circle(surf, dark,
                               (int(ex + dx / d * 6), int(ey + dy / d * 6)), 7)
            pygame.draw.line(surf, dark, (ex - 18 * sign, ey - 22),
                             (ex + 14 * sign, ey - 12), 4)

        # Mulut bergigi
        mx0, mx1, my = int(r.x + r.w * 0.32), int(r.x + r.w * 0.68), r.bottom - 22
        pygame.draw.rect(surf, dark, (mx0, my, mx1 - mx0, 12), border_radius=4)
        seg = (mx1 - mx0) / 6
        for i in range(6):
            x = mx0 + i * seg
            pygame.draw.polygon(surf, WHITE, [(x, my), (x + seg, my),
                                              (x + seg / 2, my + 8)])

    def draw_bar(self, surf):
        bw, bh = 300, 12
        x, y = WIDTH // 2 - bw // 2, HUD_H + 14
        pygame.draw.rect(surf, (30, 20, 40), (x, y, bw, bh), border_radius=6)
        fill = int(bw * max(0, self.hp) / self.max_hp)
        if fill > 0:
            pygame.draw.rect(surf, self.PHASE_COLORS[self.phase],
                             (x, y, fill, bh), border_radius=6)
        pygame.draw.rect(surf, WHITE, (x, y, bw, bh), width=2, border_radius=6)
        draw_text(surf, f"BOSS {self.number}", FONT_S, WHITE,
                  (x - 45, y + bh // 2))


# ----------------------------------------------------------------------
# Game manager
# ----------------------------------------------------------------------
class Game:
    def __init__(self):
        self.bgs = [make_background(t, b) for t, b in THEMES + [BOSS_THEME]]
        self.world = pygame.Surface((WIDTH, HEIGHT))
        self.stars = [[random.uniform(0, WIDTH), random.uniform(0, HEIGHT),
                       random.uniform(0.1, 0.5), random.randint(1, 2)]
                      for _ in range(70)]
        self.highscore = load_highscore()
        self.char_index = 0
        cw, chh, gap = 220, 360, 30
        x0 = (WIDTH - (3 * cw + 2 * gap)) // 2
        self.card_rects = [pygame.Rect(x0 + i * (cw + gap), 112, cw, chh)
                           for i in range(len(CHARACTERS))]
        # state: start, select, playing, paused, bossintro, levelclear, gameover
        self.state = "start"
        self.reset_game()

    @property
    def char(self):
        return CHARACTERS[self.char_index]

    @property
    def tempo(self):
        """Pengali kecepatan; naik pelan-pelan selama bola terbang."""
        bonus = self.play_time / FPS / TEMPO_FULL_SECONDS * TEMPO_MAX_BONUS
        return 1.0 + min(TEMPO_MAX_BONUS, bonus)

    # ---------------- setup ----------------
    def reset_game(self):
        self.score = 0
        self.lives = self.char["lives"]
        self.level = 1
        self.combo = 0
        self.shake = 0
        self.level_timer = 0
        self.intro_timer = 0
        self.hurt_timer = 0
        self.play_time = 0.0
        self.laser_cd = 0
        self.clear_msg = ""
        self.paddle = Paddle(self.char)
        self.ball = Ball()
        self.boss = None
        self.bullets = []
        self.lasers = []
        self.particles, self.texts, self.powerups = [], [], []
        self.build_level()

    def build_level(self):
        self.bricks = []
        self.bullets = []
        self.lasers = []
        self.boss = None
        is_boss = self.level % BOSS_EVERY == 0

        cols, gap, bw, bh = 10, 6, 67, 22
        total_w = cols * bw + (cols - 1) * gap
        start_x = (WIDTH - total_w) // 2

        if is_boss:
            self.boss = Boss(self.level // BOSS_EVERY)
            rows, start_y = 2, HUD_H + 150
            pattern = lambda r, c, R_, C: random.random() < 0.6
        else:
            rows = min(5 + self.level // 2, 8)
            start_y = HUD_H + 40
            n = self.level - self.level // BOSS_EVERY - 1  # urutan level non-boss
            pattern = PATTERNS[n % len(PATTERNS)]

        strong_chance = min(0.08 + 0.07 * self.level, 0.5)
        bomb_chance = 0.06 if self.level >= 2 else 0.0

        for row in range(rows):
            for col in range(cols):
                if not pattern(row, col, rows, cols):
                    continue
                x = start_x + col * (bw + gap)
                y = start_y + row * (bh + gap)
                color = ROW_COLORS[row % len(ROW_COLORS)]
                roll = random.random()
                if roll < bomb_chance:
                    brick = Brick(x, y, bw, bh, color, 1, "bomb")
                elif roll < bomb_chance + strong_chance:
                    brick = Brick(x, y, bw, bh, color, 2)
                else:
                    brick = Brick(x, y, bw, bh, color, 1)
                self.bricks.append(brick)

        speed = min(6.0 + 0.5 * (self.level - 1), 10.0)
        self.ball.base_speed = speed * self.char["ball"]
        self.ball.slow_timer = 0
        self.ball.fire_timer = 0
        self.powerups.clear()
        self.paddle.target_w = self.paddle.base_w
        self.paddle.wide_timer = 0
        self.paddle.laser_timer = 0
        self.ball.stick_to(self.paddle)
        self.combo = 0

    def begin_level(self):
        self.build_level()
        if self.boss:
            self.state = "bossintro"
            self.intro_timer = 150
            sfx.play("warn")
        else:
            self.state = "playing"

    # ---------------- input ----------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key == pygame.K_m:
                sfx.toggle()
            elif event.key == pygame.K_p and self.state in ("playing", "paused"):
                self.state = "paused" if self.state == "playing" else "playing"
                sfx.play("select")
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.action()
            elif event.key == pygame.K_c and self.state == "gameover":
                self.state = "select"
                sfx.play("select")
            elif event.key == pygame.K_n and self.state == "playing":
                # Pintasan demo: lompat ke level berikutnya (untuk uji boss)
                self.level += 1
                self.begin_level()
            elif self.state == "select":
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    self.char_index = (self.char_index - 1) % len(CHARACTERS)
                    sfx.play("select")
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    self.char_index = (self.char_index + 1) % len(CHARACTERS)
                    sfx.play("select")

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.state == "select":
                for i, rect in enumerate(self.card_rects):
                    if rect.collidepoint(event.pos):
                        if i == self.char_index:
                            self.action()
                        else:
                            self.char_index = i
                            sfx.play("select")
            else:
                self.action()
        if event.type == pygame.MOUSEMOTION and \
                self.state in ("playing", "bossintro"):
            self.paddle.set_center(event.pos[0])
        return True

    def action(self):
        if self.state == "start":
            self.state = "select"
            sfx.play("confirm")
        elif self.state in ("select", "gameover"):
            self.reset_game()
            self.state = "playing"
            sfx.play("confirm")
        elif self.state == "paused":
            self.state = "playing"
        elif self.state == "playing" and self.ball.stuck:
            self.ball.launch()
            sfx.play("launch")

    