import logging
import os
import shutil
from functools import partial

import tensorflow as tf
from zoobot.estimators import input_utils


def train_input(params):
    mode = 'train'
    return input_utils.input(
        tfrecord_loc=params['train_loc'], size=params['image_dim'], name=mode, batch_size=params['batch_size'], stratify=params['train_stratify'])


def eval_input(params):
    mode = 'test'
    return input_utils.input(
        tfrecord_loc=params['test_loc'], size=params['image_dim'], name=mode, batch_size=params['batch_size'], stratify=params['eval_stratify'])


def run_estimator(model_fn, params):
    """
    Train and evaluate an estimator

    Args:
        model_fn (function): estimator model function
        params (dict): parameters controlling both estimator and train/test procedure

    Returns:
        None
    """

    if os.path.exists(params['log_dir']):
        shutil.rmtree(params['log_dir'])

    # Create the Estimator
    model_fn_partial = partial(model_fn, params=params)
    estimator = tf.estimator.Estimator(
        model_fn=model_fn_partial, model_dir=params['log_dir'])

    # can't move out of run_estimator, uses closure to avoid arguments
    # def serving_input_receiver_fn():
    #     """An input receiver that expects a serialized tf.Example."""
    #     serialized_tf_example = tf.placeholder(dtype=tf.string,
    #                                            name='input_example_tensor')
    #     receiver_tensors = {'examples': serialized_tf_example}
    #     feature_spec = input_utils.matrix_feature_spec(size=params['image_dim'])
    #     features = tf.parse_example(serialized_tf_example, feature_spec)
    #     # update each image with the preprocessing from input_utils
    #     # outputs {x: new images}
    #     new_features = input_utils.preprocess_batch(features['matrix'], size=params['image_dim'], name='input_batch')
    #     return tf.estimator.export.ServingInputReceiver(new_features, receiver_tensors)

    train_input_partial = partial(train_input, params=params)
    eval_input_partial = partial(eval_input, params=params)

    train_logging, eval_logging, predict_logging = params['logging_hooks']

    epoch_n = 0
    while epoch_n < params['epochs']:
        print(epoch_n, 'epoch')
        logging.info('training begins')
        # Train the estimator
        estimator.train(
            input_fn=train_input_partial,
            steps=params['train_batches'],
            max_steps=params['max_train_batches'],
            hooks=train_logging
        )

        # Evaluate the estimator and logging.info results
        logging.info('eval begins')
        eval = estimator.evaluate(
            input_fn=eval_input_partial,
            steps=params['eval_batches'],
            hooks=eval_logging
        )
        print('Doing eval')
        print(eval)
        #
        # if epoch_n % 10 == 0:
        #
        predictions = estimator.predict(
            eval_input_partial,
            hooks=predict_logging
        )
        prediction_rows = list(predictions)
        logging.info('Predictions: ')
        logging.info(len(prediction_rows))
        for row in prediction_rows[:10]:
            logging.info(row)
        #
        #     logging.info('Saving model at epoch {}'.format(epoch_n))
        #     estimator.export_savedmodel(
        #         export_dir_base=params['log_dir'],
        #         serving_input_receiver_fn=serving_input_receiver_fn)

        epoch_n += 1
