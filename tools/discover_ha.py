#!/usr/bin/env python3
"""Lê um Home Assistant e propõe um house.json para o Skippy TV.

Uso:  HASS_URL=http://ha:8123 HASS_TOKEN=xxxx python3 tools/discover_ha.py > house.draft.json
      (opcional) PLEX_URL=http://plex:32400  GO2RTC_URL=http://cam:1984  PUBLIC_URL=http://docker-host:8099

Só LÊ (GET /api/states e POST /api/template, que não muda nada). Tudo que não der pra adivinhar sai como
"TODO" — a IA/humano decide. Comentários sobre cada escolha vão para stderr, o JSON para stdout.
"""
import json, os, re, sys, unicodedata, urllib.request

HA = os.environ.get('HASS_URL', '').rstrip('/')
TOK = os.environ.get('HASS_TOKEN', '')
if not HA or not TOK:
    sys.exit('defina HASS_URL e HASS_TOKEN')

def req(path, body=None):
    r = urllib.request.Request(HA + path, data=json.dumps(body).encode() if body else None,
                               headers={'Authorization': f'Bearer {TOK}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=20) as f:
        return f.read().decode()

def note(*a): print('#', *a, file=sys.stderr)

states = json.loads(req('/api/states'))
# área de cada entidade (o REST não expõe; o template sim)
tpl = "{% for s in states %}{{ s.entity_id }}\t{{ area_name(s.entity_id) or '' }}\n{% endfor %}"
areas = dict(l.split('\t', 1) for l in req('/api/template', {'template': tpl}).splitlines() if '\t' in l)
S = {s['entity_id']: s for s in states}
dc = lambda e: S[e]['attributes'].get('device_class')
name = lambda e: S[e]['attributes'].get('friendly_name', e)
alive = lambda e: S[e]['state'] not in ('unavailable', 'unknown')

def pick(cands, why):
    cands = [e for e in cands if alive(e)]
    if not cands: note(f'{why}: nada encontrado -> TODO'); return 'TODO'
    note(f'{why}: {cands[0]} ({name(cands[0])}, área {areas.get(cands[0]) or "-"})' + (f'  [outros: {", ".join(cands[1:4])}]' if len(cands) > 1 else ''))
    return cands[0]

# luzes: uma por área (grupo de todas as light.* da área), a primeira com brilho vira o dimmer
lights, by_area = [], {}
for e in S:
    if e.startswith('light.') and alive(e) and not S[e]['attributes'].get('entity_id'):   # pula grupos de luz
        by_area.setdefault(areas.get(e) or 'Sem área', []).append(e)
for e in S:   # grupos de luz (light.* com entity_id) valem mais que as luzes soltas da mesma área
    if e.startswith('light.') and S[e]['attributes'].get('entity_id') and alive(e):
        by_area[areas.get(e) or name(e)] = [e]
for area, ents in sorted(by_area.items()):
    modes = set(m for x in ents for m in S[x]['attributes'].get('supported_color_modes') or [])
    dimmable = bool(modes - {'onoff'}) and len(ents) == 1   # cada luz com brilho ganha barra de dimmer no painel
    plain = unicodedata.normalize('NFKD', area).encode('ascii', 'ignore').decode().lower()
    lid = re.sub(r'[^a-z0-9]+', '_', plain).strip('_') or 'luz'
    lights.append({'id': lid, 'name': area, 'entities': ents, **({'dimmable': True} if dimmable else {})})
note(f'luzes: {len(lights)} grupos por área; o painel mostra bem até 4-5. Corte os que não interessam.')

temps = [e for e in S if e.startswith('sensor.') and dc(e) == 'temperature']
hums = [e for e in S if e.startswith('sensor.') and dc(e) == 'humidity']
outdoor = lambda e: re.search(r'(out|exter|fora|rua|garden|patio|pátio|quintal|varanda)', (e + ' ' + name(e) + ' ' + (areas.get(e) or '')).lower())
hw = lambda e: re.search(r'(cpu|gpu|soc|core|nvme|disk|thermal|battery|bateria|charger|composite|servidor|server|\d+_\d+_\d+_\d+|router|printer)', (e + name(e)).lower())
indoor_t = sorted([e for e in temps if not outdoor(e) and not hw(e)], key=lambda e: (not areas.get(e), e))   # com área primeiro
door = [e for e in S if e.startswith('binary_sensor.') and dc(e) in ('door', 'opening', 'garage_door')]
motion = [e for e in S if e.startswith('binary_sensor.') and dc(e) in ('motion', 'occupancy', 'moving')]
cams = [e for e in S if e.startswith('camera.')]
mps = [e for e in S if e.startswith('media_player.')]

house = {
    '_doc': 'Rascunho gerado por tools/discover_ha.py. Revise cada TODO e cada escolha (veja os comentários no stderr). Esquema: docs/HOUSE.md',
    'server': {'public_url': os.environ.get('PUBLIC_URL', 'http://TODO-docker-host:8099')},
    'hass': {'url': HA},
    'plex': {'url': os.environ.get('PLEX_URL', 'TODO (ou remova os cards do Plex)'), 'machine_id': 'TODO: curl http://PLEX:32400/identity'},
    'camera': {'go2rtc': os.environ.get('GO2RTC_URL', 'TODO'), 'stream': 'TODO: nome do stream no go2rtc.yaml',
               'label': 'TODO (ex.: PORTÃO)', 'title': 'TODO (ex.: Câmera do portão)',
               'motion_entity': pick(motion, 'sensor de movimento da câmera'), 'windy_per_hour': 15},
    'door': {'entity': pick(door, 'porta'), 'room': (areas.get(door[0]) or 'TODO').lower() if door else 'TODO'},
    'climate': {'label': 'TODO (cômodo)',
                'indoor_temp': pick(indoor_t, 'temperatura interna'),
                'indoor_hum': pick([e for e in hums if not outdoor(e)], 'umidade interna'),
                'outdoor_temp': pick([e for e in temps if outdoor(e) and not hw(e)], 'temperatura externa'),
                'outdoor_hum': pick([e for e in hums if outdoor(e)], 'umidade externa'),
                'weather': pick([e for e in S if e.startswith('weather.')], 'previsão do tempo'),
                'is_night': pick([e for e in S if e.startswith('binary_sensor.') and re.search(r'(night|noite|dark|escuro)', e)] or ['sun.sun'], 'é noite')},
    'lights': lights,
    'devices': [{'ip': 'TODO', 'room': 'TODO', 'bridge': 'BRIDGE 01', 'label': 'TODO', 'media_player': 'TODO (um destes: ' + ', '.join(mps[:6]) + ')',
                 'wallpaper': 'dist/out/wallpaper-anim.mp4'}],
    'extras': {},
}
note(f'câmeras no HA: {", ".join(cams) or "nenhuma"} (o vídeo ao vivo vem do go2rtc, não do HA)')
note('is_night = sun.sun não é binário: se ficar sun.sun, troque por um binary_sensor ou crie um template (above_horizon -> off)')
json.dump(house, sys.stdout, ensure_ascii=False, indent=2); print()
