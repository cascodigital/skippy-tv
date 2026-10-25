# Widget do Plex: o que está passando, continuar, próximo episódio, chegou na biblioteca e a tua semana.
# Pôsteres saem pelo proxy /plex/img do skippy-cards (o token do Plex nunca vai pro aparelho).
import json, re, threading, time, urllib.parse, urllib.request

_cache = {'t': 0, 'v': None}
_dur = {}           # (sem uso: o histórico do Plex não traz ratingKey nem duração, então não há horas da semana)
_lock = threading.Lock()

def _get(base, token, path, **q):
    q['X-Plex-Token'] = token
    req = urllib.request.Request(f'{base}{path}?{urllib.parse.urlencode(q)}', headers={'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read())['MediaContainer']

def img(path, w=200, h=300):
    return f'/plex/img?{urllib.parse.urlencode({"u": path, "w": w, "h": h})}'

def _item(m, kind):
    ep = m['type'] == 'episode'
    show = m.get('grandparentTitle') if ep else m.get('title')
    off, dur = m.get('viewOffset') or 0, m.get('duration') or 0
    return {
        'kind': kind, 'key': m['ratingKey'], 'show': show,
        'sub': (f"T{m.get('parentIndex', '?')} · E{m.get('index', '?')}  {m.get('title', '')}" if ep
                else ' · '.join(x for x in [str(m.get('year') or ''), f"{int(dur / 60000)} min" if dur else ''] if x)),
        'poster': img(m.get('grandparentThumb') if ep else m.get('thumb') or m.get('parentThumb') or ''),
        'art': img(m.get('grandparentArt') or m.get('art') or '', 640, 360),
        'prog': round(off / dur, 3) if off and dur else 0,
        'left': int((dur - off) / 60000) if off and dur else None,
        'slug': m.get('grandparentSlug') if ep else m.get('slug'),
        'season': m.get('parentIndex'), 'episode': m.get('index'), 'type': m['type'],
    }

def _week(base, token):
    since = int(time.time()) - 7 * 86400
    h = _get(base, token, '/status/sessions/history/all', sort='viewedAt:desc', **{'viewedAt>': since}).get('Metadata', [])
    eps = sum(1 for x in h if x['type'] == 'episode'); movies = sum(1 for x in h if x['type'] == 'movie')
    shows = {}
    for x in h:
        if x['type'] == 'episode': shows[x.get('grandparentTitle')] = shows.get(x.get('grandparentTitle'), 0) + 1
    top = max(shows, key=shows.get) if shows else None
    clean = re.sub(r'\s*\(\d{4}\)$', '', top) if top else None
    return {'eps': eps, 'movies': movies, 'top': clean, 'top_n': shows.get(top, 0)}

def data(base, token):
    with _lock:
        if _cache['v'] and time.time() - _cache['t'] < 60:
            return _cache['v']
        v = {'now': None, 'cont': [], 'next': None, 'new': [], 'week': None, 'at': int(time.time())}
        try:
            for s in _get(base, token, '/status/sessions').get('Metadata', []):
                it = _item(s, 'now'); it['state'] = (s.get('Player') or {}).get('state'); it['player'] = (s.get('Player') or {}).get('title')
                v['now'] = it; break
        except Exception as e: print('plex now', e, flush=True)
        try:
            cw = _get(base, token, '/hubs/continueWatching/items').get('Metadata', [])
            v['cont'] = [_item(m, 'cont') for m in cw if m.get('viewOffset')][:3]
            nxt = [m for m in cw if not m.get('viewOffset') and m['type'] == 'episode']
            if nxt: v['next'] = _item(nxt[0], 'next')
        except Exception as e: print('plex cont', e, flush=True)
        try:
            for m in _get(base, token, '/library/recentlyAdded', **{'X-Plex-Container-Start': 0, 'X-Plex-Container-Size': 6}).get('Metadata', []):
                if m['type'] == 'season':
                    v['new'].append({'kind': 'new', 'key': m['ratingKey'], 'show': m.get('parentTitle'), 'sub': m.get('title', '').replace('Season', 'Temporada'),
                                     'poster': img(m.get('thumb') or m.get('parentThumb') or ''), 'art': img(m.get('art') or '', 640, 360),
                                     'prog': 0, 'slug': None, 'type': 'season', 'added': m.get('addedAt')})
                elif m['type'] in ('movie', 'episode'):
                    it = _item(m, 'new'); it['added'] = m.get('addedAt'); v['new'].append(it)
            v['new'] = v['new'][:4]
        except Exception as e: print('plex new', e, flush=True)
        try: v['week'] = _week(base, token)
        except Exception as e: print('plex week', e, flush=True)
        _cache.update(t=time.time(), v=v)
        return v

def link(it, mid):
    """Link que abre o item no app do Plex (watch.plex.tv abre o item exato; plex:// só abre o app)."""
    if it.get('type') == 'episode' and it.get('slug'):
        return f"https://watch.plex.tv/show/{it['slug']}/season/{it.get('season', 1)}/episode/{it.get('episode', 1)}"
    if it.get('type') == 'movie' and it.get('slug'):
        return f"https://watch.plex.tv/movie/{it['slug']}"
    return f"plex://server://{mid}/com.plexapp.plugins.library/library/metadata/{it['key']}"

def ago(ts):
    d = int((time.time() - (ts or 0)) / 86400)
    return 'hoje' if d < 1 else 'ontem' if d < 2 else f'há {d} dias'
