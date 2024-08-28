"""
This module contains various utility functions related to PyvCloud.

"""
import logging
from enum import Enum
import time
import urllib3
import redis
from lxml import etree
import django_rq
from rq.job import Job
from django.db import IntegrityError, transaction
from pyvcloud.vcd.client import Client, TaskStatus, QueryResultFormat
from pyvcloud.vcd.system import System
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.exceptions import InvalidParameterException, OperationNotSupportedException
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.models import SppUser, Events, RetryInterval

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


class PowerState(Enum):
    # MIXED = vapp stopped but not powered off (undeployed)
    POWER_ON = 'POWERED_ON'
    POWER_OFF = 'POWERED_OFF'
    MIXED = 'MIXED'
    SUSPENDED = 'SUSPENDED'


def get_system(client: Client, admin_href=None, admin_resource=None):
    """
    Retrieve the system information.

    Args:
        client: pyvcloud.vcd.client.Client: The client object for making API requests.
        admin_href: str: The href of the admin entity.
        admin_resource: pyvcloud.vcd.system.System: The admin resource.

    Returns:
        pyvcloud.vcd.system.System: The system information.

    """
    system = None
    try:
        system = System(client, admin_href=admin_href,
                        admin_resource=admin_resource)
    except InvalidParameterException as error:
        print(f'method:get_system()\n {error}')
    return system


def get_vdc(client: Client, name=None, href=None, resource=None):
    """
    Retrieve the VDC (Virtual Data Center) information.

    Args:
        client: pyvcloud.vcd.client.Client: The client object for making API requests.
        name: str: The name of the VDC.
        href: str: The href of the VDC.
        resource: pyvcloud.vcd.vdc.VDC: The VDC resource.

    Returns:
        pyvcloud.vcd.vdc.VDC: The VDC information.

    """
    vdc = None
    try:
        vdc = VDC(client, name=name, href=href, resource=resource)
    except InvalidParameterException as error:
        print(f'method:get_vdc()\n {error}')
    return vdc


def href_to_id(href):
    """
    Convert the href to a vCD ID.

    Returns:
        str: The vCD ID.
    """
    last = href.split("/")[-1].split("-")

    vmware_element = last[0]
    vcd_id = "-".join(last[1::])
    start = "urn:vcloud:"

    return start + vmware_element + ":" + vcd_id


def execute_task(client: Client, task):
    """
    Execute a task and wait for its completion.

    Args:
        client: pyvcloud.vcd.client.Client: The client object for making API requests.
        task: pyvcloud.vcd.client.Task: The task to execute.

    Raises:
        Exception: If the task does not complete successfully.

    """
    task_monitor = client.get_task_monitor()
    wait = task_monitor.wait_for_status(
        task=task,
        timeout=500,
        poll_frequency=2,
        expected_target_statuses=[
            TaskStatus.SUCCESS, TaskStatus.ABORTED, TaskStatus.ERROR,
            TaskStatus.CANCELED],
        callback=None)

    status = wait.get("status")
    if status != TaskStatus.SUCCESS.value:
        raise Exception(etree.tostring(wait, pretty_print=True))


def get_api_url(element_type):
    """
    Get the API URL for the given element type.

    Args:
        element_type: str: The element type (e.g., 'vapp', 'orgvdc', 'vm').

    Returns:
        str: The API URL for the element type.

    """
    element_dict = {'vapp': '/vApp/vapp-{}',
                    'orgvdc': '/vdc/{}',
                    'vm': '/vApp/vm-{}'}

    return element_dict[element_type]


def save_models(models):
    """
    Save the models in the database in a transaction.

    Args:
        models: list: The list of models to save.

    Raises:
        IntegrityError: If there is an integrity error when saving the models.

    """
    try:
        with transaction.atomic():
            for model in models:
                model.save()
    except IntegrityError as integrity:
        raise IntegrityError from integrity


def get_user_ldap_groups(user):
    """
    Get the LDAP groups associated with the user.

    Args:
        user: obj: The user object.

    Returns:
        str: The LDAP groups associated with the user.

    """
    ldap_groups = ""
    if isinstance(user, SppUser):
        ldap_groups = user.ldap_groups
    else:
        ldap_groups = SppUser.objects.get(user=user).ldap_groups
    return "" if not ldap_groups else ldap_groups


def send_typed_query(client: Client, resource_type, fields, qfilter, query_result_format=QueryResultFormat.RECORDS, sort_desc=None, sort_asc=None):
    """
    Send a typed query to the vCD API.

    Args:
        client: pyvcloud.vcd.client.Client: The client object for making API requests.
        resource_type: str: The type of resource to query.
        fields: str: The fields to retrieve.
        qfilter: str: The query filter.
        query_result_format: pyvcloud.vcd.client.QueryResultFormat: The format of the query result.
        sort_desc: str: The field to sort in descending order.
        sort_asc: str: The field to sort in ascending order.

    Returns:
        list: The response from the query.

    """
    response = []
    client_to_use = client
    i = 0
    params = {
        'query_result_format': query_result_format,
        'fields': fields,
        'qfilter': qfilter,
        'sort_desc': sort_desc,
        'sort_asc': sort_asc,
    }
    while not response and i <= 3:
        i += 1
        try:
            response = list(client_to_use.get_typed_query(
                resource_type,
                **params
            ).execute())
        except (AttributeError, TypeError, OperationNotSupportedException):
            time.sleep(1)
            client_to_use = VMWareClientSingleton().client

    if not response:
        logger.info(
            f'Error with typed Query : params {resource_type}  {fields}   {qfilter}. No Result Returned. ')
    return response


def get_redis():
    """
    Get the Redis client.

    Returns:
        redis.StrictRedis: The Redis client.

    """
    return redis.StrictRedis('localhost', 6379, charset="utf-8", decode_responses=True)


def add_vapp_or_vm_to_busy_cache(resource_id, event):
    """
    Add a vApp or VM to the busy cache.

    Args:
        resource_id: str: The ID of the resource.
        event: str: The event associated with the resource.

    """
    logger.info(f'resource {resource_id} added to busy cache : {event}')
    redis_instance = get_redis()
    redis_instance.set(resource_id, event, ex=3600)


def remove_vapp_or_vm_from_busy_cache(resource_id):
    """
    Remove a vApp or VM from the busy cache.

    Args:
        resource_id: str: The ID of the resource.

    """
    logger.info(f'resource {resource_id} removed from busy cache')
    redis_instance = get_redis()
    redis_instance.delete(resource_id)


def remove_rq_job_resource_id_from_redis(job_args):
    """
    Remove the resource ID associated with an RQ job from Redis.

    Args:
        job_args: dict: The arguments of the RQ job.

    """
    resource_id = job_args.get('resource_id', "")
    remove_vapp_or_vm_from_busy_cache(resource_id)


def log_worker_completion(job_args, event):
    """
    Log the completion of an RQ worker.

    Args:
        job_args: dict: The arguments of the RQ job.
        event: str: The event associated with the completion.

    """
    resource_id = job_args.get('resource_id', "")
    func_name = job_args.get('func_name')
    retry_settings = RetryInterval.objects.get_retry_obj(func_name)
    retry_limit = retry_settings[1]['retry'].max
    retries = retry_limit - job_args.get('retries_left', 0)
    job_args['retries'] = retries
    job_args['event_stage'] = 'End'
    api_valid = job_args.get('is_api')
    logger.info(f' {event} : {func_name}, resource_id: {resource_id}')
    Events.objects.filter(function_name=func_name, created=job_args['created']).update(
        job_id=job_args['job_id'], is_api=api_valid)
    if func_name not in ['vapp_templates_rename']:
        create_event_in_db(job_args)


def on_worker_failure(job, connection, type, value, traceback):
    """
    Handle the failure of an RQ worker.

    Args:
        job: rq.job.Job: The failed job.
        connection: rq.Connection: The connection to Redis.
        type: Type: The type of the exception.
        value: Exception: The exception instance.
        traceback: Traceback: The traceback of the exception.

    """
    job_args = job.args[0]
    job_id = job.id
    resource_id = job_args.get('resource_id', "")
    func_name = job_args.get('func_name')
    resource_type = job_args.get('resource_type')
    if job.retries_left:
        logger.info(
            f' Job with ID : {job_id} for function {func_name} and {resource_type} with ID {resource_id }Failed, retrying. {job.retries_left} atempts left')
        return

    job_args['outcome'] = 'Failed'
    job_args['job_id'] = job_id
    log_worker_completion(job_args, 'Failure')
    remove_rq_job_resource_id_from_redis(job_args)
    # TODO: Failure mails


def on_worker_success(job, connection, result):
    """
    Handle the success of an RQ worker.

    Args:
        job: rq.job.Job: The successful job.
        connection: rq.Connection: The connection to Redis.
        result: Any: The result of the job.

    """
    job_args = job.args[0]
    job_args['retries_left'] = job.retries_left
    job_args['outcome'] = 'Completed'
    job_args['job_id'] = job.id
    log_worker_completion(job_args, 'Success')
    remove_rq_job_resource_id_from_redis(job_args)
    # TODO: Success mails


def update_failed_events_in_db():
    """
    Update failed events in the database.

    This function retrieves unhandled failed events from the database and updates their messages with the corresponding
    exception information from RQ jobs.

    """
    unhandled_failed_events = Events.objects.filter(
        outcome='Failed', message__exact="")
    failed_events_to_update = []
    job_ids = [event.job_id for event in unhandled_failed_events]
    rq_redis_connection = django_rq.get_connection()
    rq_jobs = Job.fetch_many(job_ids, rq_redis_connection)
    for event in unhandled_failed_events:
        for job in rq_jobs:
            if job and event.job_id == job.id:
                event.message = job.exc_info
                failed_events_to_update.append(event)
    if failed_events_to_update:
        Events.objects.bulk_update(failed_events_to_update, ['message'])


def create_event_in_db(params):
    """
    This function creates a new event object in the database based on the provided parameters.

    Args:
        params: dict: The parameters for creating the event.

    """
    if not isinstance(params['user'], SppUser):
        params['user'] = SppUser.objects.get(user=params['user'])
    event_obj, created = Events.objects.get_or_create(
        user=params.get('user'),
        function_name=params.get('func_name'),
        function_parameters=params,
        object_type=params.get('resource_type'),
        resource_id=params.get('resource_id'),
        event_stage=params.get('event_stage'),
        retries=params.get('retries', 0),
        created=params.get('created'),
        outcome="" if not 'outcome' in params else params['outcome'],
        message="" if not 'message' in params else params['message'],
        job_id="" if not 'job_id' in params else params['job_id'],
        is_api=params['is_api'],
        request_host=params.get('request_host')
    )


def create_event_params(func_name=None, resource_id=None, user=None, resource_type='vapp', event_stage='Start', outcome='', created=None, extra_params={}, is_api=False, request_host='localhost'):
    """
    This function creates a dictionary of event parameters with the provided values.

    Args:
        func_name: str: The name of the function associated with the event.
        resource_id: str: The ID of the resource associated with the event.
        user: User: The user associated with the event.
        resource_type: str: The type of the resource associated with the event.
        event_stage: str: The stage of the event (e.g., "Start", "End").
        outcome: str: The outcome of the event.
        created: datetime: The timestamp of when the event was created.
        extra_params: dict: Additional parameters for the event.
        is_api: bool: Indicates if the event is triggered by an API request.
        request_host: str: The host of the API request.

    Returns:
        dict: The event parameters.

    Raises:
        Exception: If the mandatory parameters are not provided.

    """
    if not any([func_name, resource_id, user, created]):
        raise Exception(
            'Parameters func_name, resource_id, user and created are mandatory when creating events and have no default values')
    event_params = {'func_name': func_name,  'resource_id': resource_id, 'user': user, 'resource_type': resource_type,
                    'event_stage': event_stage, 'created': created, 'is_api': is_api, 'request_host': request_host, 'outcome': outcome}
    event_params.update(extra_params)
    return event_params
