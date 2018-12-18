import json
import ast
import itertools
import os
import argparse

import pandas as pd
import numpy as np
import statsmodels.api as sm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_context('poster')
sns.set()
from zoobot.estimators import input_utils

from zoobot.tfrecord import read_tfrecord
from zoobot.tests import TEST_FIGURE_DIR



def show_subjects_by_iteration(tfrecord_index_loc, n_subjects, size, channels, save_loc):
    with open(tfrecord_index_loc, 'r') as f:
        tfrecord_locs = json.load(f)
        assert isinstance(tfrecord_locs, list)
    
    nrows = len(tfrecord_locs)
    ncols = n_subjects
    scale = 2.
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(ncols * scale, nrows * scale))

    for iteration_n, tfrecord_loc in enumerate(tfrecord_locs):
        subjects = read_tfrecord.load_examples_from_tfrecord(
            [tfrecord_loc], 
            read_tfrecord.matrix_label_feature_spec(size, channels),
            n_examples=n_subjects)

        for subject_n, subject in enumerate(subjects):
            read_tfrecord.show_example(subject, size, channels, axes[iteration_n][subject_n])


    fig.tight_layout()
    fig.savefig(save_loc)


def get_metrics_from_log(log_loc):
    with open(log_loc, 'r') as f:
        content = f.readlines()
    log_entries = filter(lambda x: is_eval_log_entry(x) or is_iteration_split(x), content)

    iteration = 0
    eval_data = []
    for entry in log_entries:
        if is_iteration_split(entry):
            iteration += 1
        else:
            entry_data = parse_eval_log_entry(entry)
            entry_data['iteration'] = iteration
            eval_data.append(entry_data)
        
    metrics = pd.DataFrame(list(eval_data))
    return metrics[metrics['loss'] > 0]


def is_iteration_split(line):
    return 'All epochs completed - finishing gracefully' in line


def parse_eval_log_entry(line):
    """[summary]
    
    Args:
        line (str): [description]
    """
    # strip everything left of the colon, and interpret the rest as a literal expression
    colon_index = line.find('global step')
    step_str, data_str = line[colon_index + 12:].split(':')
    step = int(step_str)

    # split on commas, and remove commas
    key_value_strings = data_str.split(',')

    # split on equals, remove equals
    data = {}
    for string in key_value_strings:
        key, value = string.strip(',').split('=')
        data[key.strip()] = float(value.strip())
        data['step'] = step
    return data


def is_eval_log_entry(line):
    return 'Saving dict for global step' in line


def smooth_metrics(metrics_list):
    """[summary]
    
    Args:
        metrics_list (list): of df, where each df is the metrics for an iteration (step=row)
    
    Returns:
        [type]: [description]
    """

    smoothed_list = []
    for df in metrics_list:
        lowess = sm.nonparametric.lowess
        smoothed_metrics = lowess(
            df['loss'],
            df['step'],
            is_sorted=True, 
            frac=0.25)
        df['smoothed_loss'] = smoothed_metrics[:, 1]
        smoothed_list.append(df)
    return smoothed_list


def plot_log_metrics(metrics_list, save_loc, title=None):

    fig, (ax1, ax2) = plt.subplots(nrows=2, figsize=(8, 6), sharex=True, sharey=True)
    for df in metrics_list:
        iteration = df['iteration'].iloc[0]
        ax1.plot(
            df['step'],
            df['smoothed_loss'],
            label='Iteration {}'.format(iteration)
        )

        ax2.plot(
            df['step'],
            df['loss'],
            label='Iteration {}'.format(iteration)
        )

    ax2.set_xlabel('Step')
    ax1.set_ylabel('Eval Loss')
    ax2.set_ylabel('Eval Loss')
    ax1.legend()
    ax2.legend()
    if title is not None:
        ax1.set_title(title)
    fig.tight_layout()
    fig.savefig(save_loc)


def find_log(directory):
    return os.path.join(directory, list(filter(lambda x: '.log' in x, os.listdir(directory)))[0])  # returns as tuple of (dir, name)


def compare_metrics(all_metrics, save_loc, title=None):
    
    best_rows = []
    for df in all_metrics:
        df = df.reset_index()
        best_loss_idx = df['smoothed_loss'].idxmin()
        best_row = df.iloc[best_loss_idx]
        best_rows.append(best_row)

    metrics = pd.DataFrame(best_rows)


    fig, ax = plt.subplots()
    sns.barplot(
        data=metrics, 
        x='iteration', 
        y='smoothed_loss', 
        hue='name', 
        ax=ax,
        ci=80
    )
    # ax.set_ylim([0.75, 0.95])
    ax.set_ylabel('Final eval Loss')
    if title is not None:
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(save_loc)

def split_by_iter(df):
    return [df[df['iteration'] == iteration] for iteration in df['iteration'].unique()]


def get_smooth_metrics_from_log(log_loc, name=None):
        metrics = get_metrics_from_log(log_loc)
        metric_iters = split_by_iter(metrics)
        metric_smooth = smooth_metrics(metric_iters)
        if name is not None:
            for df in metric_smooth:
                df['name'] = name  # record baseline vs active, for example
        return metric_smooth


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Analyse active learning')
    parser.add_argument('--active_dir', dest='active_dir', type=str,
                    help='')
    parser.add_argument('--baseline_dir', dest='baseline_dir', type=str,
                    help='')
    parser.add_argument('--initial', dest='initial', type=int,
                    help='')
    parser.add_argument('--per_iter', dest='per_iter', type=int,
                    help='')
    parser.add_argument('--output_dir', dest='output_dir', type=str,
                    help='')

    args = parser.parse_args()
    if not os.path.isdir(args.output_dir):
        os.mkdir(args.output_dir)

    initial = args.initial
    per_iter = args.per_iter
    title = 'Initial: {}. Per iter: {}. From scratch.'.format(initial, per_iter)
    name = '{}init_{}per'.format(initial, per_iter)

    # TODO refactor?
    active_index_loc = os.path.join(args.active_dir, list(filter(lambda x: 'requested_tfrecords_index' in x, os.listdir(args.active_dir)))[0])  # returns as tuple of (dir, name)

    n_subjects = 15
    size = 128
    channels = 3
    show_subjects_by_iteration(active_index_loc, 15, 128, 3, os.path.join(args.output_dir, 'subject_history_active.png'))


    active_log_loc = find_log(args.active_dir)
    active_save_loc = os.path.join(args.output_dir, 'acc_metrics_active_' + name + '.png')

    active_smooth_metrics = get_smooth_metrics_from_log(active_log_loc, name='active')
    plot_log_metrics(active_smooth_metrics, active_save_loc, title=title)

    if args.baseline_dir != '':
        baseline_index_loc = os.path.join(args.baseline_dir, list(filter(lambda x: 'requested_tfrecords_index' in x, os.listdir(args.baseline_dir)))[0])  # returns as tuple of (dir, name)
        show_subjects_by_iteration(baseline_index_loc, 15, 128, 3, os.path.join(args.output_dir, 'subject_history_baseline.png'))
        baseline_log_loc = find_log(args.baseline_dir)
        baseline_save_loc = os.path.join(args.output_dir, 'acc_metrics_baseline_' + name + '.png')
        baseline_smooth_metrics = get_smooth_metrics_from_log(baseline_log_loc, name='baseline')
        plot_log_metrics(baseline_smooth_metrics, baseline_save_loc, title=title)

        comparison_save_loc = os.path.join(args.output_dir, 'acc_comparison_' + name + '.png')
        compare_metrics(baseline_smooth_metrics + active_smooth_metrics, comparison_save_loc, title=title)
