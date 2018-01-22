import os
import shutil

import tensorflow as tf
import numpy as np
from functools import partial

from tensorboard import summary as tensorboard_summary
from input_utils import input

from estimator_models import chollet_model_results


def spiral_classifier(features, labels, mode, params):
    """
    Classify images of galaxies into spiral/not spiral
    Based on MNIST example from tensorflow docs

    Args:
        features ():
        labels ():
        mode ():
        params ():

    Returns:

    """

    predictions, loss = chollet_model_results(features, labels, mode, params)

    if mode == tf.estimator.ModeKeys.PREDICT:
        return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)

    if mode == tf.estimator.ModeKeys.TRAIN:
        optimizer = params['optimizer'](learning_rate=params['learning_rate'])
        train_op = optimizer.minimize(
            loss=loss,
            global_step=tf.train.get_global_step())
        return tf.estimator.EstimatorSpec(mode=mode, loss=loss, train_op=train_op)

    tensorboard_summary.pr_curve_streaming_op(
        name='spirals',
        labels=labels,
        predictions=predictions['probabilities'][:, 1],
    )
    # Add evaluation metrics (for EVAL mode)
    eval_metric_ops = get_eval_metric_ops(labels, predictions)
    return tf.estimator.EstimatorSpec(
        mode=mode, loss=loss, eval_metric_ops=eval_metric_ops)


def get_eval_metric_ops(labels, predictions):

    # record distribution of predictions for tensorboard
    tf.summary.histogram('Probabilities', predictions['probabilities'])
    tf.summary.histogram('Classes', predictions['classes'])

    return {
        "acc/accuracy": tf.metrics.accuracy(
            labels=labels, predictions=predictions["classes"]),
        "pr/auc": tf.metrics.auc(labels=labels, predictions=predictions['classes']),
        "acc/mean_per_class_accuracy": tf.metrics.mean_per_class_accuracy(labels=labels, predictions=predictions['classes'], num_classes=2),
        'pr/precision': tf.metrics.precision(labels=labels, predictions=predictions['classes']),
        'pr/recall': tf.metrics.recall(labels=labels, predictions=predictions['classes']),
        'confusion/true_positives': tf.metrics.true_positives(labels=labels, predictions=predictions['classes']),
        'confusion/true_negatives': tf.metrics.true_negatives(labels=labels, predictions=predictions['classes']),
        'confusion/false_positives': tf.metrics.false_positives(labels=labels, predictions=predictions['classes']),
        'confusion/false_negatives': tf.metrics.false_negatives(labels=labels, predictions=predictions['classes'])
    }


def train_input(params):
    mode = 'train'
    # filename = '/data/galaxy_zoo/gz2/tfrecord/spiral_{}_{}.tfrecord'.format(params['image_dim'], 'test')
    filename = '/data/galaxy_zoo/gz2/tfrecord/spiral_{}_{}.tfrecord'.format(params['image_dim'], mode)
    return input(
        filename=filename, size=params['image_dim'], mode=mode, batch=params['batch_size'], augment=True, stratify=True)


def eval_input(params):
    mode = 'test'
    # filename = '/data/galaxy_zoo/gz2/tfrecord/spiral_{}_{}.tfrecord'.format(SIZE, 'train')
    filename = '/data/galaxy_zoo/gz2/tfrecord/spiral_{}_{}.tfrecord'.format(params['image_dim'], mode)
    return input(
        filename=filename, size=params['image_dim'], mode=mode, batch=params['batch_size'], augment=True, stratify=True)


# def serving_input_receiver_fn():
#     """Build the serving inputs."""
#     # The outer dimension (None) allows us to batch up inputs for
#     # efficiency. However, it also means that if we want a prediction
#     # for a single instance, we'll need to wrap it in an outer list.
#     inputs = {"x": tf.placeholder(shape=[None, 4], dtype=tf.float32)}
#     return tf.estimator.export.ServingInputReceiver(inputs, inputs)


def serving_input_receiver_fn():
  """An input receiver that expects a serialized tf.Example."""
  serialized_tf_example = tf.placeholder(dtype=tf.string,
                                         shape=[default_batch_size],
                                         name='input_example_tensor')
  receiver_tensors = {'examples': serialized_tf_example}
  features = tf.parse_example(serialized_tf_example, feature_spec)
  return tf.estimator.export.ServingInputReceiver(features, receiver_tensors)


def run_experiment(model_fn, params):

    if os.path.exists(params['log_dir']):
        shutil.rmtree(params['log_dir'])

    # Create the Estimator
    model_fn_partial = partial(model_fn, params=params)
    estimator = tf.estimator.Estimator(
        model_fn=model_fn_partial, model_dir=params['log_dir'])

    # Set up logging for predictions
    tensors_to_log = {"probabilities": "softmax_tensor"}
    logging_hook = tf.train.LoggingTensorHook(
        tensors=tensors_to_log, every_n_iter=params['log_freq'])

    train_input_partial = partial(train_input, params=params)
    eval_input_partial = partial(eval_input, params=params)

    epoch_n = 0
    while epoch_n < params['epochs']:
        print('training begins')
        # Train the estimator
        estimator.train(
            input_fn=train_input_partial,
            steps=params['train_batches'],
            max_steps=params['max_train_batches'],
            hooks=[logging_hook]
        )

        # Evaluate the estimator and print results
        print('eval begins')
        eval_results = estimator.evaluate(
            input_fn=eval_input_partial,
            steps=params['eval_batches'],
            hooks=[logging_hook]
        )
        print(eval_results)

        print('saving model at epoch {}'.format(epoch_n))
        estimator.export_savedmodel(
            export_dir_base="/path/to/model",
            serving_input_receiver_fn=serving_input_receiver_fn)

        epoch_n += 1
