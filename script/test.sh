#!/bin/bash
source /home/ax/opt/anaconda3/etc/profile.d/conda.sh
conda activate py3
ipfs repo gc
ipfs daemon --enable-gc &
cd /home/ax/workspace/IPFS/test_1105
sudo sysctl -w net.core.rmem_max=2500000
mkdir $(date +%F)
python run.py
killall ipfs
bash test_hop.sh
