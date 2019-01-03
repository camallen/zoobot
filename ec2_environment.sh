# cannot be run directly, copy instead!
# need to press 'yes' for now at clone, will pipe later
sudo mkfs -t ext4 /dev/xvdb && \
mkdir root && \
sudo mount /dev/xvdb root && \
sudo chmod 777 root && cd root && \
aws s3 cp s3://galaxy-zoo/github ~/.ssh/github  && \
aws s3 cp s3://galaxy-zoo/github.pub ~/.ssh/github.pub  && \
eval "$(ssh-agent -s)"  && \
chmod 400 ~/.ssh/github  && \
ssh-add ~/.ssh/github  && \
yes | git clone git@github.com:mwalmsley/zoobot.git && \
cd zoobot && git checkout al-iter && cd ../ && \
source activate tensorflow_p36 && \
pip install -r zoobot/requirements.txt && \
pip install -e zoobot  && \
git clone https://github.com/mwalmsley/shared-astro-utilities.git && \
pip install -e shared-astro-utilities  && \
cd zoobot && \
aws s3 sync s3://galaxy-zoo/decals/fits_native data/fits_native && \
dvc pull -r s3 make_shards.dvc &&
source deactivate && \
screen -R run
