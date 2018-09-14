from connexion import request
from flask import current_app

import wes_elixir.ga4gh.wes.utils_runs as runs
import wes_elixir.ga4gh.wes.utils_service_info as service_info


def CancelRun(run_id):
    '''Cancel unfinished workflow run'''
    return runs.cancel_run(
        config=current_app.config,
        run_id=run_id
    )


def GetRunLog(run_id):
    '''Return detailed run info'''
    return runs.get_run_log(
        config=current_app.config,
        run_id=run_id
    )


def GetRunStatus(run_id):
    '''Return run status'''
    return runs.get_run_status(
        config=current_app.config,
        run_id=run_id
    )


def GetServiceInfo():
    '''Return service info'''
    return service_info.get_service_info(
        config=current_app.config
    )


def ListRuns(**kwargs):
    '''List ids and status of all workflow runs'''
    return runs.list_runs(
        config=current_app.config,
        **kwargs
    )


def RunWorkflow():
    '''Execute workflow'''
    return runs.run_workflow(
        config=current_app.config,
        form_data=request.form
    )