#!/usr/bin/env bash
# Experimentos de evaluación (modo sincrónico, partidos completos de 2x3000 ciclos)
AG=$(cd "$(dirname "$0")" && pwd); R=$AG/../runs
# E1: AutonomoFC (izq) vs BaselineChaser (der), 5 semillas
for s in 1 2 3 4 5; do $AG/run_match.sh $R/E1_s$s player.py AutonomoFC naive.py BaselineChaser 300 $s 6100; done
# E2: lados invertidos, 3 semillas
for s in 1 2 3; do $AG/run_match.sh $R/E2_s$s naive.py BaselineChaser player.py AutonomoFC 300 $s 6100; done
