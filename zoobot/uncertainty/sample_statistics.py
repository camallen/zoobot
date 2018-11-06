
import numpy as np
import matplotlib
matplotlib.use('Agg') # TODO move this to .matplotlibrc
import statsmodels.api as sm
import pymc3

from zoobot.estimators import make_predictions


def samples_to_posterior(samples):
    # by row, expects samples of one subject
    # return stats.gaussian_kde(samples).pdf
    kernel = sm.nonparametric.KDEUnivariate(samples)
    kernel.fit()
    return kernel.evaluate


def samples_to_interval(samples, alpha=0.05):
    return pymc3.stats.hpd(samples, alpha)
