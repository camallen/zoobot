import pytest

import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from zoobot.tests import TEST_FIGURE_DIR
from zoobot.estimators import make_predictions


@pytest.fixture
def predictions():
    return np.array([[0.4, 0.5, 0.6] for n in range(2)])


@pytest.fixture
def n_draws():
    return 10


@pytest.fixture
def bin_probs(n_draws):
    unscaled_probs = np.random.rand(12, 3, n_draws + 1)
    total_by_k = np.sum(unscaled_probs, axis=2)
    total_by_k_expanded = np.tile(np.expand_dims(total_by_k, axis=-1), n_draws + 1)
    return unscaled_probs / total_by_k_expanded


def test_load_predictor(predictor_model_loc):
    predictor = make_predictions.load_predictor(predictor_model_loc)
    assert callable(predictor)


def test_get_samples_of_subjects(predictor, size, channels):
    n_samples = 5
    n_subjects = 26
    images = np.random.rand(n_subjects, size, size, channels)
    samples = make_predictions.get_samples_of_images(predictor, images, n_samples)
    assert samples.shape == (n_subjects, n_samples)
    assert not np.allclose(samples[0, 0], samples [0, 1])
    assert not np.allclose(samples[0], samples[1])  # predictor is non-deterministic

def test_get_samples_of_many_subjects(predictor, size, channels):
    n_samples = 5
    n_subjects = 20000
    images = np.random.rand(n_subjects, size, size, channels)
    samples = make_predictions.get_samples_of_images(predictor, images, n_samples)
    assert predictor.call_count > n_samples
    assert samples.shape == (n_subjects, n_samples)
    assert not np.allclose(samples[0, 0], samples [0, 1])
    assert not np.allclose(samples[0], samples[1])  # predictor is NOT deterministic
    # TODO replace with a non-deterministic predictor


def test_binomial_prob_per_k(n_draws):
    sampled_rho = 0.5
    prob_per_k = make_predictions.binomial_prob_per_k(sampled_rho, n_draws)
    for n in range(int(n_draws/2) - 1):
        assert np.allclose(prob_per_k[n], prob_per_k[-1-n])
    assert prob_per_k[0] < prob_per_k[1] < prob_per_k[2]
