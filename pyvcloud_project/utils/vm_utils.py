"""
This module contains functions for importing and
 managing virtual machines =(VMs) from VMware
   vSphere using the pyvcloud library.

"""
import time
from datetime import datetime
from typing import List
import logging
import json
from collections import defaultdict
from django_rq import job
import redis
import concurrent.futures
from typing import List
from pyvcloud.vcd.vm import VM
from pyvcloud.vcd.client import ResourceType
from pyVmomi import vim
from django.http import HttpResponse, HttpResponseBadRequest
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.utils import pyvcloud_utils as utils
from pyvcloud_project.models import Vapps
from pyvcloud.vcd.vm import VM
from pyvcloud.vcd.client import ResourceType
from pyvcloud_project.utils import (pyvcloud_utils as utils, vapp_network_utils, vsphere_utils,
                                    vapp_utils)
from pyvcloud_project.models import Vapps, Vms
from pyvcloud_project.worker_queue_settings import RetryIntervalLimits
from pyvcloud_project.vmware_client import VMWareClientSingleton
logger = logging.getLogger(__name__)

def import_vms():
    """
    Imports virtual machines from vCloud Director to the database.

    :return: A string indicating the result of the import operation.
    """
    client = VMWareClientSingleton().client
    redis_server = redis.Redis()
    add_vms = []
    vm_ids = []
    vm_storage_dict = {}
    vapp_vm_dict = defaultdict(list)
    vm_objs = Vms.objects.filter()
    qfilter = "isExpired==false;isVAppTemplate==false"
    fields = ("name,datastoreName,vmNameInVc,hostName,status,container,"
              "numberOfCpus,memoryMB,containerName,org,vdc")
    resource_type = ResourceType.ADMIN_VM.value
    virtual_machines = utils.send_typed_query(client, resource_type,
                                              fields, qfilter)

    if redis_server.exists('vsphere_vm_storage'):
        vm_storage_dict = json.loads(redis_server.get('vsphere_vm_storage'))
    else:
        vm_storage_dict = vsphere_utils.import_vm_storage_from_vsphere(
            return_dict=True)

    for virtual_machine in virtual_machines:
        vapp_id = virtual_machine.get('container').split('vapp-')[-1]
        vapp_vm_dict[vapp_id].append(virtual_machine)

    for vapp_id in vapp_vm_dict:
        vapp_vms = vapp_vm_dict[vapp_id]
        try:
            vapp_vm_storage = vm_storage_dict[vapp_id]
        except KeyError:
            # Log the error and continue
            logging.error(f"Error accessing storage info for vapp {vapp_id}")
            continue
        try:
            vapp_obj = Vapps.objects.get(vcd_id__contains=vapp_id)
        except Vapps.DoesNotExist:
            continue
        for vm in vapp_vms:
            vm_id = utils.href_to_id(vm.get('href'))
            vm_committed_storage = 0
            vm_provisioned_storage = 0
            vm_disk_datastore_string = ""
            vm_attached_disk_string = ""
            if vm.get('name') in vapp_vm_storage:
                for datastore, vm_used_disk in (vapp_vm_storage[vm.get('name')]
                                                ['datastore_committed']
                                                .items()):
                    vm_committed_storage += vm_used_disk
                    vm_disk_datastore_string += datastore + \
                        '/'+str(vm_used_disk)+','
                for datastore, vm_disk in (vapp_vm_storage[vm.get('name')]
                                           ['datastore_provisioned']
                                           .items()):
                    vm_provisioned_storage += vm_disk
                for disk_name, disk_size in (vapp_vm_storage[vm.get('name')]
                                             ['diskinfo']
                                             .items()):
                    vm_attached_disk_string += disk_name+'/'+str(disk_size)+';'
            add_vms.append(create_vm_model(vm, vm_id, vapp_obj,
                                           vm_committed_storage,
                                           vm_provisioned_storage,
                                           vm_attached_disk_string,
                                           vm_disk_datastore_string))
            vm_ids.append(vm_id)

    for vm_obj in vm_objs:
        vm_id = vm_obj.vcd_id
        if vm_id not in vm_ids:
            vm_obj.delete()

    if add_vms:
        utils.save_models(add_vms)

    return "VM's are imported"


def create_vm_model(vm, vm_id, vapp_obj, vm_committed_storage,
                    vm_provisioned_storage, vm_attached_disks,
                    vm_disks_in_datastore):
    """
    Creates a Vms model object using the provided data.

    Args:
        vm (dict): Dictionary containing the virtual machine data.
        vm_id (str): The ID of the virtual machine.
        vapp_obj (Vapps): The Vapps model object associated
                          with the virtual machine.
        vm_committed_storage (int): Committed storage of the
                                    virtual machine.
        vm_provisioned_storage (int): Provisioned storage of
                                      the virtual machine.
        vm_attached_disks (str): String representation of
                                 attached disks of the virtual machine.
        vm_disks_in_datastore (str): String representation of
                                     disks in the datastore of the
                                     virtual machine.

    Returns:
        Vms: The created Vms model object.
    """
    try:
        vm_obj = Vms.objects.get(vcd_id__contains=vm_id)
        vm_obj.host_name = "" if not vm.get(
            'hostName') else vm.get('hostName').split('.')[0]
        vm_obj.datastore = vm.get('datastoreName')
        vm_obj.cpu = vm.get('numberOfCpus')
        vm_obj.memory = vm.get('memoryMB')
        vm_obj.committed_storage = vm_committed_storage
        vm_obj.provisioned_storage = vm_provisioned_storage
        vm_obj.vsphere_name = vm.get('vmNameInVc')
        vm_obj.detailed_storage = vm_disks_in_datastore
        vm_obj.vm_attached_disks = vm_attached_disks
    except Vms.DoesNotExist:
        vm_obj = Vms(
            name=vm.get('name'),
            vcd_id=vm_id,
            vapp_obj=vapp_obj,
            host_name="" if not vm.get('hostName') else vm.get(
                'hostName').split('.')[0],
            vsphere_name=vm.get('vmNameInVc'),
            datastore=vm.get('datastoreName'),
            cpu=vm.get('numberOfCpus'),
            memory=vm.get('memoryMB'),
            committed_storage=vm_committed_storage,
            provisioned_storage=vm_provisioned_storage,
            detailed_storage=vm_disks_in_datastore,
            vm_attached_disks=vm_attached_disks,
        )
    return vm_obj


def get_vm_id_from_href(vm_href):
    """
    Extracts the virtual machine ID from the provided href.

    Returns:
        str: The extracted virtual machine ID.
    """
    return vm_href.rsplit('/', 1)[1].split('-', 1)[1]


def get_vms(client, vapp_id) -> List:
    """
    Retrieves the list of virtual machines
    associated with the specified vApp ID.

    Args:
        client: The VMWareClient instance.
        vapp_id (str): The ID of the vApp.

    Returns:
        List: A list of virtual machines.
    """
    qfilter = f"isExpired==false;container=={vapp_id}"
    resource_type = ResourceType.ADMIN_VM.value
    fields = "name,containerName"
    vapp_vms = utils.send_typed_query(client, resource_type, fields, qfilter)
    return vapp_vms


@job(RetryIntervalLimits.power_on_vm.args,
     **RetryIntervalLimits.power_on_vm.kwargs,
     on_success=utils.on_worker_success,
     on_failure=utils.on_worker_failure)
def power_on_vm(params):
    """
    Job function to power on a virtual machine.

    Args:
        params (dict): Parameters for the job.
    """
    vm_id = params['resource_id']
    vm_href = params['vm_href']
    vm_name = params['vm_name']
    client = VMWareClientSingleton().client
    logger.info(f' vm_id: {vm_id}')
    vm = VM(client, href=vm_href)
    task = vm.power_on()
    client.get_task_monitor().wait_for_success(task)
    # Check if the vApp is a "master_gateway"
    if vm_name == "master_gateway":
        logger.info("VM is master_gateway... Importing Hostname")
        import_networks_and_update_vapps(vm_id)

def import_networks_and_update_vapps(vm_id):
    """
    Imports networks from VMware vCD to the Django database and updates Vapps model with the hostname.

    Args:
        vm_href (str): The virtual machine's href.

    Returns:
        str: A message indicating that the vApp networks have been imported.
    """
    client = VMWareClientSingleton().client

    vm_obj = Vms.objects.get(vcd_id=vm_id)
    vapp_obj = vm_obj.vapp_obj
    vapp_vcd_id = vapp_obj.vcd_id
    vapp_href = vapp_utils.get_vapp_href(client, vapp_vcd_id)

    ip_address = None
    MAX_RETRIES = 10
    retries = 0
    while retries < MAX_RETRIES:
        ip_address = vapp_network_utils.get_external_ip(client, vapp_href)
        if ip_address is not None:
            vts_name = vapp_network_utils.get_hostname_from_ip(ip_address)
            break
        retries += 1
        logger.info(f"Getting hostname for vApp {vapp_obj.name}. Retry attempt: {retries}")
        time.sleep(10)  # Wait for 10 seconds before the next retry

    Vapps.objects.update_or_create(
        vcd_id=vapp_vcd_id,
        defaults={
            'ip_address': ip_address,
            'vts_name': vts_name,
        }
    )
    logger.info(f"Hostname Update for the vApp {vapp_obj.name}")

@job(RetryIntervalLimits.power_off_vm.args,
     **RetryIntervalLimits.power_off_vm.kwargs,
     on_success=utils.on_worker_success,
     on_failure=utils.on_worker_failure)
def power_off_vm(params):
    """
    Job function to power off a virtual machine.

    Args:
        params (dict): Parameters for the job.
    """
    vm_id = params['resource_id']
    vm_href = params['vm_href']
    client = VMWareClientSingleton().client
    logger.info(f' vm_id: {vm_id}')
    vm = VM(client, href=vm_href)
    task = vm.undeploy(action='powerOff')
    client.get_task_monitor().wait_for_success(task)

@job(RetryIntervalLimits.power_on_vm.args,
     **RetryIntervalLimits.power_on_vm.kwargs,
     on_success=utils.on_worker_success,
     on_failure=utils.on_worker_failure)
def power_off_and_delete_vms(params):
    """
    Job function to power off and delete multiple virtual machines.

    Args:
        params (dict): Parameters for the job.
            - vms (dict): Dictionary of VMs with their names as keys and IDs
                          and HREFs as values.
              Example: {'master_gateway': {'id': 'id1', 'href': 'href1'},
                    'master_jenkinss2': {'id': 'id2', 'href': 'href2'}, ...}
    """
    vms = params
    client = VMWareClientSingleton().client

    def power_off_and_delete_vm(vm_name, vm_info):
        vm_id = vm_info['id']
        vm_href = vm_info['href']
        logger.info(f'vm_name: {vm_name}, vm_id: {vm_id}')

        # Power off the VM
        vm_obj = VM(client, href=vm_href)
        is_vapp_powered_on = vm_obj.get_power_state()
        # 4: Powered on
        if is_vapp_powered_on == 4:
            print(f"Powering off {vm_name}")
            task = vm_obj.power_off()
            client.get_task_monitor().wait_for_success(task)

        # Delete the VM
        print(f"Deleting {vm_name}")
        vm_obj_delete = VM(client, href=vm_href)
        task_delete = vm_obj_delete.delete()
        client.get_task_monitor().wait_for_success(task_delete)

    # Use ThreadPoolExecutor to execute the operations in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for vm_name, vm_info in vms.items():
            futures.append(executor.submit(
                power_off_and_delete_vm, vm_name, vm_info))

        # Wait for all operations to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"An error occurred: {e}")


@job(RetryIntervalLimits.shutdown_vm.args,
     **RetryIntervalLimits.shutdown_vm.kwargs,
     on_success=utils.on_worker_success,
     on_failure=utils.on_worker_failure)
def shutdown_vm(params):
    """
    Job function to shut down a virtual machine.

    Args:
        params (dict): Parameters for the job.
    """
    vm_id = params['resource_id']
    vm_href = params['vm_href']
    client = VMWareClientSingleton().client
    logger.info(f' vm_id: {vm_id}')
    vm = VM(client, href=vm_href)
    task = vm.shutdown()
    client.get_task_monitor().wait_for_success(task)


def vm_tools_is_installed(href):
    """
    Checks if VMware Tools is installed on the virtual machine with the
    provided href.

    Args:
        href (str): The href of the virtual machine.

    Returns:
        bool: True if VMware Tools is installed, False otherwise.
    """
    client = VMWareClientSingleton().client
    vm = VM(client, href=href)
    vm_xml = vm.get_resource()
    vm_name = vm_xml.get('name')
    try:
        vm_tools_version = vm_xml.VmSpecSection.VmToolsVersion
    except AttributeError:
        logger.info(f' could not get vm tools version for vm: {vm_name}')

    if vm_tools_version:
        return True
    return False


def get_vm_href(client, vm_vcd_id):
    """
    Retrieves the href of the virtual machine with the provided vCD ID.

    Args:
        client: The VMWareClient instance.
        vm_vcd_id (str): The vCD ID of the virtual machine.

    Returns:
        str: The href of the virtual machine.
    """
    api_uri = client.get_api_uri()
    vm_uri_segment = utils.get_api_url('vm')
    extracted_vm_vcd_id = vm_vcd_id.split(':')[-1]
    href = api_uri + vm_uri_segment.format(extracted_vm_vcd_id)
    return href


def is_vapp_or_vm_busy(vm_id):
    """
    Checks if the vApp or virtual machine with the provided ID is busy.

    Args:
        vm_id (str): The ID of the vApp or virtual machine.

    Returns:
        bool: True if the vApp or virtual machine is busy, False otherwise.
    """
    vapp_id = vapp_utils.get_vapp_id_by_vm(vm_id)
    vapp_busy = vapp_utils.get_vapp_vm_busy_status(vapp_id)
    if vapp_busy:
        return True
    return vapp_utils.get_vapp_vm_busy_status(vm_id)


def get_vm_vcenter(vm_id):
    """
    Checks if the virtual machine with the provided ID is deployed.

    Args:
        vm_id (str): The ID of the virtual machine.

    Returns:
        bool: True if the virtual machine is deployed, False otherwise.
    """
    client = VMWareClientSingleton().client
    error_msg = f"vcenter for vm with id {vm_id} could not be found"
    resource_type = ResourceType.ADMIN_VM.value
    fields = "vc"
    qfilter = f"id=={vm_id}"
    vm_vcenter_result = utils.send_typed_query(
        client, resource_type, fields, qfilter)
    for vm_vcenter in vm_vcenter_result:
        vcenter_href = vm_vcenter.get('vc')
        resource_type = ResourceType.VIRTUAL_CENTER.value
        fields = "url"
        qfilter = f"href=={vcenter_href}"
        vcenter_href_result = utils.send_typed_query(
            client, resource_type, fields, qfilter)
        for vcenter_href in vcenter_href_result:
            vcenter_url = vcenter_href.get('url')
            vcenter_url = vcenter_url.replace(
                'https://', '').replace('/sdk', '')
            return vcenter_url
    return error_msg


@job(RetryIntervalLimits.delete_vm.args,
     **RetryIntervalLimits.delete_vm.kwargs,
     on_success=utils.on_worker_success,
     on_failure=utils.on_worker_failure)
def delete_vm(params):
    """
    Job function to delete a virtual machine.

    Args:
        params (dict): Parameters for the job.
    """
    vm_id = params['resource_id']
    vm_href = params['vm_href']
    client = VMWareClientSingleton().client
    logger.info(f' vm_id: {vm_id}')
    vm = VM(client, href=vm_href)
    task = vm.delete()
    client.get_task_monitor().wait_for_success(task)

def get_vm_status(client, vm_id):
    """Get the status of a VM.

    Args:
        client: VMWare client object.
        vm_id (str): VM resource ID.

    Returns:
        dict: Dictionary with the status information of the VM.
    """
    shortened_operation = ""
    resource_type = ResourceType.ADMIN_TASK.value
    fields = "status,operationFull"
    qfilter = f"object=={vm_id}"
    sort_desc = 'startDate'
    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilter, sort_desc=sort_desc)

    if not query_result:
        return {'status': 'No running tasks'}

    cases = {
        'purging' : 'Cleaning up..',
        'capturing virtual' : 'Copying..',
        'stopping' : 'Powering Off VM..',
        'resetting': 'Resetting VM..',
        'starting': 'Powering On VM..'
    }

    vm_status = query_result[0].get('status')
    vm_operation = query_result[0].get('operationFull', '').lower().split(' ')[0]
    shortened_operation = cases.get(vm_operation, vm_operation + '..')

    if 'running' not in vm_status:
        shortened_operation = 'No running tasks'

    return {'status': shortened_operation}

def poweron_vm_api(request, vapp_id, vm_id, vm_name):
    client = VMWareClientSingleton().client
    fields = "status,numberOfCpus,memoryMB,container,name"
    qfilters = f"container=={vapp_id};id=={vm_id}"
    resource_type = ResourceType.ADMIN_VM.value
    query_result = utils.send_typed_query(client, resource_type, fields, qfilters)
    logger.info(f"Trying to get {vm_name} VM Details for vApp {vapp_id} & vm_id {vm_id}")
    if not query_result:
        return HttpResponseBadRequest("Error getting VM details")
    logger.info("VM Details Found")
    vm_status = query_result[0].get("status")
    logger.info(f"VM status is {vm_status}")
    # Check if the VM is in a valid state to be powered on
    if vm_status not in (utils.PowerState.POWER_OFF.value, utils.PowerState.SUSPENDED.value):
        return HttpResponse("VM is already powered on")

    func_name = request.resolver_match.view_name
    vm_href = query_result[0].get("href")
    extra_params = {'vm_href': vm_href,
                    'vm_name': vm_name}
    event_params = utils.create_event_params(func_name=func_name, resource_id=vm_id,user=request.user,resource_type='vm',event_stage='Completed',
                                       created=datetime.now(),extra_params=extra_params)
    logger.info("Powering on VM...")
    power_on_vm(event_params)
    logger.info("VM has been powered on...")

def poweroff_vm_api(request, vapp_id, vm_id, vm_name):
    client = VMWareClientSingleton().client
    fields = "status,numberOfCpus,memoryMB,container,name"
    qfilters = f"container=={vapp_id};id=={vm_id}"
    resource_type = ResourceType.ADMIN_VM.value
    query_result = utils.send_typed_query(client, resource_type, fields, qfilters)
    logger.info(f"Trying to get {vm_name} VM Details for vApp {vapp_id} & vm_id {vm_id}")
    if not query_result:
        return HttpResponseBadRequest("Error getting VM details")
    logger.info("VM Details Found")
    vm_status = query_result[0].get("status")
    logger.info(f"VM status is {vm_status}")
    # Check if the VM is in a valid state to be powered off
    if vm_status not in (utils.PowerState.POWER_ON.value, utils.PowerState.SUSPENDED.value):
        return HttpResponse("VM is already powered off")

    func_name = request.resolver_match.view_name
    vm_href = query_result[0].get("href")
    extra_params = {'vm_href': vm_href,
                    'vm_name': vm_name}
    event_params = utils.create_event_params(func_name=func_name, resource_id=vm_id,user=request.user,resource_type='vm',event_stage='Completed',
                                       created=datetime.now(),extra_params=extra_params)
    logger.info("Powering off VM...")
    power_off_vm(event_params)
    logger.info("VM has been powered off...")

def reboot_vm_api(request, vapp_id, vm_id, vm_name):
    client = VMWareClientSingleton().client
    fields = "status,numberOfCpus,memoryMB,container,name"
    qfilters = f"container=={vapp_id};id=={vm_id}"
    resource_type = ResourceType.ADMIN_VM.value
    query_result = utils.send_typed_query(client, resource_type, fields, qfilters)
    logger.info(f"Trying to get {vm_name} VM Details for vApp {vapp_id} & vm_id {vm_id}")

    if not query_result:
        return HttpResponseBadRequest("Error getting VM details")
    logger.info("VM Details Found")

    func_name = request.resolver_match.view_name
    vm_href = query_result[0].get("href")
    logger.info(f"Rebooting VM with vm_id: {vm_id}")
    vm = VM(client, href=vm_href)
    logger.info("Rebooting VM. . .")
    task = vm.power_reset()
    client.get_task_monitor().wait_for_success(task)

    # Check if the vApp is a "master_gateway"
    if vm_name == "master_gateway":
        logger.info("VM is master_gateway... Importing Hostname")
        import_networks_and_update_vapps(vm_id)

    extra_params = {'vm_href': vm_href, 'vm_name': vm_name}
    event_params  = utils.create_event_params(func_name=func_name, resource_id=vm_id, user=request.user, resource_type='vm', event_stage='Completed', created=datetime.now(),extra_params=extra_params)
    logger.info("VM has been rebooted...")

def trim_vm_name(vm_name):
    vm = ''
    for i in range(len(vm_name.split('-')) - 1):
        if i > 0:
            vm += '-'
        vm += vm_name.split('-')[i]
    return vm

def find_vm_by_ip(content, ip_address):
    """
    Find a VM by IP address.

    Parameters:
    content (ServiceInstance): VMware service instance
    ip_address (str): IP address to search for

    Returns:
    vim.VirtualApp: vApp containing the VM with the matching IP address, or None if not found
    """

    # Create a view of all VMs
    container_view = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.VirtualMachine], True)

    for vm in container_view.view:
        # Iterate through all network cards on the VM
        if vm.guest.ipAddress == ip_address:
            return vm

    return None

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_vm_nics(vms, recompose=False):
    """
    Retrieves the nics of virtual machines on vcd.

    Args:
        vms: Dict of vms. Can have any number of subkeys, so long as the 'href' key exists in the sub dicts.
        format: {vm_name: { ..., "href": vm_href}, vm2_name: { ...,  "href": vm_href}, vm3_name: { ...,  "href": vm_href}  }
    Returns:
        list: A dictionary representing the VMs in the vApp. Each subdictionary contains the VM's name and details for each of it's nics.
    """
    vm_nics = defaultdict(dict)
    client = VMWareClientSingleton().client
    def _get_vm_nics(vm):
        vm_href = vm.get('href')
        vcd_vm = VM(client, href=vm_href)
        vm_resource = vcd_vm.get_resource()
        vm_name = vm_resource.get('name')
        vm_nics = vcd_vm.list_nics()

        # Need to get the XML formatted Mac Address Data from vmware to be used when reapplying the mac addresses at the end of a recompose
        # nc.MACAddress is format <class 'lxml.objectify.StringElement'> , not string.
        if recompose:
            net_conn_section = vm_resource.NetworkConnectionSection
            for nc in net_conn_section.NetworkConnection:
                for nic in vm_nics:
                    if nc.NetworkConnectionIndex == nic['index']:
                        nic['mac_address'] = nc.MACAddress
        return {vm_name: vm_nics}

    for vm in vms:
        vm_nics.update(_get_vm_nics(vms[vm]))

    return vm_nics


def print_vmware_nics(vm_href, return_dict=True):
    tempdict = {}
    client = VMWareClientSingleton().client
    vcd_vm = VM(client, href=vm_href)
    net_conn_section = vcd_vm.get_resource().NetworkConnectionSection
    for nc in net_conn_section.NetworkConnection:
        tempdict[nc.NetworkConnectionIndex] = nc.MACAddress

    ordered_dict = {}
    sorted_dict_keys = sorted(tempdict)
    for sorted_key in sorted_dict_keys:
        ordered_dict[sorted_key] = tempdict[sorted_key]

    for dict_key in ordered_dict:
        print(dict_key, ordered_dict[dict_key])

    if return_dict:
        return ordered_dict
