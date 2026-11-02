#!/usr/bin/env bash
# Compila el servidor y el monitor oficiales de RoboCup Soccer Simulation 2D (Ubuntu 22.04/24.04).
set -e
sudo apt-get install -y build-essential cmake flex bison libboost-system-dev \
     libboost-filesystem-dev libboost-program-options-dev qtbase5-dev libfontconfig1-dev libxt-dev
mkdir -p ext && cd ext
git clone --depth 1 https://github.com/rcsoccersim/rcssserver
git clone --depth 1 https://github.com/rcsoccersim/rcssmonitor
(cd rcssserver && mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release && make -j4)
(cd rcssmonitor && mkdir -p build && cd build && cmake .. && make -j4)
echo "Servidor: ext/rcssserver/build/rcssserver"
echo "Monitor:  ext/rcssmonitor/build/rcssmonitor"
