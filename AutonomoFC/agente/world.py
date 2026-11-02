"""Modelo del mundo: auto-localización por banderas, balón, compañeros y rivales.

Todas las coordenadas internas están en el marco del equipo: el agente siempre
ataca hacia +x (si juega por la derecha se invierten las banderas).
"""
import math
from sexp import parse

# ---------------------------------------------------------------- banderas
FLAGS = {
    'g l': (-52.5, 0), 'g r': (52.5, 0),
    'f c': (0, 0), 'f c t': (0, -34), 'f c b': (0, 34),
    'f l t': (-52.5, -34), 'f l b': (-52.5, 34),
    'f r t': (52.5, -34), 'f r b': (52.5, 34),
    'f p l t': (-36, -20.16), 'f p l c': (-36, 0), 'f p l b': (-36, 20.16),
    'f p r t': (36, -20.16), 'f p r c': (36, 0), 'f p r b': (36, 20.16),
    'f g l t': (-52.5, -7.01), 'f g l b': (-52.5, 7.01),
    'f g r t': (52.5, -7.01), 'f g r b': (52.5, 7.01),
    'f t 0': (0, -39), 'f b 0': (0, 39), 'f l 0': (-57.5, 0), 'f r 0': (57.5, 0),
}
for d in (10, 20, 30, 40, 50):
    FLAGS['f t l %d' % d] = (-d, -39)
    FLAGS['f t r %d' % d] = (d, -39)
    FLAGS['f b l %d' % d] = (-d, 39)
    FLAGS['f b r %d' % d] = (d, 39)
for d in (10, 20, 30):
    FLAGS['f l t %d' % d] = (-57.5, -d)
    FLAGS['f l b %d' % d] = (-57.5, d)
    FLAGS['f r t %d' % d] = (57.5, -d)
    FLAGS['f r b %d' % d] = (57.5, d)


def norm_angle(a):
    while a > 180:
        a -= 360
    while a < -180:
        a += 360
    return a


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def polar(d, ang_deg):
    r = math.radians(ang_deg)
    return d * math.cos(r), d * math.sin(r)


class Obj:
    def __init__(self, pos, t, vel=(0.0, 0.0), unum=None, goalie=False):
        self.pos = pos
        self.t = t
        self.vel = vel
        self.unum = unum
        self.goalie = goalie


class World:
    def __init__(self, team):
        self.team = team
        self.side = 'l'
        self.unum = 0
        self.playmode = 'before_kick_off'
        self.time = 0
        self.see_time = -1
        # estado propio
        self.pos = (0.0, 0.0)
        self.head = 0.0          # ángulo global de la cabeza (grados)
        self.neck = 0.0          # ángulo cuello relativo al cuerpo
        self.stamina = 8000.0
        self.speed = 0.0
        self.pos_conf = 0        # nº de banderas usadas en la última estimación
        self.speed_dir = 0.0
        self._body = 0.0         # ángulo global del cuerpo
        self.pending_turn = 0.0  # giro efectivo del último comando turn
        # objetos
        self.ball = None
        self.ball_prev = None
        self.mates = []
        self.opps = []
        self.score = [0, 0]      # [nuestro, rival]

    # --------------------------------------------------------- derivados
    @property
    def body(self):
        return self._body

    def flag_table(self):
        if self.side == 'l':
            return FLAGS
        return {k: (-v[0], -v[1]) for k, v in FLAGS.items()}

    def ball_age(self):
        return self.time - self.ball.t if self.ball else 999

    def ball_pred(self, n):
        """Posición del balón dentro de n ciclos (decaimiento 0.94)."""
        if not self.ball:
            return None
        (x, y), (vx, vy) = self.ball.pos, self.ball.vel
        k = (1 - 0.94 ** n) / 0.06
        return (x + vx * k, y + vy * k)

    def advance(self):
        """Estimación por odometría cuando no hubo 'see' en este ciclo."""
        self._body = norm_angle(self._body + self.pending_turn)
        self.head = norm_angle(self._body + self.neck)
        a = math.radians(self.head + self.speed_dir)
        self.pos = (self.pos[0] + self.speed * math.cos(a),
                    self.pos[1] + self.speed * math.sin(a))
        if self.ball:
            (x, y), (vx, vy) = self.ball.pos, self.ball.vel
            self.ball.pos = (x + vx, y + vy)
            self.ball.vel = (vx * 0.94, vy * 0.94)

    # --------------------------------------------------------- mensajes
    def handle(self, raw):
        msg = parse(raw)
        if not msg or not isinstance(msg, list):
            return None
        kind = msg[0]
        if kind == 'init':
            self.side, self.unum, self.playmode = msg[1], int(msg[2]), msg[3]
        elif kind == 'sense_body':
            self._sense_body(msg)
        elif kind == 'see':
            self._see(msg)
        elif kind == 'hear':
            self._hear(msg)
        return kind

    def _sense_body(self, msg):
        self.time = int(msg[1])
        for item in msg[2:]:
            if not isinstance(item, list):
                continue
            if item[0] == 'stamina':
                self.stamina = float(item[1])
            elif item[0] == 'speed':
                self.speed = float(item[1])
                self.speed_dir = float(item[2]) if len(item) > 2 else 0.0
            elif item[0] == 'head_angle':
                self.neck = float(item[1])

    def _hear(self, msg):
        t, sender = int(msg[1]), msg[2]
        if sender == 'referee':
            pm = msg[3]
            self.playmode = pm
            if pm.startswith('goal_'):
                parts = pm.split('_')
                if parts[1] == self.side:
                    self.score[0] = int(parts[2])
                else:
                    self.score[1] = int(parts[2])

    def _see(self, msg):
        t = int(msg[1])
        self.see_time = t
        self.time = max(self.time, t)
        flags = self.flag_table()
        seen_flags = []
        raw_ball = None
        raw_players = []
        for obj in msg[2:]:
            name = obj[0]
            vals = [float(v) for v in obj[1:]]
            if len(vals) < 2:
                continue
            key = ' '.join(name)
            if name[0] in ('f', 'g') and key in flags:
                seen_flags.append((flags[key], vals[0], vals[1]))
            elif name[0] in ('b', 'B'):
                raw_ball = vals
            elif name[0] in ('p', 'P'):
                raw_players.append((name, vals))
        self._localize(seen_flags)
        if raw_ball:
            self._update_ball(raw_ball, t)
        self._update_players(raw_players, t)

    # ----------------------------------------------- auto-localización
    def _localize(self, seen):
        """Triangulación por pares de banderas: estima ángulo de cabeza y posición.

        Para dos banderas A,B con vectores relativos rA,rB (marco de la cabeza):
        theta = atan2(B-A) - atan2(rB-rA);  p = A - R(theta) rA.
        """
        if len(seen) < 2:
            return
        seen.sort(key=lambda s: s[1])
        seen = seen[:8]                          # las más cercanas = menos ruido
        sx = sy = 0.0
        for i in range(len(seen)):
            for j in range(i + 1, len(seen)):
                (A, dA, aA), (B, dB, aB) = seen[i], seen[j]
                rA, rB = polar(dA, aA), polar(dB, aB)
                gx, gy = B[0] - A[0], B[1] - A[1]
                lx, ly = rB[0] - rA[0], rB[1] - rA[1]
                if math.hypot(lx, ly) < 5:       # par mal condicionado
                    continue
                th = math.atan2(gy, gx) - math.atan2(ly, lx)
                sx += math.cos(th)
                sy += math.sin(th)
        if sx == 0 and sy == 0:
            return
        theta = math.degrees(math.atan2(sy, sx))
        px = py = wsum = 0.0
        for (F, d, a) in seen:
            vx, vy = polar(d, a + theta)
            w = 1.0 / (1.0 + d)                   # pondera banderas cercanas
            px += (F[0] - vx) * w
            py += (F[1] - vy) * w
            wsum += w
        self.head = theta
        self._body = norm_angle(theta - self.neck)
        self.pos = (px / wsum, py / wsum)
        self.pos_conf = len(seen)

    def to_global(self, d, a):
        vx, vy = polar(d, a + self.head)
        return (self.pos[0] + vx, self.pos[1] + vy)

    def _update_ball(self, vals, t):
        pos = self.to_global(vals[0], vals[1])
        vel = (0.0, 0.0)
        if len(vals) >= 4:
            # distchg/dirchg -> velocidad relativa aproximada
            d, a, dd, da = vals[:4]
            ar = math.radians(a + self.head)
            vr = dd
            vt = math.radians(da) * d
            vel = (vr * math.cos(ar) - vt * math.sin(ar),
                   vr * math.sin(ar) + vt * math.cos(ar))
        elif self.ball and 0 < t - self.ball.t <= 3:
            dt = t - self.ball.t
            vel = ((pos[0] - self.ball.pos[0]) / dt, (pos[1] - self.ball.pos[1]) / dt)
        self.ball_prev = self.ball
        self.ball = Obj(pos, t, vel)

    def _update_players(self, raws, t):
        mates, opps = [], []
        for name, vals in raws:
            pos = self.to_global(vals[0], vals[1])
            team = name[1].strip('"') if len(name) > 1 else None
            unum = int(name[2]) if len(name) > 2 else None
            goalie = len(name) > 3 and name[3] == 'goalie'
            o = Obj(pos, t, unum=unum, goalie=goalie)
            if team is None:
                # jugador lejano sin equipo: se ignora
                continue
            (mates if team == self.team else opps).append(o)
        self.mates, self.opps = mates, opps

    # --------------------------------------------------------- utilidades
    def offside_line(self):
        xs = sorted([o.pos[0] for o in self.opps], reverse=True)
        line = xs[1] if len(xs) >= 2 else 0.0
        if self.ball:
            line = max(line, self.ball.pos[0])
        return max(line, 0.0)

    def nearest_opp(self, p):
        if not self.opps:
            return None, 99.0
        o = min(self.opps, key=lambda o: dist(o.pos, p))
        return o, dist(o.pos, p)

    def our_set_piece(self):
        pm = self.playmode
        for k in ('kick_off_', 'kick_in_', 'free_kick_', 'corner_kick_',
                  'goal_kick_', 'offside_', 'indirect_free_kick_', 'foul_charge_',
                  'back_pass_', 'free_kick_fault_', 'goalie_catch_ball_'):
            if pm.startswith(k):
                letter = pm[len(k):len(k) + 1]
                # offside_X / back_pass_X / foul_charge_X: falta DEL equipo X
                if k in ('offside_', 'back_pass_', 'foul_charge_', 'free_kick_fault_'):
                    return letter != self.side
                return letter == self.side
        return False

    def their_set_piece(self):
        return self.playmode != 'play_on' and not self.our_set_piece() and \
            not self.playmode.startswith(('before_kick_off', 'goal_', 'time_over', 'half_time'))
