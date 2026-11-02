#!/usr/bin/env bash
# Graba el video de demostración reproduciendo logs .rcg en el rcssmonitor oficial (Xvfb + ffmpeg).
set -e
V=$(cd "$(dirname "$0")" && pwd)
MON=/home/claude/proyecto/rcssmonitor/build/rcssmonitor
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
FONTB=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/claude-0
pgrep -x Xvfb >/dev/null || (Xvfb :99 -screen 0 1280x800x24 >/dev/null 2>&1 &) ; sleep 1

record() {  # rcg  segundos  salida  intervalo_ms
  pkill -x rcssmonitor || true; sleep 0.5
  $MON --geometry 1280x800+0+0 --show-menu-bar off --timer-interval $4 "$1" > /dev/null 2>&1 &
  sleep 4
  xdotool mousemove 69 22 click 1; sleep 0.2; xdotool mousemove 1279 799
  ffmpeg -y -loglevel error -f x11grab -draw_mouse 0 -framerate 25 -video_size 1280x800 -i :99 \
     -t $2 -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "$3"
  pkill -x rcssmonitor || true
}

card() {  # salida segundos texto_archivo
  ffmpeg -y -loglevel error -f lavfi -i color=c=0x14233c:s=1280x800:d=$2:r=25 \
    -vf "drawtext=fontfile=$FONT:expansion=none:textfile=$3:fontcolor=white:fontsize=30:line_spacing=14:x=80:y=(h-text_h)/2" \
    -c:v libx264 -preset veryfast -pix_fmt yuv420p "$1"
}

label() {  # entrada salida texto
  ffmpeg -y -loglevel error -i "$1" -vf "drawtext=fontfile=$FONTB:text='$3':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.6:boxborderw=10:x=20:y=60" \
    -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "$2"
}

cd "$V"
card c1.mp4 7 titulo.txt
card c2.mp4 9 evidencia.txt
record /home/claude/proyecto/runs/E1_s1/match.rcg 128 r1.mp4 50
label r1.mp4 s1.mp4 'E1  AutonomoFC (amarillo) vs BaselineChaser (azul)  -  velocidad 2x'
record /home/claude/proyecto/runs/E3_s1/match.rcg 72 r2.mp4 50
label r2.mp4 s2.mp4 'E3  AutonomoFC (amarillo) vs HELIOS-base (azul)  -  velocidad 2x'
card c3.mp4 7 cierre.txt
printf "file '%s'\n" c1.mp4 c2.mp4 s1.mp4 s2.mp4 c3.mp4 > list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i list.txt -c copy demo_AutonomoFC.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 demo_AutonomoFC.mp4
