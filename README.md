# AutonomoFC — agente para RoboCup Soccer Simulation 2D

Equipo de 11 agentes autónomos en Python 3 (sin dependencias externas) para el
servidor oficial `rcssserver` (probado con 19.0.0).

## Estructura

```
scripts/instalar_servidor.sh compila rcssserver y rcssmonitor
agente/
  sexp.py                  parser de S-expresiones del protocolo
  world.py                 modelo del mundo: auto-localización por banderas, balón, jugadores
  player.py                agente AutonomoFC (formación, interceptor, tiro/pase/conducción, portero)
  naive.py                 equipo línea base BaselineChaser
  start_team.sh            lanza 11 jugadores de un equipo
  run_match.sh             partido completo en modo sincrónico con logs
  run_experiments.sh       experimentos E1 y E2
  run_experiments_helios.sh  experimento E3 (requiere helios-base compilado)
analisis/
  metrics.py               métricas desde .rcg + logs de agentes
  aggregate.py             resumen y figuras del informe
  gen_latex.py             tabla de resultados para LaTeX
resultados/                métricas por partido (metrics.json) y summary.json
video/make_video.sh        grabación del video con rcssmonitor + Xvfb + ffmpeg
informe/                   fuente LaTeX (IEEEtran) del informe
```

## Uso rápido

1. Compilar el servidor: https://github.com/rcsoccersim/rcssserver (CMake).
2. Partido en tiempo real (con monitor abierto):
   ```
   rcssserver &
   rcssmonitor &
   ./agente/start_team.sh player.py AutonomoFC logs &
   ./agente/start_team.sh naive.py BaselineChaser logs &
   ```
   y pulsar *Kick Off* en el monitor (o arrancar el servidor con `server::auto_mode=true`).
3. Partido rápido con logs y métricas:
   ```
   SRV=/ruta/a/rcssserver ./agente/run_match.sh runs/demo player.py AutonomoFC naive.py BaselineChaser
   python3 analisis/metrics.py runs/demo
   ```
