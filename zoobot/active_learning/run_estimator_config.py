import logging
import os
import copy
import shutil
import time
from functools import partial
from typing import List

import tensorflow as tf
import pandas as pd
import matplotlib
import numpy as np

from zoobot.estimators import bayesian_estimator_funcs, input_utils, losses


class FixedEstimatorParams():
    def __init__(self, initial_size, final_size, questions, label_cols, batch_size):
        self.initial_size=initial_size
        self.final_size = final_size
        self.questions=questions
        self.label_cols=label_cols
        self.batch_size=batch_size

    # TODO move to shared utilities
    def asdict(self):
        excluded_keys = ['__dict__', '__doc__', '__module__', '__weakref__']
        return dict([(key, value) for (key, value) in self.__dict__.items() if key not in excluded_keys])




class RunEstimatorConfig():
    def __init__(
            self,
            initial_size,
            final_size,
            label_cols: List,
            channels=3,
            epochs=250,  # rely on earlystopping callback
            train_steps=30,
            eval_steps=3,
            batch_size=128,
            min_epochs=0,
            patience=15,
            log_dir='runs/default_run_{}'.format(time.time()),
            save_freq=10,
            warm_start=True,
            warm_start_settings=None
    ):  # TODO refactor for consistent order
        self.initial_size = initial_size
        self.final_size = final_size
        self.channels = channels
        self.label_cols = label_cols
        self.epochs = epochs
        self.train_batches = train_steps
        self.eval_batches = eval_steps
        self.batch_size = batch_size
        self.log_dir = log_dir
        self.save_freq = save_freq
        self.warm_start = warm_start
        self.patience = patience
        self.min_epochs = min_epochs
        self.train_config = None
        self.eval_config = None
        self.model = None
        self.warm_start_settings = warm_start_settings

    
    def assemble(self, train_config, eval_config, model):
        self.train_config = train_config
        self.eval_config = eval_config
        self.model = model
        assert self.is_ready_to_train()

    def is_ready_to_train(self):
        # TODO can make this check much more comprehensive
        return (self.train_config is not None) and (self.eval_config is not None)

    def log(self):
        logging.info('Parameters used: ')
        for config_object in [self, self.train_config, self.eval_config, self.model]:
            for key, value in config_object.asdict().items():
                logging.info('{}: {}'.format(key, value))

    # TODO move to shared utilities
    def asdict(self):
        excluded_keys = ['__dict__', '__doc__', '__module__', '__weakref__']
        return dict([(key, value) for (key, value) in self.__dict__.items() if key not in excluded_keys])


    # don't decorate, this is session creation point
    def run_estimator(self):
        """
        Train and evaluate an estimator.
        `self` may well be provided by default_estimator_params.py`

        TODO save every n epochs 
        TODO enable early stopping
        TODO enable use with tf.serving
        TODO enable logging hooks?

        Args:
            self (RunEstimatorConfig): parameters controlling both estimator and train/test procedure

        Returns:
            None
        """
        if not self.warm_start:  # don't try to load any existing models
            if os.path.exists(self.log_dir):
                shutil.rmtree(self.log_dir)

        train_dataset = input_utils.get_input(config=self.train_config)
        test_dataset = input_utils.get_input(config=self.eval_config)

        callbacks = [
            tf.keras.callbacks.TensorBoard(
                log_dir=os.path.join(self.log_dir, 'tensorboard'),
                histogram_freq=3,
                write_images=True,
                profile_batch=0  # i.e. disable profiling
            ),
            tf.keras.callbacks.ModelCheckpoint(
                filepath=os.path.join(self.log_dir, 'models'),
                save_weights_only=True),
            bayesian_estimator_funcs.UpdateStepCallback(
                batch_size=self.batch_size
            ),
            tf.keras.callbacks.EarlyStopping(restore_best_weights=True, patience=self.patience),
            bayesian_estimator_funcs.UpdateStepCallback(
                batch_size=self.batch_size
            )
        ]

        # https://www.tensorflow.org/tensorboard/scalars_and_keras
        fit_summary_writer = tf.summary.create_file_writer(os.path.join(self.log_dir, 'manual_summaries'))
        with fit_summary_writer.as_default():

            # for debugging
            # self.model.run_eagerly = True
            # https://www.tensorflow.org/api_docs/python/tf/keras/Model

            self.model.fit(
                train_dataset,
                validation_data=test_dataset,
                validation_steps=int(1000/self.batch_size),
                epochs=self.epochs,
                callbacks=callbacks,
            )

        logging.info('All epochs completed - finishing gracefully')
        self.model.save_weights(os.path.join(self.log_dir, 'models/final'))
        return self.model


# batch size changed from 256 for now, for my poor laptop
# can override less rarely specified RunEstimatorConfig defaults with **kwargs if you like
def get_run_config(initial_size, final_size, warm_start, log_dir, train_records, eval_records, epochs, questions, label_cols, batch_size, **kwargs):

    # save these to get back the same run config across iterations? But hpefully in instructions already, or can be calculated...
    # args = {
    #     'initial_size': initial_size,
    #     'final_size': final_size,
    #     'warm_start':
    # }
    run_config = RunEstimatorConfig(
        initial_size=initial_size,
        final_size=final_size,
        label_cols=label_cols,
        epochs=epochs,  # to tweak 2000 for overnight at 8 iters, 650 for 2h per iter
        log_dir=log_dir,
        warm_start=warm_start,
        batch_size=batch_size
    )

    train_config = get_train_config(train_records, run_config.label_cols, run_config.batch_size, run_config.initial_size, run_config.final_size, run_config.channels)

    eval_config = get_eval_config(eval_records, run_config.label_cols, run_config.batch_size, run_config.initial_size, run_config.final_size, run_config.channels)

    model = get_model(label_cols, questions, run_config.final_size)

    run_config.assemble(train_config, eval_config, model)
    return run_config

MAX_SHIFT = 30
MAX_SHEAR = np.pi/4.

def get_train_config(train_records, label_cols, batch_size, initial_size, final_size, channels):
    # tiny func, refactored for easy reuse
    train_config = input_utils.InputConfig(
        name='train',
        tfrecord_loc=train_records,
        label_cols=label_cols,
        stratify=False,
        shuffle=True,
        repeat=False,  # Changed from True for keras, which understands to restart a dataset
        stratify_probs=None,
        geometric_augmentation=True,
        photographic_augmentation=True,
        # zoom=(2., 2.2),  # BAR MODE
        zoom=(1.15, 1.35),  # SMOOTH MODE
        max_shift=MAX_SHIFT,
        max_shear=MAX_SHEAR,
        contrast_range=(0.98, 1.02),
        batch_size=batch_size,
        initial_size=initial_size,
        final_size=final_size,
        channels=channels,
        greyscale=True,
        zoom_central=False  # SMOOTH MODE
        # zoom_central=True  # BAR MODE
    )
    return train_config


def get_eval_config(eval_records, label_cols, batch_size, initial_size, final_size, channels):
    # tiny func, refactored for easy reuse
    eval_config = input_utils.InputConfig(
        name='eval',
        tfrecord_loc=eval_records,
        label_cols=label_cols,
        stratify=False,
        shuffle=False,  # see above
        repeat=False,
        stratify_probs=None,
        geometric_augmentation=True,
        photographic_augmentation=True,
        # zoom=(2., 2.2),  # BAR MODE
        zoom=(1.1, 1.3),  # SMOOTH MODE
        max_shift=MAX_SHIFT,
        max_shear=MAX_SHEAR,
        contrast_range=(0.98, 1.02),
        batch_size=batch_size,
        initial_size=initial_size,
        final_size=final_size,
        channels=channels,
        greyscale=True,
        zoom_central=False  # SMOOTH MODE
        # zoom_central=True  # BAR MODE
    )
    return eval_config

def get_model(label_cols, questions, final_size):
    schema = losses.Schema(label_cols, questions)
    model = bayesian_estimator_funcs.BayesianModel(
        image_dim=final_size, # not initial size
        output_dim=len(label_cols),  # will predict all label columns, in this order
        schema=schema,
        conv1_filters=32,
        conv1_kernel=3,
        conv2_filters=64,
        conv2_kernel=3,
        conv3_filters=128,
        conv3_kernel=3,
        dense1_units=128,
        dense1_dropout=0.5,
        predict_dropout=0.5,  # change this to calibrate
        regression=True,  # important!
        log_freq=10
    )  # WARNING will need to be updated for multiquestion

    model.compile(
        loss=lambda x, y: losses.multiquestion_loss(x, y, question_index_groups=schema.question_index_groups),
        optimizer=tf.keras.optimizers.Adam(),
        metrics=[bayesian_estimator_funcs.CustomMSEByColumn(name=q.text, start_col=start_col, end_col=end_col) for q, (start_col, end_col) in schema.named_index_groups.items()]
    )
    return model