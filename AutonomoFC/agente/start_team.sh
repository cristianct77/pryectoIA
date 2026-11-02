#!/usr/bin/env bash
# Lanza 11 jugadores: ./start_team.sh <player.py|naive.py> <EQUIPO> <log_dir> [--synch] [puerto]
SCRIPT=${1:-player.py}; TEAM=${2:-AutonomoFC}; LOG=${3:-logs}; EXTRA=$4; PORT=${5:-6000}
DIR=$(cd "$(dirname "$0")" && pwd)
python3 "$DIR/$SCRIPT" --team "$TEAM" --unum 1 --goalie --log-dir "$LOG" --port $PORT $EXTRA &
sleep 0.3
for i in $(seq 2 11); do
  python3 "$DIR/$SCRIPT" --team "$TEAM" --unum $i --log-dir "$LOG" --port $PORT $EXTRA &
  sleep 0.1
done
wait
