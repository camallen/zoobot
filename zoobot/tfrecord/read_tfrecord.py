import logging

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import tensorflow as tf

from zoobot.tfrecord.tfrecord_io import load_dataset


def load_examples_from_tfrecord(tfrecord_locs, feature_spec, n_examples=None):
    dataset = load_dataset(tfrecord_locs, feature_spec)
    iterator = dataset.make_one_shot_iterator()
    dataset = dataset.batch(1)  # 1 image per batch
    dataset = dataset.prefetch(1)
    batch = iterator.get_next()

    with tf.Session() as sess:
        if n_examples is None:  # load full record
            data = []
            while True:
                try:
                    loaded_example = sess.run(batch)
                    data.append(loaded_example)
                except tf.errors.OutOfRangeError:
                    logging.debug('tfrecords {} exhausted'.format(tfrecord_locs))
                    break
        else:
            logging.debug('Loading the first {} examples from {}'.format(n_examples, tfrecord_locs))
            data = [sess.run(batch) for n in range(n_examples)]

    return data


def matrix_label_feature_spec(size, channels):
    return {
        "matrix": tf.FixedLenFeature((size * size * channels), tf.float32),
        "label": tf.FixedLenFeature((), tf.int64)
        }


def matrix_id_feature_spec(size, channels):
    return {
        "matrix": tf.FixedLenFeature((size * size * channels), tf.float32),
        "id_str": tf.FixedLenFeature((), tf.string)
        }


def matrix_label_id_feature_spec(size, channels):
    return {
        "matrix": tf.FixedLenFeature((size * size * channels), tf.float32),
        "label": tf.FixedLenFeature((), tf.int64),
        "id_str": tf.FixedLenFeature((), tf.string)
        }


# not required, use tf.parse_single_example directly
# def parse_example(example, size, channels):
#     features = {
#         'matrix': tf.FixedLenFeature((size * size * channels), tf.float32),
#         'label': tf.FixedLenFeature([], tf.int64),
#         }

#     return tf.parse_single_example(example, features=features)


# these are actually not related to reading a tfrecord, they are very general
def show_examples(examples, size, channels):
    # simple wrapper for pretty example plotting
    # TODO make plots in a grid rather than vertical column
    fig, axes = plt.subplots(nrows=len(examples), figsize=(4, len(examples) * 3))
    for n, example in enumerate(examples):
        show_example(example, size, channels, ax=axes[n])
    fig.tight_layout()
    return fig, axes


def show_example(example, size, channels, ax):  # modifies ax inplace
    # saved as floats but truly int, show as int
    im = example['matrix'].reshape(size, size, channels) 
    label = example['label']
    name_mapping = {
        0: 'Feat.',
        1: 'Smooth'
    }
    try:
        ax.imshow(im)
    except ValueError: 
        ax.imshow(im.astype(int))
    # ax.text(60, 110, name_mapping[label], fontsize=16, color='r')
