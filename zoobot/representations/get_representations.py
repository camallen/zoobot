import os
import logging
import glob
import pandas as pd

import tensorflow as tf

from zoobot import label_metadata, schemas
from zoobot.data_utils import image_datasets
from zoobot.estimators import define_model, preprocess
from zoobot.predictions import predict_on_tfrecords, predict_on_images

import argparse

"""
Almost an exact copy of make_predictions.py, but saving the activations (features) just before the final layers, rather than making a standard prediction.
These features can then be used for other downstream tasks like anomaly detection
"""

if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)

    # useful to avoid errors on small GPU
    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        for gpu in gpus:
          tf.config.experimental.set_memory_growth(gpu, True)

    """
    List the images to make predictions on.
    If you like, use ``predict_on_images.paths_in_folder`` to easily list the images in a folder.
    """
   
    unordered_image_paths = predict_on_images.paths_in_folder('/raid/scratch/walml/galaxy_zoo/decals/png', file_format='png', recursive=True)
    file_format = 'png'

    assert len(unordered_image_paths) > 0
    assert os.path.isfile(unordered_image_paths[0])

    """
    Load the images as a tf.dataset, just as for training
    """
    initial_size = 300  # 300 for paper, from tfrecord or from png (png will be resized when loaded, before preprocessing)
    batch_size = 64  # 128 for paper, you'll need a very good GPU. 8 for debugging, 64 for RTX 2070
    raw_image_ds = image_datasets.get_image_dataset([str(x) for x in unordered_image_paths], file_format, initial_size, batch_size)

    preprocessing_config = preprocess.PreprocessingConfig(
        label_cols=[],  # no labels are needed, we're only doing predictions
        input_size=initial_size,
        make_greyscale=True,
        normalise_from_uint8=True
    )
    image_ds = preprocess.preprocess_dataset(raw_image_ds, preprocessing_config)
    # image_ds will give batches of (images, paths) when label_cols=[]

    
    """
    Define the model and load the weights.
    You must define the model exactly the same way as when you trained it.
    If you have done finetuning, use include_top=False and replace the output layers exactly as you did when training.
    For example, below is how to load the model in finetune_minimal.py.
    """
    crop_size = int(initial_size * 0.75)
    resize_size = 224  # 224 for paper
    channels = 3

    checkpoint_dir = 'data/pretrained_models/gz_decals_full_m0/in_progress'
    finetuned_dir = 'results/finetune_advanced/full/checkpoint'
    base_model = define_model.load_model(
      checkpoint_dir,
      include_top=False,
      input_size=initial_size,
      crop_size=crop_size,
      resize_size=resize_size,
      output_dim=None 
    )

    new_head = tf.keras.Sequential([
      tf.keras.layers.InputLayer(input_shape=(7,7,1280)),
      tf.keras.layers.GlobalAveragePooling2D()
    ])
    model = tf.keras.Sequential([
      tf.keras.Input(shape=(initial_size, initial_size, 1)),
      base_model,
      new_head
    ])
    define_model.load_weights(model, finetuned_dir, expect_partial=True)

    label_cols = [f'feat_{x}' for x in range(1280)]

    """
    If you're just using the full pretrained Galaxy Zoo model, without finetuning, you can just use include_top=True.
    """

    save_loc = 'data/results/dr5_b0_full_output_all.csv'
    n_samples = 1
    predict_on_images.predict(image_ds, model, n_samples, label_cols, save_loc)
    # and then run through reformat_predictions.py for easier loading
  