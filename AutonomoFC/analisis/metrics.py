"""Cálculo de métricas a partir del log del servidor (.rcg) y de los logs de agentes.

Uso: python3 metrics.py <carpeta_partido> [--json salida.json]
"""
import glob
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

PLAYER_RE = re.compile(
    r'\(\((l|r) (\d+)\) (\d+) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+)(.*?)\(c ([\d ]+)\)\)')
BALL_RE = re.compile(r'\(\(b\) (\S+) (\S+) (\S+) (\S+)\)')
STAM_RE = re.compile(r'\(s (\S+) (\S+) (\S+) (\S+)\)')


def parse_rcg(path):
    frames, modes, teams = [], [], None
    for line in open(path, errors='ignore'):
        if line.startswith('(show '):
            t = int(line.split()[1])
            b = BALL_RE.search(line)
            ball = tuple(map(float, b.groups()))
            players = {}
            for m in PLAYER_RE.finditer(line):
                side, unum = m.group(1), int(m.group(2))
                x, y, vx, vy, body, neck = map(float, m.group(5, 6, 7, 8, 9, 10))
                st = STAM_RE.search(m.group(11))
                stamina = float(st.group(1)) if st else 0.0
                counts = list(map(int, m.group(12).split()))
                players[(side, unum)] = dict(x=x, y=y, vx=vx, vy=vy, body=body, neck=neck,
                                             stamina=stamina, kick=counts[0], dash=counts[1],
                                             state=int(m.group(4), 16))
            frames.append((t, ball, players))
        elif line.startswith('(playmode '):
            _, t, mode = line.strip('()\n').split()
            modes.append((int(t), mode))
        elif line.startswith('(team '):
            p = line.strip('()\n').split()
            teams = dict(left=p[2], right=p[3], score_l=int(p[4]), score_r=int(p[5]))
    return frames, modes, teams


def team_frame(side, x, y):
    return (x, y) if side == 'l' else (-x, -y)


def match_metrics(folder):
    frames, modes, teams = parse_rcg(os.path.join(folder, 'match.rcg'))
    # modo de juego vigente en cada frame
    mode_at = []
    mi, cur = 0, 'before_kick_off'
    for (t, ball, pl) in frames:
        while mi < len(modes) and modes[mi][0] <= t:
            cur = modes[mi][1]
            mi += 1
        mode_at.append(cur)

    res = {s: defaultdict(float) for s in ('l', 'r')}
    poss_cycles = Counter()
    last_holder = None
    kicks = []                               # (t, side, unum, ball_after)
    dist_run = defaultdict(float)
    prev = None
    min_stamina = defaultdict(lambda: 9e9)
    for i, (t, ball, pl) in enumerate(frames):
        bx, by = ball[0], ball[1]
        play = mode_at[i] == 'play_on'
        # posesión (último jugador en zona de control del balón)
        near = [(math.hypot(p['x'] - bx, p['y'] - by), k) for k, p in pl.items()]
        if near:
            d, k = min(near)
            if d < 1.2:
                last_holder = k
        if play and last_holder:
            poss_cycles[last_holder[0]] += 1
        if play:
            res['l']['ball_att_half'] += bx > 0
            res['r']['ball_att_half'] += bx < 0
            res['l']['ball_x_sum'] += bx
            res['r']['ball_x_sum'] += -bx
            res['l']['play_cycles'] += 1
            res['r']['play_cycles'] += 1
        if prev:
            _, pball, ppl = prev
            for k, p in pl.items():
                if k in ppl:
                    q = ppl[k]
                    step = math.hypot(p['x'] - q['x'], p['y'] - q['y'])
                    if step < 3:
                        dist_run[k] += step
                    if p['kick'] > q['kick'] and math.hypot(q['x'] - pball[0], q['y'] - pball[1]) < 1.25:
                        kicks.append((t, k[0], k[1], ball, mode_at[i]))
        for k, p in pl.items():
            if p['stamina'] > 0:
                min_stamina[k] = min(min_stamina[k], p['stamina'])
        prev = (t, ball, pl)

    # pases, intercepciones y tiros a partir de la secuencia de patadas
    for idx, (t, side, unum, ball, mode) in enumerate(kicks):
        r = res[side]
        r['kicks'] += 1
        bx, by, vx, vy = ball
        x, y = team_frame(side, bx, by)
        vx, vy = (vx, vy) if side == 'l' else (-vx, -vy)
        speed = math.hypot(vx, vy)
        is_shot = False
        if x > 30 and vx > 0.5 and speed > 1.6:
            ty = y + vy * (52.5 - x) / vx
            if abs(ty) < 12:
                is_shot = True
                r['shots'] += 1
                r['shots_on_target'] += abs(ty) < 7.01
        nxt = None
        for j in range(idx + 1, len(kicks)):
            if kicks[j][1:3] != (side, unum):
                nxt = kicks[j]
                break
            else:
                break                          # conducción: mismo jugador vuelve a tocar
        if is_shot or nxt is None or (nxt and nxt[0] - t > 60):
            continue
        if nxt[1] == side:
            r['passes_ok'] += 1
        else:
            r['passes_lost'] += 1

    ret = {'teams': teams, 'cycles': frames[-1][0] if frames else 0}
    total_poss = sum(poss_cycles.values()) or 1
    mode_counts = Counter(m for _, m in modes)
    for s in ('l', 'r'):
        r = res[s]
        name = teams['left'] if s == 'l' else teams['right']
        att = r['passes_ok'] + r['passes_lost']
        pc = r['play_cycles'] or 1
        runs = [v for k, v in dist_run.items() if k[0] == s]
        stams = [v for k, v in min_stamina.items() if k[0] == s and v < 9e9]
        other = 'r' if s == 'l' else 'l'
        ret[s] = dict(
            team=name,
            goals=teams['score_l'] if s == 'l' else teams['score_r'],
            possession=100.0 * poss_cycles[s] / total_poss,
            ball_in_att_half=100.0 * r['ball_att_half'] / pc,
            mean_ball_x=r['ball_x_sum'] / pc,
            kicks=int(r['kicks']),
            shots=int(r['shots']), shots_on_target=int(r['shots_on_target']),
            pass_attempts=int(att), passes_ok=int(r['passes_ok']),
            pass_accuracy=100.0 * r['passes_ok'] / att if att else 0.0,
            dist_per_player=sum(runs) / max(1, len(runs)),
            min_stamina_mean=sum(stams) / max(1, len(stams)),
            offsides=sum(c for m, c in mode_counts.items() if m == 'offside_' + s),
            fouls=sum(c for m, c in mode_counts.items()
                      if m in ('foul_charge_' + s, 'back_pass_' + s, 'free_kick_fault_' + s,
                               'catch_fault_' + s, 'foul_push_' + s)),
            corners=mode_counts.get('corner_kick_' + s, 0),
        )
    # métricas internas de los agentes (localización, tiempo de decisión)
    truth = {}
    for (t, ball, pl) in frames:
        for k, p in pl.items():
            truth[(t,) + k] = (p['x'], p['y'], p['body'])
    for s in ('l', 'r'):
        name = ret[s]['team']
        errs, aerrs, ms, decs = [], [], [], Counter()
        for fn in glob.glob(os.path.join(folder, 'agents', '%s_%s_*.json' % (name, s))):
            d = json.load(open(fn))
            for row in d['rows']:
                t, x, y, body, nf, dec, dt, st = row
                decs[dec] += 1
                ms.append(dt)
                tr = truth.get((t, s, d['unum']))
                if tr and dec not in ('KICKOFF_POS',):
                    tx, ty = team_frame(s, tr[0], tr[1])
                    tb = tr[2] if s == 'l' else (tr[2] + 180)
                    errs.append(math.hypot(x - tx, y - ty))
                    aerrs.append(abs((body - tb + 180) % 360 - 180))
        errs.sort(); aerrs.sort(); ms.sort()

        def pct(a, q):
            return a[min(len(a) - 1, int(q * len(a)))] if a else float('nan')
        ret[s].update(loc_err_mean=sum(errs) / max(1, len(errs)), loc_err_p50=pct(errs, .5),
                      loc_err_p90=pct(errs, .9), body_err_p50=pct(aerrs, .5),
                      think_ms_mean=sum(ms) / max(1, len(ms)), think_ms_p99=pct(ms, .99),
                      decisions=dict(decs.most_common()))
    return ret


if __name__ == '__main__':
    out = match_metrics(sys.argv[1])
    print(json.dumps(out, indent=1, default=float))
    if '--json' in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
