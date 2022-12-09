FROM nvidia/cuda:11.3.1-base-ubuntu20.04

ENV DEBIAN_FRONTEND noninteractive

WORKDIR /usr/src/zoobot

RUN apt-get update && apt-get -y upgrade && \
    apt-get install --no-install-recommends -y \
    build-essential \
    python3 \
    python3-pip \
    git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

# install a newer version of pip
# as we can't use the use the ubuntu package pip version (20.0.2)
# because it doesn't install the gz datasets from github correctly
# use pip (22.1.2) or higher
RUN python -m pip install --upgrade pip
RUN apt-get remove -y python3-pip
RUN ln -s /usr/local/bin/pip3 /usr/bin/pip

# install dependencies
COPY README.md .
COPY setup.py .
# container already has CUDA 11.3 so can directly install these with pip, hopefully?
RUN pip install torch == 1.12.1 torchvision == 0.13.2 torchaudio == 0.12.1
RUN pip install -U .[pytorch_gpu]

# install zoobot package code
COPY . .
RUN pip install -U -e .
