import logging
import os

import tensorflow as tf
import pandas as pd
import matplotlib
matplotlib.use('Agg')

from zoobot.estimators import bayesian_estimator_funcs, run_estimator, input_utils, warm_start


def get_run_config(active_config):

    channels = 3

    run_config = run_estimator.RunEstimatorConfig(
        initial_size=active_config.shards.initial_size,
        final_size=active_config.shards.final_size,
        channels=channels,
        label_col='label',
        epochs=450,  # to tweak 2000 for overnight at 8 iters, 650 for 2h per iter
        train_steps=30,
        eval_steps=5,
        batch_size=128,
        min_epochs=2000,  # no early stopping, just run it overnight
        early_stopping_window=10,  # to tweak
        max_sadness=5.,  # to tweak
        log_dir=active_config.estimator_dir,
        save_freq=10,
        warm_start=active_config.warm_start
    )

    train_config = input_utils.InputConfig(
        name='train',
        tfrecord_loc=active_config.shards.train_tfrecord_loc,
        label_col=run_config.label_col,
        stratify=False,
        shuffle=True,
        repeat=True,
        stratify_probs=None,
        geometric_augmentation=True,
        photographic_augmentation=True,
        max_zoom=1.2,
        fill_mode='wrap',
        batch_size=run_config.batch_size,
        initial_size=run_config.initial_size,
        final_size=run_config.final_size,
        channels=run_config.channels,
        noisy_labels=True  # train using softmax proxy for binomial loss
    )

    eval_config = input_utils.InputConfig(
        name='eval',
        tfrecord_loc=active_config.shards.eval_tfrecord_loc,
        label_col=run_config.label_col,
        stratify=False,
        shuffle=True,
        repeat=False,
        stratify_probs=None,
        geometric_augmentation=True,
        photographic_augmentation=True,
        max_zoom=1.2,
        fill_mode='wrap',
        batch_size=run_config.batch_size,
        initial_size=run_config.initial_size,
        final_size=run_config.final_size,
        channels=run_config.channels,
        noisy_labels=False  # eval using binomial loss
    )

    model = bayesian_estimator_funcs.BayesianModel(
        learning_rate=0.001,
        optimizer=tf.train.AdamOptimizer,
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
        log_freq=10,
        image_dim=run_config.final_size  # not initial size
    )

    run_config.assemble(train_config, eval_config, model)
    return run_config
