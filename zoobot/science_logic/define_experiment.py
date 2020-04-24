import os
import shutil
import logging
import argparse
import glob

import pandas as pd

"""Shared logic to refine catalogs. All science decisions should have happened after this script"""

def get_experiment_catalogs(catalog, save_dir):
    catalog = shuffle(catalog)  # crucial for GZ2!
    catalog = define_identifiers(catalog)
    filtered_catalog = apply_custom_filter(catalog)  # science logic lives here
    labelled, unlabelled = split_retired_and_not(filtered_catalog)  # for now using N=36, ignore galaxies with less labels
    # unlabelled and catalog will have no 'label' column
    return catalog, labelled, unlabelled


def split_retired_and_not(catalog):
    retired = catalog.apply(subject_is_retired, axis=1)
    labelled = catalog[retired]
    unlabelled = catalog[~retired]
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


def apply_custom_filter(catalog):
    # expect to change this a lot
    # for now, expect a 'smooth-or-featured_featured-or-disk_prediction_mean' col and filter > 0.25 (i.e. 10 of 40)
    # predicted beforehand by existing model TODO

    min_featured = 0.4  # roughly the half most featured - the current model very rarely predicts < 0.25 featured, which is a bit odd...
    previous_prediction_locs = glob.glob('temp/master_256_predictions_*.csv')
    previous_predictions = pd.concat([pd.read_csv(loc, usecols=['id_str', 'smooth-or-featured_featured-or-disk_prediction_mean']) for loc in previous_prediction_locs])
    len_before = len(catalog)
    catalog = pd.merge(catalog, previous_predictions, on='id_str', how='inner')
    len_merged = len(catalog)
    print(catalog['smooth-or-featured_featured-or-disk_prediction_mean'])
    filtered_catalog = catalog[catalog['smooth-or-featured_featured-or-disk_prediction_mean'] > min_featured]
    logging.info(f'{len_before} before filter, {len_merged} after merge, {len(filtered_catalog)} after filter at min_featured={min_featured}')
    print(f'{len_before} before filter, {len_merged} after merge, {len(filtered_catalog)} after filter at min_featured={min_featured}')
    return filtered_catalog


def subject_is_retired(subject):
    return subject['smooth-or-featured_total-votes'] > 36


def drop_duplicates(df):
    #  to be safe, could improve TODO
    if any(df['iauname'].duplicated()):
        logging.warning('Duplicated:')
        counts = df['iauname'].value_counts()
        logging.warning(counts[counts > 1])
    # no effect if no duplicates
    return df.drop_duplicates(subset=['iauname'], keep=False)


def get_mock_catalogs(labelled_catalog, save_dir, labelled_size, label_cols):
    # given a (historical) labelled catalog, pretend split into labelled and unlabelled
    for label_col in label_cols:
        if any(pd.isnull(labelled_catalog[label_col])):
            logging.critical(labelled_catalog[label_col])
            raise ValueError(f'Missing at least one label for {label_col}')
    # oracle has everything in real labelled catalog
    oracle = labelled_catalog.copy()  # could filter cols here if needed
    mock_labelled = labelled_catalog[:labelled_size]  # for training and eval
    mock_unlabelled = labelled_catalog[labelled_size:]  # for pool
    for label_col in label_cols:
        del mock_unlabelled[label_col]
    return mock_labelled, mock_unlabelled, oracle


if __name__ == '__main__':

    # master_catalog_loc = 'data/decals/decals_master_catalog.csv'  # currently with all galaxies but only a few classifications
    # catalog_dir = 'data/decals/prepared_catalogs/{}'.format(name)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(
        description='Define experiment (labelled catalog, question, etc) from master catalog')
    parser.add_argument('--master-catalog', dest='master_catalog_loc', type=str,
                        help='Name of experiment (save to data')
    parser.add_argument('--save-dir', dest='save_dir', type=str,
                        help='Save experiment catalogs here')
    args = parser.parse_args()
    master_catalog_loc = args.master_catalog_loc
    save_dir = args.save_dir

    # used to delete these columns from mock unlabelled catalog
    # could perhaps extract somewhere
    label_cols = [
        'smooth-or-featured_smooth',
        'smooth-or-featured_featured-or-disk',
        'has-spiral-arms_yes',
        'has-spiral-arms_no',
        'spiral-winding_tight',
        'spiral-winding_medium',
        'spiral-winding_loose',
        'bar_strong',
        'bar_weak',
        'bar_no',
        'bulge-size_dominant',
        'bulge-size_large',
        'bulge-size_moderate',
        'bulge-size_small',
        'bulge-size_none'
    ]

    if os.path.isdir(save_dir):
        shutil.rmtree(save_dir)
    os.mkdir(save_dir)

    master_catalog = pd.read_csv(master_catalog_loc)
    catalog, labelled, unlabelled = get_experiment_catalogs(
        master_catalog, save_dir)

    # ad hoc filtering here
    # catalog = catalog[:20000]

    labelled.to_csv(os.path.join(
        save_dir, 'labelled_catalog.csv'), index=False)
    unlabelled.to_csv(os.path.join(
        save_dir, 'unlabelled_catalog.csv'), index=False)
    catalog.to_csv(os.path.join(save_dir, 'full_catalog.csv'), index=False)

    simulation_dir = os.path.join(save_dir, 'simulation_context')
    if not os.path.isdir(simulation_dir):
        os.mkdir(simulation_dir)

    labelled_size = int(len(labelled) / 5.)  # pretend unlabelled, to be acquired
    mock_labelled, mock_unlabelled, oracle = get_mock_catalogs(
        labelled, simulation_dir, labelled_size, label_cols)

    mock_labelled.to_csv(os.path.join(
        simulation_dir, 'labelled_catalog.csv'), index=False)
    oracle.to_csv(os.path.join(simulation_dir, 'oracle.csv'), index=False)
    mock_unlabelled.to_csv(os.path.join(
        simulation_dir, 'unlabelled_catalog.csv'), index=False)
