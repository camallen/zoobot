#!/usr/bin/env bash
export PROJECT_ID=$(gcloud config list project --format "value(core.project)")
export IMAGE_REPO_NAME=zoobot
export IMAGE_TAG=latest
export IMAGE_URI=gcr.io/$PROJECT_ID/$IMAGE_REPO_NAME:$IMAGE_TAG

docker build -f Dockerfile -t $IMAGE_URI ./

# first time only
# gcloud auth configure-docker  

# docker push $IMAGE_URI

# https://cloud.google.com/blog/products/ai-machine-learning/introducing-deep-learning-containers-consistent-and-portable-environments
# https://cloud.docker.com/u/mikewalmsley/repository/docker/mikewalmsley/zoobot

cd zoobot && git pull && cd ../ && cp zoobot/Dockerfile Dockerfile && docker build -f Dockerfile -t $IMAGE_URI ./

docker rm $(docker ps -aq)

docker run -d \
    --name offline \
    -m 8GB \
    -v /Data/repos/zoobot/data:/home/zoobot/data \
    -v /Data/repos/zoobot/data/experiments/multilabel:/home/experiments/multilabel $IMAGE_URI  \
    python offline_training.py --train-dir /home/zoobot/data/decals/shards/multilabel/train --eval-dir /home/zoobot/data/decals/shards/multilabel/eval --experiment-dir /home/experiments/multilabel --epochs 10 --test
