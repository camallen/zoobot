import pytest

import logging
import os
import random
import hashlib
import sqlite3
import time
import json

import numpy as np
import tensorflow as tf
import pandas as pd
from astropy.io import fits

from zoobot.tests import TEST_EXAMPLE_DIR
from zoobot.tfrecord import create_tfrecord, read_tfrecord
from zoobot.estimators.estimator_params import default_four_layer_architecture, default_params
from zoobot.active_learning import active_learning
from zoobot.estimators import make_predictions

if __name__ == '__main__':
    logging.basicConfig(
        filename=os.path.join(TEST_EXAMPLE_DIR, 'active_learning_test.log'),
        filemode='w',
        format='%(asctime)s %(message)s',
        level=logging.INFO)


@pytest.fixture()
def unknown_subject(size, channels):
    return {
        'matrix': np.random.rand(size, size, channels),
        'id_str': hashlib.sha256(b'some_id_bytes').hexdigest()
    }


@pytest.fixture()
def known_subject(known_subject):
    known_subject = unknown_subject.copy()
    known_subject['label'] = np.random.randint(1)
    return known_subject


@pytest.fixture()
def test_dir(tmpdir):
    return tmpdir.strpath


@pytest.fixture()
def empty_shard_db():
    db = sqlite3.connect(':memory:')

    cursor = db.cursor()

    cursor.execute(
        '''
        CREATE TABLE catalog(
            id_str STRING PRIMARY KEY,
            label INT DEFAULT NULL,
            fits_loc STRING)
        '''
    )
    db.commit()

    cursor.execute(
        '''
        CREATE TABLE shardindex(
            id_str STRING PRIMARY KEY,
            tfrecord TEXT)
        '''
    )
    db.commit()

    cursor.execute(
        '''
        CREATE TABLE acquisitions(
            id_str STRING PRIMARY KEY,
            acquisition_value FLOAT)
        '''
    )
    db.commit()
    return db



@pytest.fixture()
def filled_shard_db(empty_shard_db):
    db = empty_shard_db
    cursor = db.cursor()

    cursor.execute(
        '''
        INSERT INTO catalog(id_str, fits_loc)
                  VALUES(:id_str, :fits_loc)
        ''',
        {
            'id_str': 'some_hash',
            'fits_loc': os.path.join(TEST_EXAMPLE_DIR, 'example_a.fits')
        }
    )
    db.commit()
    cursor.execute(
        '''
        INSERT INTO acquisitions(id_str, acquisition_value)
                  VALUES(:id_str, :acquisition_value)
        ''',
        {
            'id_str': 'some_hash',
            'acquisition_value': 0.9
        }
    )
    db.commit()
    cursor.execute(
        '''
        INSERT INTO shardindex(id_str, tfrecord)
                  VALUES(:id_str, :tfrecord)
        ''',
        {
            'id_str': 'some_hash',
            'tfrecord': 'tfrecord_a'
        }
    )
    db.commit()

    cursor.execute(
        '''
        INSERT INTO catalog(id_str, fits_loc)
                  VALUES(:id_str, :fits_loc)
        ''',
        {
            'id_str': 'some_other_hash',
            'fits_loc': os.path.join(TEST_EXAMPLE_DIR, 'example_a.fits')
        }
    )
    cursor.execute(
        '''
        INSERT INTO acquisitions(id_str, acquisition_value)
                  VALUES(:id_str, :acquisition_value)
        ''',
        {
            'id_str': 'some_other_hash',
            'acquisition_value': 0.3
        }
    )
    db.commit()
    cursor.execute(
        '''
        INSERT INTO shardindex(id_str, tfrecord)
                  VALUES(:id_str, :tfrecord)
        ''',
        {
            'id_str': 'some_other_hash',
            'tfrecord': 'tfrecord_b'
        }
    )
    db.commit()

    cursor.execute(
        '''
        INSERT INTO catalog(id_str, fits_loc)
                  VALUES(:id_str, :fits_loc)
        ''',
        {
            'id_str': 'yet_another_hash',
            'fits_loc': os.path.join(TEST_EXAMPLE_DIR, 'example_a.fits')
        }
    )
    cursor.execute(
        '''
        INSERT INTO acquisitions(id_str, acquisition_value)
                  VALUES(:id_str, :acquisition_value)
        ''',
        {
            'id_str': 'yet_another_hash',
            'acquisition_value': 0.1
        }
    )
    db.commit()
    cursor.execute(
        '''
        INSERT INTO shardindex(id_str, tfrecord)
                  VALUES(:id_str, :tfrecord)
        ''',
        {
            'id_str': 'yet_another_hash',
            'tfrecord': 'tfrecord_a'  # same as first entry, should be selected if filter on rec a
        }
    )
    db.commit()
    return db


@pytest.fixture()
def filled_shard_db_with_labels(filled_shard_db):
    db = filled_shard_db
    cursor = db.cursor()
    default_loc = os.path.join(TEST_EXAMPLE_DIR, 'example_a.fits')
    for pair in [('some_hash', 1), ('some_other_hash', 1), ('yet_another_hash', 0)]:
        cursor.execute(
            '''
            UPDATE catalog SET label = ? WHERE id_str = ?
            ''',
            (pair[1], pair[0])
        )
        db.commit()
    return db


def test_write_catalog_to_tfrecord_shards(catalog, empty_shard_db, size, channels, columns_to_save, tfrecord_dir):
    active_learning.write_catalog_to_tfrecord_shards(catalog, empty_shard_db, size, columns_to_save, tfrecord_dir, shard_size=15)
    # verify_db_matches_catalog(catalog, empty_shard_db, 'id_str', label_col)
    verify_db_matches_shards(empty_shard_db, size, channels)
    verify_catalog_matches_shards(catalog, empty_shard_db, size, channels)


def verify_db_matches_catalog(catalog, db):
     # db should contain the catalog in 'catalog' table
    cursor = db.cursor()
    cursor.execute(
        '''
        SELECT id_str, label FROM catalog
        '''
    )
    catalog_entries = cursor.fetchall()
    for entry in catalog_entries:
        recovered_id = str(entry[0])
        recovered_label = entry[1]
        expected_label = catalog[catalog['id_str'] == recovered_id].squeeze()['label']
        assert recovered_label == expected_label


def load_shardindex(db):
    cursor = db.cursor()
    cursor.execute(
        '''
        SELECT id_str, tfrecord FROM shardindex
        '''
    )
    shardindex_entries = cursor.fetchall()
    shardindex_data = []
    for entry in shardindex_entries:
        shardindex_data.append({
            'id_str': str(entry[0]),  # TODO shardindex id is str, loaded from byte string
            'tfrecord': entry[1]
        })
    return pd.DataFrame(data=shardindex_data)


def verify_db_matches_shards(db, size, channels):
    # db should contain file locs in 'shardindex' table
    # tfrecords should have been written with the right files
    shardindex = load_shardindex(db)
    tfrecord_locs = shardindex['tfrecord'].unique()
    for tfrecord_loc in tfrecord_locs:
        expected_shard_ids = set(shardindex[shardindex['tfrecord'] == tfrecord_loc]['id_str'].unique())
        examples = read_tfrecord.load_examples_from_tfrecord(
            [tfrecord_loc], 
            read_tfrecord.matrix_id_feature_spec(size, channels)
        )
        actual_shard_ids = set([example['id_str'].decode() for example in examples])
        assert expected_shard_ids == actual_shard_ids


def verify_catalog_matches_shards(catalog, db, size, channels):
    from collections import Counter
    # TODO why do I need to import Counter here?! Surely it should be script scoped...
    shardindex = load_shardindex(db)
    tfrecord_locs = shardindex['tfrecord'].unique()
    # check that every catalog id is in exactly one shard
    assert not any(catalog['id_str'].duplicated())  # catalog must be unique to start with
    catalog_ids = Counter(catalog['id_str'])  # all 1's
    shard_ids = Counter()

    for tfrecord_loc in tfrecord_locs:
        examples = read_tfrecord.load_examples_from_tfrecord(
            [tfrecord_loc],
            read_tfrecord.matrix_id_feature_spec(size, channels)
        )
        ids_in_shard = [x['id_str'].decode() for x in examples]
        assert len(ids_in_shard) == len(set(ids_in_shard))  # must be unique within shard
        shard_ids = Counter(ids_in_shard) + shard_ids

    assert catalog_ids == shard_ids



def test_add_tfrecord_to_db(example_tfrecord_loc, empty_shard_db, catalog):  # bad loc
    active_learning.add_tfrecord_to_db(example_tfrecord_loc, empty_shard_db, catalog)
    cursor = empty_shard_db.cursor()
    cursor.execute(
        '''
        SELECT id_str, tfrecord FROM shardindex
        '''
    )
    saved_subjects = cursor.fetchall()
    for n, subject in enumerate(saved_subjects):
        assert str(subject[0]) == catalog.iloc[n]['id_str']  # strange string casting when read back
        assert subject[1] == example_tfrecord_loc


def test_save_acquisition_to_db(unknown_subject, acquisition, empty_shard_db):
    active_learning.save_acquisition_to_db(unknown_subject['id_str'], acquisition, empty_shard_db)
    cursor = empty_shard_db.cursor()
    cursor.execute(
        '''
        SELECT id_str, acquisition_value FROM acquisitions
        '''
    )
    saved_subject = cursor.fetchone()
    assert saved_subject[0] == unknown_subject['id_str']
    assert np.isclose(saved_subject[1], acquisition)


def test_record_acquisitions_on_tfrecord(filled_shard_db, acquisition_func, shard_locs, size, channels):
    # TODO needs test for duplicate values/replace behaviour
    shard_loc = shard_locs[0]
    active_learning.record_acquisitions_on_tfrecord(filled_shard_db, shard_loc, size, channels, acquisition_func)
    cursor = filled_shard_db.cursor()
    cursor.execute(
        '''
        SELECT acquisition_value FROM acquisitions
        '''
    )
    saved_subjects = cursor.fetchall()
    for subject in saved_subjects:
        assert 0. < subject[0] < 1.  # doesn't actually verify value is consistent


def test_get_top_acquisitions_any_shard(filled_shard_db):
    top_ids = active_learning.get_top_acquisitions(filled_shard_db, n_subjects=2)
    assert top_ids == ['some_hash', 'some_other_hash']


def test_get_top_acquisitions(filled_shard_db):
    top_ids = active_learning.get_top_acquisitions(filled_shard_db, n_subjects=2, shard_loc='tfrecord_a')
    assert top_ids == ['some_hash', 'yet_another_hash']


def test_add_labelled_subjects_to_tfrecord(monkeypatch, filled_shard_db_with_labels, tfrecord_dir, size, channels):
    tfrecord_loc = os.path.join(tfrecord_dir, 'active_train.tfrecord')
    subject_ids = ['some_hash', 'yet_another_hash']
    active_learning.add_labelled_subjects_to_tfrecord(filled_shard_db_with_labels, subject_ids, tfrecord_loc, size)

    # open up the new record and check
    subjects = read_tfrecord.load_examples_from_tfrecord([tfrecord_loc], read_tfrecord.matrix_id_feature_spec(size, channels))
    assert subjects[0]['id_str'] == 'some_hash'.encode('utf-8')  # tfrecord saves as bytes
    assert subjects[1]['id_str'] == 'yet_another_hash'.encode('utf-8')  #tfrecord saves as bytes


def test_add_labels_to_db(filled_shard_db):
    subjects = [
        {
            'id_str': 'some_hash',
            'label': 0
        },
        {
            'id_str': 'yet_another_hash',
            'label': 1
        }
    ]
    subject_ids = [x['id_str'] for x in subjects]
    labels = [x['label'] for x in subjects]
    active_learning.add_labels_to_db(subject_ids, labels, filled_shard_db)
    # read db, check labels match
    cursor = filled_shard_db.cursor()
    for subject in subjects:
        cursor.execute(
            '''
            SELECT label FROM catalog
            WHERE id_str = (:id_str)
            ''',
            (subject['id_str'],)
        )
        results = list(cursor.fetchall())
        assert len(results) == 1
        assert results[0][0] == subject['label']


def test_get_all_shard_locs(filled_shard_db):
    assert active_learning.get_all_shard_locs(filled_shard_db) == ['tfrecord_a', 'tfrecord_b']
