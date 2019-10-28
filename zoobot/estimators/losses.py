import tensorflow as tf


def calculate_binomial_loss(labels, predictions):
    scalar_predictions = get_scalar_prediction(predictions)  # softmax, get the 2nd neuron
    return binomial_loss(labels, scalar_predictions)


def get_scalar_prediction(prediction):
    return tf.nn.softmax(prediction)[:, 1]


def multiquestion_loss(labels, predictions, question_index_groups):
    # very important that question_index_groups is fixed, else tf autograph will mess up this for loop
    total_loss = 0
    for question_group in question_index_groups:
        total_loss += multinomial_loss(labels[question_group], predictions[question_group])
    return total_loss


def multinomial_loss(successes, expected_probs):
    # for this to be correct, predictions must sum to 1 and successes must sum to n_trials
    # negative log loss, of course
    # successes x, probs p: tf.sum(x*log(p)). Each vector x, p of length k.

    # temporarily setting to be weak vs no bar, for debugging
    # loss = -tf.reduce_sum(successes * tf.log(expected_probs + tf.constant(1e-8, dtype=tf.float32)), axis=1)
    binary_loss = -tf.reduce_sum(successes[:, 1:] * tf.log(expected_probs[:, 1:] + tf.constant(1e-8, dtype=tf.float32)), axis=1)
    tf.summary.histogram('successes_0', successes[:, 0])
    tf.summary.histogram('successes_1', successes[:, 1])
    tf.summary.histogram('successes_2', successes[:, 2])
    tf.summary.histogram('expected_probs_0', expected_probs[:, 0])
    tf.summary.histogram('expected_probs_1', expected_probs[:, 1])
    tf.summary.histogram('expected_probs_2', expected_probs[:, 2])
    tf.summary.histogram('loss', binary_loss)
    # print_op = tf.print('successes', successes, 'expected_probs', expected_probs)
    # with tf.control_dependencies([print_op]):
    return binary_loss

def binomial_loss(labels, predictions):
    """Calculate likelihood of labels given predictions, if labels are binomially distributed
    
    Args:
        labels (tf.constant): of shape (batch_dim, 2) where 0th col is successes and 1st is total trials
        predictions (tf.constant): of shape (batch_dim) with values of prob. success
    
    Returns:
        (tf.constant): negative log likelihood of labels given prediction
    """
    one = tf.constant(1., dtype=tf.float32)
    # TODO may be able to use normal python types, not sure about speed
    epsilon = tf.constant(1e-8, dtype=tf.float32)

    # multiplication in tf requires floats
    successes = tf.cast(labels[:, 0], tf.float32)
    n_trials = tf.cast(labels[:, 1], tf.float32)
    p_yes = tf.identity(predictions)  # fail loudly if passed out-of-range values

    # negative log likelihood
    bin_loss = -( successes * tf.log(p_yes + epsilon) + (n_trials - successes) * tf.log(one - p_yes + epsilon) )
    tf.summary.histogram('bin_loss', bin_loss)
    tf.summary.histogram('bin_loss_clipped', tf.clip_by_value(bin_loss, 0., 50.))
    return bin_loss
