import os
import shutil
import string
import subprocess

from celery import uuid
from json import decoder, loads
from pymongo.errors import DuplicateKeyError
from random import choice
from yaml import dump

import wes_elixir.database.db_utils as db_utils

from wes_elixir.errors.errors import BadRequest, WorkflowNotFound
from wes_elixir.ga4gh.wes.utils_bg_tasks import add_command_to_task_queue


#############################
### DELETE /runs/<run_id> ###
#############################

def cancel_run(config, celery_app, run_id):
    '''Cancel running workflow'''

    # Re-assign config values
    collection_runs = config['database']['collections']['runs']

    # Get task ID from database
    task_id = db_utils.find_one_field_by_index(collection_runs, 'run_id', run_id, 'task_id')

    # Cancel workflow run
    try:
        # TODO: Implement this better; terminate=True should be last resort
        # TODO: See here: https://stackoverflow.com/questions/8920643/cancel-an-already-executing-task-with-celery
        celery_app.control.revoke(task_id, terminate=True, signal='SIGHUP')

    # Raise error if workflow run was not found
    except Exception as e:
        print(e)
        raise WorkflowNotFound

    # Build formatted response object
    response = {"run_id": run_id}

    # Return response object
    return response


##########################
### GET /runs/<run_id> ###
##########################

def get_run_log(config, run_id):
    '''Get detailed log information for specific run'''

    # Re-assign config values
    collection_runs = config['database']['collections']['runs']

    # Get document from database
    document = db_utils.find_one_field_by_index(collection_runs, 'run_id', run_id, 'api')

    # Raise error if workflow run was not found
    if document is None:
        raise WorkflowNotFound

    # Return response
    return document


#################################
### GET /runs/<run_id>/status ###
#################################

def get_run_status(config, run_id):
    '''Get status information for specific run'''

    # Re-assign config values
    collection_runs = config['database']['collections']['runs']

    # Get document from database
    document = db_utils.find_one_field_by_index(collection_runs, 'run_id', run_id, 'api')
    
    # Extract workflow run state
    state = document['state']

    # Raise error if workflow run was not found
    if state is None:
        raise WorkflowNotFound

    # Build formatted response object
    response = {
        "run_id": run_id,
        "state": state
    }

    # Return response object
    return response


#################
### GET /runs ###
#################

def list_runs(config, **kwargs):
    '''Get status information for specific run'''

    # Re-assign config values
    collection_runs = config['database']['collections']['runs']

    # TODO: stable ordering (newest last?)
    # TODO: implement next page token

    # Fall back to default page size if not provided by user
    # TODO: uncomment when implementing pagination
    #page_size = kwargs['page_size'] if 'page_size' in kwargs else cnx_app.app.config['api_endpoints']['default_page_size']

    # Query database for workflow runs
    cursor = db_utils.find_fields(collection_runs, ['run_id', 'state'])

    # Iterate through list
    runs_list = list()
    for record in cursor:
        runs_list.append(record)

    # Build formatted response object
    response = {
        "next_page_token": "token",
        "runs": runs_list
    }

    # Return response object
    return response


##################
### POST /runs ###
##################

def run_workflow(config, form_data):
    '''Execute workflow and save info to database; returns unique run id'''

    # Arrange form data in dictionary
    form_data = __immutable_multi_dict_to_nested_dict(multi_dict=form_data)

    # Validate workflow run request
    __validate_run_workflow_request(data=form_data)

    # Check compatibility with service info
    __check_service_info_compatibility(data=form_data)

    # Initialize run document
    document = __init_run_document(data=form_data)

    # Create run environment
    document = __create_run_environment(config=config, document=document)

    # Start workflow run in background
    # tmp_dir and out_dir need to go in document
    # tes_url c
    __run_workflow(config=config, document=document)

    # Build formatted response object
    response = {"run_id": document['run_id']} 

    # Return response object
    return response


def __immutable_multi_dict_to_nested_dict(multi_dict):
    '''Convert ImmutableMultiDict to nested dictionary'''

    # Convert ImmutableMultiDict to flat dictionary
    nested_dict = multi_dict.to_dict(flat=True)

    # Iterate over key in dictionary
    for key in nested_dict:

        # Try to decode JSON string; ignore JSONDecodeErrors
        try:
            nested_dict[key] = loads(nested_dict[key])

        except decoder.JSONDecodeError:
            pass

    # Return formatted request dictionary
    return nested_dict


def __validate_run_workflow_request(data):
    '''Validate presence and types of workflow run request form data; sets defaults for optional'''

    # The form data is not validated properly because all types except 'workflow_attachment' are string and none are labeled as required
    # Considering the 'RunRequest' model in the current specs (0.3.0), the following assumptions are made and verified for the indicated parameters:
    # workflow_params:
    #   type = dict
    #   required = True
    # workflow_type:
    #   type = str
    #   required = True
    # workflow_type_version:
    #   type = str
    #   required = True
    # tags:
    #   type = dict
    #   required = False
    # workflow_engine_parameters:
    #   type = dict
    #   required = False
    # workflow_url:
    #   type = str
    #   required = True 
    # workflow_attachment:
    #   type = [str]
    #   required = False

    # Set required parameters
    required = {'workflow_params', 'workflow_type', 'workflow_type_version', 'workflow_url'}
    type_str = dict((key, data[key]) for key in ['workflow_type', 'workflow_type_version', 'workflow_url'] if key in data)
    type_dict = dict((key, data[key]) for key in ['workflow_params', 'workflow_engine_parameters', 'tags'] if key in data)
    # TODO: implement type casting/checking for workflow attachment

    # Raise error if any required params are missing
    if not required <= set(data):
        raise BadRequest()

    # Raise error if any string params are not of type string
    if not all(isinstance(value, str) for value in type_str.values()):
        raise BadRequest()

    # Raise error if any dict params are not of type dict
    if not all(isinstance(value, dict) for value in type_dict.values()):
        raise BadRequest()

    # Nothing to return
    return None


def __check_service_info_compatibility(data):
    '''Check compatibility with service info; raise bad request error'''
    # TODO: implement me
    return None


def __init_run_document(data):
    '''Initialize workflow run document'''

    # Initialize document
    document = dict()
    document['api'] = dict()
    document['internal'] = dict()

    # Add required keys
    document['api']['request'] = data
    document['api']['state'] = "UNKNOWN"
    document['api']['run_log'] = dict()
    document['api']['task_logs'] = list()
    document['api']['outputs'] = dict()

    # Return run document
    return document


def __create_run_environment(config, document):
    '''Create unique run identifier and permanent and temporary storage directories for current run'''

    # Re-assign config values
    collection_runs = config['database']['collections']['runs']
    out_dir = config['storage']['permanent_dir']
    tmp_dir = config['storage']['tmp_dir']

    # Keep on trying until a unique run id was found and inserted
    # TODO: If no more possible IDs => inf loop; fix (raise customerror; 500 to user)
    while True:

        # Create unique run id
        run_id = __create_run_id(
            charset=eval(config['database']['run_id']['charset']),
            length=config['database']['run_id']['length']
        )

        # Create unique celery task id
        task_id = uuid()

        # Try to create workflow run directory (temporary)
        try:
            # TODO: Think about permissions
            # TODO: Add this to document
            # TODO: Add working dir (currently one has to run the app from the outermost dir)
            current_tmp_dir = os.path.abspath(os.path.join(tmp_dir, run_id))
            os.mkdir(current_tmp_dir)

        # Try new run id if directory already exists
        except FileExistsError:
            continue

        # Try to create output directory (permanent)
        try:
            # TODO: Think about permissions
            # TODO: Add this to document
            # TODO: Add working dir (currently one has to run the app from the outermost dir)
            current_out_dir = os.path.abspath(os.path.join(out_dir, run_id))
            os.mkdir(current_out_dir)

        # Try new run id if directory already exists
        except FileExistsError:
            continue

        # Add run/task identifier, temp/output directories to document
        document['run_id'] = run_id
        document['task_id'] = task_id
        document['internal']['tmp_dir'] = current_tmp_dir
        document['internal']['out_dir'] = current_out_dir

        # Process worflow attachments
        document = __process_workflow_attachments(document)

        # Try to insert document into database
        try:
            collection_runs.insert(document)

        # Try new run id if document already exists
        except DuplicateKeyError:

            # And remove run directories created previously
            shutil.rmtree(current_tmp_dir, ignore_errors=True)
            shutil.rmtree(current_out_dir, ignore_errors=True)

            continue

        # Catch other database errors
        # TODO: implement properly
        except Exception as e:
            print("Database error")
            print(e)
            break

        # Exit loop
        break

    # Return updated document
    return document


def __create_run_id(charset, length):
    '''Create random run id'''

    # Return run id
    return ''.join(choice(charset) for __ in range(length))


def __process_workflow_attachments(data):
    '''Process workflow attachments'''
    # TODO: implement properly
    # Current workaround until processing of workflow attachments is implemented
    # Use 'workflow_url' for path to (main) CWL workflow file on local file system)
    # Use 'workflow_params' to generate YAML file

    # Create directory for storing workflow files
    workflow_dir = os.path.abspath(os.path.join(data['internal']['out_dir'], "workflow_files"))
    try:
        os.mkdir(workflow_dir)

    except OSError:
        # TODO: Do something more reasonable here
        pass

    # Set main CWL workflow file path
    data['internal']['cwl_path'] = os.path.abspath(data['api']['request']['workflow_url'])

    # Extract name and extensions of workflow
    workflow_name_ext = os.path.splitext(os.path.basename(data['internal']['cwl_path']))

    ## Copy workflow files
    #data['internal']['cwl_path'] = os.path.join(workflow_dir, "".join(workflow_name_ext))
    #shutil.copyfile(data['api']['request']['workflow_url'], data['internal']['cwl_path'])

    # Write out parameters to YAML workflow config gile
    data['internal']['yaml_path'] = os.path.join(workflow_dir, ".".join([workflow_name_ext[0], "yml"]))
    with open(data['internal']['yaml_path'], 'w') as yaml_file:
        dump(
            data['api']['request']["workflow_params"],
            yaml_file,
            allow_unicode=True,
            default_flow_style=False
        )

    # Extract workflow attachments from form data dictionary
    if 'workflow_attachment' in data['api']['request']:

#        # TODO: do something with data['workflow_attachment']

        # Strip workflow attachments from data
        del data['api']['request']['workflow_attachment']

    # Return form data stripped of workflow attachments
    return data


def __run_workflow(config, document):
    '''Helper function for `run_workflow()`'''

    # Re-assign config values
    tes_url = config['tes']['url']
    remote_storage_url = config['storage']['remote_storage_url']

    # Re-assign document values
    task_id = document['task_id']
    tmp_dir = document['internal']['tmp_dir']
    cwl_path = document['internal']['cwl_path']
    yaml_path = document['internal']['yaml_path']

    # Build command
    command_list = [
        "cwl-tes",
        "--leave-outputs",
        "--debug",
        "--remote-storage-url", remote_storage_url,
        "--tes", tes_url,
        cwl_path,
        yaml_path
    ]

    # Execute command as background task
    add_command_to_task_queue.apply_async(
        None, {
            'command_list': command_list,
            'tmp_dir': tmp_dir
        },
        task_id=task_id
    )

    # Nothing to return
    return None
