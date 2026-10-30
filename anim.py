# Wallpaper animado (loop perfeito) do tema Skippy: frames RGB crus no stdout -> ffmpeg
import os, sys, numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import gaussian_filter

B = sys.argv[1]
F = B + '/fonts/'
K = int(os.environ.get('SCALE', '1'))     # 2 = 3840x2160 (Hisense: video na camada 4K do hardware)
W, H, FPS, T = 1920 * K, 1080 * K, 30, 24          # 24 s de loop
N = FPS * T
CYAN = (92, 225, 255)
rng = np.random.default_rng(7)
PAD = 80 * K                                # folga para a deriva da nebulosa
NW, NH = W + 2 * PAD, H + 2 * PAD

def field(scale, seed, w, h):
    r = np.random.default_rng(seed).random((h // (4 * K), w // (4 * K)))   # mesmo ruido em qualquer escala
    f = gaussian_filter(r, scale, mode='wrap')
    f = (f - f.min()) / (f.max() - f.min())
    return np.array(Image.fromarray((f * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)) / 255.

# ---- nebulosa: duas camadas que derivam em sentidos opostos ----
def nebula(seed, w, h):
    n = sum(field(s, seed + i, w, h) * k for i, (s, k) in enumerate([(60, 1), (28, .55), (12, .3), (5, .12)]))
    return (n - n.min()) / (n.max() - n.min())
yy, xx = np.mgrid[0:NH, 0:NW] / np.array([NH, NW])[:, None, None]
mask = np.exp(-(((xx - .72) / .45) ** 2 + ((yy - .30) / .40) ** 2)) * np.clip(1.15 - yy * 1.05, 0, 1)
nA = np.clip((nebula(1, NW, NH) - .30) * 1.9, 0, 1) ** 1.4 * mask
nB = np.clip((nebula(50, NW, NH) - .45) * 2.2, 0, 1) ** 1.6 * mask
hue = field(25, 3, NW, NH)
violet, blue, cyan = np.array([120, 40, 200]) / 255., np.array([20, 90, 220]) / 255., np.array(CYAN) / 255.
def colorize(d, mix):
    col = violet * mix[..., None] + blue * (1 - mix[..., None])
    return col * (1 - d[..., None] ** 2) + cyan * d[..., None] ** 2
LA = (colorize(nA, hue) * nA[..., None] * 1.2).astype(np.float32)
LB = (colorize(nB, 1 - hue) * nB[..., None] * .9).astype(np.float32)
yb = (np.mgrid[0:H, 0:W][0] / H)
floor = ((np.array([2, 4, 12]) / 255.) + (np.array([10, 20, 45]) / 255.) * np.exp(-((yb - 1.0) / .25) ** 2)[..., None]).astype(np.float32)

# ---- estrelas: 3 camadas de parallax, voltas inteiras no loop ----
layers = []
for count, speed_loops, size, bright in [(1800, 1, 1 * K, .55), (600, 2, 2 * K, .8), (120, 3, 3 * K, 1.0)]:
    x = rng.random(count) * W; y = rng.random(count) * H
    ph = rng.random(count) * 2 * np.pi; tw = rng.integers(1, 5, count)  # ciclos de brilho por loop
    b = bright * (0.4 + 0.6 * rng.random(count))
    layers.append((x, y, ph, tw, b, size, speed_loops))

# ---- planeta + HUD estático (RGBA) ----
over = Image.new('RGBA', (W, H), (0, 0, 0, 0))
cx, cy, R = 350 * K, 280 * K, 140 * K
pyy, pxx = np.mgrid[-R:R, -R:R]
r = np.sqrt(pxx ** 2 + pyy ** 2) / R
inside = r < 1
light = np.clip(1 - np.sqrt((pxx / R + .55) ** 2 + (pyy / R + .45) ** 2) / 1.6, 0, 1)
bands = 0.85 + 0.15 * np.sin(pyy / R * 18 + gaussian_filter(rng.random((2 * R, 2 * R)), 6 * K) * 20)
p = np.zeros((2 * R, 2 * R, 4))
p[..., :3] = (np.array([40, 70, 140]) / 255.) * (light * bands)[..., None] * 1.4
p[..., :3] += cyan * (np.clip((r - .9) * 10, 0, 1) * inside)[..., None] * .5
p[..., 3] = inside
planet = Image.fromarray((np.clip(p, 0, 1) * 255).astype(np.uint8), 'RGBA')
ring = Image.new('RGBA', (W, H), (0, 0, 0, 0)); rd = ImageDraw.Draw(ring)
for i, a in enumerate(range(0, 30, 3)):
    a *= K
    rd.ellipse([cx - 280 * K - a, cy - 55 * K - a // 4, cx + 280 * K + a, cy + 55 * K + a // 4], outline=(150, 200, 255, 70 - i * 6), width=2 * K)
ring = ring.rotate(-14, center=(cx, cy), resample=Image.BICUBIC)
back = Image.new('RGBA', (W, H), (0, 0, 0, 0)); back.paste(ring.crop((0, 0, W, cy)), (0, 0))
front = Image.new('RGBA', (W, H), (0, 0, 0, 0)); front.paste(ring.crop((0, cy, W, H)), (0, cy))
over.alpha_composite(back); over.alpha_composite(planet, (cx - R, cy - R)); over.alpha_composite(front)
hud = Image.new('RGBA', (W, H), (0, 0, 0, 0)); hd = ImageDraw.Draw(hud)
m, L = 36 * K, 80 * K
for (x, y, sx, sy) in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
    hd.line([(x, y + sy * L), (x, y), (x + sx * L, y)], fill=CYAN + (120,), width=2 * K)
for i in range(40):
    y = (300 + i * 11) * K
    hd.line([(m, y), (m + (15 if i % 5 == 0 else 7) * K, y)], fill=CYAN + (50,), width=K)
fo = ImageFont.truetype(F + 'Orbitron.ttf', 17 * K); fo.set_variation_by_name('Medium')
fs = ImageFont.truetype(F + 'Rajdhani-SemiBold.ttf', 17 * K)
hd.text((m + 25 * K, m + 20 * K), 'SKIPPY  //  ELDER AI', font=fo, fill=CYAN + (160,))
hd.text((m + 25 * K, m + 45 * K), os.environ.get('HUD_NODE', 'BRIDGE 01  ·  SALA  ·  NODE 192.168.2.111'), font=fs, fill=CYAN + (100,))
hud = Image.alpha_composite(hud.filter(ImageFilter.GaussianBlur(3 * K)), hud)
over.alpha_composite(hud)
OV = np.array(over).astype(np.float32) / 255.
OVa = OV[..., 3:4]; OVc = OV[..., :3]

# radar: arco que gira devagar no canto direito
def radar(t):
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    a0 = 360 * t / T
    d.arc([W - 660 * K, 450 * K, W - 60 * K, 1050 * K], a0, a0 + 70, fill=110, width=2 * K)
    d.arc([W - 620 * K, 490 * K, W - 100 * K, 1010 * K], -a0 * 1.0, -a0 + 40, fill=70, width=K)
    return np.array(im.filter(ImageFilter.GaussianBlur(1.2 * K))).astype(np.float32)[..., None] / 255.

shoot_t0, shoot_len = 15.0, 1.1   # uma estrela cadente por loop

out = sys.stdout.buffer
for f in range(N):
    t = f / FPS; ph = 2 * np.pi * t / T
    ax, ay = int(PAD + 60 * K * np.cos(ph)), int(PAD + 40 * K * np.sin(ph))
    bx, by = int(PAD - 60 * K * np.cos(ph)), int(PAD + 40 * K * np.sin(2 * ph) * .5)
    img = floor + LA[ay:ay + H, ax:ax + W] * (1 + .08 * np.sin(ph)) + LB[by:by + H, bx:bx + W] * (1 + .15 * np.sin(2 * ph + 1))
    st = Image.new('L', (W, H), 0); sd = ImageDraw.Draw(st)
    for (x, y, phs, tw, b, size, loops) in layers:
        xs = (x - W * loops * t / T) % W
        v = b * (0.65 + 0.35 * np.sin(phs + 2 * np.pi * tw * t / T))
        for xi, yi, vi in zip(xs, y, (v * 255).astype(int)):
            if size == 1: sd.point((xi, yi), fill=int(vi))   # K=2: tamanhos 2/4/6 caem na elipse
            else: sd.ellipse([xi - size / 2, yi - size / 2, xi + size / 2, yi + size / 2], fill=int(vi))
    if shoot_t0 <= t < shoot_t0 + shoot_len:
        k = (t - shoot_t0) / shoot_len
        x1, y1 = (1500 - 900 * k) * K, (120 + 300 * k) * K
        for j in range(30):
            sd.line([(x1 + j * 6 * K, y1 - j * 2 * K), (x1 + (j * 6 + 6) * K, y1 - (j * 2 + 2) * K)], fill=int(255 * (1 - j / 30) * np.sin(np.pi * k)), width=2 * K)
    S = np.array(st.filter(ImageFilter.GaussianBlur(.6 * K))).astype(np.float32)[..., None] / 255.
    img = img + S * np.array([.85, .92, 1.0], np.float32) * 1.4
    img = img + radar(t) * cyan.astype(np.float32) * .6
    img = img * (1 - OVa) + OVc * OVa
    out.write((np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
