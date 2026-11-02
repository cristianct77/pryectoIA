"""Agente autónomo 'AutonomoFC' para RoboCup Soccer Simulation 2D (rcssserver).

Arquitectura percepción -> modelo del mundo -> decisión -> acción, un proceso por
jugador comunicándose por UDP con el servidor.

Estrategias:
  * Formación 4-3-3 dinámica: la posición base se desplaza con el balón.
  * Rol de interceptor elegido por tiempo estimado de llegada al balón.
  * Árbol de decisión con balón: tiro > pase seguro > conducción > despeje.
  * Evaluación de pases con riesgo de intercepción por rivales.
  * Línea de fuera de juego estimada para delanteros.
  * Portero: cobertura del ángulo de tiro, atajada y saque.
  * Gestión de estamina y escaneo con el cuello.

Uso: python3 player.py --team AutonomoFC --unum 1 [--goalie] [--host 127.0.0.1]
"""
import argparse
import json
import math
import os
import random
import socket
import time

from world import World, dist, norm_angle

KICKABLE = 0.3 + 0.7 + 0.085        # player_size + kickable_margin + ball_size
CATCHABLE = 1.2
GOAL_X = 52.5

# Formación 4-3-3 (marco del equipo, balón en el centro del campo)
FORMATION = {
    1: (-50, 0),
    2: (-30, -22), 3: (-33, -8), 4: (-33, 8), 5: (-30, 22),
    6: (-15, -14), 7: (-18, 0), 8: (-15, 14),
    9: (3, -22), 10: (6, 0), 11: (3, 22),
}
KICKOFF = {
    1: (-50, 0),
    2: (-35, -20), 3: (-37, -7), 4: (-37, 7), 5: (-35, 20),
    6: (-22, -12), 7: (-24, 0), 8: (-22, 12),
    9: (-6, -20), 10: (-0.6, 0), 11: (-6, 20),
}


class Agent:
    def __init__(self, team, unum, goalie, host, port, log_dir, version=19, synch=False):
        self.synch = synch
        self.team, self.want_unum, self.goalie = team, unum, goalie
        self.wm = World(team)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
        self.addr = (host, port)
        init = '(init %s (version %d)%s)' % (team, version, ' (goalie)' if goalie else '')
        self.sock.sendto(init.encode(), self.addr)
        self.last_cycle = -1
        self.moved_mode = None
        self.set_piece_kicked_at = -100
        self.scan_dir = 1
        self.log = []
        self.log_dir = log_dir
        self.decision = ''

    # ------------------------------------------------------------ red
    def send(self, cmd):
        self.sock.sendto((cmd + '\x00').encode(), self.addr)

    def run(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(8192)
            except socket.timeout:
                if self.wm.playmode == 'time_over':
                    break
                continue
            self.addr = addr                       # el servidor responde desde otro puerto
            raw = data.decode(errors='ignore').strip('\x00')
            if raw.startswith('(error'):
                continue
            try:
                kind = self.wm.handle(raw)
            except Exception as e:             # un mensaje malformado no detiene al agente
                self.errors = getattr(self, 'errors', 0) + 1
                continue
            if kind == 'init':
                self.send('(synch_see)')
                self.send('(change_view normal)')
            elif kind == 'sense_body':
                self.drain()
                # se decide una vez por sense_body (también en tiempo detenido)
                if self.wm.see_time < self.wm.time and self.last_cycle >= 0:
                    self.wm.advance()
                self.last_cycle = self.wm.time
                t0 = time.perf_counter()
                self.step()
                if self.synch:
                    self.send('(done)')
                ms = (time.perf_counter() - t0) * 1000
                w = self.wm
                self.log.append([w.time, round(w.pos[0], 2), round(w.pos[1], 2),
                                 round(w.body, 1), w.pos_conf, self.decision,
                                 round(ms, 3), round(w.stamina)])
            if self.wm.playmode == 'time_over':
                break
        self.save_log()

    def drain(self, wait=0.004):
        """Procesa mensajes que llegan junto al sense_body (p.ej. el 'see' del ciclo)."""
        self.sock.settimeout(wait)
        try:
            while True:
                data, addr = self.sock.recvfrom(8192)
                raw = data.decode(errors='ignore').strip('\x00')
                try:
                    self.wm.handle(raw)
                except Exception:
                    pass
        except (socket.timeout, BlockingIOError):
            pass
        finally:
            self.sock.settimeout(0.5)

    def save_log(self):
        if not self.log_dir:
            return
        os.makedirs(self.log_dir, exist_ok=True)
        fn = os.path.join(self.log_dir, '%s_%s_%d.json' % (self.team, self.wm.side, self.wm.unum))
        with open(fn, 'w') as f:
            json.dump({'team': self.team, 'side': self.wm.side, 'unum': self.wm.unum,
                       'cols': ['t', 'x', 'y', 'body', 'nflags', 'dec', 'ms', 'stamina'],
                       'rows': self.log}, f)

    # ------------------------------------------------------- primitivas
    def turn_to(self, point):
        w = self.wm
        ang = math.degrees(math.atan2(point[1] - w.pos[1], point[0] - w.pos[0]))
        rel = norm_angle(ang - w.body)
        moment = max(-180, min(180, rel * (1 + 5 * w.speed)))   # compensa inercia
        w.pending_turn = moment / (1 + 5 * w.speed)
        self.send('(turn %.1f)' % moment)

    def go_to(self, point, power=100, tol=1.0):
        w = self.wm
        d = dist(w.pos, point)
        if d < tol:
            return False
        ang = math.degrees(math.atan2(point[1] - w.pos[1], point[0] - w.pos[0]))
        rel = norm_angle(ang - w.body)
        if abs(rel) > (25 if d > 5 else 40):
            self.turn_to(point)
        else:
            if w.stamina < 3000:
                power = min(power, 40)
            elif w.stamina < 4500:
                power = min(power, 70)
            self.send('(dash %d %.1f)' % (power, rel if abs(rel) > 8 else 0))
        return True

    def kick_to(self, target, speed):
        """Patea para que el balón salga hacia target con velocidad 'speed'."""
        w = self.wm
        b = w.ball
        bdir = math.degrees(math.atan2(b.pos[1] - w.pos[1], b.pos[0] - w.pos[0]))
        bd = dist(w.pos, b.pos)
        dir_diff = abs(norm_angle(bdir - w.body))
        eff = 0.027 * (1 - 0.25 * dir_diff / 180 - 0.25 * max(0, bd - 0.385) / 0.7)
        ang = math.atan2(target[1] - b.pos[1], target[0] - b.pos[0])
        speed = min(speed, 3.0)
        ax = speed * math.cos(ang) - b.vel[0]
        ay = speed * math.sin(ang) - b.vel[1]
        acc = math.hypot(ax, ay)
        power = min(100, acc / max(eff, 1e-3))
        kdir = norm_angle(math.degrees(math.atan2(ay, ax)) - w.body)
        self.send('(kick %.1f %.1f)' % (power, kdir))

    def look(self):
        """Cuello: sigue el balón si se conoce, si no barre el campo."""
        w = self.wm
        if w.ball and w.ball_age() <= 2:
            ang = math.degrees(math.atan2(w.ball.pos[1] - w.pos[1], w.ball.pos[0] - w.pos[0]))
            target = max(-90, min(90, norm_angle(ang - w.body)))
        else:
            target = w.neck + 60 * self.scan_dir
            if abs(target) > 90:
                self.scan_dir *= -1
                target = w.neck + 60 * self.scan_dir
        self.send('(turn_neck %.1f)' % (norm_angle(target - w.neck)))

    # ------------------------------------------------------- decisión
    def step(self):
        w = self.wm
        w.pending_turn = 0.0
        pm = w.playmode
        if pm == 'time_over':
            return
        if pm.startswith(('before_kick_off', 'goal_', 'half_time')):
            if self.moved_mode != (pm, w.time // 50):
                self.moved_mode = (pm, w.time // 50)
                x, y = KICKOFF[w.unum]
                self.send('(move %.1f %.1f)' % (x, y))
            self.decision = 'KICKOFF_POS'
            self.send('(turn 30)') if not w.ball else self.turn_to(w.ball.pos)
            return
        if not w.ball or w.ball_age() > 4:
            self.decision = 'SEARCH'
            self.wm.pending_turn = 60 / (1 + 5 * w.speed)
            self.send('(turn 60)')
            return

        self.look()
        if self.goalie:
            self.goalie_step()
            return

        bd = dist(w.pos, w.ball.pos)
        if bd <= KICKABLE:
            self.with_ball()
        elif self.i_am_chaser():
            self.decision = 'INTERCEPT'
            self.go_to(self.intercept_point(), 100, tol=0.4)
        else:
            self.positioning()

    # -------------------------------------------- selección de interceptor
    def reach_cycles(self, p):
        return max(0.0, dist(self.wm.pos, p) - KICKABLE) / 0.9

    def intercept_point(self):
        w = self.wm
        for n in range(0, 40):
            bp = w.ball_pred(n)
            if self.reach_cycles(bp) <= n:
                return bp
        return w.ball_pred(40)

    def i_am_chaser(self):
        w = self.wm
        # tras sacar un balón parado no puedo volver a tocarlo (doble toque)
        if w.time - self.set_piece_kicked_at < 15 and w.playmode != 'play_on':
            return False
        if w.their_set_piece():
            return False
        my_t = self.reach_cycles(self.intercept_point())
        for m in w.mates:
            if m.goalie:
                continue
            if max(0.0, dist(m.pos, w.ball.pos) - KICKABLE) / 0.9 < my_t - 1.5:
                return False
        return True

    # ---------------------------------------------------- con el balón
    def with_ball(self):
        w = self.wm
        me = w.pos
        set_piece = w.our_set_piece()
        goal_d = dist(me, (GOAL_X, 0))
        _, opp_d = w.nearest_opp(me)

        # 1) Tiro
        if goal_d < 22 and not set_piece:
            self.decision = 'SHOOT'
            self.kick_to(self.shoot_target(), 3.0)
            return
        # 2) Pase
        target, score = self.best_pass()
        pressured = opp_d < 5
        if target and (set_piece or pressured or score > 12):
            self.decision = 'PASS'
            d = dist(me, target)
            self.kick_to(target, min(3.0, 0.9 + 0.055 * d))
            if set_piece:
                self.set_piece_kicked_at = w.time
            return
        # 3) Despeje en zona defensiva bajo presión o saque sin opciones
        if set_piece or (me[0] < -25 and pressured):
            self.decision = 'CLEAR'
            side = 1 if me[1] >= 0 else -1
            self.kick_to((me[0] + 35, side * 25), 3.0)
            if set_piece:
                self.set_piece_kicked_at = w.time
            return
        # 4) Conducción
        self.decision = 'DRIBBLE'
        self.kick_to(self.dribble_target(), 0.85)

    def shoot_target(self):
        w = self.wm
        gk = [o for o in w.opps if o.goalie] or \
             sorted(w.opps, key=lambda o: dist(o.pos, (GOAL_X, 0)))[:1]
        gy = gk[0].pos[1] if gk else 0.0
        y = -5.8 if gy > 0 else 5.8
        if not gk:
            y = random.choice((-5.8, 5.8))
        return (GOAL_X, y)

    def dribble_target(self):
        w = self.wm
        me = w.pos
        base = math.atan2(-me[1] * 0.3, GOAL_X - me[0])
        best, best_s = None, -1e9
        for off in (-60, -40, -20, 0, 20, 40, 60):
            a = base + math.radians(off)
            p = (me[0] + 5 * math.cos(a), me[1] + 5 * math.sin(a))
            if abs(p[1]) > 32 or p[0] > 51:
                continue
            _, od = w.nearest_opp(p)
            s = p[0] * 0.3 + min(od, 8) * 1.2 - abs(off) * 0.02
            if s > best_s:
                best, best_s = p, s
        return best or (me[0] + 5, me[1])

    def pass_safe(self, src, dst):
        """Riesgo de intercepción: un rival que llega antes al segmento."""
        L = dist(src, dst)
        if L < 1:
            return False
        ux, uy = (dst[0] - src[0]) / L, (dst[1] - src[1]) / L
        for o in self.wm.opps:
            rx, ry = o.pos[0] - src[0], o.pos[1] - src[1]
            proj = rx * ux + ry * uy
            if proj < 0 or proj > L + 2:
                continue
            perp = abs(-rx * uy + ry * ux)
            if perp < 1.5 + 0.35 * proj:
                return False
        return True

    def best_pass(self):
        w = self.wm
        me = w.pos
        best, best_s = None, -1e9
        for m in w.mates:
            if m.unum == w.unum:
                continue
            d = dist(me, m.pos)
            if d < 5 or d > 32:
                continue
            # pase al hueco: un poco adelante del receptor
            tgt = (min(m.pos[0] + 2.0, 50), m.pos[1])
            if not self.pass_safe(me, tgt):
                continue
            _, od = w.nearest_opp(tgt)
            s = (tgt[0] - me[0]) + min(od, 10) * 1.0 - 0.1 * d
            if m.goalie or tgt[0] < -36:
                s -= 15
            if s > best_s:
                best, best_s = tgt, s
        return best, best_s

    # ------------------------------------------------------ sin balón
    def home_position(self):
        w = self.wm
        bx, by = w.ball.pos
        fx, fy = FORMATION[w.unum]
        x = fx + 0.55 * bx
        y = fy * 0.9 + 0.25 * by
        if w.unum >= 9:                           # delanteros: respetar fuera de juego
            x = min(x, w.offside_line() - 1.0)
        if w.unum in (2, 3, 4, 5):
            x = max(-46, min(x, bx + 5))           # defensas no pasan del balón
        return (max(-48, min(48, x)), max(-32, min(32, y)))

    def positioning(self):
        w = self.wm
        home = self.home_position()
        far = dist(w.pos, home)
        self.decision = 'POSITION'
        # marcaje sencillo: defensas/medios cubren al rival más peligroso cercano
        if w.ball.pos[0] < -10 and w.unum in (2, 3, 4, 5, 6, 7, 8):
            cands = [o for o in w.opps if dist(o.pos, home) < 9 and o.pos[0] < 0]
            if cands:
                o = min(cands, key=lambda o: dist(o.pos, (-GOAL_X, 0)))
                gx, gy = -GOAL_X - o.pos[0], -o.pos[1]
                n = math.hypot(gx, gy) or 1
                home = (o.pos[0] + 1.5 * gx / n, o.pos[1] + 1.5 * gy / n)
                self.decision = 'MARK'
        power = 100 if far > 8 else 60
        if not self.go_to(home, power, tol=1.5):
            self.turn_to(w.ball.pos)

    # --------------------------------------------------------- portero
    def goalie_step(self):
        w = self.wm
        b = w.ball.pos
        bd = dist(w.pos, b)
        in_box = b[0] < -36 and abs(b[1]) < 20.16
        if w.our_set_piece():
            if bd <= KICKABLE:
                self.decision = 'GK_KICK'
                tgt, _ = self.best_pass()
                side = 1 if w.pos[1] >= 0 else -1
                self.kick_to(tgt or (-15, side * 25), 3.0)
                self.set_piece_kicked_at = w.time
            elif w.playmode.startswith('goal_kick') and w.time - self.set_piece_kicked_at > 15:
                self.decision = 'GK_FETCH'
                self.go_to(b, 100, tol=0.5)
            else:
                self.decision = 'GK_WAIT'
                self.turn_to(b)
            return
        if in_box and bd < CATCHABLE and w.playmode == 'play_on':
            ang = math.degrees(math.atan2(b[1] - w.pos[1], b[0] - w.pos[0]))
            self.decision = 'GK_CATCH'
            self.send('(catch %.1f)' % norm_angle(ang - w.body))
            return
        if in_box and self.i_am_chaser() and b[0] < -40:
            self.decision = 'GK_INTERCEPT'
            self.go_to(self.intercept_point(), 100, tol=0.4)
            return
        # cobertura del ángulo: sobre la bisectriz balón-arco
        g = (-GOAL_X, 0)
        vx, vy = b[0] - g[0], b[1] - g[1]
        n = math.hypot(vx, vy) or 1
        r = max(1.5, min(5.0, 0.12 * n))
        tgt = (g[0] + r * vx / n, max(-6.5, min(6.5, g[1] + r * vy / n)))
        self.decision = 'GK_POSITION'
        if not self.go_to(tgt, 80, tol=0.7):
            self.turn_to(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--team', default='AutonomoFC')
    ap.add_argument('--unum', type=int, default=1)
    ap.add_argument('--goalie', action='store_true')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=6000)
    ap.add_argument('--log-dir', default='')
    ap.add_argument('--synch', action='store_true')
    a = ap.parse_args()
    Agent(a.team, a.unum, a.goalie, a.host, a.port, a.log_dir, synch=a.synch).run()


if __name__ == '__main__':
    main()
