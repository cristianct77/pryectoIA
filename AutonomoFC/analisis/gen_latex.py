"""Genera tabla_resultados.tex y numeros.tex para el informe desde runs/summary.json."""
import json
import os

B = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(B, '..', 'runs', 'summary.json')))
INF = os.path.join(B, '..', 'informe')


def f(v, d=1):
    m, s = v
    return '%.*f$\\pm$%.*f' % (d, m, d, s)


rows = [('Goles', 'goals', 1), ('Posesión (\\%)', 'possession', 0),
        ('Balón en campo rival (\\%)', 'ball_in_att_half', 0), ('Tiros', 'shots', 1),
        ('Tiros al arco', 'shots_on_target', 1), ('Intentos de pase', 'pass_attempts', 0),
        ('Precisión de pase (\\%)', 'pass_accuracy', 0),
        ('Distancia/jugador (m)', 'dist_per_player', 0),
        ('Estamina mínima media', 'min_stamina_mean', 0)]
exps = [e for e in ('E1', 'E2', 'E3') if e in S]
lines = ['\\begin{table*}[t]', '\\caption{Resultados preliminares: AutonomoFC (A) frente al rival (R), media $\\pm$ desviación}',
         '\\label{tab:res}', '\\centering', '\\footnotesize', '\\setlength{\\tabcolsep}{4pt}',
         '\\begin{tabular}{@{}l' + 'cc' * len(exps) + '@{}}', '\\toprule']
hdr = ' '
for e in exps:
    hdr += ' & \\multicolumn{2}{c}{%s: %s (n=%d)}' % (e, S[e]['opp'].replace('_', '-'), S[e]['n'])
lines.append(hdr + ' \\\\')
lines.append(''.join('\\cmidrule(lr){%d-%d}' % (2 + 2 * i, 3 + 2 * i) for i in range(len(exps))))
lines.append('Métrica' + ' & A & R' * len(exps) + ' \\\\')
lines.append('\\midrule')
lines.append('Marcadores' + ''.join(' & \\multicolumn{2}{c}{%s}' % ', '.join(S[e]['scores']) for e in exps) + ' \\\\')
for name, k, d in rows:
    lines.append(name + ''.join(' & %s & %s' % (f(S[e]['us'][k], d), f(S[e]['them'][k], d)) for e in exps) + ' \\\\')
lines.append('\\midrule')
lines.append('\\multicolumn{%d}{@{}l}{\\emph{Métricas internas de AutonomoFC}} \\\\' % (1 + 2 * len(exps)))
for name, k, d in [('Error localización P50 / P90 (m)', None, 2), ('Error orientación P50 ($^\\circ$)', 'body_err_p50', 1),
                   ('Tiempo de decisión medio / P99 (ms)', None, 2)]:
    cells = ''
    for e in exps:
        u = S[e]['us']
        if name.startswith('Error loc'):
            v = '%.2f / %.2f' % (u['loc_err_p50'][0], u['loc_err_p90'][0])
        elif name.startswith('Tiempo'):
            v = '%.2f / %.2f' % (u['think_ms_mean'][0], u['think_ms_p99'][0])
        else:
            v = '%.1f' % u[k][0]
        cells += ' & \\multicolumn{2}{c}{%s}' % v
    lines.append(name + cells + ' \\\\')
lines += ['\\bottomrule', '\\end{tabular}', '\\vspace{-1em}', '\\end{table*}']
open(os.path.join(INF, 'tabla_resultados.tex'), 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
