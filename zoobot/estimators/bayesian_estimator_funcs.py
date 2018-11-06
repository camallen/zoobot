import logging

import tensorflow as tf
from tensorflow.python.saved_model import signature_constants


def estimator_wrapper(features, labels, mode, params):
    # estimator model funcs are only allowed to have (features, labels, params) arguments
    # re-order the arguments internally to allow for the custom class to be passed around
    # params is really the model class
    return params.entry_point(features, labels, mode)  # must have exactly the args (features, labels)


class BayesianModel():

    def __init__(
            self,
            image_dim,
            learning_rate=0.001,
            optimizer=tf.train.AdamOptimizer,
            conv1_filters=32,
            conv1_kernel=1,
            conv1_activation=tf.nn.relu,
            conv2_filters=32,
            conv2_kernel=3,
            conv2_activation=tf.nn.relu,
            conv3_filters=16,
            conv3_kernel=3,
            conv3_activation=tf.nn.relu,
            dense1_units=128,
            dense1_dropout=0.5,
            dense1_activation=tf.nn.relu,
            predict_dropout=0.5,
            regression=False,
            log_freq=10,
    ):
        self.image_dim = image_dim
        self.optimizer = optimizer
        self.learning_rate = learning_rate
        self.conv1_filters = conv1_filters
        self.conv1_kernel = conv1_kernel
        self.conv2_filters = conv2_filters
        self.conv2_kernel = conv2_kernel
        self.conv3_filters = conv3_filters
        self.conv3_kernel = conv3_kernel
        self.dense1_units = dense1_units
        self.dense1_dropout = dense1_dropout
        self.conv1_activation = conv1_activation
        self.conv2_activation = conv2_activation
        self.conv3_activation = conv3_activation
        self.dense1_activation = dense1_activation
        self.pool1_size = 2
        self.pool1_strides = 2
        self.pool2_size = 2
        self.pool2_strides = 2
        self.pool3_size = 2
        self.pool3_strides = 2
        self.padding = 'same'
        self.predict_dropout = predict_dropout  # dropout rate for predict mode
        self.regression = regression
        self.log_freq = log_freq
        self.model_fn = self.main_estimator
        # self.logging_hooks = logging_hooks(self)  # TODO strange error with passing this to estimator in params
        self.logging_hooks = [None, None, None]
        self.entry_point = self.main_estimator

    # TODO move to shared utilities
    # TODO duplicated with input_utils
    def asdict(self):
        excluded_keys = ['__dict__', '__doc__', '__module__', '__weakref__']
        return dict([(key, value) for (key, value) in self.__dict__.items() if key not in excluded_keys])


    def main_estimator(self, features, labels, mode):
        """
        Estimator wrapper function for four-layer cnn performing classification or regression
        Shows the general actions for each Estimator mode
        Details (e.g. neurons, activation funcs, etc) controlled by 'params'

        Args:
            features ():
            labels ():
            mode ():

        Returns:

        """
        if self.regression:
            if labels is not None:
                logging.warning('Enforcing float labels for regression mode')
                labels = tf.cast(labels, tf.float32)
            response, loss = self.bayesian_regressor(features, labels, mode)
        if not self.regression:
            if labels is not None:
                logging.warning('Enforcing int labels for classification mode')
                labels = tf.cast(labels, tf.int64)
            response, loss = self.bayesian_classifier(features, labels, mode)
        
        if mode == tf.estimator.ModeKeys.PREDICT:
            with tf.variable_scope('predict'):
                export_outputs = {
                    signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY: tf.estimator.export.PredictOutput(response)
                }
            return tf.estimator.EstimatorSpec(mode=mode, predictions=response, export_outputs=export_outputs)

        assert labels is not None

        if mode == tf.estimator.ModeKeys.TRAIN:
            with tf.variable_scope('train'):
                optimizer = self.optimizer(learning_rate=self.learning_rate)  # TODO adaptive learning rate

                # important to explicitly use within update_ops for batch norm to work
                # see https://www.tensorflow.org/api_docs/python/tf/layers/batch_normalization
                update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
                with tf.control_dependencies(update_ops):
                    train_op = optimizer.minimize(
                        loss=loss,
                        global_step=tf.train.get_global_step())

                return tf.estimator.EstimatorSpec(mode=mode, loss=loss, train_op=train_op)

        else:  # must be EVAL mode
            with tf.variable_scope('eval'):

                # Add evaluation metrics (for EVAL mode)
                eval_metric_ops = get_eval_metric_ops(self, labels, response)
                return tf.estimator.EstimatorSpec(
                    mode=mode, loss=loss, eval_metric_ops=eval_metric_ops)


    def bayesian_regressor(self, features, labels, mode):
        """
        Model function of four-layer CNN
        Can be used in isolation or called within an estimator e.g. four_layer_binary_classifier

        Args:
            features ():
            labels ():
            mode ():
            params ():

        Returns:

        """
        dense1 = input_to_dense_normed(features, mode, self)  # use batch normalisation

        # if predict mode, feedforward from dense1 SEVERAL TIMES. Save all predictions under 'all_predictions'.
        if mode == tf.estimator.ModeKeys.PREDICT:

            with tf.variable_scope("sample"):
                # Feedforward from dense1. Always apply dropout.
                _, sample_predictions = dense_to_regression(dense1, labels, dropout_on=True, dropout_rate=self.predict_dropout)
            return sample_predictions, None  # no loss, as labels not known (in general)

        else:  # Calculate Loss for TRAIN and EVAL modes)
            # only feedforward once for one set of predictions

            predictions, response = dense_to_regression(dense1, labels, dropout_on=mode == tf.estimator.ModeKeys.TRAIN, dropout_rate=self.dense1_dropout)
            labels = tf.stop_gradient(labels)  # don't find the gradient of the labels (e.g. adversarial)

              # Calculate loss using mean squared error
            mean_loss = tf.losses.mean_squared_error(labels, predictions)

            # create dummy variables that match names in predict mode
            # TODO this is potentially wasteful as we don't actually need the feedforwards.
            # Unclear if it executes - check.
            with tf.variable_scope("sample"):
                _, _ = dense_to_regression(dense1, labels, dropout_on=True, dropout_rate=self.dense1_dropout)

            return response, mean_loss

    def bayesian_classifier(self, features, labels, mode):
        """
        Model function of four-layer CNN
        Can be used in isolation or called within an estimator e.g. four_layer_binary_classifier

        Args:
            features ():
            labels ():
            mode ():
            params ():

        Returns:

        """

        # dense1 = input_to_dense(features, mode, self)  # run from input to dense1 output
        dense1 = input_to_dense_normed(features, mode, self)  # use batch normalisation

        # if predict mode, feedforward from dense1 SEVERAL TIMES. Save all predictions under 'all_predictions'.
        if mode == tf.estimator.ModeKeys.PREDICT:

            with tf.variable_scope("sample"):
                # Feedforward from dense1. Always apply dropout.
                _, sample_predictions = dense_to_multiclass_prediction(dense1, labels, dropout_on=True, dropout_rate=self.predict_dropout)
            return sample_predictions, None  # no loss, as labels not known (in general)

        else:  # Calculate Loss for TRAIN and EVAL modes)
            # only feedforward once for one set of predictions

            logits, response = dense_to_multiclass_prediction(dense1, labels, dropout_on=mode == tf.estimator.ModeKeys.TRAIN, dropout_rate=self.dense1_dropout)
            onehot_labels = tf.one_hot(indices=tf.cast(labels, tf.int32), depth=2)
            onehot_labels = tf.stop_gradient(onehot_labels)  # don't find the gradient of the labels (e.g. adversarial)
            loss = tf.nn.softmax_cross_entropy_with_logits_v2(
                labels=onehot_labels,
                logits=logits,
                name='model/layer4/loss')


            # loss = tf.nn.softmax_cross_entropy_with_logits(labels=onehot_labels, logits=logits, name='model/layer4/loss')
            mean_loss = tf.reduce_mean(loss, name='mean_loss')

            # create dummy variables that match names in predict mode
            # TODO this is potentially wasteful as we don't actually need the feedforwards.
            # Unclear if it executes - check.
            with tf.variable_scope("sample"):
                _, _ = dense_to_multiclass_prediction(dense1, labels, dropout_on=True, dropout_rate=self.dense1_dropout)

            return response, mean_loss


def input_to_dense_normed(features, mode, model):
    """
    # TODO refactor to avoid duplication with input_to_dense, or always norm
    Args:
        features ():
        mode():
        model (BayesianBinaryModel):

    Returns:

    """
    input_layer = features["x"]
    tf.summary.image('model_input', input_layer, 1)

    conv1 = tf.layers.conv2d(
        inputs=input_layer,
        filters=model.conv1_filters,
        kernel_size=[model.conv1_kernel, model.conv1_kernel],
        padding=model.padding,
        activation=None,
        name='model/layer1/conv1')
    norm1 = tf.layers.batch_normalization(conv1)
    # TODO Does batch norm apply activation as well? I assume not, but model ran okay without any explicit activ...
    relu1 = model.conv1_activation(norm1)

    pool1 = tf.layers.max_pooling2d(
        inputs=relu1,
        pool_size=[model.pool1_size, model.pool1_size],
        strides=model.pool1_strides,
        name='model/layer1/pool1')

    conv2 = tf.layers.conv2d(
        inputs=pool1,
        filters=model.conv2_filters,
        kernel_size=[model.conv2_kernel, model.conv2_kernel],
        padding=model.padding,
        activation=None,
        name='model/layer2/conv2')
    norm2 = tf.layers.batch_normalization(conv2)
    relu2 = model.conv2_activation(norm2)
    pool2 = tf.layers.max_pooling2d(
        inputs=relu2,
        pool_size=model.pool2_size,
        strides=model.pool2_strides,
        name='model/layer2/pool2')

    conv3 = tf.layers.conv2d(
        inputs=pool2,
        filters=model.conv3_filters,
        kernel_size=[model.conv3_kernel, model.conv3_kernel],
        padding=model.padding,
        activation=None,
        name='model/layer3/conv3')
    norm3 = tf.layers.batch_normalization(conv3)
    relu3 = model.conv3_activation(norm3)
    pool3 = tf.layers.max_pooling2d(
        inputs=relu3,
        pool_size=[model.pool3_size, model.pool3_size],
        strides=model.pool3_strides,
        name='model/layer3/pool3')

    """
    Flatten tensor into a batch of vectors
    Start with image_dim shape, 1 channel
    2 * 2 * 2 = 8 factor reduction in shape from pooling, assuming stride 2 and pool_size 2
    length ^ 2 to make shape 1D
    64 filters in final layer
    """
    pool3_flat = tf.reshape(pool3, [-1, int(model.image_dim / 8) ** 2 * model.conv3_filters], name='model/layer3/flat')

    # Dense Layer
    dense1 = tf.layers.dense(
        inputs=pool3_flat,
        units=model.dense1_units,
        activation=model.dense1_activation,
        name='model/layer4/dense1')

    return dense1


def dense_to_multiclass_prediction(dense1, labels, dropout_on, dropout_rate):

    # Add dropout operation
    dropout = tf.layers.dropout(
        inputs=dense1,
        rate=dropout_rate,
        training=dropout_on)
    tf.summary.tensor_summary('dropout_summary', dropout)

    # Logits layer
    logits = tf.layers.dense(inputs=dropout, units=2, name='logits')
    tf.summary.histogram('logits_false', logits[:, 0])  # first dimension is batch, second is class (0 = featured here)
    tf.summary.histogram('logits_true', logits[:, 1])

    softmax = tf.nn.softmax(logits, name='softmax')
    softmax_true_score = softmax[:, 1]  # predicts if label = 1 i.e. smooth
    tf.summary.histogram('softmax_true_score', softmax_true_score)

    response = {
        "probabilities": softmax,
        "predictions_for_true": softmax_true_score,  # keep only one softmax per subject. Softmax sums to 1
    }
    if labels is not None:
        response.update({
            'labels': tf.identity(labels, name='labels'),  # these are None in predict mode
            "classes": tf.argmax(input=logits, axis=1, name='classes'),
        })

    return logits, response



def dense_to_regression(dense1, labels, dropout_on, dropout_rate):

    # helpful example: https://github.com/tensorflow/tensorflow/blob/r1.11/tensorflow/examples/get_started/regression/custom_regression.py
    # Add dropout operation
    # TODO refactor out, duplication + SRP
    dropout = tf.layers.dropout(
        inputs=dense1,
        rate=dropout_rate,
        training=dropout_on)
    tf.summary.tensor_summary('dropout_summary', dropout)

    linear = tf.layers.dense(
        dropout, 
        units=1, 
        # activation=tf.nn.relu, 
        name='layer_after_dropout')
    # clipped = tf.clip_by_value(rectified, 0., 1., name='clipped_after_relu')
    tf.summary.histogram('layer_after_dropout', linear)
    # tf.summary.histogram('clipped_after_relu', clipped)

    prediction = tf.squeeze(linear, 1)
    response = {
        "prediction": prediction,
    }
    if labels is not None:
        response.update({
            'labels': tf.identity(labels, name='labels'),  # these are None in predict mode
        })

    return prediction, response



def get_eval_metric_ops(self, labels, predictions):
    # record distribution of predictions for tensorboard
    tf.summary.histogram('labels', labels)
    
    if self.regression:
        assert labels.dtype == tf.float32
        assert predictions['prediction'].dtype == tf.float32
        return {"rmse": tf.metrics.root_mean_squared_error(labels, predictions['prediction'])}
    else:
        tf.summary.histogram('Probabilities', predictions['probabilities'])
        tf.summary.histogram('Classes', predictions['classes'])

        # validation loss is added behind-the-scenes by TensorFlow
        return {
            "acc/accuracy": tf.metrics.accuracy(
                labels=labels, predictions=predictions["classes"]),
            "acc/mean_per_class_accuracy": tf.metrics.mean_per_class_accuracy(labels=labels,
                                                                            predictions=predictions['classes'],
                                                                            num_classes=2),
            "pr/auc": tf.metrics.auc(labels=labels, predictions=predictions['classes']),
            'pr/precision': tf.metrics.precision(labels=labels, predictions=predictions['classes']),
            'pr/recall': tf.metrics.recall(labels=labels, predictions=predictions['classes']),
            'confusion/true_positives': tf.metrics.true_positives(labels=labels, predictions=predictions['classes']),
            'confusion/true_negatives': tf.metrics.true_negatives(labels=labels, predictions=predictions['classes']),
            'confusion/false_positives': tf.metrics.false_positives(labels=labels, predictions=predictions['classes']),
            'confusion/false_negatives': tf.metrics.false_negatives(labels=labels, predictions=predictions['classes']),
            'sanity/predictions_below_5%': tf.metrics.percentage_below(
                values=predictions['probabilities'][:, 0],
                threshold=0.05),
            'sanity/predictions_above_95%': tf.metrics.percentage_below(
                values=1 - predictions['probabilities'][:, 0],
                threshold=0.05)
        }


def logging_hooks(model_config):
    train_tensors = {
        'labels': 'labels',
        # 'logits': 'logits',  may not always exist? TODO
        "probabilities": 'softmax',
        'mean_loss': 'mean_loss'
    }
    train_hook = tf.train.LoggingTensorHook(
        tensors=train_tensors, every_n_iter=model_config.log_freq)

    # eval_hook = train_hook
    eval_hook = tf.train.LoggingTensorHook(
        tensors=train_tensors, every_n_iter=model_config.log_freq)

    prediction_tensors = {}
    # [prediction_tensors.update({'sample_{}/predictions'.format(n): 'sample_{}/predictions'.format(n)}) for n in range(3)]

    prediction_hook = tf.train.LoggingTensorHook(
        tensors=prediction_tensors, every_n_iter=model_config.log_freq
    )

    return [train_hook], [eval_hook], [prediction_hook]  # estimator expects lists of logging hooks
