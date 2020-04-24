# load the decals joint catalog and save only the important columns
import logging
import os
import argparse

import numpy as np
import pandas as pd
from astropy.table import Table

from zoobot.science_logic import define_experiment


def create_decals_master_catalog(catalog_loc, classifications_loc, save_loc):
    """Convert zooniverse/decals joint catalog (from decals repo) for active learning and join to previous classifications
    
    Args:
        catalog_loc (str): Load science catalog of galaxies from here.
        classifications_loc (str): Load GZ classifications (see gz-panoptes-reduction repo) from here
        save_loc (str): Save master catalog here
    """
    catalog = pd.read_csv(catalog_loc)
    # conversion messes up strings into bytes
    # for str_col in ['iauname', 'png_loc', 'fits_loc']:
    #     catalog[str_col] = catalog[str_col].apply(lambda x: x.decode('utf-8'))

    # rename columns for convenience (could move this to DECALS repo)
    catalog['nsa_version'] = 'v1_0_0'

    # may need to change png prefix
    catalog = catalog.rename(index=str, columns={
        'fits_loc': 'local_fits_loc',
        'png_loc': 'local_png_loc',
        'z': 'redshift'
    })

    print('Galaxies: {}'.format(len(catalog)))
    # tweak png locs according to current machine
    catalog = specify_file_locs(catalog)

    classifications = pd.read_csv(classifications_loc)
    # add all historical classifications (before starting any active learning)
    df = pd.merge(catalog, classifications, how='left',
                  on='iauname')  # many rows will have None    
    df = define_experiment.drop_duplicates(df)
    df.to_csv(save_loc, index=False)


def create_gz2_master_catalog(catalog_loc: str, save_loc: str):
    raise NotImplementedError('Needs updating for multi-question')
    # usecols = [
    #     't01_smooth_or_features_a01_smooth_count',
    #     't01_smooth_or_features_a02_features_or_disk_count',
    #     't01_smooth_or_features_a03_star_or_artifact_count',
    #     't03_bar_a06_bar_count',
    #     't03_bar_a07_no_bar_count',
    #     'id',
    #     'ra',
    #     'dec',
    #     'png_loc',
    #     'png_ready',
    #     'sample'
    # ]
    # unshuffled_catalog = pd.read_csv(catalog_loc, usecols=usecols)
    # df = shuffle(unshuffled_catalog)
    # df = df[df['sample'] == 'original']
    # # make label and total_votes columns consistent with decals
    # df = df.rename(index=str, columns={
    #     't01_smooth_or_features_a01_smooth_count': 'smooth-or-featured_smooth',
    #     't01_smooth_or_features_a02_features_or_disk_count': 'smooth-or-featured_featured-or-disk',
    #     't01_smooth_or_features_a03_star_or_artifact_count': 'smooth-or-featured_artifact',
    #     #  note that these won't match because DECALS uses strong/weak/none
    #     't03_bar_a06_bar_count': 'bar_yes',
    #     't03_bar_a07_no_bar_count': 'bar_no',  # while GZ2 used yes/no
    #     'png_loc': 'local_png_loc'  # absolute file loc on local desktop
    # }
    # )
    # df['smooth-or-featured_total-votes'] = df['smooth-or-featured_smooth'] + \
    #     df['smooth-or-featured_featured-or-disk'] + \
    #     df['smooth-or-featured_artifact']
    # df['bar_total-votes'] = df['bar_yes'] + df['bar_no']
    # df['id_str'] = df['id'].astype(str)
    # # change to be inside data folder, specified relative to repo root
    # df['png_loc'] = df['local_png_loc'].apply(
    #     lambda x: 'data/' + x.lstrip('/Volumes/alpha'))
    # df = specify_file_locs(df)  # expected absolute file loc on EC2
    # assert os.path.exists
    # df.to_csv(save_loc, index=False)


def get_png_root_loc():
    # EC2
    if os.path.isdir('/home/ec2-user'):
        return '/home/ec2-user/root/repos/zoobot/data/decals'
    # laptop
    elif os.path.isdir('/home/walml'):
        return '/media/walml/beta/decals/'
    # EC2 Ubuntu
    elif os.path.isdir('/home/ubuntu'):
        return '/home/ubuntu/root/repos/zoobot/data/decals'
    # Oxford Desktop
    elif os.path.isdir('/data/repos'):
        # logging.critical('Local master catalog - do not use on EC2!')
        return '/Volumes/alpha/decals'
    else:
        raise ValueError('Cannot work out appropriate png root')


def specify_file_locs(df):
    """
    Add 'file_loc' which points to pngs at expected absolute EC2 path
    Remove 'png_loc (png relative to repo root) to avoid confusion
    """
    print(df.iloc[0]['local_png_loc'])
    # change to be inside data folder, specified relative to repo root
    df['png_loc'] = df['local_png_loc'].apply(
        lambda x: x.replace('/Volumes/alpha/decals/', get_png_root_loc())  # extra / is temporary?
    )
    print(df.iloc[0]['png_loc'])

    df['file_loc'] = df['png_loc']
    assert all(loc for loc in df['file_loc'])
    del df['png_loc']  # else may load this by default
    print(df['file_loc'].sample(5))
    check_no_missing_files(df['file_loc'])
    return df


def check_no_missing_files(locs):
    locs_missing = [not os.path.isfile(path) for path in locs]
    if any(locs_missing):
        raise ValueError('Missing {} files e.g. {}'.format(
            np.sum(locs_missing), locs[locs_missing][0]))


def shuffle(df):
    # THIS IS CRUCIAL. GZ catalog is not properly shuffled, and featured-ness changes systematically
    return df.sample(len(df)).reset_index()


if __name__ == '__main__':

    """
    Example use:
    python zoobot/science_logic/prepare_catalogs.py /media/mike/beta/decals/catalogs/decals_dr5_uploadable_master_catalog_nov_2019.csv /media/mike/beta/decals/results/classifications_oct_3_2019.csv data/decals/decals_master_catalog.csv
    """
    parser = argparse.ArgumentParser(description='Make shards')
    parser.add_argument('catalog_loc', type=str,
                        help='Path to csv of decals catalog (dr5 only), from decals repo')
    parser.add_argument('classifications_loc', type=str,
                        help='Latest streamed classifications, from gzreduction')
    parser.add_argument('save_loc', type=str,
                        help='Place active learning master catalog here')
    args = parser.parse_args()
    # assume run from repo root
    # LOCAL ONLY upload the results with dvc.

    # should run full reduction first and place in classifications_loc
    # see mwalmsley/gzreduction/get_latest.py

    create_decals_master_catalog(
        catalog_loc=args.catalog_loc,
        classifications_loc=args.classifications_loc,
        save_loc=args.save_loc
    )

    # create_gz2_master_catalog(
    #     catalog_loc='data/gz2/gz2_classifications_and_subjects.csv',
    #     save_loc='data/gz2/gz2_master_catalog.csv'
    # )
    # remember to add to dvc and push to s3

    # Agnostic of which question to answer
    # later, run finalise_catalog to apply filters and specify the question to solve
    # this is considered part of the shards, and results are saved to the shards directory

    # df = pd.read_csv('data/decals/decals_master_catalog.csv')
    # df['file_loc'] = df['file_loc'].apply(lambda x: '/home/ubuntu' + x)
    # print(df['file_loc'][0])
    # df.to_csv('data/decals/decals_master_catalog.csv', index=False)
