#!/bin/bash
#source /home/ax/opt/anaconda3/etc/profile.d/conda.sh
#conda activate py3
cd $(date +%F)
sudo sysctl -w net.core.rmem_max=2500000
../ipfs repo gc
../ipfs daemon --enable-gc > $(date +%F)_daemon.txt 2>&1 &
sleep 600
../ipfs log level dht warn
python ../record.py
killall ipfs
