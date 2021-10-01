import tensorflow as tf
import tensorflow_probability as tfp



def get_multiquestion_loss(question_index_groups, reduction=tf.keras.losses.Reduction.SUM):
    """
    Get subclass of tf.keras.losses.Loss which wraps ``calculate_multiquestion_loss`` and sums over batch.

    tf.keras.losses.Reduction.SUM_OVER_BATCH_SIZE will assume the question dimension (10) is also part of the batch, and divide by an extra factor of 10
    tf.keras.losses.Reduction.SUM_OVER_BATCH_SIZE also does not work in distributed training (as batch size is split between replicas)
    tf.keras.losses.Reduction.SUM will simply add everything up, so divide by the global batch size externally with tf.reduce_sum

    Args:
        question_index_groups (list): Answer indices for each question i.e. [(question.start_index, question.end_index), ...] for all questions. Useful for slicing model predictions by question.

    Returns:
        MultiquestionLoss: see above.
    """

    class MultiquestionLoss(tf.keras.losses.Loss):

        def call(self, labels, predictions):
            return calculate_multiquestion_loss(labels, predictions, question_index_groups)

    return MultiquestionLoss(reduction=reduction) 


def calculate_multiquestion_loss(labels, predictions, question_index_groups):
    """
    The full decision tree loss used for training GZ DECaLS models

    Negative log likelihood of observing ``labels`` (volunteer answers to all questions)
    from Dirichlet-Multinomial distributions for each question, using concentrations ``predictions``.
    
    Args:
        labels (tf.Tensor): (galaxy, k successes) where k successes dimension is indexed by question_index_groups.
        predictions (tf.Tensor):  Dirichlet concentrations, matching shape of labels
        question_index_groups (list): Paired (tuple) integers of (first, last) indices of answers to each question, listed for all questions.
    
    Returns:
        tf.Tensor: neg. log likelihood of shape (batch, question).
    """
    # very important that question_index_groups is fixed and discrete, else tf.function autograph will mess up 
    q_losses = []
    # will give shape errors if model output dim is not labels dim, which can happen if losses.py substrings are missing an answer
    for q_n in range(len(question_index_groups)):
        q_indices = question_index_groups[q_n]
        q_start = q_indices[0]
        q_end = q_indices[1]

        q_loss = dirichlet_loss(labels[:, q_start:q_end+1], predictions[:, q_start:q_end+1])

        q_losses.append(q_loss)
    
    total_loss = tf.stack(q_losses, axis=1)

    return total_loss  # leave the reduce_sum to the tf.keras.losses.Loss base class, loss should keep the batch size. 
    # https://www.tensorflow.org/api_docs/python/tf/keras/losses/Loss will auto-reduce (sum) over the batch anyway



def dirichlet_loss(labels_for_q, concentrations_for_q):
    """
    Negative log likelihood of ``labels_for_q`` being drawn from Dirichlet-Multinomial distribution with ``concentrations_for_q`` concentrations.
    This loss is for one question. Sum over multiple questions if needed (assumes independent).
    Applied by :meth:`calculate_multiquestion_loss`, above.

    Args:
        labels_for_q (tf.constant): observed labels (count of volunteer responses) of shape (batch, answer)
        concentrations_for_q (tf.constant): concentrations for multinomial-dirichlet predicting the observed labels, of shape (batch, answer)

    Returns:
        tf.constant: negative log. prob per galaxy, of shape (batch_dim).
    """
    total_count = tf.reduce_sum(labels_for_q, axis=1)
    dist = tfp.distributions.DirichletMultinomial(total_count, concentrations_for_q, validate_args=True)
    return -dist.log_prob(labels_for_q)  # important minus sign

