import os
import shutil
import json
import logging
import time
from datetime import datetime

import pandas as pd
from shared_astro_utils import upload_utils, time_utils
from gzreduction.get_latest.main import Volunteers  # TODO sloppy

from zoobot.active_learning.oracle import Oracle
from zoobot.active_learning import prepare_catalogs, define_experiment

# Oracle state must not change between iterations! (Panoptes itself can change, of course)

# TODO define working_dir for volunteers service, copy if/else 

class Panoptes(Oracle):

    def __init__(self, catalog_loc, login_loc, project_id, workflow_id, last_id, question):
        assert os.path.exists(catalog_loc)  # in principle, should only need unlabelled galaxies
        self._catalog_loc = catalog_loc  # unlabelled catalog
        self._login_loc = login_loc
        self._project_id = project_id
        self._workflow_id = workflow_id
        self._full_catalog = pd.read_csv(catalog_loc)  # e.g. joint catalog with file locs
        # all catalog columns will be uploaded, be careful
        self.last_id = last_id  # ignore classifications before this id TODO REMOVE
        # '91178981' for first DECALS classification, bad idea - >1 million responses!
        # 'TODO' for last id as of last major reduction, 2nd April 2019
        self.question = question  # e.g. 'smooth', 'bar'

        if os.path.isdir('/ubuntu/root'):
            # running on EC2
            working_dir = '/ubuntu/root/repos/zoobot/data/decals/classifications/streaming'
        else:
            working_dir = '/data/repos/zoobot/data/decals/classifications/streaming'
        assert os.path.isdir(working_dir)
        self._volunteers = Volunteers(
            working_dir=working_dir,
            workflow_id=self._workflow_id,
            max_classifications=1e8
        )

    def request_labels(self, subject_ids, name, retirement):
        """Upload subjects with ids matching subject_ids to Panoptes project
        
        Args:
            subject_ids ([type]): [description]
        """
        selected_catalog = self._full_catalog[self._full_catalog['id_str'].isin(subject_ids)]  # getting really messy with this...
        #restrict to key columns
        upload_cols = ['iauname', 'nsa_id', 'ra', 'dec', 'petrotheta', 'petroth50', 'petroth90', 'redshift', 'nsa_version', 'file_loc']
        upload_catalog = selected_catalog[upload_cols]
        upload_catalog['#retirement_limit'] = retirement
        upload_catalog['#uploader'] = 'panoptes_oracle'

        logging.info('Uploading {} subjects to {}'.format(len(subject_ids), name))
        manifest = upload_utils.create_manifest_from_catalog(upload_catalog)
        upload_utils.upload_manifest_to_galaxy_zoo(
            subject_set_name=name,
            manifest=manifest,
            project_id=self._project_id,
            login_loc=self._login_loc)
        logging.info('Upload complete')

    def get_labels(self, working_dir):
        """Get all recent labels from Panoptes. 
        - (Download with Panoptes Python client
        - Aggregate with GZ Reduction Spark routine)
        """
        if not os.path.isdir(working_dir):
            os.mkdir(working_dir)

        # Run GZ Reduction to get all new classifications
        # print('WARNING LIMITING TO 500 classifications! DEBUG ONLY')
        # classifications = execute_reduction(
        #     workflow_id=self._workflow_id,
        #     working_dir=working_dir,
        #     last_id=self.last_id,
        #     max_classifications=500  # WARNING WARNING DEBUG VALUE TODO
        # )
        # get the latest classifications

        all_classifications = self._volunteers.get_all_classifications()
        # this now gets ALL (retired) labels, not just new ones - be careful when using!

        retired, _ = define_experiment.split_retired_and_not(all_classifications, self.question)
        retired = define_experiment.define_identifiers(retired)  # add iauname
        retired = define_experiment.define_labels(retired, self.question)  # add 'label' and 'total_votes', drop low n bars

        # drop any iauname-duplicated galaxies for safety (will already be grouped on subject_id)
        if any(retired['iauname'].duplicated()):  # TODO refactor out from here and master catalog
            print('Duplicated:')
            counts = retired['iauname'].value_counts()
            print(counts[counts > 1])
            retired = retired.drop_duplicates(subset=['iauname'], keep=False)

        logging.info('Labels acquired from oracle: {}'.format(len(retired)))
        return retired['id_str'].values, retired['label'].values, retired['total_votes'].values


    def save(self, save_dir):
        data = {
            'catalog_loc': self._catalog_loc,
            'login_loc': self._login_loc,
            'project_id': self._project_id,
            'workflow_id': self._workflow_id,
            'last_id': self.last_id,
            'question': self.question
        }
        with open(os.path.join(save_dir, 'oracle_config.json'), 'w') as f:
            json.dump(data, f)

class PanoptesMock(Oracle):

    def __init__(self, oracle_loc, subjects_requested_loc):
        assert os.path.isfile(oracle_loc)  # must already exist
        logging.info('Using oracle loc: {}'.format(oracle_loc))
        logging.info('Using subjects requested loc: {}'.format(subjects_requested_loc))
        self._oracle_loc = oracle_loc
        self._subjects_requested_loc = subjects_requested_loc

    def request_labels(self, subject_ids, name, retirement):
        logging.info('Pretending to upload {} subjects: {}'.format(len(subject_ids), name))
        assert len(set(subject_ids)) == len(subject_ids)  # must be unique
        with open(self._subjects_requested_loc, 'w') as f:
            json.dump(subject_ids, f)

    def get_labels(self, working_dir):
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
        print(len(id_str_dummy_df), 'id strs in dummy df')
        print('e.g. {}'.format(id_str_dummy_df['id_str'][:5]))
        print(len(known_catalog), 'known catalog at', self._oracle_loc)
        print('with ids e.g. {}'.format(known_catalog['id_str'][:5]))
        matching_df = pd.merge(id_str_dummy_df, known_catalog, how='inner', on='id_str')
        print(len(matching_df), 'matches in known catalog')
        labels = list(matching_df['label'].astype(int))
        total_votes = list(matching_df['total_votes'].astype(int))
        print(len(labels), 'labels')
        print(len(total_votes), 'total_votes')
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


def load_panoptes_oracle(save_dir):
    with open(os.path.join(save_dir, 'oracle_config.json'), 'r') as f:
        return Panoptes(**json.load(f))

def load_panoptes_mock_oracle(save_dir):
    with open(os.path.join(save_dir, 'oracle_config.json'), 'r') as f:
        return PanoptesMock(**json.load(f))

def load_oracle(save_dir):
    try:
        return load_panoptes_oracle(save_dir)
    except TypeError:  # will have different args for init
        return load_panoptes_mock_oracle(save_dir)
