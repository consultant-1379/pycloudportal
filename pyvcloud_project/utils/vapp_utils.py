"""
This module provides utility functions related to vApps.

"""

import time
import logging
import requests
from lxml import etree
from django_rq import job
from django.conf import settings
from pyvcloud.vcd.client import Client, ResourceType, VCLOUD_STATUS_MAP, VAppPowerStatus, EntityType, E, RelationType
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.exceptions import InvalidParameterException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.vm import VM

from pyvcloud_project.worker_queue_settings import RetryIntervalLimits
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.utils import org_utils, orgvdc_utils, pyvcloud_utils as utils, vapp_network_utils, vm_utils, vsphere_utils
from pyvcloud_project.utils.pyvcloud_utils import PowerState
from pyvcloud_project.models import OrgVdcs, Vapps, Vms
from collections import defaultdict

logger = logging.getLogger(__name__)


def import_vapps():
    """
    Imports vApps from the VMware vCloud Director to the local database.

    Returns:
        str: A message indicating that vApps have been imported.
    """
    client = VMWareClientSingleton().client
    organisations = client.get_org_list()

    all_vapps_db = Vapps.objects.filter()
    add_vapps = []
    vapp_ids = []

    for org_res in organisations:
        org = org_utils.get_org(client, resource=org_res)

        for vdc_data in org.list_vdcs():
            vdc_res = org.get_vdc(vdc_data["name"])
            vdc = utils.get_vdc(client, resource=vdc_res)

            vapps = vdc.list_resources(EntityType.VAPP)
            for vapp_data in vapps:
                vapp_res = vdc.get_vapp(vapp_data["name"])
                try:
                    org_vdc_db = OrgVdcs.objects.get(name=vdc_res.get("name"))
                except OrgVdcs.DoesNotExist:
                    print(f"method: import_vapps()\n failed to find org called\
                        {vdc_res.get('name')} for vapp {vapp_data['name']} in the db")
                    continue

                vapp = create_vapp_model(client, vapp_res, org_vdc_db)

                vapp_ids.append(vapp.vcd_id)
                add_vapps.append(vapp)

    for vapp in all_vapps_db:
        vcd_id = vapp.vcd_id
        if vcd_id not in vapp_ids:
            vapp.delete()

    if add_vapps:
        utils.save_models(add_vapps)

    return 'Vapps are imported'


def get_vapp(client: Client, name=None, href=None, resource=None):
    """
    Retrieves a vApp object from the VMware vCloud Director.

    Args:
        client (pyvcloud.vcd.client.Client): The VMware vCloud Director client.
        name (str, optional): The name of the vApp. Defaults to None.
        href (str, optional): The href of the vApp. Defaults to None.
        resource (dict, optional): The resource representation of the vApp. Defaults to None.

    Returns:
        pyvcloud.vcd.vapp.VApp: The vApp object.
    """
    vapp = None
    try:
        vapp = VApp(client, name, href=href, resource=resource)
    except InvalidParameterException as error:
        print(f'method:get_vdc()\n {error}')
    return vapp

def get_vapp_info(vapp, client):
    vapp_vcd_id = vapp.vcd_id
    vapp_power_state = get_vapp_power_state(client, vapp_vcd_id)
    created_by = vapp.created_by_user_obj.username if vapp.created_by_user_obj else 'N/A'
    vapp_info = {
        'vapp_vcd_id': vapp_vcd_id,
        'catalog_name': vapp.org_vdc_obj.name,
        'name': vapp.name,
        'vapp_power_state': vapp_power_state,
        'gateway': vapp.vts_name,
        'created_by': created_by,
        'creation_date': vapp.created,
        'origin_catalog_name': vapp.origin_catalog_name,
        'origin_template_name': vapp.origin_template_name,
        'org_vdc_id': vapp.org_vdc_obj.org_vdc_id,
    }
    return vapp_info

def get_vapp_resource_info(client, vapps_data):
    vapp_info_list = [get_vapp_info(vapp, client) for vapp in vapps_data]
    org_ids = list(set([vapp.org_vdc_obj.org_vdc_id for vapp in vapps_data]))
    org_vapps = defaultdict(list)

    for org_id in org_ids:
        org_vapps[org_id] = orgvdc_utils.get_vapp_resources(client, org_id)

    for vapp_info in vapp_info_list:
        vapp_org_vdc_id = vapp_info['org_vdc_id']
        vapp_resource_data = org_vapps[vapp_org_vdc_id].get(vapp_info['vapp_vcd_id'])
        if vapp_resource_data:
            vapp_info['running_cpu'] = vapp_resource_data['cpu_on_count']
            vapp_info['running_memory'] = vapp_resource_data['memory_on_count']

    return vapp_info_list

def create_vapp_model(client, vapp_res, org_vdc_db):
    """
    Creates a vApp model object.

    Args:
        client (pyvcloud.vcd.client.Client): The VMware vCloud Director client.
        vapp_res (dict): The resource representation of the vApp.
        org_vdc_db (pyvcloud_project.models.OrgVdcs): The OrgVdcs object.

    Returns:
        pyvcloud_project.models.Vapps: The vApp model object.
    """
    vapp = get_vapp(client, resource=vapp_res)
    vapp_id = vapp_res.get("id")

    try:
        vapp_obj = Vapps.objects.get(vcd_id=vapp_id)
        vapp_obj.name = vapp.name
        vapp_obj.org_vdc_obj = org_vdc_db
    except Vapps.DoesNotExist:
        vapp_obj = Vapps(
            name=vapp.name,
            vcd_id=vapp_id,
            org_vdc_obj=org_vdc_db,
            created=str(vapp_res.DateCreated)
        )

    return vapp_obj


def allowed_poweron_another_vapp(client, orgvdc_id):
    """
    Checks if it is allowed to power on another vApp in the specified organization virtual data center.

    Args:
        client (pyvcloud.vcd.client.Client): The VMware vCloud Director client.
        orgvdc_id (str): The ID of the organization virtual data center.

    Returns:
        bool: True if it is allowed to power on another vApp, False otherwise.
    """
    running = count_vapps(client, orgvdc_id)[0]
    quota = OrgVdcs.objects.get(org_vdc_id=orgvdc_id).running_tb_limit

    return running + 1 < quota


def allowed_power_on_vapp_resources(client, orgvdc_id, vapp_template_name):
    """
    Checks if it is allowed to power on vApp resources for the specified organization virtual data center and vApp template name.

    Args:
        client (pyvcloud.vcd.client.Client): The VMware vCloud Director client.
        orgvdc_id (str): The ID of the organization virtual data center.
        vapp_template_name (str): The name of the vApp template.

    Returns:
        bool: True if it is allowed to power on vApp resources, False otherwise.
    """
    total_cpu = 0
    total_mem = 0
    resource_type = ResourceType.VAPP_TEMPLATE.value
    fields = "name,numberOfCpus,memoryAllocationMB"
    qfilter = f"isExpired==false;name=={vapp_template_name}"

    vapp_templates_resources = utils.send_typed_query(
        client, resource_type, fields, qfilter)
    orgvdc = OrgVdcs.objects.get(org_vdc_id=orgvdc_id)
    vdc_href = orgvdc_utils.get_vdc_href(client, orgvdc_id)

    resource_type = ResourceType.ADMIN_VAPP.value
    fields = "numberOfCpus,memoryAllocationMB"
    qfilter = f"vdc=={vdc_href}"
    existing_vapps_resources = utils.send_typed_query(
        client, resource_type, fields, qfilter)

    for template in vapp_templates_resources:
        total_cpu += int(template.get("numberOfCpus"))
        total_mem += int(template.get("memoryAllocationMB")) /1024
    for vapp in existing_vapps_resources:
        total_cpu += int(vapp.get("numberOfCpus"))
        total_mem += int(vapp.get("memoryAllocationMB")) / 1024

    if total_cpu > orgvdc.cpu_limit or total_mem > orgvdc.memory_limit:
        return False
    return True


def allowed_create_another_vapp(client, orgvdc_id):
    """
    Checks if it is allowed to create another vApp in the specified organization virtual data center.

    Args:
        client (pyvcloud.vcd.client.Client): The VMware vCloud Director client.
        orgvdc_id (str): The ID of the organization virtual data center.

    Returns:
        bool: True if it is allowed to create another vApp, False otherwise.
    """
    [running, not_running] = count_vapps(client, orgvdc_id)
    quota = OrgVdcs.objects.get(org_vdc_id=orgvdc_id).stored_tb_limit

    return running + not_running + 1 < quota


def count_vapps(client, orgvdc_id):
    """
    Counts the number of running and not running vApps in the specified organization virtual data center.

    Args:
        client (pyvcloud.vcd.client.Client): The VMware vCloud Director client.
        orgvdc_id (str): The ID of the organization virtual data center.

    Returns:
        list: A list containing the number of running and not running vApps.
    """
    resource_type = ResourceType.ADMIN_VAPP.value
    fields = "name,status"
    qfilter = f"isExpired==false;vdc=={orgvdc_id}"

    vapps = utils.send_typed_query(client, resource_type, fields, qfilter)
    running = 0
    not_running = 0
    for vapp in vapps:
        status = vapp.get("status")
        if status == PowerState.POWER_ON.value:
            running += 1
        else:
            not_running += 1
    return [running, not_running]


def get_status_number(status_str: str):
    """
    Gets the status number corresponding to the given status string.

    Args:
        status_str (str): The status string.

    Returns:
        int: The status number, or None if not found.
    """
    for key, value in VCLOUD_STATUS_MAP.items():
        if value.replace(' ', '').lower() == status_str.lower():
            return key
    return None


def on_worker_success(worker_job, connection, result):
    """
    Callback function called when a worker job is successful.

    Args:
        worker_job: The job object.
        connection: The connection object.
        result: The result of the job.
    """
    utils.on_worker_success(worker_job, connection, result)


def on_worker_failure(job, connection, type, value, traceback):
    """
    Callback function called when a worker job fails.

    Args:
        worker_job: The job object.
        connection: The connection object.
        type: The type of the failure.
        value: The value associated with the failure.
        traceback: The traceback information.
    """
    utils.on_worker_failure(job, connection, type, value, traceback)


@job(RetryIntervalLimits.start_vapp.args, **RetryIntervalLimits.start_vapp.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def start_vapp(params):
    """
    Job function to start a vApp.

    Args:
        params (dict): The parameters for the job.
    """
    vapp_vcd_id = params['resource_id']
    logger.info(f' vapp_id: {vapp_vcd_id}')
    client = VMWareClientSingleton().client
    vapp_obj = Vapps.objects.get(vcd_id=vapp_vcd_id)
    vapp_href = get_vapp_href(client, vapp_vcd_id)
    vapp_name = vapp_obj.name
    vapp = VApp(client, name=vapp_name, href=vapp_href)
    task = vapp.power_on()
    client.get_task_monitor().wait_for_success(task)

    # Find the hostname of the vApp
    vts_name = get_gateway_vm_hostname(client, vapp_href)
    vapp_obj.vts_name = vts_name
    vapp_obj.ip_address = vapp_network_utils.get_external_ip(client, vapp_href)
    vapp_obj.save()
    logger.info(f'Updated Vapps entry for vApp {vapp_name} with vts_name: {vts_name}')

def get_gateway_vm_hostname(client, vapp_href, gateway_vm_href=None):
    """
    Retrieves the hostname of the gateway VM.

    Args:
        client (pyvcloud.vcd.client.Client): The VMware vCloud Director client.
        vapp_href (str): The href of the vApp.
        gateway_vm_href (str, optional): The href of the gateway VM. Defaults to None.

    Returns:
        str: The hostname of the gateway VM.
    """
    external_ip = None
    loop_index = 0
    while not external_ip or external_ip == 'error' or loop_index == 20:
        external_ip = vapp_network_utils.get_external_ip(
            client, vapp_href, gateway_vm_href=gateway_vm_href)
        time.sleep(15)
        loop_index += 1

    return vapp_network_utils.get_hostname_from_ip(external_ip)

@job(RetryIntervalLimits.stop_vapp.args, **RetryIntervalLimits.stop_vapp.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def stop_vapp(params):
    """
    Job function to stop a vApp.

    Args:
        params (dict): The parameters for the job.
    """
    vapp_vcd_id = params['resource_id']
    logger.info(f' vapp_id: {vapp_vcd_id}')
    client = VMWareClientSingleton().client
    vapp_obj = Vapps.objects.get(vcd_id=vapp_vcd_id)
    vapp_name = vapp_obj.name
    vapp_href = get_vapp_href(client, vapp_vcd_id)
    vapp = VApp(client, name=vapp_name, href=vapp_href)
    task = vapp.shutdown()
    client.get_task_monitor().wait_for_success(task)


@job(RetryIntervalLimits.recompose_vapp.args, **RetryIntervalLimits.recompose_vapp.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def recompose_vapp(params):
    """
    Job function to recompose a vApp.

    Args:
        params (dict): The parameters for the job.
    """
    vapp_vcd_id = params['resource_id']
    recompose_vms = params['recompose_vms']
    template_href = params['template_href']
    template_id = params['template_id']
    logger.info(
        f'Recomposing vApp with ID: {vapp_vcd_id}, VMs to recompose: {recompose_vms}, Template ID: {template_id}')

    client = VMWareClientSingleton().client
    vapp_obj = Vapps.objects.get(vcd_id=vapp_vcd_id)
    vapp_name = vapp_obj.name
    vapp_href = get_vapp_href(client, vapp_vcd_id)
    vapp_res = client.get_resource(vapp_href)
    vapp = get_vapp(client, resource=vapp_res)

    # Get VM dictionaries
    vapp_vm_dict = {vm['name']: {'id': vm['id'], 'href': vm['href']} for vm in list_vapp_vms(vapp_vcd_id)}
    template_vm_dict = {vm['name']: {'id': vm['id'], 'href': vm['href']} for vm in list_vapp_vms(template_id, is_vapp_template=True)}

    # Determine VMs to delete and add
    vms_to_delete = {vm_name: vapp_vm_dict[vm_name] for vm_name in recompose_vms if vm_name in vapp_vm_dict}
    vms_to_add = {vm_name: template_vm_dict[vm_name] for vm_name in recompose_vms if vm_name in template_vm_dict}

    # Get NIC information for template VMs
    original_vm_nics = vm_utils.get_vm_nics(vms_to_add, recompose=True)

    # Power off & delete the vms that we need to recompose from vApp
    if vms_to_delete:
        vm_utils.power_off_and_delete_vms(vms_to_delete)
        vapp.reload()

    template_resource = client.get_resource(template_href)
    vm_specs_to_add = []

    for vm in recompose_vms:
        vm_spec = {'vapp': template_resource, 'source_vm_name': vm}
        vm_specs_to_add.append(vm_spec)

    task = vapp.add_vms(vm_specs_to_add, power_on=False)
    client.get_task_monitor().wait_for_success(task)

    # Reloading the vApp resources after Vm add
    vapp.reload()
    vapp_res = vapp.get_resource()
    vapp_children_to_recompose = {child.get('name'):child for child in vapp_res.Children.Vm if child.get('name') in vms_to_add}

    recomposed_vapp_vms = list_vapp_vms(vapp_vcd_id)
    vms_to_update = {vm['name']: {'nics': original_vm_nics[vm['name']],'vm': vm} for vm in recomposed_vapp_vms if vm['name'] in original_vm_nics.keys()}

    for vm in vms_to_update.values():
        original_vm_nics = vm['nics']
        vcd_vm = vapp_children_to_recompose[vm['vm']['name']]
        net_conn_section = vcd_vm.NetworkConnectionSection

        for nic in original_vm_nics:
            for nc in net_conn_section.NetworkConnection:
                if nc.NetworkConnectionIndex == nic['index']:
                    nc.MACAddress = nic['mac_address']
                    break

        task = client.put_linked_resource(net_conn_section, RelationType.EDIT, EntityType.NETWORK_CONNECTION_SECTION.value, net_conn_section)
        client.get_task_monitor().wait_for_success(task)

    logger.info(
        f'Recompose Completed. Powering on the vApp {vapp_name}')
    # Powering on the Vapp
    task = vapp.power_on()
    client.get_task_monitor().wait_for_success(task)
    logger.info("Starting Import of recomposed VMs")
    vsphere_utils.import_vm_storage_from_vsphere()
    vm_utils.import_vms()
    logger.info("Completed VM import")



@job(RetryIntervalLimits.delete_vapp.args, **RetryIntervalLimits.delete_vapp.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def delete_vapp(params):
    """
    Job function to delete a vApp.

    Args:
        params (dict): The parameters for the job.
    """
    vapp_vcd_id = params['resource_id']
    logger.info(f' vapp_id: {vapp_vcd_id}')
    client = VMWareClientSingleton().client
    vapp_obj = Vapps.objects.get(vcd_id=vapp_vcd_id)
    org_vdc_obj = vapp_obj.org_vdc_obj
    org_vdc_id = org_vdc_obj.org_vdc_id
    vapp_name = vapp_obj.name
    pvdc_obj = org_vdc_obj.provider_vdc_obj
    pvdc_name = pvdc_obj.name
    orgvdc_client = VDC(client, name=pvdc_name, href=org_vdc_id)
    task = orgvdc_client.delete_vapp(vapp_name)
    client.get_task_monitor().wait_for_success(task)
    vapp_obj.delete()


@job(RetryIntervalLimits.poweroff_and_delete_vapp.args, **RetryIntervalLimits.poweroff_and_delete_vapp.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def poweroff_and_delete(params):
    """Power off and delete a vApp.

    Args:
        params (dict): Parameters containing the vApp resource ID.
    """
    vapp_vcd_id = params['resource_id']
    logger.info(f' vapp_id: {vapp_vcd_id}')
    client = VMWareClientSingleton().client
    vapp_obj = Vapps.objects.get(vcd_id=vapp_vcd_id)
    org_vdc_obj = vapp_obj.org_vdc_obj
    org_vdc_id = org_vdc_obj.org_vdc_id
    vapp_name = vapp_obj.name
    pvdc_obj = org_vdc_obj.provider_vdc_obj
    pvdc_name = pvdc_obj.name
    orgvdc_client = VDC(client, name=pvdc_name, href=org_vdc_id)
    vapp_power_state = get_vapp_power_state(client, vapp_vcd_id)
    if PowerState.POWER_OFF.value != vapp_power_state:
        poweroff_vapp(params)
    task = orgvdc_client.delete_vapp(vapp_name)
    client.get_task_monitor().wait_for_success(task)
    vapp_obj.delete()


def get_vapp_power_state(client, vapp_vcd_id):
    """Get the power state of a vApp.

    Args:
        client: VMWare client object.
        vapp_vcd_id (str): vApp resource ID.

    Returns:
        str: Power state of the vApp.

    """
    vapp_power_state = ''
    resource_type = ResourceType.ADMIN_VAPP.value
    fields = "status,isDeployed"
    qfilter = f"id=={vapp_vcd_id}"
    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilter)
    if query_result:
        vapp_power_state = query_result[0].get('status')
        is_vapp_deployed = query_result[0].get('isDeployed')
        vapp_power_state = orgvdc_utils.create_vapp_status_string(
            vapp_power_state, is_vapp_deployed)
    return vapp_power_state


def get_vapp_status(client, vapp_vcd_id):
    """Get the status of a vApp.

    Args:
        client: VMWare client object.
        vapp_vcd_id (str): vApp resource ID.

    Returns:
        dict: Dictionary with the status information of the vApp.
    """
    shortened_operation = ""
    resource_type = ResourceType.ADMIN_TASK.value
    fields = "status,operationFull"
    qfilter = f"object=={vapp_vcd_id}"
    sort_desc = 'startDate'

    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilter, sort_desc=sort_desc)
    vapp_status = "" if not query_result else query_result[0].get('status')
    if 'running' in vapp_status:
        vapp_operation = query_result[0].get('operationFull')
        if 'purging' in vapp_operation.lower():
            shortened_operation = 'Cleaning up..'
        elif 'capturing virtual' in vapp_operation.lower():
            shortened_operation = 'Copying..'
        elif 'powering off' in vapp_operation.lower():
            shortened_operation = 'Powering Off VM..'
        elif 'resetting' in vapp_operation.lower():
            shortened_operation = 'Resetting VM..'
        else:
            shortened_operation = vapp_operation.split(' ')[0] + '..'
    else:
        shortened_operation = 'No running tasks'

    return {'status': shortened_operation}


@job(RetryIntervalLimits.poweroff_vapp.args, **RetryIntervalLimits.poweroff_vapp.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def poweroff_vapp(params):
    """Power off a vApp.

    Args:
        params (dict): Parameters containing the vApp resource ID.

    """
    vapp_vcd_id = params['resource_id']
    logger.info(f' vapp_id: {vapp_vcd_id}')
    vapp_obj = Vapps.objects.get(vcd_id=vapp_vcd_id)
    client = VMWareClientSingleton().client
    vapp_href = get_vapp_href(client, vapp_vcd_id)
    vapp_name = vapp_obj.name
    vapp = VApp(client, name=vapp_name, href=vapp_href)
    task = vapp.undeploy(action='powerOff')
    client.get_task_monitor().wait_for_success(task)


def get_vapp_vcenter(vapp_id):
    """
    Retrieves the vCenter information for a given vApp.

    Args:
        vapp_id (str): The ID of the vApp.

    Returns:
        str or None: The vCenter information for the vApp, or None if not found.
    """
    client = VMWareClientSingleton().client
    resource_type = ResourceType.ADMIN_VM.value
    fields = "vc"
    qfilter = f"container=={vapp_id}"
    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilter)
    if not query_result:
        logger.info(f"Unable to get vcenter for vapp with id {vapp_id}")
    for result in query_result:
        vm_href = result.get('href')
        vm_id = vm_href.split('vm-')[-1]
        vcenter = vm_utils.get_vm_vcenter(vm_id)
        return vcenter
    return query_result


@job(RetryIntervalLimits.rename_vapp.args, **RetryIntervalLimits.rename_vapp.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def rename_vapp(params):
    """
    Job function to rename a vApp.

    Args:
        params (dict): The parameters for the job.
            - resource_id (str): The ID of the vApp to be renamed.
            - new_vapp_name (str): The new name for the vApp.

    """
    vapp_vcd_id = params['resource_id']
    new_vapp_name = params['new_vapp_name']
    logger.info(f' vapp_id: {vapp_vcd_id} , new vapp name : {new_vapp_name}')
    vapp_obj = Vapps.objects.get(vcd_id=vapp_vcd_id)
    client = VMWareClientSingleton().client
    vapp_href = get_vapp_href(client, vapp_vcd_id)
    vapp_name = vapp_obj.name
    vapp = VApp(client, name=vapp_name, href=vapp_href)
    task = vapp.edit_name_and_description(name=new_vapp_name)
    client.get_task_monitor().wait_for_success(task)
    vapp_obj.name = new_vapp_name
    vapp_obj.save()


@job(RetryIntervalLimits.rename_vapp_template.args, **RetryIntervalLimits.rename_vapp_template.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def vapp_templates_rename(params):
    """
    Job function to rename vApp templates.

    Args:
        params (dict): The parameters for the job.
            - resource_id (str): The ID of the vApp template to be renamed.
            - templates (dict): A dictionary containing information about the templates.
            - contents (str): The contents of the templates.
    """
    vapp_template_id = params['resource_id']
    templates = params['templates']
    contents = params['contents']
    logger.info(f' vapp_template_id: {vapp_template_id}')
    client = VMWareClientSingleton().client
    templates = params['templates']
    contents = params['contents']
    task = client.put_resource(templates.get("href"),
                               etree.fromstring(contents), EntityType.VAPP_TEMPLATE.value)
    utils.execute_task(client, task)


@job(RetryIntervalLimits.add_to_catalog_vapp.args, **RetryIntervalLimits.add_to_catalog_vapp.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def add_vapp_to_catalog(params):
    """
    Job function to add a vApp to a catalog.

    Args:
        params (dict): The parameters for the job.
            - resource_id (str): The ID of the vApp to be added to the catalog.
            - org_href (str): The href of the organization.
            - catalog_name (str): The name of the catalog.
            - new_template_name (str): The new name for the vApp template in the catalog.
            - vapp_href (str): The href of the vApp.

    """
    vapp_vcd_id = params['resource_id']
    org_href = params['org_href']
    catalog_name = params['catalog_name']
    new_template_name = params['new_template_name']
    vapp_href = params['vapp_href']
    vapp_vcd_id = get_vapp_id_from_href(vapp_href)
    logger.info(
        f' vapp_id: {vapp_vcd_id}, new template name : {new_template_name} catalog name: {catalog_name}')
    client = VMWareClientSingleton().client
    org = Org(client, href=org_href)
    catalog_res = org.get_catalog(catalog_name)
    task = org.capture_vapp(catalog_res, vapp_href, new_template_name, "")
    client.get_task_monitor().wait_for_success(task)


@job(RetryIntervalLimits.add_to_catalog_vapp.args, **RetryIntervalLimits.add_to_catalog_vapp.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def stop_and_add_vapp_to_catalog(params):
    """
    Job function to stop a vApp, and then add it to a catalog.

    Args:
        params (dict): The parameters for the job.
            - resource_id (str): The ID of the vApp to be stopped and added to the catalog.
            - org_href (str): The href of the organization.
            - catalog_name (str): The name of the catalog.
            - new_template_name (str): The new name for the vApp template in the catalog.
            - vapp_href (str): The href of the vApp.
    """
    vapp_vcd_id = params['resource_id']
    client = VMWareClientSingleton().client
    vapp_power_state = get_vapp_power_state(client, vapp_vcd_id)
    if PowerState.POWER_OFF.value != vapp_power_state:
        poweroff_vapp(params)

    org_href = params['org_href']
    catalog_name = params['catalog_name']
    new_template_name = params['new_template_name']
    vapp_href = params['vapp_href']
    vapp_vcd_id = get_vapp_id_from_href(vapp_href)
    logger.info(
        f' vapp_id: {vapp_vcd_id}, new template name : {new_template_name} catalog name: {catalog_name}')
    org = Org(client, href=org_href)
    catalog_res = org.get_catalog(catalog_name)
    task = org.capture_vapp(catalog_res, vapp_href, new_template_name, "")
    client.get_task_monitor().wait_for_success(task)


@job(RetryIntervalLimits.create_from_template_vapp.args, **RetryIntervalLimits.create_from_template_vapp.kwargs, on_success=on_worker_success, on_failure=on_worker_failure)
def create_vapp_from_template(params):
    """
    Job function to create a vApp from a template.

    Args:
        params (dict): The parameters for the job.
            - resource_id (str): The ID of the vApp template.
            - org_vdc_id (str): The ID of the organization VDC.
            - org_vdc_name (str): The name of the organization VDC.
            - power_on (bool): Whether to power on the vApp after instantiation.
            - vapp_name (str): The name of the vApp.
            - template_name (str): The name of the template.
            - catalog_name (str): The name of the catalog.
    """
    def reset_gateway_vm_mac(vdc_vapp):
        logger.info(f"LMI Request: Reseting the MAC Addresss")
        gateway_vm_res = vdc_vapp.get_vm('master_gateway')

        # Reset the Mac Address of the nic connected to the external network on the gateway VM
        net_conn_section = gateway_vm_res.NetworkConnectionSection
        for network in net_conn_section.NetworkConnection:
            if 0 == network.NetworkConnectionIndex:
                network.MACAddress = E.MACAddress("")
                logger.info('entitytyepe {}'.format(
                    EntityType.NETWORK_CONNECTION_SECTION.value))
                task = client.put_linked_resource(
                    net_conn_section, RelationType.EDIT, EntityType.NETWORK_CONNECTION_SECTION.value, net_conn_section)
                client.get_task_monitor().wait_for_success(task)
                break  # Break out of the loop once index 0 is found
        gateway_vm_href = gateway_vm_res.get('href')
        logger.info(f"LMI Request: MAC Addresss reseting completed")
        return gateway_vm_href, vdc_vapp

    vapp_template_id = params['resource_id']
    client = VMWareClientSingleton().client
    orgvdc_href = orgvdc_utils.get_vdc_href(client, params['org_vdc_id'])
    vdc = utils.get_vdc(client, name=params['org_vdc_name'], href=orgvdc_href)
    power_on = params['power_on']
    '''
    Vmware can sometimes instantiate the vapp but then fail to power it on, if this occurs the job will fail and be retried after it (the job) has timed out.
    When retried, it will check vmware to see does a vapp with this name already exist (we already checked uniqueness in the view)
    If a vapp with this name exists, it means we are in a retried job and that there is most likely an issue on the vmware side
    that is preventing this vapp from powering on.
    There's nothing we can do about that here, raise an exception and kill the job.
    '''
    vapp_already_exists = is_vapp_name_unique_on_vcd(
        client, params["vapp_name"])
    if vapp_already_exists:
        raise Exception(
            f'There was an issue powering on Vapp {params["vapp_name"]} from template with ID {vapp_template_id}, please contact an administrator')

    logger.info(
        f' vapp template id: {vapp_template_id}, template name : {params["template_name"]} catalog name: {params["catalog_name"]}')
    # vapp must be instantiated powered off initially so that the mac address of the gateway vm nic connected to the external network can be reset
    vapp_res = vdc.instantiate_vapp(
        name=params['vapp_name'],
        catalog=params['catalog_name'],
        template=params['template_name'],
        power_on=None,
        deploy=None
    )
    task_status = None

    # 80 * 15 seconds = 20 minutes. If vapp still hasn't instantiated and reached a powered off status in 20 minutes, something most likely going wrong.
    loop_index = 0
    while task_status != VAppPowerStatus.STOPPED.value and loop_index < 80:
        task_status = client.get_task_monitor().get_status(vapp_res)
        time.sleep(15)
        loop_index = loop_index + 1

    # This Exception will be hidden by the exception under vapp_already_exists if the job retries, but just in case the retry limit is set to 0.
    if task_status != VAppPowerStatus.STOPPED.value:
        raise Exception(
            f'There was an issue instantiating Vapp {params["vapp_name"]} from template with ID {vapp_template_id}, please contact an administrator')

    # Get the gateway vm resource
    vapp_href = vapp_res.get('href')
    vdc_vapp = VApp(client, name=params['vapp_name'], href=vapp_href)

    # Retry resetting gateway VM's MAC address if an exception occurs
    try:
        gateway_vm_href, vdc_vapp = reset_gateway_vm_mac(vdc_vapp)
    except Exception as e:
        logger.info(
            f"Failed to reset MAC address of gateway VM for vApp {params['vapp_name']}, HREF {vapp_href}, Retrying ..")
        time.sleep(10)
        vdc_vapp = VApp(client, name=params['vapp_name'], href=vapp_href)
        gateway_vm_href = None
        index = 0
        while not gateway_vm_href and index < 3:
            try:
                gateway_vm_href, vdc_vapp = reset_gateway_vm_mac(vdc_vapp)
            except Exception:
                time.sleep(10)
                vdc_vapp = VApp(
                    client, name=params['vapp_name'], href=vapp_href)
                index += 1
            logger.info(
                f"Retry attempt {index+1} to reset MAC address of gateway VM")

    logger.info(
        f"API Request: Requested power state is -> {power_on} for vApp {params['vapp_name']}")

    if power_on:
        task = vdc_vapp.power_on()
        client.get_task_monitor().wait_for_success(task)
        # Find the hostname of the gateway VM
        vts_name = get_gateway_vm_hostname(client, vapp_href, gateway_vm_href)
        logger.info(f"vApp {params['vapp_name']} with gateway {vts_name} Mapping to CI Portal Started")
        connection_established = mapGatewayToSPP(vts_name)
        success_failure = 'was successful' if connection_established else 'failed'
        logger.info(f"API Request: Powering for vApp {params['vapp_name']} completed. Mapping to CI Portal {success_failure}.")
    else:
        logger.info(f"API Request: Powering for vApp {params['vapp_name']} skipped and vApp Mapping skipped.")
        vts_name = None

    org_vdc_obj = OrgVdcs.objects.get(org_vdc_id=params['org_vdc_id'])
    vapp_obj = create_vapp_model(client, vapp_res, org_vdc_obj)
    vapp_obj.ip_address = vapp_network_utils.get_external_ip(client, vapp_href, gateway_vm_href)
    vapp_obj.vts_name = vts_name
    vapp_obj.created_by_user_obj = params['sppuser']
    vapp_obj.origin_catalog_name = params['catalog_name']
    vapp_obj.origin_template_name = params['template_name']
    vapp_obj.save()

    logger.info(f"vApp {params['vapp_name']} Object Saved Successfully")
    logger.info(f"vApp {params['vapp_name']} Importing vm storage from vSphere...")
    vsphere_utils.import_vm_storage_from_vsphere()
    logger.info("Importing newly added VM's")
    vm_utils.import_vms()

def mapGatewayToSPP(vts_name):
    """
    Function to establish connection between SPP and CI portal using CURL command.

    Args:
        gateway (str): The gateway to be mapped to SPP.

    Returns:
        bool: True if the connection is successfully established, False otherwise.
    """
    url = f"{settings.CI_PORTAL_URL}mapGatewayToSpp/"
    data = {
        "gateway": vts_name,
        "spp": settings.SPP_URL
    }

    curl_command = f'curl -X POST -d "gateway={vts_name}" -d "spp={settings.SPP_URL}" {url}'
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        logger.info(f"CURL command {curl_command} was successful. Connection between SPP and CI Portal established.")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error executing CURL command '{curl_command}': {e}")
        return False

def is_vapp_or_any_vm_busy(vapp_id):
    """
    Check if a vApp or any of its virtual machines are busy.

    Args:
        vapp_id (str): The ID of the vApp.

    Returns:
        bool: True if the vApp or any of its virtual machines are busy, False otherwise.
    """
    if get_vapp_vm_busy_status(vapp_id):
        return True
    vms = list_vapp_vms(vapp_id)
    for vm in vms:
        if get_vapp_vm_busy_status(vm['id']):
            return True
    return False


def get_vapp_vm_busy_status(resource_id):
    """
    Check the busy status of a vApp or virtual machine.

    Args:
        resource_id (str): The ID of the vApp or virtual machine.

    Returns:
        bool: True if the vApp or virtual machine is busy, False otherwise.
    """
    redis_instance = utils.get_redis()
    if redis_instance.exists(resource_id):
        return True
    return False


def get_vapp_id_from_href(vapp_href):
    """
    Extracts the vApp ID from the given vApp href.

    Args:
        vapp_href (str): The href of the vApp.

    Returns:
        str: The vApp ID extracted from the href.
    """
    return vapp_href.rsplit('/', 1)[1].split('-', 1)[1]


def list_vapp_vms(vapp_id, is_vapp_template=False):
    """
    Lists the virtual machines (VMs) in a vApp.

    Args:
        vapp_id (str): The ID of the vApp.

    Returns:
        list: A list of dictionaries representing the VMs in the vApp. Each dictionary contains the VM's name, ID, and href.
    """
    client = VMWareClientSingleton().client
    resource_type = ResourceType.ADMIN_VM.value
    fields = "name"
    qfilter = f"isVAppTemplate=={is_vapp_template};container=={vapp_id}"
    query_results = utils.send_typed_query(
        client, resource_type, fields, qfilter)
    vapp_vms = []
    for vm_res in query_results:
        vm_name = vm_res.get("name")
        vm_href = vm_res.get('href')
        vm_id = vm_href.rsplit('/', 1)[1].split('-', 1)[1]
        vapp_vms.append({'name': vm_name, "id": vm_id, "href": vm_href})
    return vapp_vms


def get_vapp_id_by_vm(vm_id):
    """
    Retrieves the vApp ID associated with a virtual machine (VM).

    Args:
        vm_id (str): The ID of the VM.

    Returns:
        str: The ID of the vApp that contains the VM. Returns an empty string if the VM is not associated with any vApp.
    """
    client = VMWareClientSingleton().client
    vapp_vcd_id = ""
    try:
        vm_obj = Vms.objects.get(vcd_id=vm_id)
        vapp_obj = vm_obj.vapp_obj
        vapp_vcd_id = vapp_obj.vcd_id
    except Vms.DoesNotExist:
        resource_type = ResourceType.ADMIN_VM.value
        fields = "container"
        qfilter = f"id=={vm_id}"
        query_result = utils.send_typed_query(
            client, resource_type, fields, qfilter)
        if query_result:
            vapp_href = query_result[0].get('container')
            vapp_vcd_id = get_vapp_id_from_href(vapp_href)
    return vapp_vcd_id


def get_vapp_href(client, vapp_vcd_id):
    """
    Retrieves the href (URL) of a vApp based on its vCD ID.

    Args:
        client: The VMWareClient instance.
        vapp_vcd_id (str): The vCD ID of the vApp.

    Returns:
        str: The href (URL) of the vApp.
    """
    api_uri = client.get_api_uri()
    vapp_uri_segment = utils.get_api_url('vapp')
    extracted_vapp_vcd_id = vapp_vcd_id.split(':')[-1]
    href = api_uri + vapp_uri_segment.format(extracted_vapp_vcd_id)
    return href


def toggle_vapp_shared_state(vapp_id, share_unshare):
    """
    Toggles the shared state of a vApp.

    Args:
        vapp_id (str): The vCD ID of the vApp.
        share_unshare (str): A string representation of the shared state to be set.
            - '0' or 'False' to unshare the vApp.
            - '1' or 'True' to share the vApp.

    Returns:
        bool: The updated shared state of the vApp.
    """
    vapp_shared = bool(int(share_unshare))
    Vapps.objects.filter(vcd_id=vapp_id).update(shared=vapp_shared)
    return vapp_shared


def is_vapp_name_unique_on_vcd(client, vapp_name):
    """
    Checks if a vApp name is unique within a vCD instance.

    Args:
        client: The vCD client object.
        vapp_name (str): The name of the vApp to check.

    Returns:
        bool: True if the vApp name is unique, False otherwise.
    """
    resource_type = ResourceType.ADMIN_VAPP.value
    fields = "name"
    qfilter = f"isExpired==false;name=={vapp_name}"
    results = utils.send_typed_query(client, resource_type, fields, qfilter)
    return bool(results)


def is_vapp_powered_off(client, vapp_vcd_id):
    """
    Checks if a vApp is powered off.

    Args:
        client: The vCD client object.
        vapp_vcd_id (str): The vApp VCD ID.

    Returns:
        str: The power status of the vApp. Returns an empty string if the vApp doesn't exist or if the query result is empty.
    """
    qfilter = f"id=={vapp_vcd_id}"
    fields = "org,status"
    resource_type = ResourceType.ADMIN_VAPP.value
    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilter)
    return "" if not query_result else query_result[0].get('status')
