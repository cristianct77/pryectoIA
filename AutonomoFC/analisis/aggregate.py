"""Agrega métricas de todos los partidos y genera figuras/tablas para el informe."""
import glob
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from metrics import match_metrics

RUNS = os.path.join(os.path.dirname(__file__), '..', 'runs')
OUT = os.path.join(os.path.dirname(__file__), '..', 'informe', 'fig')
os.makedirs(OUT, exist_ok=True)

EXPS = {'E1': 'vs BaselineChaser (izq.)', 'E2': 'vs BaselineChaser (der.)', 'E3': 'vs HELIOS-base'}


def ours(m):
    return 'l' if m['l']['team'] == 'AutonomoFC' else 'r'


rows = {}
for exp in EXPS:
    for d in sorted(glob.glob(os.path.join(RUNS, exp + '_s*'))):
        if not os.path.exists(os.path.join(d, 'match.rcg')):
            continue
        m = match_metrics(d)
        json.dump(m, open(os.path.join(d, 'metrics.json'), 'w'), indent=1, default=float)
        rows.setdefault(exp, []).append(m)

KEYS = ['goals', 'possession', 'ball_in_att_half', 'shots', 'shots_on_target', 'pass_attempts',
        'pass_accuracy', 'dist_per_player', 'min_stamina_mean', 'loc_err_p50', 'loc_err_p90',
        'body_err_p50', 'think_ms_mean', 'think_ms_p99', 'offsides', 'fouls']
summary = {}
for exp, ms in rows.items():
    s = {}
    for who in ('us', 'them'):
        vals = {}
        for k in KEYS:
            arr = [m[ours(m) if who == 'us' else ('r' if ours(m) == 'l' else 'l')][k] for m in ms]
            vals[k] = (float(np.mean(arr)), float(np.std(arr)))
        s[who] = vals
    s['n'] = len(ms)
    s['scores'] = ['%d-%d' % (m[ours(m)]['goals'], m['r' if ours(m) == 'l' else 'l']['goals']) for m in ms]
    s['opp'] = ms[0]['r' if ours(ms[0]) == 'l' else 'l']['team']
    dec = {}
    for m in ms:
        for k, v in m[ours(m)]['decisions'].items():
            dec[k] = dec.get(k, 0) + v
    s['decisions'] = dec
    summary[exp] = s
json.dump(summary, open(os.path.join(RUNS, 'summary.json'), 'w'), indent=1)
for exp, s in summary.items():
    print(exp, s['n'], s['scores'])
    for k in KEYS:
        print('  %-18s us %8.2f ±%6.2f | them %8.2f ±%6.2f' % (k, *s['us'][k], *s['them'][k]))

# ------------------------------------------------------------------ figuras
plt.rcParams.update({'font.size': 8, 'font.family': 'serif', 'axes.spines.top': False,
                     'axes.spines.right': False})
C_US, C_THEM = '#1f5fa8', '#c0504d'
exps = [e for e in EXPS if e in summary]
metrics = [('goals', 'Goles'), ('possession', 'Posesión (%)'), ('shots', 'Tiros'),
           ('pass_accuracy', 'Precisión pase (%)')]
fig, axes = plt.subplots(1, 4, figsize=(7.0, 1.75))
x = np.arange(len(exps))
for ax, (k, title) in zip(axes, metrics):
    us = [summary[e]['us'][k] for e in exps]
    th = [summary[e]['them'][k] for e in exps]
    ax.bar(x - 0.2, [u[0] for u in us], 0.38, yerr=[u[1] for u in us], color=C_US,
           label='AutonomoFC', capsize=2, error_kw={'lw': 0.6})
    ax.bar(x + 0.2, [t[0] for t in th], 0.38, yerr=[t[1] for t in th], color=C_THEM,
           label='Rival', capsize=2, error_kw={'lw': 0.6})
    ax.set_xticks(x)
    ax.set_xticklabels(exps)
    ax.set_title(title, fontsize=8)
    ax.tick_params(length=2)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, fontsize=7, loc='upper center', ncol=2, bbox_to_anchor=(0.5, 1.02))
fig.tight_layout(pad=0.4, rect=(0, 0, 1, 0.9))
fig.savefig(os.path.join(OUT, 'resultados.pdf'))

# CDF error de localización (todos los partidos E1)
errs = []
import math, re
sys.path.insert(0, os.path.dirname(__file__))
from metrics import parse_rcg, team_frame
for d in sorted(glob.glob(os.path.join(RUNS, 'E1_s*'))):
    frames, _, _ = parse_rcg(os.path.join(d, 'match.rcg'))
    truth = {}
    for t, b, pl in frames:
        for k, p in pl.items():
            truth[(t,) + k] = (p['x'], p['y'])
    for fn in glob.glob(os.path.join(d, 'agents', 'AutonomoFC_l_*.json')):
        dd = json.load(open(fn))
        for r in dd['rows']:
            tr = truth.get((r[0], 'l', dd['unum']))
            if tr and r[5] != 'KICKOFF_POS':
                errs.append(math.hypot(r[1] - tr[0], r[2] - tr[1]))
errs = np.sort(np.array(errs))
fig, ax = plt.subplots(figsize=(3.4, 1.6))
ax.plot(errs, np.linspace(0, 1, len(errs)), color=C_US, lw=1.2)
for q in (0.5, 0.9):
    v = errs[int(q * len(errs))]
    ax.axvline(v, color='0.6', lw=0.6, ls='--')
    ax.text(v + 0.02, q - 0.12, 'P%d=%.2f m' % (q * 100, v), fontsize=6.5)
ax.set_xlim(0, 1.2)
ax.set_xlabel('Error de posición estimada (m)')
ax.set_ylabel('Fracción acumulada')
fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(OUT, 'localizacion.pdf'))
print('n muestras localización', len(errs))
