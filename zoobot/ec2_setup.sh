#!/bin/bash

# Set up fresh EC2 instance ready for shard creation

# Running on Deep Learning AMI or Miniconda with Python 3

# run beforehand 'aws configure' and add secrets. Not in this script, obviously.

sudo yum update

sudo yum install git
git clone https://github.com/RustyPanda/zoobot.git
git checkout bayesian-cnn

conda update -n base condaß
conda create --name zoobot python=3.6
source activate zoobot
pip install -r zoobot/requirements.txt  # needs C compiler for photutils, disabled for now

aws s3 cp s3://galaxy-zoo/decals/panoptes_predictions.csv /home/ec2-user/panoptes_predictions_original.csv
aws s3 sync s3://galaxy-zoo/decals/fits_native /home/ec2-user/fits_native  # gets everything
python zoobot/zoobot/update_catalog_fits_loc.py
python zoobot/zoobot/active_learning/run_active_learning.py  # shards only, use comments


