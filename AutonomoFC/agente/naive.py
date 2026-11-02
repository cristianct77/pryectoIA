"""Equipo base 'BaselineChaser' (línea base de comparación).

Comportamiento reactivo clásico de 'kiddy soccer': todos los jugadores de
campo corren hacia el balón y, si lo alcanzan, patean a máxima potencia hacia
el arco rival. Sin formación, sin pases, sin roles. Reutiliza el modelo del
mundo para que la comparación aísle la capa de decisión.
"""
import argparse, math
from player import Agent, KICKOFF, GOAL_X
from world import dist


class Chaser(Agent):
    def step(self):
        w = self.wm
        w.pending_turn = 0.0
        pm = w.playmode
        if pm.startswith(('before_kick_off', 'goal_', 'half_time')):
            if self.moved_mode != (pm, w.time // 50):
                self.moved_mode = (pm, w.time // 50)
                self.send('(move %.1f %.1f)' % KICKOFF[w.unum])
            self.decision = 'KICKOFF_POS'
            return
        if not w.ball or w.ball_age() > 4:
            self.decision = 'SEARCH'
            self.send('(turn 60)')
            return
        if w.their_set_piece():
            self.decision = 'WAIT'
            self.turn_to(w.ball.pos)
            return
        if self.goalie and (w.ball.pos[0] > -36 or abs(w.ball.pos[1]) > 20):
            self.decision = 'GK_POSITION'
            if not self.go_to((-50, max(-5, min(5, w.ball.pos[1] * 0.2))), 60):
                self.turn_to(w.ball.pos)
            return
        if dist(w.pos, w.ball.pos) <= 1.085:
            self.decision = 'KICK_GOAL'
            self.kick_to((GOAL_X, 0), 3.0)
        else:
            self.decision = 'CHASE'
            self.go_to(w.ball.pos, 100, tol=0.3)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--team', default='BaselineChaser')
    ap.add_argument('--unum', type=int, default=1)
    ap.add_argument('--goalie', action='store_true')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=6000)
    ap.add_argument('--log-dir', default='')
    ap.add_argument('--synch', action='store_true')
    a = ap.parse_args()
    Chaser(a.team, a.unum, a.goalie, a.host, a.port, a.log_dir, synch=a.synch).run()
