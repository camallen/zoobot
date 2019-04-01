import os
import json
import logging
import time

import pandas as pd
from shared_astro_utils import upload_utils, time_utils
from zoobot.active_learning.oracle import Oracle

# Oracle state must not change between iterations! (Panoptes itself can change, of course)

class Panoptes(Oracle):

    def __init__(self, catalog_loc, login_loc, project_id):
        assert os.path.exists(catalog_loc)
        self._catalog_loc = catalog_loc
        self._login_loc = login_loc
        self._project_id = project_id
        self._full_catalog = pd.read_csv(catalog_loc)  # may cause memory problems?
        # all catalog columns will be uploaded, be careful


    def request_labels(self, subject_ids, name):
        """Upload subjects with ids matching subject_ids to Panoptes project
        
        Args:
            subject_ids ([type]): [description]
        """
        selected_catalog = self._full_catalog[self._full_catalog['subject_id'].isin(subject_ids)]
        subject_set_name = '{}_{}_{}'.format(time_utils.current_date(), time.time(), name)
        logging.info('Uploading {} subjects: {}'.format(len(subject_ids), name))
        manifest = upload_utils.create_manifest_from_catalog(selected_catalog)
        upload_utils.upload_manifest_to_galaxy_zoo(
            subject_set_name=subject_set_name,
            manifest=manifest,
            galaxy_zoo_id=self._project_id,
            login_loc=self._login_loc)
        logging.info('Upload complete')

    def get_labels(self):
        """Get all recent labels from Panoptes. 
        - Download with Panoptes Python client
        - Aggregate with GZ Reduction Spark routine
        """
        raise NotImplementedError

    def save(self, save_dir):
        data = {
            'catalog_loc': self._catalog_loc,
            'login_loc': self._login_loc,
            'project_id': self._project_id
        }
        with open(os.path.join(save_dir, 'oracle_config.json'), 'w') as f:
            json.dump(data, f)

def load_panoptes_oracle(save_dir):
    with open(os.path.join(save_dir, 'oracle_config.json'), 'r') as f:
        return Panoptes(**json.load(f))

class PanoptesMock(Oracle):

    def __init__(self, oracle_loc, subjects_requested_loc):
        assert os.path.isfile(oracle_loc)  # must already exist
        logging.info('Using oracle loc: {}'.format(oracle_loc))
        logging.info('Using subjects requested loc: {}'.format(subjects_requested_loc))
        self._oracle_loc = oracle_loc
        self._subjects_requested_loc = subjects_requested_loc

    def request_labels(self, subject_ids, name):
        logging.info('Pretending to upload {} subjects: {}'.format(len(subject_ids), name))
        assert len(set(subject_ids)) == len(subject_ids)  # must be unique
        with open(self._subjects_requested_loc, 'w') as f:
            json.dump(subject_ids, f)

    def get_labels(self):
        # oracle.csv is created by make_shards.py, contains label and id_str pairs of vote fractions
        if not os.path.isfile(self._subjects_requested_loc):
            logging.warning(
                'No previous subjects requested at {}'.format(self._subjects_requested_loc))
            return [], [], []  # must unpack 3 values, look here if 'not enough values to unpack' error

        with open(self._subjects_requested_loc, 'r') as f:
            subject_ids = json.load(f)
        assert isinstance(subject_ids, list)
        assert len(subject_ids) > 0
        assert len(set(subject_ids)) == len(subject_ids)  # must be unique
        os.remove(self._subjects_requested_loc)

        known_catalog = pd.read_csv(
            self._oracle_loc,
            usecols=['id_str', 'label', 'total_votes'],
            dtype={'id_str': str, 'label': int, 'total_votes': int}
        )
        # return labels from the oracle, mimicking live GZ classifications
        labels = []
        id_str_dummy_df = pd.DataFrame(data={'id_str': subject_ids})
        matching_df = pd.merge(id_str_dummy_df, known_catalog, how='inner', on='id_str')
        labels = list(matching_df['label'].astype(int))
        total_votes = list(matching_df['total_votes'].astype(int))
        assert len(id_str_dummy_df) == len(matching_df)
        assert len(subject_ids) == len(labels)
        return subject_ids, labels, total_votes

    def save(self, save_dir):
        data = {
            'oracle_loc': self._oracle_loc,
            'subjects_requested_loc': self._subjects_requested_loc,
        }
        with open(os.path.join(save_dir, 'oracle_config.json'), 'w') as f:
            json.dump(data, f)

def load_panoptes_mock_oracle(save_dir):
    with open(os.path.join(save_dir, 'oracle_config.json'), 'r') as f:
        return PanoptesMock(**json.load(f))

def load_oracle(save_dir):
    try:
        return load_panoptes_oracle(save_dir)
    except KeyError:  # TODO actually wrong exception
        return load_panoptes_mock_oracle(save_dir)
