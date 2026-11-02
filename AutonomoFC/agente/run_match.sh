#!/usr/bin/env bash
# Partido en modo sincrónico (rápido) con logs.
# ./run_match.sh <out_dir> <left_script> <left_team> <right_script> <right_team> [half_time_s] [seed] [port]
# Un "script" puede ser player.py, naive.py o 'helios' (equipo helios-base compilado).
OUT=$1; LS=$2; LT=$3; RS=$4; RT=$5; HT=${6:-300}; SEED=${7:--1}; PORT=${8:-6000}
SYNCH=${SYNCH:-true}
AG=$(cd "$(dirname "$0")" && pwd)
SRV=${SRV:-/home/claude/proyecto/rcssserver/build/rcssserver}
HELIOS=${HELIOS:-/home/claude/proyecto/ext/helios-base/build/bin}
mkdir -p "$OUT"; cd "$OUT"
$SRV server::synch_mode=$SYNCH server::auto_mode=true server::half_time=$HT \
  server::port=$PORT server::coach_port=$((PORT+1)) server::olcoach_port=$((PORT+2)) \
  server::nr_extra_halfs=0 server::penalty_shoot_outs=false \
  server::game_log_dir=./ server::text_log_dir=./ server::game_log_dated=false \
  server::text_log_dated=false server::game_log_fixed=true server::text_log_fixed=true \
  server::game_log_fixed_name=match server::text_log_fixed_name=match \
  server::kick_off_wait=30 server::connect_wait=100000 server::game_over_wait=20 \
  player::random_seed=$SEED > server.out 2>&1 &
SPID=$!
sleep 1
launch() {  # script team side
  F=""; [ "$SYNCH" = "true" ] && F="--synch"
  if [ "$1" = "helios" ]; then
    (cd "$HELIOS" && LD_LIBRARY_PATH=/home/claude/proyecto/ext/local/lib ./start.sh -t "$2" -p $PORT -P $((PORT+2)) > "$OUT/$3.out" 2>&1 &)
  else
    "$AG/start_team.sh" "$1" "$2" "$OUT/agents" "$F" $PORT > "$OUT/$3.out" 2>&1 &
  fi
}
launch "$LS" "$LT" left
sleep 2
launch "$RS" "$RT" right
wait $SPID
sleep 2
pkill -f "port $PORT" 2>/dev/null
grep Score server.out
