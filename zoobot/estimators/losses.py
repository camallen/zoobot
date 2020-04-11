import numpy as np
import tensorflow as tf
from typing import List

def calculate_binomial_loss(labels, predictions):
    scalar_predictions = get_scalar_prediction(predictions)  # softmax, get the 2nd neuron
    return binomial_loss(labels, scalar_predictions)


def get_scalar_prediction(prediction):
    return tf.nn.softmax(prediction)[:, 1]


class Schema():
    """
    Relate the df label columns to question/answer groups and to tfrecod label indices
    """
    def __init__(self, label_cols: List, questions: List):
        """
        Requires that labels be continguous by question - easily satisfied
        
        Args:
            label_cols (List): columns (strings) which record k successes for each galaxy for each answer
            questions (List): semantic names of questions which group those answers
        """
        self.label_cols = label_cols
        self.questions = questions
        self.question_index_groups = []  # start and end indices of answers to each question in label_cols e.g. [[0, 1]. [1, 3]] 
        if 'smooth-or-featured' in questions:
            self.question_index_groups.append([
                label_cols.index('smooth-or-featured_smooth'),
                label_cols.index('smooth-or-featured_featured-or-disk')
                # TODO add artifact?
            ])
        if 'has-spiral-arms' in questions:
            self.question_index_groups.append([
                label_cols.index('has-spiral-arms_yes'),
                label_cols.index('has-spiral-arms_no')
            ])
        assert len(self.question_index_groups) > 0
    # TODO write to disk
    


def get_indices_from_label_cols(label_cols, questions):
    """
    Get indices for use with tf.dynamic_slice
    Example use:

    questions = ['q1', 'q2']
    label_cols = ['q1_a1', 'q1_a2', 'q2_a1', 'q2_a2']

    Returns:
    indices = [0, 0, 1, 1]
    """
    raise NotImplementedError('This has been deprecated, use get_schema above')
    # indices = np.zeros(len(label_cols))
    # for question_n, question in enumerate(questions):
    #     for column_n, label_col in enumerate(label_cols):
    #         if label_col.startswith(question):
    #             indices[column_n] = question_n
    # return tf.constant(indices.astype(int), dtype=tf.int32)


# @tf.function
def multiquestion_loss(labels, predictions, question_index_groups):
    """[summary]
    
    Args:
        labels (tf.Tensor): (galaxy, k successes) where k successes dimension is indexed by question_index_groups
        predictions (tf.Tensor): coin-toss probabilities of success, matching shape of labels
        question_index_groups (list): Paired (tuple) integers of (first, last) indices of answers to each question, listed for all questions
    
    Returns:
        [type]: [description]
    """
    # very important that question_index_groups is fixed and discrete, else tf.function autograph will mess up 
    q_losses = []
    for q_n in range(len(question_index_groups)):
        q_indices = question_index_groups[q_n]
        q_start = q_indices[0]
        q_end = q_indices[1]
        q_loss = multinomial_loss(labels[:, q_start:q_end+1], predictions[:, q_start:q_end+1])
        # tf.summary.histogram('question_{}_loss'.format(q_n), q_loss)
        q_losses.append(q_loss)
    
    total_loss = tf.stack(q_losses, axis=1)
    # tf.summary.histogram('total_loss', total_loss)
    return total_loss  # leave the reduce_sum to the estimator


def multinomial_loss(successes, expected_probs, output_dim=2):
    """
    For this to be correct, predictions must sum to 1 and successes must sum to n_trials (i.e. all answers to each question are known)
    Negative log loss, of course
    
    Args:
        successes (tf.Tensor): (galaxy, k_successes) where k_successes is indexed by each answer (e.g. [:, 0] = smooth votes, [:, 1] = featured votes)
        expected_probs (tf.Tensor): coin-toss probability of success, same dimensions as successes
        output_dim (int, optional): Number of answers (i.e. successes.shape[1]). Defaults to 2. TODO may remove?
    
    Returns:
        tf.Tensor: neg log likelihood of k_successes observed across all answers. With batch dimension.
    """
    # successes x, probs p: tf.sum(x*log(p)). Each vector x, p of length k.
    loss = -tf.reduce_sum(input_tensor=successes * tf.math.log(expected_probs + tf.constant(1e-8, dtype=tf.float32)), axis=1)
    for n in range(output_dim):  # careful, output_dim must be fixed
        tf.compat.v1.summary.histogram('successes_{}'.format(n), successes[:, n])
        tf.compat.v1.summary.histogram('expected_probs_{}', expected_probs[:, n])
    tf.compat.v1.summary.histogram('loss', loss)
    # print_op = tf.print('successes', successes, 'expected_probs', expected_probs)
    # with tf.control_dependencies([print_op]):
    return loss

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
    bin_loss = -( successes * tf.math.log(p_yes + epsilon) + (n_trials - successes) * tf.math.log(one - p_yes + epsilon) )
    tf.compat.v1.summary.histogram('bin_loss', bin_loss)
    tf.compat.v1.summary.histogram('bin_loss_clipped', tf.clip_by_value(bin_loss, 0., 50.))
    return bin_loss
