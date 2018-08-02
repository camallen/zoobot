import os
import random

import numpy as np
import pytest
import tensorflow as tf
import matplotlib
matplotlib.use('Agg')  # don't actually show any figures
import matplotlib.pyplot as plt
from PIL import Image

from zoobot.estimators import input_utils
from zoobot.tfrecord import create_tfrecord

TEST_EXAMPLE_DIR = 'zoobot/test_examples'


"""
Test augmentation applied to a single image (i.e. within map_fn)
"""

@pytest.fixture()
# actual image used for visual checks
def visual_check_image():
    return tf.constant(np.array(Image.open(TEST_EXAMPLE_DIR + '/example_b.png')))


def test_geometric_augmentations_on_image(visual_check_image):

    final_image = input_utils.geometric_augmentation(visual_check_image, max_zoom=1.5, final_size=256)

    with tf.Session() as session:
        session.run(tf.global_variables_initializer())
        original_image = session.run(visual_check_image)
        final_image = np.squeeze(session.run(final_image))  # remove batch dimension

        fig, axes = plt.subplots(ncols=2)
        axes[0].imshow(original_image)
        axes[0].set_title('Before')
        axes[1].imshow(final_image)
        axes[1].set_title('After')
        fig.tight_layout()
        fig.savefig(TEST_EXAMPLE_DIR + '/geometric_augmentation_check_single_image.png')


def test_photometric_augmentations_on_image(visual_check_image):
    final_image = input_utils.photographic_augmentation(visual_check_image, max_brightness_delta=0.1, contrast_range=(0.9, 1.1))

    with tf.Session() as session:
        session.run(tf.global_variables_initializer())
        input_image = session.run(visual_check_image)
        final_image = np.squeeze(session.run(final_image))  # adds a batch dimension

    fig, axes = plt.subplots(ncols=2)
    axes[0].imshow(input_image)
    axes[0].set_title('Before')
    print(final_image.shape)
    axes[1].imshow(final_image)
    axes[1].set_title('After')
    fig.tight_layout()
    fig.savefig(TEST_EXAMPLE_DIR + '/photometric_augmentation_check_single_image.png')


@pytest.fixture()
def batch_of_visual_check_image(visual_check_image):
    return tf.stack([visual_check_image for n in range(16)], axis=0)  # dimensions batch, height, width, channels


def test_repeated_geometric_augmentations_on_image(batch_of_visual_check_image):
    transformed_images = input_utils.geometric_augmentation(batch_of_visual_check_image, max_zoom=1.5, final_size=256)

    with tf.Session() as session:
        session.run(tf.global_variables_initializer())
        transformed_images = session.run(transformed_images)

    fig, axes = plt.subplots(nrows=16, figsize=(4, 4 * 16))
    for image_n, image in enumerate(transformed_images):
        axes[image_n].imshow(image)
    fig.tight_layout()
    fig.savefig(TEST_EXAMPLE_DIR + '/geometric_augmentation_check_on_batch.png')


def test_repeated_photometric_augmentations_on_image(batch_of_visual_check_image):
    transformed_images = input_utils.photographic_augmentation(batch_of_visual_check_image, max_brightness_delta=0.1, contrast_range=(0.9, 1.1))

    with tf.Session() as session:
        session.run(tf.global_variables_initializer())
        transformed_images = session.run(transformed_images)

    fig, axes = plt.subplots(nrows=16, figsize=(4, 4 * 16))
    for image_n, image in enumerate(transformed_images):
        axes[image_n].imshow(image)
    fig.tight_layout()
    fig.savefig(TEST_EXAMPLE_DIR + '/photometric_augmentation_check_on_batch.png')


def test_all_augmentations_on_batch(batch_of_visual_check_image):

    input_config = input_utils.InputConfig(
        name='pytest',
        tfrecord_loc='',
        label_col='',
        initial_size=424,
        final_size=256,
        channels=3,
        batch_size=16,
        stratify=False,
        shuffle=False,
        stratify_probs=None,
        geometric_augmentation=True,
        shift_range=None,
        max_zoom=1.5,
        fill_mode=None,
        photographic_augmentation=True,
        max_brightness_delta=0.2,
        contrast_range=(0.8, 1.2)
    )

    transformed_batch = input_utils.augment_images(batch_of_visual_check_image, input_config)

    with tf.Session() as sess:
        transformed_batch = sess.run(transformed_batch)

    assert not isinstance(transformed_batch, list)  # should be a single 4D tensor
    transformed_images = [transformed_batch[n] for n in range(len(transformed_batch))]  # back to list form
    fig, axes = plt.subplots(nrows=len(transformed_images), figsize=(4, 4 * len(transformed_images)))
    for image_n, image in enumerate(transformed_images):
        axes[image_n].imshow(image)
    fig.tight_layout()
    fig.savefig(TEST_EXAMPLE_DIR + '/all_augmentations_check.png')


"""
Test augmentation applied by map_fn to a chain of images from from_tensor_slices
"""


# @pytest.fixture()
# def benchmark_image():
#     single_channel = np.array([[1., 2., 3., 4.] for n in range(4)])  # each channel has rows of 1 2 3 4
#     return np.array([single_channel for n in range(3)])  # copied 3 times

"""
Functional test on fake data, saved to temporary tfrecords
"""


@pytest.fixture(scope='module')
def size():
    return 4


@pytest.fixture(scope='module')
def true_image_values():
    return 3.


@pytest.fixture(scope='module')
def false_image_values():
    return -3.


@pytest.fixture()
def example_data(size, true_image_values, false_image_values):
    n_true_examples = 100
    n_false_examples = 400

    true_images = [np.ones((size, size, 3), dtype=float) * true_image_values for n in range(n_true_examples)]
    false_images = [np.ones((size, size, 3), dtype=float) * false_image_values for n in range(n_false_examples)]
    true_labels = [1 for n in range(n_true_examples)]
    false_labels = [0 for n in range(n_false_examples)]
    print('starting: probs: ', np.mean(true_labels + false_labels))

    true_data = list(zip(true_images, true_labels))
    false_data = list(zip(false_images, false_labels))
    all_data = true_data + false_data
    random.shuffle(all_data)
    return all_data


@pytest.fixture()
def tfrecord_dir(tmpdir):
    return tmpdir.mkdir('tfrecord_dir').strpath


@pytest.fixture()
def example_tfrecords(tfrecord_dir, example_data):
    tfrecord_locs = [
        '{}/train.tfrecords'.format(tfrecord_dir),
        '{}/test.tfrecords'.format(tfrecord_dir)
    ]
    for tfrecord_loc in tfrecord_locs:
        if os.path.exists(tfrecord_loc):
            os.remove(tfrecord_loc)
        writer = tf.python_io.TFRecordWriter(tfrecord_loc)

        for example in example_data:
            writer.write(create_tfrecord.serialize_image_example(matrix=example[0], label=example[1]))
        writer.close()


def test_input_utils(tfrecord_dir, example_tfrecords, size, true_image_values, false_image_values):
    # example_tfrecords sets up the tfrecords to read - needs to be an arg but is implicitly called by pytest

    train_batch = 64
    test_batch = 128

    train_loc = tfrecord_dir + '/train.tfrecords'
    test_loc = tfrecord_dir + '/test.tfrecords'
    assert os.path.exists(train_loc)
    assert os.path.exists(test_loc)

    train_config = input_utils.InputConfig(
        name='train',
        tfrecord_loc=train_loc,
        initial_size=size,
        final_size=size,
        channels=3,
        label_col=None,  # TODO not sure about this
        batch_size=train_batch,
        stratify=False,
        shuffle=False,
        stratify_probs=None,
        geometric_augmentation=False,
        photographic_augmentation=False
    )
    train_features, train_labels = input_utils.get_input(train_config)
    train_images = train_features['x']

    train_strat_config = input_utils.InputConfig(
        name='train',
        tfrecord_loc=train_loc,
        initial_size=size,
        final_size=size,
        channels=3,
        label_col=None,  # TODO not sure about this
        batch_size=train_batch,
        stratify=True,
        shuffle=False,
        stratify_probs=np.array([0.8, 0.2]),
        geometric_augmentation=False,
        photographic_augmentation=False
    )
    train_features_strat, train_labels_strat = input_utils.get_input(train_strat_config)
    train_images_strat = train_features_strat['x']

    test_config = input_utils.InputConfig(
        name='test',
        tfrecord_loc=test_loc,
        initial_size=size,
        final_size=size,
        channels=3,
        label_col=None,  # TODO not sure about this
        batch_size=test_batch,
        stratify=False,
        shuffle=False,
        stratify_probs=None,
        geometric_augmentation=False,
        photographic_augmentation=False
    )
    test_features, test_labels = input_utils.get_input(test_config)
    test_images = test_features['x']

    test_strat_config = input_utils.InputConfig(
        name='test_strat',
        tfrecord_loc=test_loc,
        initial_size=size,
        final_size=size,
        channels=3,
        label_col=None,  # TODO not sure about this
        batch_size=test_batch,
        stratify=True,
        shuffle=False,
        stratify_probs=np.array([0.8, 0.2]),
        geometric_augmentation=False,
        photographic_augmentation=False
    )
    test_features_strat, test_labels_strat = input_utils.get_input(test_strat_config)
    test_images_strat = test_features_strat['x']

    with tf.train.MonitoredSession() as sess:  # mimic Estimator environment

        train_images, train_labels = sess.run([train_images, train_labels])
        assert len(train_labels) == train_batch
        assert train_images.shape[0] == train_batch
        assert train_labels.mean() < .6  # should not be stratified
        assert train_images.shape == (train_batch, size, size, 1)
        verify_images_match_labels(train_images, train_labels, true_image_values, false_image_values, size)

        train_images_strat, train_labels_strat = sess.run([train_images_strat, train_labels_strat])
        assert len(train_labels_strat) == train_batch
        assert train_images_strat.shape[0] == train_batch
        assert train_labels_strat.mean() < 0.75 and train_labels_strat.mean() > 0.25  # stratify not very accurate...
        assert train_images_strat.shape == (train_batch, size, size, 1)
        verify_images_match_labels(train_images_strat, train_labels_strat, true_image_values, false_image_values, size)

        test_images, test_labels = sess.run([test_images, test_labels])
        assert len(test_labels) == test_batch
        assert test_images.shape[0] == test_batch
        assert test_labels.mean() < 0.6  # should not be stratified
        assert test_images.shape == (test_batch, size, size, 1)
        verify_images_match_labels(test_images, test_labels, true_image_values, false_image_values, size)

        test_images_strat, test_labels_strat = sess.run([test_images_strat, test_labels_strat])
        assert len(test_labels_strat) == test_batch
        assert test_images_strat.shape[0] == test_batch
        assert test_labels_strat.mean() < 0.75 and test_labels_strat.mean() > 0.25  # stratify not very accurate...
        assert test_images_strat.shape == (test_batch, size, size, 1)
        verify_images_match_labels(test_images_strat, test_labels_strat, true_image_values, false_image_values, size)


def verify_images_match_labels(images, labels, true_values, false_values, size):
    for example_n in range(len(labels)):
        if labels[example_n] == 1:
            expected_values = true_values
        else:
            expected_values = false_values
        expected_matrix = np.ones((size, size, 1), dtype=np.float32) * expected_values
        assert images[example_n, :, :, :] == pytest.approx(expected_matrix)


# 64, 0.4 loads perfectly for both
# 28, 0.5 loads perfectly for both
# same input routines at 2 different sizes work perfectly on the oldest tfrecords
# 424, 0.4 fails for both (newer than the others)
# 48, 0.4 - new routine with small image, fails for both
# 96, 0.4 - fails for both


def test_input_utils_visual():
    # example_tfrecords sets up the tfrecords to read - needs to be an arg but is implicitly called by pytest

    batch_size = 16
    size = 96
    channels = 3
    tfrecord_loc = 'zoobot/data/panoptes_featured_s{}_l0.4_train.tfrecord'.format(str(int(size)))
    assert os.path.exists(tfrecord_loc)

    config = input_utils.InputConfig(
        name='train',
        tfrecord_loc=tfrecord_loc,
        initial_size=size,
        final_size=size,
        channels=channels,
        label_col=None,  # TODO not sure about this
        batch_size=batch_size,
        stratify=False,
        shuffle=False,
        stratify_probs=None,
        geometric_augmentation=False,
        photographic_augmentation=False)

    batch_images, _ = input_utils.load_batches(config)

    with tf.train.MonitoredSession() as sess:
        batch_images = sess.run(batch_images)

    print(batch_images.shape)
    plt.clf()
    plt.imshow(batch_images[0])
    plt.savefig(TEST_EXAMPLE_DIR + '/original_loaded_image.png')


def test_minimal_loading_from_tfrecord():
    n_examples = 16
    size = 96
    channels = 3
    tfrecord_loc = 'zoobot/data/panoptes_featured_s{}_l0.4_train.tfrecord'.format(str(int(size)))

    serialized_examples = load_serialized_examples_from_tfrecord(tfrecord_loc, n_examples)
    examples = [parse_example(example, size, channels) for example in serialized_examples]
    images = [example['matrix'].reshape(size, size, channels) for example in examples]
    plt.clf()
    plt.imshow(images[0])
    plt.savefig(TEST_EXAMPLE_DIR + '/original_minimal_loaded_image.png')


def load_serialized_examples_from_tfrecord(tfrecord_loc, n_examples):
    # see http://www.machinelearninguru.com/deep_learning/tensorflow/basics/tfrecord/tfrecord.html
    with tf.Session() as sess:
        filename_queue = tf.train.string_input_producer([tfrecord_loc], num_epochs=1)
        reader = tf.TFRecordReader()
        _, serialized_example = reader.read(filename_queue)

        init_op = tf.group(tf.global_variables_initializer(), tf.local_variables_initializer())
        sess.run(init_op)
        # Create a coordinator and run all QueueRunner objects
        coord = tf.train.Coordinator()
        threads = tf.train.start_queue_runners(coord=coord)
        return [sess.run(serialized_example) for n in range(n_examples)]


def parse_example(example, size, channels):
    with tf.Session() as sess:
        features = {
            'matrix': tf.FixedLenFeature((size * size * channels), tf.float32),
            'label': tf.FixedLenFeature([], tf.int64),
        }
        parsed_example = tf.parse_single_example(example, features=features)
        return sess.run(parsed_example)

#
# def show_example(example, ax=None):
#     im = example['matrix'].reshape(size, size, channels)
#     label = example['label']
    # if ax is None:
    #     ax = plt
    # ax.imshow(im)
    # ax.text(50, 50, label, fontsize=16)