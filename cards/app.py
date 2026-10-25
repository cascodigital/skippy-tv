# skippy-cards: desenha os cards do canal "Skippy" do Shield (Plex + HASS) e serve /feed.json + /c/*.png
import io, json, os, random, threading, time, urllib.parse, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

PLEX = os.environ.get('PLEX_URL', 'http://192.168.2.46:32400')
PLEX_TOKEN = os.environ['PLEX_TOKEN']
PLEX_MID = os.environ.get('PLEX_MID', '')
HASS = os.environ.get('HASS_URL', 'http://192.168.2.25:8123')
HASS_TOKEN = os.environ['HASS_TOKEN']
PUBLIC = os.environ.get('PUBLIC_URL', 'http://192.168.2.46:8099')
OUT = os.environ.get('OUT_DIR', '/data/c')
F = os.environ.get('APP_DIR', '/app') + '/fonts/'
APPD = os.environ.get('APP_DIR', '/app')
WALL = APPD + '/wallpaper.jpg'
TTL = 240
W, H = 960, 540
CYAN = (92, 225, 255)
NAVY = (5, 11, 20)
os.makedirs(OUT, exist_ok=True)

def font(name, size, var=None):
    f = ImageFont.truetype(F + name, size)
    if var: f.set_variation_by_name(var)
    return f

ORB = lambda s: font('Orbitron.ttf', s, 'SemiBold')
RAJ = lambda s: font('Rajdhani-SemiBold.ttf', s)
RAJB = lambda s: font('Rajdhani-Bold.ttf', s)

def get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def plex_json(path, **q):
    q['X-Plex-Token'] = PLEX_TOKEN
    return json.loads(get(f'{PLEX}{path}?{urllib.parse.urlencode(q)}', {'Accept': 'application/json'}))['MediaContainer']

def plex_img(path, w, h):
    q = urllib.parse.urlencode({'width': w, 'height': h, 'minSize': 1, 'upscale': 1, 'url': path, 'X-Plex-Token': PLEX_TOKEN})
    return Image.open(io.BytesIO(get(f'{PLEX}/photo/:/transcode?{q}'))).convert('RGBA')

def hass(entity):
    try:
        return json.loads(get(f'{HASS}/api/states/{entity}', {'Authorization': f'Bearer {HASS_TOKEN}'}, 8))
    except Exception:
        return {'state': 'unavailable', 'attributes': {}}

class dr:
    """ImageDraw que compõe cada traço com alpha por cima (desenhar direto em RGBA substitui o pixel)."""
    def __init__(self, im): self.im = im
    def textlength(self, *a, **k): return ImageDraw.Draw(self.im).textlength(*a, **k)
    def __getattr__(self, name):
        def f(*a, **k):
            lay = Image.new('RGBA', self.im.size, (0, 0, 0, 0)); getattr(ImageDraw.Draw(lay), name)(*a, **k)
            self.im.alpha_composite(lay)
        return f

# ---------- moldura HUD comum ----------
CUT = 40
POLY = [(CUT, 0), (W, 0), (W, H - CUT), (W - CUT, H), (0, H), (0, CUT)]

def frame(im, chip=None):
    msk = Image.new('L', (W, H), 0); ImageDraw.Draw(msk).polygon(POLY, fill=255)
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0)); out.paste(im, (0, 0), msk)
    sl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sl)
    for y in range(0, H, 4):
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, 40))
    sl.putalpha(ImageChops.multiply(sl.split()[3], msk)); out.alpha_composite(sl)
    d = dr(out)
    d.line(POLY + [POLY[0]], fill=CYAN + (150,), width=3)
    d.line([(CUT + 14, 10), (CUT + 170, 10)], fill=CYAN + (240,), width=5)
    d.line([(W - 190, H - 11), (W - CUT - 14, H - 11)], fill=CYAN + (240,), width=5)
    if chip:
        f = ORB(22); tw = d.textlength(chip, font=f)
        d.polygon([(30, 30), (30 + tw + 46, 30), (30 + tw + 62, 46), (30 + tw + 46, 62), (30, 62)], fill=NAVY + (210,))
        d.line([(30, 30), (30 + tw + 46, 30), (30 + tw + 62, 46), (30 + tw + 46, 62), (30, 62), (30, 30)], fill=CYAN + (200,), width=2)
        d.rectangle([40, 41, 49, 50], fill=CYAN + (255,))
        d.text((60, 33), chip, font=f, fill=(225, 248, 255, 255))
    return out

def grade(bg):
    # unifica a paleta: escurece, puxa para navy/ciano e cria gradiente de leitura à esquerda/embaixo
    bg = ImageOps.fit(bg.convert('RGB'), (W, H), Image.LANCZOS)
    gray = ImageOps.grayscale(bg)
    duo = ImageOps.colorize(gray, black=(3, 8, 18), white=(170, 225, 255), mid=(40, 90, 140))
    bg = Image.blend(bg, duo, 0.45).convert('RGBA')
    g = Image.new('L', (W, H), 0); gd = ImageDraw.Draw(g)
    for x in range(W):
        gd.line([(x, 0), (x, H)], fill=int(235 * max(0, 1 - x / (W * 0.78)) ** 1.3))
    gb = Image.new('L', (W, H), 0); gbd = ImageDraw.Draw(gb)
    for y in range(H):
        gbd.line([(0, y), (W, y)], fill=int(220 * max(0, (y - H * 0.35) / (H * 0.65)) ** 1.5))
    shade = Image.new('RGBA', (W, H), NAVY + (255,))
    bg.paste(shade, (0, 0), ImageChops.lighter(g, gb))
    return bg

def glow_text(im, xy, text, f, fill=(235, 250, 255, 255), glow=CYAN, r=8):
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).text(xy, text, font=f, fill=glow + (200,))
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(r)))
    dr(im).text(xy, text, font=f, fill=fill)

def fit_text(d, text, f, maxw):
    if d.textlength(text, font=f) <= maxw: return text
    while text and d.textlength(text + '…', font=f) > maxw: text = text[:-1]
    return text.rstrip() + '…'

def logo_or_title(im, m, title, y_bottom):
    d = dr(im)
    logo = next((i['url'] for i in m.get('Image', []) if i['type'] == 'clearLogo'), None)
    if logo:
        try:
            lg = plex_img(logo, 600, 260)
            lg = lg.crop(lg.getbbox())
            k = min(470 / lg.width, 170 / lg.height); lg = lg.resize((int(lg.width * k), int(lg.height * k)), Image.LANCZOS)
            sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); a = lg.split()[3]
            blk = Image.new('RGBA', lg.size, (0, 0, 0, 255)); blk.putalpha(a)
            sh.alpha_composite(blk, (58, y_bottom - lg.height + 4)); im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
            im.alpha_composite(lg, (56, y_bottom - lg.height))
            return
        except Exception:
            pass
    f = RAJB(76)
    glow_text(im, (56, y_bottom - 80), fit_text(d, title.upper(), f, 820), f, r=6)

def progress(im, frac, label):
    d = dr(im)
    x0, x1, y = 58, W - 90, H - 58
    d.rounded_rectangle([x0, y, x1, y + 8], 4, fill=(255, 255, 255, 40))
    if frac:
        xe = x0 + int((x1 - x0) * frac)
        lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).rounded_rectangle([x0, y - 2, xe, y + 10], 6, fill=CYAN + (220,))
        im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(6)))
        d.rounded_rectangle([x0, y, xe, y + 8], 4, fill=CYAN + (255,))
    f = ORB(18); tw = d.textlength(label, font=f)
    d.text((x1 - tw, y - 32), label, font=f, fill=CYAN + (230,))

def via_skippy(go, pkg):
    # o Projectivy reescreve o pacote do intent do card; o app do canal recebe e repassa
    q = lambda x: urllib.parse.quote(x, safe='')
    return f'intent:#Intent;component=dev.skippy.channel/.Main;S.go={q(go)};S.pkg={pkg};end'

def plex_intent(m):
    if m['type'] == 'episode' and m.get('grandparentSlug'):
        go = f"https://watch.plex.tv/show/{m['grandparentSlug']}/season/{m.get('parentIndex', 1)}/episode/{m.get('index', 1)}"
    elif m['type'] == 'movie' and m.get('slug'):
        go = f"https://watch.plex.tv/movie/{m['slug']}"
    else:
        go = f"plex://server://{PLEX_MID}/com.plexapp.plugins.library/library/metadata/{m['ratingKey']}"
    return via_skippy(go, 'com.plexapp.android')

def card_episode(m, chip):
    bg = grade(plex_img(m.get('grandparentArt') or m['art'], W, H))
    im = frame(bg, chip)
    show = m.get('grandparentTitle') or m['title']
    logo_or_title(im, m, show, H - 150)
    d = dr(im)
    if m['type'] == 'episode':
        sub = f"T{m.get('parentIndex', '?')} · E{m.get('index', '?')}   {m['title']}"
    else:
        sub = f"{m.get('year', '')}   {m.get('title', '')}" if m.get('grandparentTitle') else str(m.get('year', ''))
    glow_text(im, (58, H - 132), fit_text(d, sub, RAJ(40), 600), RAJ(40), fill=(215, 240, 255, 255), r=4)
    off, dur = m.get('viewOffset'), m.get('duration')
    if off and dur:
        frac = off / dur; label = f'{int(frac * 100)}%  ·  FALTAM {max(1, int((dur - off) / 60000))} MIN'
    else:
        frac = 0; label = 'PRÓXIMO' if m['type'] == 'episode' else f"{int((dur or 0) / 60000)} MIN"
    progress(im, frac, label)
    return im

COND = {'rainy': 'CHUVA', 'pouring': 'TEMPORAL', 'cloudy': 'NUBLADO', 'partlycloudy': 'PARCIALMENTE NUBLADO',
        'sunny': 'SOL', 'clear-night': 'CÉU LIMPO', 'fog': 'NEBLINA', 'windy': 'VENTO', 'lightning': 'RAIOS',
        'lightning-rainy': 'TEMPESTADE', 'snowy': 'NEVE', 'hail': 'GRANIZO', 'exceptional': 'ESTRANHO'}
QUIPS = [
    'Estou monitorando a casa. Tu, pelo visto, o sofá.',
    'Sinais vitais da sala: aceitáveis. Os teus, discutíveis.',
    'Escolhe logo. Eu já calculei os 3 finais.',
    'Mais um episódio não vai te matar. Provavelmente.',
    'Rede estável, Plex no ar. De nada, macaco.',
    'Tua nave está pronta. O piloto, nem tanto.',
    'Lembrete gentil: a lata pensa. Tu, às vezes.',
    'Processando o universo. E a tua lista de pendências.',
]

def card_status():
    wall = Image.open(WALL).convert('RGB')
    bg = wall.crop((1500, 60, 1500 + 2200, 60 + 1238)).resize((W, H), Image.LANCZOS).convert('RGBA')
    bg.alpha_composite(Image.new('RGBA', (W, H), NAVY + (120,)))
    im = frame(bg, 'PONTE // SALA')
    d = dr(im)
    t = hass('sensor.sala_temperatura')['state']; u = hass('sensor.sala_umidade')['state']
    tr = hass('sensor.0xa4c13822447901eb_temperature')['state']; ur = hass('sensor.0xa4c13822447901eb_humidity')['state']
    w = hass('weather.forecast_home')
    def num(x):
        try: return f'{float(x):.1f}'.replace('.', ',')
        except Exception: return '--'
    glow_text(im, (56, 110), num(t) + '°', RAJB(190), r=12)
    d.text((62, 330), f'UMIDADE {num(u)}%', font=ORB(24), fill=CYAN + (230,))
    x = 560
    d.line([(x - 40, 120), (x - 40, 400)], fill=CYAN + (90,), width=2)
    d.text((x, 118), 'LÁ FORA', font=ORB(20), fill=CYAN + (200,))
    glow_text(im, (x, 140), num(tr) + '°', RAJB(110), r=8)
    d.text((x, 270), f'{num(ur)}% UMID.', font=RAJ(34), fill=(215, 240, 255, 255))
    cond = COND.get(w['state'], w['state'].upper())
    d.text((x, 315), fit_text(d, cond, ORB(24), 360), font=ORB(24), fill=(235, 250, 255, 255))
    random.seed(int(time.time() // 1800))
    q = random.choice(QUIPS)
    d.text((58, H - 100), fit_text(d, '“' + q + '”', RAJ(34), 840), font=RAJ(34), fill=(200, 230, 255, 235))
    d.text((58, H - 58), 'SKIPPY  //  ELDER AI', font=ORB(16), fill=CYAN + (160,))
    return im

# ---------- luzes (lista branca: o painel só alcança estes 4 grupos) ----------
LIGHTS = [
    {'id': 'sala', 'name': 'Sala', 'ents': ['light.luz_da_sala'], 'dim': True},
    {'id': 'quarto', 'name': 'Quarto', 'ents': ['light.luz_quarto']},
    {'id': 'cozinha', 'name': 'Cozinha', 'ents': ['light.luz_da_porta', 'light.luz_da_pia', 'light.luz_freezer']},
    {'id': 'rua', 'name': 'Rua', 'ents': ['light.luzes_do_patio']},
]
LMAP = {l['id']: l for l in LIGHTS}
GO2RTC = os.environ.get('GO2RTC_URL', 'http://192.168.2.102:1984')

def hass_call(domain, service, data):
    req = urllib.request.Request(f'{HASS}/api/services/{domain}/{service}', data=json.dumps(data).encode(), method='POST',
                                 headers={'Authorization': f'Bearer {HASS_TOKEN}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status

def lights_state():
    out = []
    for l in LIGHTS:
        st = [hass(e) for e in l['ents']]
        on = any(x['state'] == 'on' for x in st)
        bri = st[0]['attributes'].get('brightness') if l.get('dim') else None
        out.append({'id': l['id'], 'name': l['name'], 'on': on, 'dim': bool(l.get('dim')),
                    'bri': round((bri or 0) * 100 / 255) if on and bri is not None else (100 if on else 0),
                    'ok': all(x['state'] in ('on', 'off') for x in st)})
    return out

def light_action(lid, action, value=None):
    l = LMAP[lid]
    if action == 'toggle':
        on = any(hass(e)['state'] == 'on' for e in l['ents'])
        action = 'off' if on else 'on'
    if action == 'on':
        hass_call('light', 'turn_on', {'entity_id': l['ents']})
    elif action == 'off':
        hass_call('light', 'turn_off', {'entity_id': l['ents']})
    elif action == 'set' and l.get('dim'):
        v = max(1, min(100, int(value)))
        hass_call('light', 'turn_on', {'entity_id': l['ents'], 'brightness_pct': v, 'transition': 0.4})
    else:
        raise ValueError('acao')

def card_camera():
    snap = Image.open(io.BytesIO(get(f'{GO2RTC}/api/frame.jpeg?src=rua', timeout=20))).convert('RGB')
    bg = ImageOps.fit(snap, (W, H), Image.LANCZOS)
    bg = Image.blend(bg, ImageOps.colorize(ImageOps.grayscale(bg), black=(3, 8, 18), white=(190, 235, 255)), 0.25).convert('RGBA')
    sh = Image.new('L', (W, H), 0); sd = ImageDraw.Draw(sh)
    for y in range(H):
        sd.line([(0, y), (W, y)], fill=int(210 * max(0, (y - H * 0.5) / (H * 0.5)) ** 1.4))
    bg.paste(Image.new('RGBA', (W, H), NAVY + (255,)), (0, 0), sh)
    im = frame(bg, 'AO VIVO // RUA')
    d = dr(im)
    d.ellipse([W - 92, 34, W - 66, 60], fill=(255, 70, 70, 255))
    glow_text(im, (56, H - 170), 'CÂMERA DA RUA', RAJB(76), r=6)
    d.text((58, H - 88), 'OK para abrir ao vivo  ·  ' + time.strftime('%H:%M'), font=ORB(20), fill=CYAN + (230,))
    return im

def bulb(d, x, y, on, s=1.0):
    col = CYAN + (255,) if on else (90, 120, 150, 255)
    d.ellipse([x, y, x + 64 * s, y + 64 * s], outline=col, width=int(5 * s))
    d.rectangle([x + 20 * s, y + 66 * s, x + 44 * s, y + 80 * s], fill=col)
    if on:
        for ax, ay, bx, by in [(-26, 32, -12, 32), (76, 32, 90, 32), (32, -26, 32, -12), (-12, -10, -2, 0), (66, 0, 76, -10)]:
            d.line([(x + ax * s, y + ay * s), (x + bx * s, y + by * s)], fill=col, width=int(4 * s))

def card_lights(st):
    wall = Image.open(WALL).convert('RGB')
    bg = wall.crop((200, 900, 200 + 2200, 900 + 1238)).resize((W, H), Image.LANCZOS).convert('RGBA')
    bg.alpha_composite(Image.new('RGBA', (W, H), NAVY + (150,)))
    im = frame(bg, 'LUZES DA CASA')
    d = dr(im)
    for i, l in enumerate(st):
        x = 60 + i * 215; y = 130
        if l['on']:
            g = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse([x + 20, y, x + 150, y + 130], fill=CYAN + (110,))
            im.alpha_composite(g.filter(ImageFilter.GaussianBlur(28)))
        bulb(d, x + 52, y + 20, l['on'], 1.0)
        f = ORB(26); tw = d.textlength(l['name'].upper(), font=f)
        d.text((x + 85 - tw / 2, y + 150), l['name'].upper(), font=f, fill=(235, 250, 255, 255) if l['on'] else (130, 160, 190, 255))
        lab = (f"{l['bri']}%" if l['dim'] and l['on'] else ('LIGADA' if l['on'] else 'DESLIGADA')) if l['ok'] else 'SEM SINAL'
        f2 = RAJB(34); tw = d.textlength(lab, font=f2)
        d.text((x + 85 - tw / 2, y + 192), lab, font=f2, fill=CYAN + (255,) if l['on'] else (110, 140, 170, 255))
    d.text((58, H - 88), 'OK para o painel  ·  dimmer da sala no painel', font=ORB(20), fill=CYAN + (220,))
    return im

def ponte_intent(focus):
    return f'intent:#Intent;component=dev.skippy.channel/.Ponte;S.focus={focus};end'

state = {'t': 0, 'feed': None}
lock = threading.Lock()

def render():
    ts = int(time.time())
    cards = []
    def save(im, name):
        fn = f'{name}-{ts}.png'; im.save(f'{OUT}/{fn}', optimize=True); return f'{PUBLIC}/c/{fn}'
    try:
        cards.append({'id': 'status', 'title': 'Ponte · Sala', 'desc': 'Skippy // Elder AI', 'img': save(card_status(), 'status'),
                      'intent': ponte_intent('luzes')})
    except Exception as e:
        print('status', e, flush=True)
    try:
        cards.append({'id': 'camera', 'title': 'Câmera da rua', 'desc': 'Ao vivo · OK para abrir', 'img': save(card_camera(), 'camera'),
                      'intent': ponte_intent('camera')})
    except Exception as e:
        print('camera', e, flush=True)
    try:
        st = lights_state()
        acesas = [l['name'] for l in st if l['on']]
        cards.append({'id': 'luzes', 'title': 'Luzes da casa', 'desc': ('Acesas: ' + ', '.join(acesas)) if acesas else 'Tudo apagado',
                      'img': save(card_lights(st), 'luzes'), 'intent': ponte_intent('luzes')})
    except Exception as e:
        print('luzes', e, flush=True)
    try:
        for m in plex_json('/hubs/continueWatching/items', includeImages=1).get('Metadata', [])[:7]:
            try:
                ep = f"T{m.get('parentIndex', '?')} · E{m.get('index', '?')} — {m['title']}" if m['type'] == 'episode' else str(m.get('year', ''))
                cards.append({'id': 'cw' + m['ratingKey'], 'title': m.get('grandparentTitle') or m['title'], 'desc': ep,
                              'img': save(card_episode(m, 'CONTINUAR'), 'cw' + m['ratingKey']), 'intent': plex_intent(m)})
            except Exception as e:
                print('cw', m.get('title'), e, flush=True)
        for m in plex_json('/hubs/home/recentlyAdded', type=1, count=3, includeImages=1).get('Metadata', [])[:3]:
            try:
                cards.append({'id': 'new' + m['ratingKey'], 'title': m['title'],
                              'desc': f"Novo no Plex · {m.get('year', '')} · {int((m.get('duration') or 0) / 60000)} min",
                              'img': save(card_episode(m, 'NOVO NO PLEX'), 'new' + m['ratingKey']), 'intent': plex_intent(m)})
            except Exception as e:
                print('new', m.get('title'), e, flush=True)
    except Exception as e:
        print('plex', e, flush=True)
    for f in os.listdir(OUT):  # limpa render antigo
        if not f.endswith(f'-{ts}.png') and os.path.getmtime(f'{OUT}/{f}') < time.time() - 3600:
            os.remove(f'{OUT}/{f}')
    return {'channel': 'Skippy', 'generated': ts, 'cards': cards}

def refresher():
    # renderiza em segundo plano: o feed nunca espera os ~16 s de um render frio
    while True:
        try:
            f = render()
            with lock:
                state['feed'] = f; state['t'] = time.time()
        except Exception as e:
            print('refresh', e, flush=True)
        for _ in range(TTL):
            time.sleep(1)
            if state['t'] == 0: break   # ação numa luz pede redesenho já

def feed():
    for _ in range(60):   # só no primeiro boot do container espera o primeiro render
        with lock:
            if state['feed']: return state['feed']
        time.sleep(0.5)
    return {'channel': 'Skippy', 'generated': 0, 'cards': []}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/feed.json':
            body = json.dumps(feed(), ensure_ascii=False).encode(); ct = 'application/json'
        elif p.startswith('/c/') and '/' not in p[3:] and os.path.exists(OUT + '/' + p[3:]):
            body = open(OUT + '/' + p[3:], 'rb').read(); ct = 'image/png'
        elif p == '/health':
            body = b'ok'; ct = 'text/plain'
        elif p == '/ponte':
            body = open(APPD + '/ponte.html', 'rb').read(); ct = 'text/html; charset=utf-8'
        elif p in ('/static/wallpaper.jpg', '/static/Orbitron.ttf', '/static/Rajdhani-SemiBold.ttf', '/static/Rajdhani-Bold.ttf'):
            n = p.split('/')[-1]
            body = open(WALL if n == 'wallpaper.jpg' else F + n, 'rb').read()
            ct = 'image/jpeg' if n.endswith('jpg') else 'font/ttf'
        elif p == '/static/video-rtc.js':
            # player do go2rtc servido daqui: import de módulo de outra origem é barrado por CORS
            body = get(f'{GO2RTC}/video-rtc.js'); ct = 'text/javascript'
        elif p == '/api/lights':
            body = json.dumps(lights_state()).encode(); ct = 'application/json'
        else:
            self.send_response(404); self.end_headers(); return
        self.reply(200, body, ct)

    def reply(self, code, body, ct):
        self.send_response(code); self.send_header('Content-Type', ct); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        if self.path.split('?')[0] != '/api/light':
            return self.reply(404, b'{}', 'application/json')
        try:
            n = int(self.headers.get('Content-Length') or 0)
            j = json.loads(self.rfile.read(n) or b'{}')
            if j.get('id') not in LMAP or j.get('action') not in ('toggle', 'on', 'off', 'set'):
                return self.reply(403, b'{"erro":"fora da lista branca"}', 'application/json')
            light_action(j['id'], j['action'], j.get('value'))
            time.sleep(0.35)
            state['t'] = 0  # próximo feed redesenha o card de luzes
            self.reply(200, json.dumps(lights_state()).encode(), 'application/json')
        except Exception as e:
            self.reply(500, json.dumps({'erro': str(e)}).encode(), 'application/json')
    def log_message(self, *a): pass

if __name__ == '__main__':
    threading.Thread(target=refresher, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()
