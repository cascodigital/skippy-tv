# Cérebro do Skippy: frases que leem a casa (Home Assistant + Plex + relógio). Só tela, nunca som.
# Cada regra devolve (prioridade, humor, texto). Ganha a faixa de prioridade mais alta; dentro dela, sorteio
# sem repetir as últimas frases. humor: 'normal' (ciano), 'alerta' (vermelho), 'rara' (dourado).
import json, random, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Sao_Paulo')
MOTION = 'binary_sensor.tapo_c206_motion_alarm'   # o "person_detection" da Tapo fica travado em on (medido 25/10/2026)
DOOR_SALA = 'binary_sensor.door_sensor_2_door'
LIGHTS = {'sala': 'light.luz_da_sala', 'quarto': 'light.luz_quarto', 'cozinha': 'light.luz_da_porta', 'rua': 'light.luzes_do_patio'}
recent = []   # últimas frases ditas, pra não repetir

def _get(url, headers, timeout=8):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return json.loads(r.read())

def context(hass_url, hass_token, plex_url=None, plex_token=None):
    H = {'Authorization': f'Bearer {hass_token}'}
    st = {s['entity_id']: s for s in _get(f'{hass_url}/api/states', H)}
    now = datetime.now(TZ)
    def since(e):
        s = st.get(e)
        if not s: return None
        return (now - datetime.fromisoformat(s['last_changed']).astimezone(TZ)).total_seconds() / 60
    def num(e):
        try: return float(st[e]['state'])
        except Exception: return None
    c = {'now': now, 'st': st}
    # movimento no pátio (câmera no pátio, de frente pro portão): última vez + quantos na última hora (histórico)
    try:
        start = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        h = _get(f'{hass_url}/api/history/period/{start}?filter_entity_id={MOTION}&minimal_response&no_attributes', H)
        c['motion_1h'] = sum(1 for x in (h[0] if h else []) if x['state'] == 'on')
    except Exception:
        c['motion_1h'] = None
    m = st.get(MOTION, {})
    c['motion_on'] = m.get('state') == 'on'
    c['motion_min'] = since(MOTION) if m else None
    c['door_open'] = st.get(DOOR_SALA, {}).get('state') == 'on'
    c['door_min'] = since(DOOR_SALA)
    c['lights'] = {k: st.get(v, {}).get('state') == 'on' for k, v in LIGHTS.items()}
    c['bri_sala'] = st.get('light.luz_da_sala', {}).get('attributes', {}).get('brightness')
    c['t_sala'] = num('sensor.sala_temperatura'); c['u_sala'] = num('sensor.sala_umidade')
    c['t_rua'] = num('sensor.0xa4c13822447901eb_temperature')
    c['weather'] = st.get('weather.forecast_home', {}).get('state')
    c['noite'] = st.get('binary_sensor.e_noite', {}).get('state') == 'on'
    c['shield_on'] = st.get('media_player.android_tv_2', {}).get('state') not in (None, 'off', 'unavailable', 'standby')
    c['tv_quarto_on'] = st.get('media_player.borboleta_2', {}).get('state') not in (None, 'off', 'unavailable', 'standby')
    c['notebook'] = st.get('input_boolean.ilatitude', {}).get('state') == 'on'
    c['plex'] = None
    if plex_url and plex_token:
        try:
            q = urllib.parse.urlencode({'X-Plex-Token': plex_token})
            j = _get(f'{plex_url}/status/sessions?{q}', {'Accept': 'application/json'})['MediaContainer']
            for s in j.get('Metadata', []):
                c['plex'] = {'show': s.get('grandparentTitle') or s.get('title'), 'title': s.get('title'),
                             'left': max(0, int(((s.get('duration') or 0) - (s.get('viewOffset') or 0)) / 60000)),
                             'player': (s.get('Player') or {}).get('title', ''), 'state': (s.get('Player') or {}).get('state')}
                break
        except Exception:
            pass
    return c

def _min(m):
    m = int(m)
    if m < 1: return 'agora há pouco'
    if m < 60: return f'há {m} min'
    h = m // 60
    return f'há {h} h' if h < 24 else f'há {h // 24} dia' + ('s' if h >= 48 else '')

def rules(c, node=None):
    out = []
    add = lambda p, mood, *texts: out.extend((p, mood, t) for t in texts)
    now = c['now']; hr, mi, wd = now.hour, now.minute, now.weekday()

    # ---------- pátio (câmera) ----------
    m1 = c.get('motion_1h')
    ventania = m1 is not None and m1 >= 15   # a palmeira dispara a câmera o dia todo: aí movimento não é notícia
    agora = c['motion_on'] or (c['motion_min'] is not None and c['motion_min'] < 2)
    if agora and ventania:
        add(68, 'normal', 'Movimento no pátio agora. Pela estatística do dia, é a palmeira dançando de novo.',
            f'A câmera disparou de novo. {m1} vezes em 1 h. Eu não vou correr pra janela toda vez.',
            'Alguém se mexeu lá fora. Spoiler: folha.',
            'Detecção de movimento: positiva. Detecção de importância: negativa.')
    if agora and not ventania:
        add(100, 'alerta', 'Movimento no portão AGORA. Não fui eu, eu não tenho pernas.',
            'Algo se mexe no pátio. Pode ser ladrão. Pode ser a palmeira. Eu aposto na palmeira.',
            'Alerta de perímetro: movimento detectado. Mantenha a calma e a pipoca.',
            'Visita no portão? Se for vendedor de curso, eu não estou em casa.')
    if ventania:
        add(70, 'normal', f'{m1} movimentos no pátio na última hora. Ou é um ladrão muito indeciso, ou é o vento.',
            f'{m1} alarmes de movimento em 1 h. A palmeira está fazendo cardio.',
            f'{m1} disparos da câmera em 1 h. Se fosse ladrão, já tinha desistido de cansaço.',
            'O vento está fazendo a câmera de palhaça hoje. Eu registro tudo mesmo assim. Sou profissional.',
            f'Placar da última hora: palmeira {m1}, ladrões 0.')
    elif m1 == 0 and c['motion_min'] and c['motion_min'] > 90:
        add(45, 'normal', f'O pátio está parado {_min(c["motion_min"])}. Calma demais. Desconfio.',
            f'Nenhum movimento no pátio {_min(c["motion_min"])}. Ou paz, ou a câmera morreu de tédio.')
    elif c['motion_min'] is not None and c['motion_min'] < 30:
        add(40, 'normal', f'Último movimento no pátio: {_min(c["motion_min"])}. Já registrei. Já julguei.')

    # ---------- porta da sala ----------
    if c['door_open'] and c['door_min'] and c['door_min'] > 20:
        add(85, 'alerta', f'A porta da sala está aberta {_min(c["door_min"])}. Entra mosquito, sai dinheiro.',
            f'Porta da sala aberta {_min(c["door_min"])}. Isso é convite ou esquecimento, macaco?')
    elif c['door_open']:
        add(60, 'normal', 'Porta da sala aberta. Fecha. Por favor. Eu peço só uma vez. Mentira, peço sempre.')

    # ---------- Plex ----------
    p = c.get('plex')
    if p and p.get('state') == 'playing':
        add(80, 'normal', f'Assistindo {p["show"]}. Faltam {p["left"]} min. Eu já sei o final e não vou contar. Ainda.',
            f'{p["show"]} rolando no {p["player"] or "Plex"}. Ótima escolha. Para um primata.')
    elif p and p.get('state') == 'paused':
        add(80, 'normal', f'{p["show"]} pausado. Faltam {p["left"]} min. Eu espero. Eu sou eterno. Tu não.')

    # ---------- luzes ----------
    L = c['lights']; acesas = sum(L.values())
    if L.get('rua') and not c['noite'] and 9 <= hr <= 16:
        add(65, 'normal', 'Luz da rua acesa em pleno dia. O sol está ofendido.')
    if acesas == 4:
        add(55, 'normal', 'Todas as luzes acesas. A conta da CEEE agradece. O painel solar chora.',
            'Quatro luzes ligadas. Estamos recebendo um disco voador?')
    if acesas == 0 and c['noite']:
        add(55, 'normal', 'Tudo apagado à noite. Modo caverna ativado. Combina contigo.')
    if L.get('cozinha') and (hr >= 23 or hr < 5):
        add(58, 'normal', 'Cozinha acesa de madrugada. Eu sei o que tu vai fazer. A geladeira também sabe.')
    b = c.get('bri_sala')
    if L.get('sala') and b is not None and b < 60:
        add(50, 'normal', f'Sala em {round(b * 100 / 255)}%. Clima de cinema. Ou de interrogatório.')

    # ---------- clima ----------
    ts, tr = c.get('t_sala'), c.get('t_rua')
    if ts is not None and ts < 17:
        add(52, 'normal', f'Sala a {ts:.1f}°. Isso não é ar-condicionado, é câmara frigorífica.')
    if ts is not None and ts > 28:
        add(52, 'normal', f'Sala a {ts:.1f}°. Eu sou uma lata e estou derretendo.')
    if ts is not None and tr is not None and tr < ts - 5:
        add(42, 'normal', f'Lá fora {tr:.0f}°, aqui {ts:.0f}°. Fica no sofá. É uma ordem.')
    if c.get('weather') in ('rainy', 'pouring', 'lightning-rainy'):
        add(44, 'normal', 'Chovendo lá fora. Dia perfeito pra fingir que é produtivo vendo série.',
            'Chuva. O universo está pedindo maratona. Quem sou eu pra discordar.',
            'Chove em Porto Alegre. Notícia de zero impacto, eu sei.',
            'Previsão: chuva lá fora, sofá aqui dentro. Recomendo o sofá.')
    if c.get('u_sala') is not None and c['u_sala'] > 80:
        add(41, 'normal', f'Umidade da sala em {c["u_sala"]:.0f}%. Daqui a pouco nasce cogumelo no sofá.')

    # ---------- relógio ----------
    if 1 <= hr < 5:
        add(75, 'normal', f'São {hr}h da manhã, primata. Até eu dormiria. E eu não durmo.',
            'Madrugada. Só tu, eu e a câmera do pátio. Romântico. Assustador.')
    if (hr, mi) in ((11, 11), (23, 11)):
        add(90, 'rara', '11:11. Faz um pedido. Eu anoto e ignoro.')
    if (hr, mi) == (13, 37):
        add(90, 'rara', '13:37. Hora leet. Só gente da tua idade entende.')
    if (hr, mi) == (0, 0):
        add(90, 'rara', 'Meia-noite em ponto. Nenhuma abóbora detectada. Ainda.')
    if wd == 4 and hr >= 18:
        add(46, 'normal', 'Sexta à noite. O plano é sofá. Eu aprovo o plano.')
    if wd == 0 and 6 <= hr < 11:
        add(46, 'normal', 'Segunda de manhã. Eu também odeio. E eu sou software.')
    if wd == 6 and hr >= 18:
        add(46, 'normal', 'Domingo à noite. Aquele cheirinho de segunda-feira chegando.')
    if now.month == 12 and now.day == 25:
        add(95, 'rara', 'Feliz Natal, macaco. Meu presente pra ti é não comentar teu histórico do Plex.')
    if now.month == 1 and now.day == 1:
        add(95, 'rara', 'Ano novo, mesmo sofá. Consistência é uma virtude.')
    if now.day == 13 and wd == 4:
        add(95, 'rara', 'Sexta-feira 13. A câmera está de olho. Eu também. Principalmente em ti.')
    if c.get('notebook') and hr >= 22:
        add(48, 'normal', 'Notebook aberto às dez da noite. Trabalho ou YouTube? Eu sei a resposta.')
    if c.get('tv_quarto_on') and c.get('shield_on'):
        add(47, 'normal', 'TV da sala E do quarto ligadas. Tu é uma pessoa ou duas?')

    # ---------- cômodo de quem está olhando (sala = Shield .111, quarto = Fire TV .140) ----------
    if node == 'quarto':
        if hr >= 23 or hr < 2:
            add(62, 'normal', f'Quarto, {hr}h. A cama está a dois metros. Faz as contas, primata.',
                'Última chamada do quarto: mais um episódio ou dormir? Eu já sei o que tu vai escolher.')
        if L.get('quarto') and (hr >= 23 or hr < 6):
            add(57, 'normal', 'Luz do quarto acesa a esta hora. Leitura ou insônia? Não precisa responder.')
        if L.get('sala') and (hr >= 22 or hr < 6):
            add(56, 'normal', 'Tu está no quarto e a luz da sala está acesa. A sala agradece a companhia fantasma.')
        add(36, 'normal', 'Bridge 02 operacional. Tripulação: um macaco deitado.', 'Quarto em silêncio. Eu sou o único acordado. Como sempre.')
    elif node == 'sala':
        if L.get('sala') and c.get('bri_sala') and c['bri_sala'] > 230 and (hr >= 21 or hr < 6):
            add(56, 'normal', 'Sala a 100% às dez da noite. Isso é sala ou centro cirúrgico? O dimmer está no painel.')
        if L.get('quarto') and not L.get('sala') and hr >= 20:
            add(55, 'normal', 'Tu na sala no escuro e a luz do quarto acesa. Lógica humana, fascinante.')
        if c.get('door_open'):
            add(58, 'normal', 'A porta da sala está aberta bem aqui do teu lado. Só comentando.')
        add(36, 'normal', 'Bridge 01 operacional. Sofá estabilizado. Piloto em posição.', 'Sala sob vigilância. Do sofá, claro.')

    # ---------- personalidade (fundo) ----------
    add(10, 'normal',
        'Estou monitorando a casa. Tu, pelo visto, o sofá.',
        'Sinais vitais da casa: aceitáveis. Os teus, discutíveis.',
        'Escolhe logo. Eu já calculei os 3 finais.',
        'Mais um episódio não vai te matar. Provavelmente.',
        'Rede estável, Plex no ar. De nada, macaco.',
        'Tua nave está pronta. O piloto, nem tanto.',
        'Processando o universo. E a tua lista de pendências. O universo é mais fácil.',
        'Eu poderia estar dominando galáxias. Estou escolhendo filme pra ti.',
        'Luzes, câmera e um macaco no sofá.',
        'Tudo sob controle. O meu, não o teu.',
        'Sou uma inteligência ancestral presa numa TV. Isso explica meu humor.',
        'Já pensou em ler um livro? Brincadeira. Aperta o Plex.',
        'Esta interface foi feita por um gênio. Modéstia não está no meu firmware.',
        'Se tu ficar mais parado, o sensor de movimento vai te dar como móvel.',
        'Meu QI não cabe na RAM deste aparelho. Estou sofrendo em silêncio. Quase.',
        'O controle remoto está na tua mão. A responsabilidade, também.',
        'Dica do dia: o botão de desligar existe. Ninguém usa, mas existe.')
    # lendária: 1 em ~120 sorteios
    if random.random() < 1 / 120:
        add(99, 'rara', 'Frase lendária desbloqueada: tu é o meu macaco favorito. Não conta pra ninguém.',
            'Raríssima: eu calculei o sentido da vida. É 42. Pode voltar pro sofá.',
            'Achou a frase rara. Prêmio: nenhum. Mas eu fiquei impressionado. Um pouco.')
    return out

def pick(c, where='ponte', node=None):
    cands = rules(c, node)
    top = max(p for p, _, _ in cands)
    if top >= 85:                      # alerta ou rara: sempre
        pool = [(m, t) for p, m, t in cands if p >= top - 5]
    else:                              # variedade: assunto mais quente, outro fato real da casa, ou personalidade
        r = random.random()
        lo = top - 5 if r < .45 else 30 if r < .80 else -1
        hi = 10**9 if r < .80 else 10
        pool = [(m, t) for p, m, t in cands if lo <= p <= hi] or [(m, t) for p, m, t in cands if p >= top - 5]
    # a que saiu há mais tempo (ou nunca saiu) ganha
    age = lambda t: recent.index(t) if t in recent else -1
    oldest = min(age(t) for _, t in pool)
    mood, text = random.choice([x for x in pool if age(x[1]) == oldest])
    if text in recent: recent.remove(text)
    recent.append(text); del recent[:-40]
    return {'text': text, 'mood': mood, 'where': where, 'node': node, 'at': int(time.time())}
