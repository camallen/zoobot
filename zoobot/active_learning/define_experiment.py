import os
import shutil
import logging

import pandas as pd

"""Shared logic to refine catalogs"""

def get_experiment_catalogs(catalog, question, save_dir):
    catalog = shuffle(catalog)  # crucial for GZ2!
    catalog = define_identifiers(catalog)
    catalog = define_labels(catalog, question)
    labelled, unlabelled = split_labelled_and_unlabelled(catalog, question)
    return catalog, labelled, unlabelled


def split_labelled_and_unlabelled(catalog, question):
    retired = catalog.apply(subject_is_retired, axis=1)
    labelled = catalog[retired]
    if question == 'bar':
        labelled = labelled.query('bar_total-votes' < 10)
    unlabelled= catalog[~retired]
    return labelled, unlabelled


def shuffle(df):
    # THIS IS CRUCIAL. GZ catalog is not properly shuffled, and featured-ness changes systematically
    return df.sample(len(df)).reset_index()


def define_identifiers(catalog):
    if any(catalog.duplicated(subset=['iauname'])):
        logging.warning('Found duplicated iaunames - dropping!')
        catalog = catalog.drop_duplicates(subset=['iauname'], keep=False)
    catalog['id_str'] = catalog['iauname']
    return catalog


def subject_is_retired(subject):
    return subject['smooth-or-featured_total-votes'] > 1 # TODO !!temporary until first big reduction! Will be 37ish 


def define_labels(catalog, question):
    catalog['total_votes'] = catalog['smooth-or-featured_total-votes']
    if question == 'smooth':
        catalog['label'] = catalog['smooth-or-featured_smooth']
    elif question == 'bar':
        catalog['total_votes'] = catalog['bar_total-votes']
        try:
            catalog['label'] = catalog['bar_weak']  # DECALS
        except KeyError:
            catalog['label'] = catalog['bar_yes']  # GZ2
    else:
        raise ValueError('question {} not understood'.format(question))
    return catalog



def get_mock_catalogs(labelled_catalog, save_dir, train_size=256, eval_size=2500):
    # given a (historical) labelled catalog, pretend split into labelled and unlabelled
    assert not any(pd.isnull(labelled_catalog['label']))
    oracle = labelled_catalog[['id_str', 'total_votes', 'label']]
    labelled_size = train_size + eval_size
    mock_labelled = labelled_catalog[:labelled_size]  # for training and eval. Could do basic split on these!
    mock_unlabelled = labelled_catalog[labelled_size:]  # for pool
    del mock_unlabelled['label']
    return mock_labelled, mock_unlabelled, oracle



if __name__ == '__main__':

    name = 'smooth_unfiltered'
    question = 'smooth'

    master_catalog_loc = 'data/decals/decals_master_catalog.csv'  # currently with all galaxies but only a few classifications
    catalog_dir = 'data/decals/prepared_catalogs/{}'.format(name)
    if os.path.isdir(catalog_dir):
        shutil.rmtree(catalog_dir)
    os.mkdir(catalog_dir)

    master_catalog = pd.read_csv(master_catalog_loc)
    catalog, labelled, unlabelled = get_experiment_catalogs(master_catalog, question, catalog_dir)

    # ad hoc filtering here
    catalog = catalog[:10000]

    labelled.to_csv(os.path.join(catalog_dir, 'labelled_catalog.csv'), index=False)
    unlabelled.to_csv(os.path.join(catalog_dir, 'unlabelled_catalog.csv'), index=False)
    catalog.to_csv(os.path.join(catalog_dir, 'full_catalog.csv'), index=False)

    simulation_dir = os.path.join(catalog_dir, 'simulation_context')
    if not os.path.isdir(simulation_dir):
        os.mkdir(simulation_dir)
    mock_labelled, mock_unlabelled, oracle = get_mock_catalogs(labelled, simulation_dir)

    mock_labelled.to_csv(os.path.join(simulation_dir, 'labelled_catalog.csv'), index=False)
    oracle.to_csv(os.path.join(simulation_dir, 'oracle.csv'), index=False)
    mock_unlabelled.to_csv(os.path.join(simulation_dir, 'unlabelled_catalog.csv'), index=False)
