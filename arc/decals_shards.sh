#!/bin/bash

#SBATCH --time=12:00:00
#SBATCH --job-name=single_core
#SBATCH --ntasks-per-node=1
#SBATCH --partition=htc

module purge

module load python/anaconda3/2019.03

source activate /data/phys-zooniverse/chri5177/envs/zoobot

python /data/phys-zooniverse/chri5177/repos/zoobot/make_decals_tfrecords.py --labelled-catalog=/data/phys-zooniverse/chri5177/repos/zoobot/data/latest_labelled_catalog.csv --eval-size=3000 --shard-dir=/data/phys-zooniverse/chri5177/repos/zoobot/data/decals/shards/multilabel_256 --img-size 256
