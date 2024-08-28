from http.client import HTTPResponse
import math
import socket
import logging
from datetime import datetime
from django.conf import settings
from django.shortcuts import render, redirect, reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from pyvcloud.vcd.client import ResourceType
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.utils import pyvcloud_utils as utils
from pyvcloud_project.utils import vm_utils, vapp_utils
from pyvcloud_project.utils.pyvcloud_utils import PowerState
from pyvcloud_project.models import Vms, Vapps
from rest_framework.response import Response
from django.http import HttpResponseBadRequest, JsonResponse

logger = logging.getLogger(__name__)


@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
def index(request, vapp_id):
    """
    Displays VM index page. User must be logged in.

    **Context**

    ``Models used:``
        :model:`pyvcloud_project.vms`

    **Template**

    :template:`vms/index.html`
    """
    # TODO when vapp story is done, need to pass orgvdc_id here as well
    # TODO check cache if vm is busy. If busy disable action button.
    context = {}
    context["container_name"] = " "
    vm_disks_per_datastore = {}
    vm_attached_disks = {}
    vm_dict = {}
    vm_obj = None
    redis_server = utils.get_redis()
    client = VMWareClientSingleton().client
    fields = ("name,status,container,numberOfCpus,memoryMB,"
              "containerName,org,vdc,isDeployed")
    qfilters = f"isExpired==false;container=={vapp_id}"
    resource_type = ResourceType.ADMIN_VM.value
    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilters)
    vapp_name = Vapps.objects.get(vcd_id=vapp_id).name

    for vm in query_result:
        try:
            vm_obj = Vms.objects.get(name=vm.get(
                "name"), vapp_obj__vcd_id__contains=vapp_id)
        except Exception:
            logger.info(f"Exception Raised when trying to get VM for the Vapp {vapp_id}")
            continue
        vm_name = vm.get("name")
        vm_attached_disks[vm_name] = {}
        vm_dict[vm_name] = {}
        disks_on_datastores_list = "" if not vm_obj.detailed_storage else [
            x for x in vm_obj.detailed_storage.split(',') if x]
        for disk_on_datastore in disks_on_datastores_list:
            datastore, disk_size = disk_on_datastore.strip(',').split('/')
            vm_disks_per_datastore[vm_name] = {}
            vm_disks_per_datastore[vm_name][datastore] = [
                int(disk_size), vm_obj.vsphere_name]
        vm_attached_disks_list = "" if not vm_obj.vm_attached_disks else [
            x for x in vm_obj.vm_attached_disks.split(';') if x]
        for vm_disk in vm_attached_disks_list:
            disk_name, disk_size = vm_disk.strip(';').split('/')
            vm_attached_disks[vm_name][disk_name] = int(float(disk_size)/1024)
        vm_id = vm_obj.vcd_id

        context["container_name"]: vm.get("containerName")
        vm_dict[vm_name] = {
            "name": vm.get("name"),
            "status": vm.get("status"),
            "container": vm.get("container"),
            "number_of_cpus": int(vm.get("numberOfCpus")),
            "memory_mb": math.trunc(int(vm.get("memoryMB"))/1024),
            'committed_storage': vm_obj.committed_storage,
            'provisioned_storage': vm_obj.provisioned_storage,
            'vsphere_name': vm_obj.vsphere_name,
            "org": vm.get("org"),
            'hostname': vm_obj.host_name,
            "vdc": vm.get("vdc"),
            'id': vm_id,
            'busy': redis_server.exists(vm_id)
        }
    context['range'] = list(range(1, 33))
    context['vapp_id'] = vapp_id
    context['vms'] = vm_dict
    context['dod'] = vm_disks_per_datastore
    context['attached'] = vm_attached_disks
    context['vAppName'] = vapp_name
    return render(request, 'Vms/index.html', context)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def get_vms(request, vapp_vcd_id, api=True):

    func_name = 'Get_Vm_In_VApp'
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']
    client = VMWareClientSingleton().client
    redis_server = utils.get_redis()
    fields = ("name,status,container,numberOfCpus,"
              "memoryMB,containerName,org,vdc")
    qfilters = f"isExpired==false;container=={vapp_vcd_id}"
    resource_type = ResourceType.ADMIN_VM.value
    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilters)

    vms = Vms.objects.filter(vapp_obj__vcd_id__contains=vapp_vcd_id)
    vm_dict_map = {vm.name: vm for vm in vms}

    vm_list = [{
        "name": vm.get("name"),
        "status": vm.get("status"),
        "number_of_cpus": int(vm.get("numberOfCpus")),
        "memory_mb": int(vm.get("memoryMB")),
        "committed_storage": vm_dict_map[vm.get("name")].committed_storage,
        "provisioned_storage": vm_dict_map[vm.get("name")].provisioned_storage,
        "vsphere_name": vm_dict_map[vm.get("name")].vsphere_name,
        "hostname": vm_dict_map[vm.get("name")].host_name,
        "id": vm.get("href").rsplit('/', 1)[1].split('-', 1)[1],
        'busy': redis_server.exists(vm.get("href")
                                    .rsplit('/', 1)[1].split('-', 1)[1])
    } for vm in query_result]

    if not vm_list:
        msg = f"VM's not found for the given Vapp {vapp_vcd_id}"
        return HttpResponseBadRequest(msg)

    return Response(vm_list)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def vm_templates(request, template_id):
    """
    Displays VM templates index page. User must be logged in.

    **Template**

    :template:`vmtemplates/index.html`
    """
    context = {}
    client = VMWareClientSingleton().client
    qfilter = f"isExpired==false;container=={template_id}"
    fields = "name,status,numberOfCpus,memoryMB,vdc,containerName"
    resource_type = ResourceType.ADMIN_VM.value
    templates = utils.send_typed_query(client, resource_type, fields, qfilter)

    context["container_name"] = "" if not templates else templates[0].get(
        "containerName")
    for template in templates:
        template["name"] = template.get("name")
        template["status"] = template.get("status")
        template["number_of_cpus"] = template.get("numberOfCpus")
        template["memory_allocation"] = template.get("memoryMB")
        template["id"] = template.get("id")
    context["templates"] = templates
    context['template_id'] = template_id
    return render(request, 'VmsTemplates/index.html', context)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def power_on_vm(request, vapp_id, vm_id):

    msg = None
    client = VMWareClientSingleton().client
    fields = "status,numberOfCpus,memoryMB,container,name"
    qfilters = f"container=={vapp_id};id=={vm_id}"
    resource_type = ResourceType.ADMIN_VM.value
    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilters)

    # if the query fails query result will be None
    if not query_result:
        msg = "error getting vm details, please contact an administrator"
        messages.error(request, msg)
        return redirect(reverse('Vms:vm_index', args=[vapp_id]))

    vm_name = query_result[0].get("name")
    vm_status = query_result[0].get("status")

    # Has another user added this vm to the busy cache
    if vapp_utils.get_vapp_vm_busy_status(vm_id):
        msg = f"{vm_name} is currently busy and is unable to be powered on"
    # Is this vm in the correct state to be powered on
    elif vm_status not in (PowerState.POWER_OFF.value,
                           PowerState.SUSPENDED.value):
        msg = f"VM \"{vm_name}\" is already on"
    if msg:
        messages.error(request, msg)
        return redirect(reverse('Vms:vm_index', args=[vapp_id]))

    func_name = request.resolver_match.view_name
    logger.info(
        f' user: {request.user} vapp_id: {vapp_id} vm_id: {vm_id}')
    vm_href = query_result[0].get("href")
    extra_params = {'vm_name': vm_name, 'vm_href': vm_href}
    event_params = utils.create_event_params(func_name=func_name,
                                             resource_id=vm_id,
                                             user=request.user,
                                             resource_type='vm',
                                             event_stage='Start',
                                             created=datetime.now(),
                                             extra_params=extra_params)
    utils.add_vapp_or_vm_to_busy_cache(vm_id, 'Powering on')
    utils.create_event_in_db(event_params)
    vm_utils.power_on_vm.delay(event_params)
    msg = f"You have requested the vm {vm_name} to start "
    messages.success(request, msg)

    return redirect(reverse('Vms:vm_index', args=[vapp_id]))


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def power_off_vm(request, vapp_id, vm_id):

    msg = None
    client = VMWareClientSingleton().client
    fields = "status,numberOfCpus,memoryMB,container,name"
    qfilters = f"container=={vapp_id};id=={vm_id}"
    resource_type = ResourceType.ADMIN_VM.value
    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilters)

    # if the query fails query result will be None
    if not query_result:
        msg = "error getting vm details, please contact an administrator"
        messages.error(request, msg)
        return redirect(reverse('Vms:vm_index', args=[vapp_id]))

    vm_name = query_result[0].get("name")
    vm_status = query_result[0].get("status")

    # Has another user added this VM to the busy cache
    if vapp_utils.get_vapp_vm_busy_status(vm_id):
        msg = f"{vm_name} is currently busy and is unable to stop"

    # Make sure VM is in correct power state to be powered off
    elif vm_status not in (PowerState.POWER_ON.value,
                           PowerState.SUSPENDED.value):
        msg = f"{vm_name} must be powered on to be stopped"
    if msg:
        messages.error(request, msg)
        return redirect(reverse('Vms:vm_index', args=[vapp_id]))

    func_name = request.resolver_match.view_name
    logger.info(
        f' user: {request.user} vapp_id: {vapp_id} vm_id: {vm_id}')
    vm_href = query_result[0].get("href")
    extra_params = {'vm_name': vm_name, 'vm_href': vm_href}
    event_params = utils.create_event_params(func_name=func_name,
                                             resource_id=vm_id,
                                             user=request.user,
                                             resource_type='vm',
                                             event_stage='Start',
                                             created=datetime.now(),
                                             extra_params=extra_params)
    utils.add_vapp_or_vm_to_busy_cache(vm_id, 'Powering off')
    utils.create_event_in_db(event_params)
    vm_utils.power_off_vm.delay(event_params)
    msg = f"You have requested the vm {vm_name} to power off"
    messages.success(request, msg)
    return redirect(reverse('Vms:vm_index', args=[vapp_id]))


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def shutdown_vm(request, vapp_id, vm_id):

    msg = None
    client = VMWareClientSingleton().client
    fields = "status,numberOfCpus,memoryMB,container,name"
    qfilters = f"container=={vapp_id};id=={vm_id}"
    resource_type = ResourceType.ADMIN_VM.value
    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilters)

    # if the query fails query result will be None
    if not query_result:
        msg = "error getting vm details for vm, \
               please contact an administrator"
        messages.error(request, msg)
        return redirect(reverse('Vms:vm_index', args=[vapp_id]))

    vm_name = query_result[0].get("name")
    vm_href = query_result[0].get("href")
    vm_tools_installed = vm_utils.vm_tools_is_installed(vm_href)
    vm_status = query_result[0].get("status")

    # If VM tools is not installed on this VM,
    # a Guest Shutdown can't be performed
    if not vm_tools_installed:
        msg = (
            f"{vm_name} can not perform a Guest shutdown because VMWare Tools \
            is not installed on this VM")

    # Has another user added this VM to the busy cache
    elif vapp_utils.get_vapp_vm_busy_status(vm_id):
        msg = f"{vm_name} is currently busy and is unable to stop"

    # Make sure VM is in correct power state to be shutdown
    elif vm_status not in (PowerState.POWER_ON.value,
                           PowerState.SUSPENDED.value):
        msg = f"{vm_name} must be powered on to be Shutdown"

    if msg:
        messages.error(request, msg)
        return redirect(reverse('Vms:vm_index', args=[vapp_id]))

    func_name = request.resolver_match.view_name
    logger.info(
        f' user: {request.user} vapp_id: {vapp_id} vm_id: {vm_id}')
    extra_params = {'vm_name': vm_name, 'vm_href': vm_href}
    event_params = utils.create_event_params(func_name=func_name,
                                             resource_id=vm_id,
                                             user=request.user,
                                             resource_type='vm',
                                             event_stage='Start',
                                             created=datetime.now(),
                                             extra_params=extra_params)
    utils.add_vapp_or_vm_to_busy_cache(vm_id, 'Shutting Down')
    utils.create_event_in_db(event_params)
    vm_utils.shutdown_vm.delay(event_params)
    msg = f"you have requested the vm {vm_name} to shutdown"
    messages.success(request, msg)

    return redirect(reverse('Vms:vm_index', args=[vapp_id]))


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def delete_vm(request, vapp_id, vm_id):

    msg = None
    client = VMWareClientSingleton().client
    fields = "status,numberOfCpus,memoryMB,container,name"
    qfilters = f"container=={vapp_id};id=={vm_id}"
    resource_type = ResourceType.ADMIN_VM.value
    query_result = utils.send_typed_query(client, resource_type,
                                          fields, qfilters)

    # Failed query will result in 'None'
    if not query_result:
        msg = "Error getting vm details, please contact an Administrator"
        messages.error(request, msg)
        return redirect(reverse('Vms:vm_index', args=[vapp_id]))

    vm_name = query_result[0].get("name")
    vm_status = query_result[0].get("status")

    # Has another user added this vm to the busy cache
    if vapp_utils.get_vapp_vm_busy_status(vm_id):
        msg = f"{vm_name} is currently busy and cannot be deleted"
    # Is this vm in the correct state to be deleted
    elif vm_status not in (PowerState.POWER_OFF.value,
                           PowerState.SUSPENDED.value):
        msg = f"Please power off \"{vm_name}\" before deleting."
    if msg:
        messages.error(request, msg)
        return redirect(reverse('Vms:vm_index', args=[vapp_id]))

    func_name = request.resolver_match.view_name
    logger.info(
        f' user: {request.user} vapp_id: {vapp_id} vm_id: {vm_id}')
    vm_href = query_result[0].get("href")
    extra_params = {'vm_name': vm_name, 'vm_href': vm_href}
    event_params = utils.create_event_params(func_name=func_name,
                                             resource_id=vm_id,
                                             user=request.user,
                                             resource_type='vm',
                                             event_stage='Start',
                                             created=datetime.now(),
                                             extra_params=extra_params,
                                             is_api=False)
    utils.add_vapp_or_vm_to_busy_cache(vm_id, 'Deleting')
    utils.create_event_in_db(event_params)
    vm_utils.delete_vm.delay(event_params)
    msg = f"You have requested the vm: {vm_name} to be deleted."
    messages.success(request, msg)

    return redirect(reverse('Vms:vm_index', args=[vapp_id]))

def vm_tasks(request, vm_id):
    client = VMWareClientSingleton().client
    return JsonResponse(vm_utils.get_vm_status(client, vm_id))
