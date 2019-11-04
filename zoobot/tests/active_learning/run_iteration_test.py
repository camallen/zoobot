import pytest

import os
import json

from zoobot.active_learning import run_iteration
# Functional test for running a single iteration TODO



def initial_state(request, initial_estimator_ckpt):
    iteration_dir = tmpdir.mkdir('initial_iteration_dir').strpath
    return run_iteration.InitialState(
        iteration_dir=iteration_dir,
        iteration_n=12,
        initial_estimator_ckpt=initial_estimator_ckpt,
        initial_train_tfrecords='some_train_tfrecords',
        initial_db_loc='some.db',
        prediction_shards='some_prediction_shards',
        learning_rate=0.001,
        epochs=14
    )


@pytest.fixture()
def final_state(tmpdir):
    return run_iteration.FinalState(
        iteration_n=7,
        estimators_dir='some_estimator_dir',
        train_records=['train_a.tfrecord', 'train_b.tfrecord'],
        db_loc='some_db_loc.db'
    )


@pytest.fixture()
def this_iteration_dir(tmpdir):
    return tmpdir.mkdir('this_iteration_dir').strpath


@pytest.fixture(params=[None, "", 'stuff/iteration_4'])
def previous_iteration_dir(request):
    return request.param


def test_get_initial_state(monkeypatch, instructions, this_iteration_dir, previous_iteration_dir, final_state):
    def mock_load_final_state(x):
        return final_state
    monkeypatch.setattr(run_iteration, 'load_final_state', mock_load_final_state)
    def mock_get_prediction_shards(x, y):
        return ['prediction_shard_a', 'prediction_shard_b']
    monkeypatch.setattr(run_iteration, 'get_prediction_shards', mock_get_prediction_shards)
    
    initial_state = run_iteration.get_initial_state(
        instructions, this_iteration_dir, previous_iteration_dir)
    
    assert this_iteration_dir == this_iteration_dir
    
    if (previous_iteration_dir is None) or (previous_iteration_dir is ""):
        assert initial_state.iteration_n == 0
        assert initial_state.initial_estimator_ckpt == instructions.initial_estimator_ckpt
        # etc
    else:
        assert initial_state.initial_estimator_ckpt == final_state.estimators_dir
        assert initial_state.iteration_n == final_state.iteration_n + 1
        # etc


def test_save_final_state(final_state, tmpdir):
    save_dir = tmpdir.mkdir('save_dir').strpath
    run_iteration.save_final_state(
        final_state=final_state,
        save_dir=save_dir
    )

    with open(os.path.join(save_dir, 'final_state.json')) as f: 
        saved_state = json.load(f)
        assert saved_state['iteration_n'] == final_state.iteration_n
        assert saved_state['estimators_dir'] == final_state.estimators_dir
        assert saved_state['train_records'] == final_state.train_records
        assert saved_state['db_loc'] == final_state.db_loc


@pytest.mark.skip(reason="not implemented")
def test_main():
    pass

@pytest.mark.skip(reason="not implemented")
def test_get_prediction_shards(instructions):
    pass



# def test_run(active_config, tmpdir, monkeypatch, catalog_random_images, tfrecord_dir, mocker):
#     # TODO need to test we're using the estimators we expect, needs refactoring first
#     # catalog_random_images is a required arg because the fits files must actually exist

#     # retrieve these shard locs for use in .run()
#     mocker.patch('zoobot.active_learning.execute.active_learning.get_all_shard_locs')
#     execute.active_learning.get_all_shard_locs.return_value = ['shard_loc_a', 'shard_loc_b', 'shard_loc_c', 'shard_loc_d']

#     # mock out Iteration
#     mocker.patch('zoobot.active_learning.execute.iterations.Iteration', autospec=True)
#     mock_iteration = execute.iterations.Iteration.return_value  # shorthand reference for the instantiated class
#     # set db_loc and estimator_dirs attributes
#     type(mock_iteration).db_loc = mocker.PropertyMock(side_effect=['first_db_loc', 'second_db_loc', 'third_db_loc'])  
#     type(mock_iteration).estimators_dir = mocker.PropertyMock(side_effect=['first_est_dir', 'second_est_dir', 'third_est_dir'])  
#     # set train_records
#     mock_iteration.get_train_records.side_effect = ['first_records', 'second_records', 'third_records']

#     # TODO mock iterations as a whole, piecemeal moved to iterations
#     active_config.run(
#         conftest.mock_acquisition_func, 
#         conftest.mock_acquisition_func)

#     # created three iterations
#     assert execute.iterations.Iteration.call_count == 3
#     # called with:
#     # print(execute.iterations.Iteration.mock_calls)
#     calls = execute.iterations.Iteration.mock_calls
#     assert len(calls) == 9  # 3 inits, 3 .get_train_records, 3 .run
#     init_calls = [call for call in calls if call[0] == '']
#     assert len(init_calls) == 3

#     # for each call, check that args are updated correctly over iterations
#     first_init_call_args = init_calls[0][2]
#     assert first_init_call_args['prediction_shards'] == [
#         os.path.join(active_config.shards.shard_dir, shard_loc) for shard_loc in ['shard_loc_a', 'shard_loc_b']
#         ]
#     assert first_init_call_args['initial_estimator_ckpt'] == active_config.initial_estimator_ckpt
#     assert first_init_call_args['initial_db_loc'] == active_config.db_loc
#     assert first_init_call_args['initial_train_tfrecords'] == [os.path.join(active_config.shards.train_dir, loc) for loc in os.listdir(active_config.shards.train_dir) if loc.endswith('.tfrecord')]
#     assert first_init_call_args['eval_tfrecords'] == [os.path.join(active_config.shards.eval_dir, loc) for loc in os.listdir(active_config.shards.eval_dir) if loc.endswith('.tfrecord')]

#     second_init_call_args = init_calls[1][2]
#     assert second_init_call_args['prediction_shards'] == [
#         os.path.join(active_config.shards.shard_dir, shard_loc) for shard_loc in ['shard_loc_c', 'shard_loc_d']
#         ]
#     assert second_init_call_args['initial_estimator_ckpt'] == 'first_est_dir'
#     assert second_init_call_args['initial_db_loc'] == 'first_db_loc'
#     assert second_init_call_args['initial_train_tfrecords'] == 'first_records'

#     third_init_call_args = init_calls[2][2]
#     assert third_init_call_args['prediction_shards'] == [
#         os.path.join(active_config.shards.shard_dir, shard_loc) for shard_loc in ['shard_loc_a', 'shard_loc_b']
#         ]
#     assert third_init_call_args['initial_estimator_ckpt'] == 'second_est_dir'
#     assert third_init_call_args['initial_db_loc'] == 'second_db_loc'
#     assert third_init_call_args['initial_train_tfrecords'] == 'second_records'

#     # ran three times (mock iteration itself is always used, not created afresh)
#     assert mock_iteration.run.call_count == 3
