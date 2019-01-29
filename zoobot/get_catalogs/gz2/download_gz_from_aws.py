from tqdm import tqdm
import functools
import numpy as np

from multiprocessing.dummy import Pool as ThreadPool

from PIL import Image
from urllib.request import urlretrieve  # urlretrieve is unstable multithreaded - but doesn't seem to fall apart here


def download_png_threaded(catalog, png_dir, overwrite=False):

    catalog['png_loc'] = [get_png_loc(png_dir, catalog.iloc[index]) for index in range(len(catalog))]

    # pbar = tqdm(total=len(catalog), unit=' images created')
    # download_params = {
    #     'overwrite': overwrite,
    #     'pbar': pbar
    # }
    # download_images_partial = functools.partial(download_images, **download_params)

    # pool = ThreadPool(30)
    # pool.map(download_images_partial, catalog.iterrows())
    # pbar.close()
    # pool.close()
    # pool.join()

    catalog = check_images_are_downloaded(catalog)

    print("\n{} total galaxies".format(len(catalog)))
    print("{} png are downloaded".format(np.sum(catalog['png_ready'])))

    return catalog


def get_png_loc(png_dir, galaxy):
    return '{}/{}.png'.format(png_dir, galaxy['dr7objid'])


def download_images(galaxy, overwrite, max_attempts=5, pbar=None):

    # TODO Temporary fix for iterrows
    galaxy = galaxy[1]

    png_loc = galaxy['png_loc']

    if not png_downloaded_correctly(png_loc) or overwrite:
        attempt = 0
        while attempt < max_attempts:
            try:
                urlretrieve(galaxy['location'], galaxy['png_loc'])
                assert png_downloaded_correctly(png_loc)
                break
            except Exception as err:
                print(err, 'on galaxy {}, attempt {}'.format(galaxy['dr7objid'], attempt))
                attempt += 1

    if pbar:
        pbar.update()


def png_downloaded_correctly(png_loc):
    try:
        _ = Image.open(png_loc)
        return True
    except:
        return False


def check_images_are_downloaded(catalog):
    catalog['png_ready'] = np.zeros(len(catalog), dtype=bool)

    for row_index, galaxy in tqdm(catalog.iterrows(), total=len(catalog), unit=' images checked'):
        png_loc = galaxy['png_loc']
        catalog['png_ready'][row_index] = png_downloaded_correctly(png_loc)

    return catalog
