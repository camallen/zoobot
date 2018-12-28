import pytest

import copy
import os

import numpy as np
import pandas as pd

from astropy.io import fits
from zoobot.active_learning import make_shards, execute


# due to conftest.py, catalog fits_loc is absolute and points to fits_native_dir
@pytest.fixture()
def labelled_catalog(catalog_random_images):
    catalog = catalog_random_images.copy()
    catalog['id_str'] = catalog_random_images['id_str'] + '_from_labelled'  # must be unique
    catalog['label'] = np.random.rand(len(catalog))
    return catalog


@pytest.fixture()
def unlabelled_catalog(catalog_random_images):
    catalog = catalog_random_images.copy()
    catalog['id_str'] = catalog_random_images['id_str'] + '_from_unlabelled'  # must be unique
    return catalog


@pytest.fixture()
def shard_config(tmpdir, size, channels):
    config = make_shards.ShardConfig(
        shard_dir=tmpdir.mkdir('base_dir').strpath,
        inital_size=size,
        final_size=size,
        channels=channels)
    return config


@pytest.fixture()
def shard_config_ready(shard_config, labelled_catalog, unlabelled_catalog):
    config = copy.copy(shard_config)
    config.prepare_shards(labelled_catalog, unlabelled_catalog)
    assert config.ready()
    return config


@pytest.fixture(
    params=[
        {
            'initial_estimator_ckpt': 'use_predictor',
            'warm_start': True
        },
        {
            'initial_estimator_ckpt': None,
            'warm_start': False
        }
    ])
def active_config(shard_config_ready, tmpdir, predictor_model_loc, request):

    warm_start = request.param['warm_start']

    # work around using fixture as param by having param toggle whether the fixture is used
    if request.param['initial_estimator_ckpt'] == 'use_predictor':
        initial_estimator_ckpt = predictor_model_loc
    else:
        initial_estimator_ckpt = None
    
    config = execute.ActiveConfig(
        shard_config_ready, 
        run_dir=tmpdir.mkdir('run_dir').strpath,
        iterations=2,
        shards_per_iter=2,
        subjects_per_iter=10,
        initial_estimator_ckpt=initial_estimator_ckpt,
        warm_start=warm_start
        )
    return config


@pytest.fixture()
def active_config_ready(active_config):
    config = copy.copy(active_config)
    config.prepare_run_folders()
    assert config.ready()
    return config


@pytest.fixture
def catalog_random_images(size, channels, fits_native_dir):
    assert os.path.exists(fits_native_dir)
    n_subjects = 64
    id_strings = [str(n) for n in range(n_subjects)]
    matrices = np.random.rand(n_subjects, size, size, channels)
    relative_fits_locs = ['random_{}.fits'.format(n) for n in range(n_subjects)]
    fits_locs = list(map(lambda rel_loc: os.path.join(fits_native_dir, rel_loc), relative_fits_locs))
    for matrix, loc in zip(matrices, fits_locs):  # write to fits
        hdu = fits.PrimaryHDU(matrix)
        hdu.writeto(loc, overwrite=True)
        assert os.path.isfile(loc)
    catalog = pd.DataFrame(data={'id_str': id_strings, 'fits_loc': fits_locs})
    return catalog


@pytest.fixture()
def db_loc(tmpdir):
    return os.path.join(tmpdir.mkdir('db_dir').strpath, 'db_is_here.db')


@pytest.fixture()
def acquisition_func():
    # Converts loaded subjects to acquisition scores. Here, takes the mean.
    # Must return float, not np.float32, else db will be confused and write as bytes
    def mock_acquisition_callable(matrix_list):
        assert isinstance(matrix_list, list)
        assert all([isinstance(x, np.ndarray) for x in matrix_list])
        assert all([x.shape[0] == x.shape[1] for x in matrix_list])
        return [float(x.mean()) for x in matrix_list]
    return mock_acquisition_callable


@pytest.fixture()
def acquisition():
    return np.random.rand()