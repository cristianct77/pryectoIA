#!/usr/bin/env bash
# E3: AutonomoFC vs helios-base (equipo de referencia de la comunidad), 3 semillas
AG=$(cd "$(dirname "$0")" && pwd); R=$AG/../runs
for s in 1 2 3; do $AG/run_match.sh $R/E3_s$s player.py AutonomoFC helios HELIOS_base 300 $s 6300; done
