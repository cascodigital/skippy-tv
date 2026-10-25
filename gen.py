import io, re, sys, numpy as np, cairosvg
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import gaussian_filter

B = sys.argv[1]
F = B + '/fonts/'
CYAN = (92, 225, 255)
rng = np.random.default_rng(7)

# ---------- wallpaper ----------
W, H = 3840, 2160
def noise(scale, seed):
    r = np.random.default_rng(seed).random((H // 8, W // 8))
    return gaussian_filter(r, scale, mode='wrap')

n = sum(noise(s, i) * w for i, (s, w) in enumerate([(60, 1), (28, .55), (12, .3), (5, .12)]))
n = (n - n.min()) / (n.max() - n.min())
n = np.array(Image.fromarray((n * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) / 255.
yy, xx = np.mgrid[0:H, 0:W] / np.array([H, W])[:, None, None]
# nebula concentrated upper right, fading towards the dock
mask = np.exp(-(((xx - .72) / .42) ** 2 + ((yy - .30) / .38) ** 2)) * np.clip(1.15 - yy * 1.05, 0, 1)
d = np.clip((n - .30) * 1.9, 0, 1) ** 1.4 * mask
n2 = np.array(Image.fromarray((noise(10, 99) * 0 + 0).astype(np.uint8)))  # placeholder keep shape
c2 = gaussian_filter(np.random.default_rng(3).random((H // 8, W // 8)), 25, mode='wrap')
c2 = (c2 - c2.min()) / (c2.max() - c2.min())
c2 = np.array(Image.fromarray((c2 * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) / 255.
violet = np.array([120, 40, 200]) / 255.
blue = np.array([20, 90, 220]) / 255.
cyan = np.array(CYAN) / 255.
col = violet[None, None] * c2[..., None] + blue[None, None] * (1 - c2[..., None])
col = col * (1 - d[..., None] ** 2) + cyan[None, None] * d[..., None] ** 2
base = np.array([2, 4, 12]) / 255.
img = base[None, None] + col * d[..., None] * 1.25
img += (np.array([10, 20, 45]) / 255.)[None, None] * np.exp(-((yy - 1.0) / .25) ** 2)[..., None]  # floor glow
img = np.clip(img, 0, 1)

# stars
stars = np.zeros((H, W))
k = 9000
ys, xs = rng.integers(0, H, k), rng.integers(0, W, k)
stars[ys, xs] = rng.random(k) ** 3
big = gaussian_filter(stars * (stars > .55), 3) * 30
stars = np.clip(stars + big, 0, 1) * (0.35 + 0.65 * np.clip(1.2 - yy, 0, 1))
img = np.clip(img + stars[..., None] * np.array([.85, .92, 1.0])[None, None], 0, 1)
wall = Image.fromarray((img * 255).astype(np.uint8))

# planet with ring, top-left
pl = Image.new('RGBA', (W, H), (0, 0, 0, 0))
pd = ImageDraw.Draw(pl)
cx, cy, R = 700, 560, 280
pyy, pxx = np.mgrid[-R:R, -R:R]
r = np.sqrt(pxx ** 2 + pyy ** 2) / R
inside = r < 1
light = np.clip(1 - np.sqrt((pxx / R + .55) ** 2 + (pyy / R + .45) ** 2) / 1.6, 0, 1)
bands = 0.85 + 0.15 * np.sin(pyy / R * 18 + gaussian_filter(rng.random((2 * R, 2 * R)), 6) * 20)
p = np.zeros((2 * R, 2 * R, 4))
p[..., :3] = (np.array([40, 70, 140]) / 255.)[None, None] * (light * bands)[..., None] * 1.4
rim = np.clip((r - .9) * 10, 0, 1) * inside
p[..., :3] += cyan[None, None] * rim[..., None] * .5
p[..., 3] = inside * 1.0
planet = Image.fromarray((np.clip(p, 0, 1) * 255).astype(np.uint8), 'RGBA')
ring = Image.new('RGBA', (W, H), (0, 0, 0, 0))
rd = ImageDraw.Draw(ring)
for i, a in enumerate(range(0, 60, 6)):
    rd.ellipse([cx - 560 - a, cy - 110 - a // 4, cx + 560 + a, cy + 110 + a // 4], outline=(150, 200, 255, 70 - i * 6), width=3)
ring = ring.rotate(-14, center=(cx, cy), resample=Image.BICUBIC)
back = ring.crop((0, 0, W, cy)); front = ring.crop((0, cy, W, H))
wall = wall.convert('RGBA')
wall.alpha_composite(Image.new('RGBA', (W, H), 0).crop((0, 0, W, H)))
tmp = Image.new('RGBA', (W, H), (0, 0, 0, 0)); tmp.paste(back, (0, 0))
wall.alpha_composite(tmp)
wall.alpha_composite(planet, (cx - R, cy - R))
tmp = Image.new('RGBA', (W, H), (0, 0, 0, 0)); tmp.paste(front, (0, cy))
wall.alpha_composite(tmp)

# HUD overlay
hud = Image.new('RGBA', (W, H), (0, 0, 0, 0))
hd = ImageDraw.Draw(hud)
hc = CYAN + (110,)
m, L = 70, 160
for (x, y, sx, sy) in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
    hd.line([(x, y + sy * L), (x, y), (x + sx * L, y)], fill=hc, width=4)
    hd.line([(x + sx * 20, y + sy * 20), (x + sx * 60, y + sy * 20)], fill=CYAN + (60,), width=2)
for i in range(40):  # ticks along left edge
    y = 600 + i * 22
    hd.line([(m, y), (m + (30 if i % 5 == 0 else 14), y)], fill=CYAN + (45,), width=2)
fo = ImageFont.truetype(F + 'Orbitron.ttf', 34); fo.set_variation_by_name('Medium')
fs = ImageFont.truetype(F + 'Rajdhani-SemiBold.ttf', 34)
hd.text((m + 50, m + 40), 'SKIPPY  //  ELDER AI', font=fo, fill=CYAN + (150,))
hd.text((m + 50, m + 90), 'BRIDGE 01  ·  SALA  ·  NODE 192.168.2.111', font=fs, fill=CYAN + (90,))
hd.arc([W - 1320, 900, W - 120, 2100], 200, 300, fill=CYAN + (40,), width=3)
hd.arc([W - 1240, 980, W - 200, 2020], 210, 280, fill=CYAN + (70,), width=2)
glow = hud.filter(ImageFilter.GaussianBlur(6))
wall.alpha_composite(glow); wall.alpha_composite(hud)
wall.convert('RGB').save(B + '/dist/out/wallpaper.jpg', quality=93)

# ---------- banners ----------
BW, BH = 640, 360
def svg_white(path, h):
    s = open(path).read().replace('<path ', '<path fill="#ffffff" ')
    png = cairosvg.svg2png(bytestring=s.encode(), output_height=h)
    return Image.open(io.BytesIO(png)).convert('RGBA')

def tint(im, rgb):
    a = im.split()[3]
    out = Image.new('RGBA', im.size, rgb + (0,)); out.putalpha(a); return out

def panel():
    im = Image.new('RGBA', (BW, BH), (0, 0, 0, 0))
    g = np.linspace(0, 1, BH)[:, None]
    top, bot = np.array([14, 30, 52]), np.array([4, 9, 18])
    arr = (top * (1 - g) + bot * g)[..., None].repeat(BW, 1).transpose(0, 1, 2)
    arr = np.broadcast_to((top[None, None] * (1 - g[..., None]) + bot[None, None] * g[..., None]), (BH, BW, 3))
    bg = Image.fromarray(arr.astype(np.uint8)).convert('RGBA')
    cut = 34
    poly = [(cut, 0), (BW, 0), (BW, BH - cut), (BW - cut, BH), (0, BH), (0, cut)]
    msk = Image.new('L', (BW, BH), 0); ImageDraw.Draw(msk).polygon(poly, fill=255)
    im.paste(bg, (0, 0), msk)
    d = ImageDraw.Draw(im)
    for yy_ in range(0, BH, 6):  # scanlines
        d.line([(0, yy_), (BW, yy_)], fill=(255, 255, 255, 6))
    im.putalpha(Image.fromarray(np.minimum(np.array(im.split()[3]), np.array(msk))))
    d = ImageDraw.Draw(im)
    d.line(poly + [poly[0]], fill=CYAN + (170,), width=3)
    d.line([(cut + 10, 8), (cut + 120, 8)], fill=CYAN + (230,), width=4)
    d.line([(BW - 130, BH - 9), (BW - cut - 10, BH - 9)], fill=CYAN + (230,), width=4)
    return im

def glowpaste(im, logo, xy):
    pad = 40
    big = Image.new('RGBA', (logo.width + 2 * pad, logo.height + 2 * pad), (0, 0, 0, 0))
    big.paste(logo, (pad, pad)); logo = big; xy = (xy[0] - pad, xy[1] - pad)
    g = tint(logo, CYAN).filter(ImageFilter.GaussianBlur(10))
    im.alpha_composite(g, xy); im.alpha_composite(g, xy)
    im.alpha_composite(tint(logo, (215, 248, 255)), xy)

label = ImageFont.truetype(F + 'Orbitron.ttf', 44); label.set_variation_by_name('SemiBold')
APPS = {  # pacote: (svg ou None, rótulo, texto do logo)
    'plex': ('plex', 'PLEX', None), 'youtube': ('youtube', 'YOUTUBE', None),
    'globoplay': (None, 'GLOBOPLAY', 'globoplay'), 'youtubemusic': ('youtubemusic', 'YT MUSIC', None),
    'kodi': ('kodi', 'KODI', None), 'playstore': ('googleplay', 'PLAY STORE', None),
    'netflix': ('netflix', 'NETFLIX', None), 'primevideo': ('primevideo', 'PRIME VIDEO', None),
    'downloader': ('arrow', 'DOWNLOADER', None), 'plexserver': ('plex', 'PLEX SERVER', None),
    'appletv': ('appletv', 'APPLE TV', None), 'max': (None, 'MAX', 'max'), 'vlc': ('vlc', 'VLC', None),
    'apps': ('grid', 'APPS', None), 'ponte': ('cam', 'PONTE', None),
    'skippy': (None, 'ELDER AI', 'SKIPPY'), 'settings': ('gear', 'AJUSTES', None), 'livechannels': ('tv', 'CANAIS', None),
}
for key, (svg, name, txt) in APPS.items():
    im = panel()
    if svg:
        logo = svg_white(f'{B}/logos/{svg}.svg', 600)
        logo = logo.crop(logo.getbbox())
        k = min(360 / logo.width, 124 / logo.height)
        logo = logo.resize((round(logo.width * k), round(logo.height * k)), Image.LANCZOS)
    else:
        ft = ImageFont.truetype(F + 'Rajdhani-Bold.ttf', 120 if len(txt) > 2 else 170)
        bb = ft.getbbox(txt); logo = Image.new('RGBA', (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (0, 0, 0, 0))
        ImageDraw.Draw(logo).text((10 - bb[0], 10 - bb[1]), txt, font=ft, fill='white')
    x = (BW - logo.width) // 2; y = 140 - logo.height // 2
    glowpaste(im, logo, (x, y))
    d = ImageDraw.Draw(im)
    tw = d.textlength(name, font=label)
    d.text(((BW - tw) / 2, BH - 92), name, font=label, fill=CYAN + (235,))
    im.save(f'{B}/dist/out/banner-{key}.png')
print('ok')
