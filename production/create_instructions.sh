#!/bin/bash
set +e  # stop if error

CATALOG_DIR=$1
SHARD_DIR=$2
EXPERIMENT_DIR=$3 
BASELINE=$4
TEST=$5  # expects --test or blank
PANOPTES=$6  # expects --panoptes or blank

SHARD_CONFIG=$SHARD_DIR'/shard_config.json'
INSTRUCTIONS_DIR=$EXPERIMENT_DIR/instructions

echo 'base directory: ' $EXPERIMENT_DIR
echo 'shard configuration json: ' $SHARD_CONFIG
echo 'instructions for each iteration: ' $INSTRUCTIONS_DIR 
echo --

mkdir $EXPERIMENT_DIR
mkdir $INSTRUCTIONS_DIR

# warm start is always on?
python zoobot/active_learning/create_instructions.py  --catalog-dir=$CATALOG_DIR --shard-config=$SHARD_CONFIG --instructions-dir=$INSTRUCTIONS_DIR --warm-start $BASELINE $TEST $PANOPTES
RESULT=$?
if [ $RESULT -gt 0 ]
then
    echo "Failure!" $RESULT 
    exit 1
fi
echo "Instructions succesfully created at $INSTRUCTIONS_DIR"
