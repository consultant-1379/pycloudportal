import json
from django.utils import timezone
from django.conf import settings
import logging
from collections import defaultdict
from django.shortcuts import render, redirect, reverse
from django.http import JsonResponse
from pyvcloud.vcd.vm import VM
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from pyvcloud.vcd.client import ResourceType
from rest_framework.response import Response
from pyvcloud_project.models import OrgVdcs, Vapps, Catalogs, Groups, SppUser
from pyvcloud_project.utils import vm_utils, vapp_network_utils, orgvdc_utils,\
    vapp_utils, pyvcloud_utils as utils
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.utils.pyvcloud_utils import PowerState, remove_vapp_or_vm_from_busy_cache
from datetime import datetime
from django.http import HttpResponseBadRequest
logger = logging.getLogger(__name__)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def index(request, org_vdc_id):
    """
    Displays vapp index page. Login is required to access the page.

    **Context**

    ``Models used:``
        :model:`pyvcloud_project.orgvdcs`\n
        :model:`pyvcloud_project.vapps`\n
        :model:`pyvcloud_project.sppuser`\n
        :model:`pyvcloud_project.groups`

    **Template**

    :template:`vapps/vapp_index.html`
    """
    messages.get_messages(request).used = True
    redis_server = utils.get_redis()
    client = VMWareClientSingleton().client
    org_vdc_obj = OrgVdcs.objects.get(org_vdc_id=org_vdc_id)
    vapps = Vapps.objects.filter(org_vdc_obj=org_vdc_obj).values('vcd_id', 'shared', 'created', 'name').annotate(status=F('state_id'),
                                                                                                                 gateway=F(
                                                                                                                     'vts_name'),
                                                                                                                 created_by=F('created_by_user_obj__user__username'))

    vapp_resources = orgvdc_utils.get_vapp_resources(client, org_vdc_id)
    vapp_power_states = orgvdc_utils.get_power_state_of_vapps(
        client, org_vdc_id)

    spp_user = SppUser.objects.get(user=request.user)
    spp_user_ldap_groups = utils.get_user_ldap_groups(spp_user)
    permission_groups = Groups.objects.filter(org_vdc_obj=org_vdc_obj)

    spp_user_admin_permission = spp_user.is_staff or spp_user.is_superuser
    if not spp_user_admin_permission:
        for group in permission_groups:
            group_cn = group.group_dn.split(',', 1)[0]
            if group_cn in spp_user_ldap_groups:
                spp_user_admin_permission = group.admin_permission
                if spp_user_admin_permission:
                    break

    filtered_vapps = []
    for vapp in vapps:
        if spp_user_admin_permission or vapp['created_by'] == spp_user.username or vapp['shared']:
            vapp_vcd_id = vapp['vcd_id']
            vapp['gateway'] = "" if not vapp['gateway'] else vapp['gateway'].split('.')[
                0]
            vapp['created_by'] = "" if not vapp['created_by'] else vapp['created_by']
            try:
                vapp.update(vapp_resources[vapp_vcd_id])
            except KeyError:
                # vapp import might need to be done first
                continue
            try:
                vapp.update(vapp_power_states[vapp_vcd_id])
            except KeyError:
                # vapp import might need to be done first
                continue
            vapp['busy'] = redis_server.exists(vapp_vcd_id)
            filtered_vapps.append(vapp)
        else:
            continue

    context = {'vapps': filtered_vapps, 'org_vdc_id': org_vdc_id,
               'admin_permission': spp_user_admin_permission, 'sppuser': spp_user.username, 'cloudAreaName': org_vdc_obj.name }
    return render(request, 'Vapps/vapp_index.html', context)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def create_vapp_from_template(request):
    # Params from URL
    ############################################
    vapp_name = request.GET.get('vapp_name')
    power_on = (request.GET.get('power_state', 'off').lower() == 'on')
    vapp_template_id = request.GET.get('vapp_template_id')
    orgvdc_name = request.GET.get('org_vdc_name').replace(' ', '')
    ############################################

    func_name = 'Create_VApp_From_Template'
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    client = VMWareClientSingleton().client
    resource_type = ResourceType.VAPP_TEMPLATE.value
    fields = 'catalogName,name'
    qfilter = f"isExpired==false;id=={vapp_template_id}"
    query_result = utils.send_typed_query(
        client, resource_type, fields, qfilter)

    sppuser = None
    if not isinstance(request.user, SppUser):
        sppuser = SppUser.objects.get(user=request.user)

    if not query_result:
        msg = f"Could not retrieve template from vmware for template id {vapp_template_id}"
        return HttpResponseBadRequest(msg)

    redis_server = utils.get_redis()
    vapp_details = []

    try:
        vapp_name_exist = vapp_utils.is_vapp_name_unique_on_vcd(
            client, vapp_name)

        if vapp_name_exist:
            # Retrieve the details of the existing vApp
            vapp = Vapps.objects.filter(name=vapp_name).select_related(
                'org_vdc_obj', 'created_by_user_obj__user').values('vcd_id', 'shared', 'created', 'name',
                                                                   'state_id', 'vts_name',
                                                                   'created_by_user_obj__user__username', 'ip_address')
            if vapp:
                vapp_vcd_id = vapp[0].get('vcd_id')
                gateway = vapp[0].get('vts_name', '').split('.')[0]
                created_by = vapp[0].get(
                    'created_by_user_obj__user__username', '')

                vapp_power_state = vapp_utils.get_vapp_power_state(
                    client, vapp_vcd_id)
                number_of_vms = vapp_utils.list_vapp_vms(vapp_vcd_id)

                vapp_details = {
                    'name': vapp[0].get('name', ''),
                    'status': vapp_power_state,
                    'creation_date': vapp[0].get('created'),
                    'number_of_vms': len(number_of_vms),
                    'vapp_id': vapp_vcd_id,
                    'gateway_hostname': gateway,
                    'gateway_ipaddress': vapp[0].get('ip_address', ''),
                    'owner': created_by,
                    'shared': vapp[0].get('shared'),
                    'busy': redis_server.exists(vapp_vcd_id),
                }

                return Response(vapp_details)

            else:
                msg = f'Vapp with name {vapp_name} exists but could not retrieve vApp details'
                return HttpResponseBadRequest(msg)

    except Exception as e:
        msg = f'An error occurred while checking if the vApp name {vapp_name} is unique. VApp name might not be provided in the request'
        return HttpResponseBadRequest(msg)

    templates = query_result[0]
    catalog_name = templates[0].get("catalogName")
    template_name = templates[0].get("name")

    if not all([catalog_name, template_name, vapp_name, orgvdc_name, power_on]):
        msg = f'Failed to open catalog area. Check provided arguments "catalog_name": {catalog_name or "MISSING"}, "template_name": {template_name or "MISSING"}, "vapp_name": {vapp_name or "MISSING"}, "orgvdc_name": {orgvdc_name or "MISSING"}'
        return HttpResponseBadRequest(msg)

    try:
        orgvdc_obj = OrgVdcs.objects.select_related(
            'provider_vdc_obj').get(name=orgvdc_name)
    except OrgVdcs.DoesNotExist:
        msg = f"Org VDC with name {orgvdc_name} not found."
        return HttpResponseBadRequest(msg)

    orgvdc_id = orgvdc_obj.org_vdc_id

    if orgvdc_obj.provider_vdc_obj.new_quota_system and power_on and not vapp_utils.allowed_power_on_vapp_resources(client, orgvdc_id, template_name):
        msg = f"Starting this vApp {vapp_name} would bring you over the running Resource (CPU/Memory) quota, please power off other vApps first"
        return HttpResponseBadRequest(msg)
    elif power_on and not vapp_utils.allowed_poweron_another_vapp(client, orgvdc_id):
        msg = f"Choosing to power on this new vApp would bring you over the running vApp quota, please power off other vApps first"
        return HttpResponseBadRequest(msg)
    elif not vapp_utils.allowed_create_another_vapp(client, orgvdc_id):
        msg = f"Creating this vApp {vapp_name} would bring you over the Total vApps quota, please delete other vApps first"
        return HttpResponseBadRequest(msg)

    extra_params = {'org_vdc_id': orgvdc_obj.org_vdc_id, 'vapp_name': vapp_name, 'catalog_name': catalog_name,
                    'template_name': template_name, 'power_on': power_on, 'org_vdc_name': orgvdc_name, 'sppuser': sppuser}
    event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_template_id, user=request.user, resource_type='vapp',
                                             event_stage='Start', created=timezone.now(), extra_params=extra_params, is_api=True, request_host=request_host)

    logger.info(f'user: {request.user} vapp_name {vapp_name} vapp_template_name: {template_name} vapp_template_id: {vapp_template_id} catalog_name {catalog_name} orgvdc_name: {orgvdc_name} orgvdc_id: {orgvdc_obj.org_vdc_id}')

    utils.create_event_in_db(event_params)
    vapp_utils.create_vapp_from_template(event_params)

    logger.info(
        f"LMI Request: vApp {vapp_name} Created & Powered On. Retriving the vApp Details")

    # Retrieve the details of the created vApp
    vapp = Vapps.objects.filter(org_vdc_obj=orgvdc_obj, name=vapp_name).select_related(
        'created_by_user_obj__user').values('vcd_id', 'shared', 'created', 'name',
                                            'state_id', 'vts_name',
                                            'created_by_user_obj__user__username', 'ip_address')

    if vapp:
        vapp_vcd_id = vapp[0].get('vcd_id')
        gateway = vapp[0].get('vts_name', '').split('.')[0]
        created_by = vapp[0].get('created_by_user_obj__user__username', '')

        vapp_power_state = vapp_utils.get_vapp_power_state(client, vapp_vcd_id)
        number_of_vms = vapp_utils.list_vapp_vms(vapp_vcd_id)

        vapp_details.append({
            'name': vapp[0].get('name', ''),
            'status': vapp_power_state,
            'creation_date': vapp[0].get('created'),
            'number_of_vms': len(number_of_vms),
            'vapp_id': vapp_vcd_id,
            'gateway_hostname': gateway,
            'gateway_ipaddress': vapp[0].get('ip_address', ''),
            'owner': created_by,
            'shared': vapp[0].get('shared'),
            'busy': redis_server.exists(vapp_vcd_id),
        })

    logger.info(
        f"LMI Request: vApp {vapp_name} Details found.")

    return Response(vapp_details)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def stop_and_add_vapp_to_catalog(request):
    """
    Takes a vApps in the specified organization VDC, power them off amd then adds the stopped VApps to the specified catalog. Login is required to perform the action.

    Parameters:
    - vapp_vcd_id : vApp ID to be added to catalog from.
    - catalog_name (str): The name of the catalog where the stopped VApp template will be added.
    - new_catalog_name (str): The name of the new template to be added.
    - api (bool): Whether to return the data in API format or not.

    Returns:
    - list: A list of dictionaries representing the stopped VApps that were added to the specified catalog. If `api` is True, returns the raw API response instead.
    """

    func_name = "Stop_And_Add_VApp_To_Catalog"
    vapp_vcd_id = request.GET.get('vapp_vcd_id')
    catalog_name = request.GET.get('orgcatalogs')
    new_template_name = request.GET.get('new_template_name')

    if not all([vapp_vcd_id, catalog_name, new_template_name]):
        msg = f'Failed to proceed. Check provided arguments "catalog_name": {vapp_vcd_id or "MISSING"}, "catalog_name": {catalog_name or "MISSING"}, "new_template_name": {new_template_name or "MISSING"}'
        return HttpResponseBadRequest(msg)

    try:
        vapp = Vapps.objects.get(vcd_id=vapp_vcd_id)
        vapp_name = vapp.name

        client = VMWareClientSingleton().client
        request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

        vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
        if vapp_busy:
            msg = f"Vapp {vapp_name} is currently busy and is unable to be powered off."
            return HttpResponseBadRequest(msg)

        power_state = vapp_utils.is_vapp_powered_off(client, vapp_vcd_id)
        if power_state != PowerState.POWER_OFF.value:
            logger.info(f'Is Vapp Powered_off {power_state}')

        qfilter = f"id=={vapp_vcd_id}"
        fields = "org"
        resource_type = ResourceType.ADMIN_VAPP.value
        query_result = utils.send_typed_query(
            client, resource_type, fields, qfilter)

        if not query_result:
            msg = f"Error getting org details for vapp {vapp_name}. Please contact an Administrator"
            return HttpResponseBadRequest(msg)

        org_vdc_id = vapp.org_vdc_obj.org_vdc_id

        # check if template with same name already exists
        qfilter = f"isExpired==false;catalogName=={catalog_name}"
        fields = "name"
        resource_type = ResourceType.VAPP_TEMPLATE.value
        catalog_templates = utils.send_typed_query(
            client, resource_type, fields, qfilter)

        if not catalog_templates:
            msg = f"Error retrieving templates for catalog: {catalog_name}"
            logger.info(
                f'user: {request.user} Error retrieving templates for catalog: {catalog_name}')
            return HttpResponseBadRequest(msg)

        # check if the catalog/orgvdc will allow more templates to be added
        catalog_obj = Catalogs.objects.get(name=catalog_name)
        if not len(catalog_templates) < catalog_obj.allowed_templates:
            msg = f"Catalog {catalog_name} already has the max allowed templates, {catalog_obj.allowed_templates}. One or more must be removed before more can be added"
            return HttpResponseBadRequest(msg)

        for template in catalog_templates:
            if template.get('name').lower() == new_template_name.lower():
                msg = f"Template with name {new_template_name} already exists in Catalog {catalog_name}"
                return HttpResponseBadRequest(msg)

        # Get Org & Vapp href
        qfilter = f"id=={vapp_vcd_id}"
        fields = "org,status"
        resource_type = ResourceType.ADMIN_VAPP.value
        query_result = utils.send_typed_query(
            client, resource_type, fields, qfilter)
        if not query_result:
            msg = f"Error getting org details for vapp {vapp_name}, Cannot add vapp to catalog {catalog_name}. Please contact an Administrator"
            return HttpResponseBadRequest(msg)

        org_href = query_result[0].get('org')
        vapp_href = query_result[0].get('href')
        logger.info(
            f'user: {request.user} vapp_id: {vapp_vcd_id} orgvdc_id: {org_vdc_id}')

        extra_params = {'vapp_name': vapp_name, 'vapp_href': vapp_href, 'org_href': org_href,
                        'catalog_name': catalog_name, 'new_template_name': new_template_name, 'org_vdc_id': org_vdc_id}
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=True, request_host=request_host)

        utils.add_vapp_or_vm_to_busy_cache(
            vapp_vcd_id, 'API Request: Stopping & Adding To Catalog')
        utils.create_event_in_db(event_params)
        vapp_utils.stop_and_add_vapp_to_catalog.delay(event_params)

        msg = f"vApp \"{vapp_name}\" is being added to catalog {catalog_name}"
        return Response(msg)

    except Vapps.DoesNotExist:
        msg = f"Vapp with ID {vapp_vcd_id} cannot be found. Please check the Vapp ID provided"
        return HttpResponseBadRequest(msg)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def get_vapps(request, org_vdc_id):
    """
    Returns a list of all Vapps in the specified org vdc. Login is required to perform the action.

    Parameters:
    org_vdc_id (str): ID of the organization VDC
    api (bool): Whether to return the data in API format or not

    Returns:
    list: List of Vapps in the specified org vdc
    """
    func_name = 'Get_VApps'
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']
    redis_server = utils.get_redis()
    client = VMWareClientSingleton().client

    vapps_in_orgVdc = []

    # Get the list of Vapps in the specified org vdc
    try:
        org_vdc_obj = OrgVdcs.objects.get(org_vdc_id=org_vdc_id)
    except OrgVdcs.DoesNotExist:
        return HttpResponseBadRequest(f"OrgVDC with ID: {org_vdc_id} not found")

    vapps_obj = Vapps.objects.filter(org_vdc_obj=org_vdc_obj).select_related(
        'created_by_user_obj__user').values('vcd_id', 'shared', 'created', 'name',
                                            'state_id', 'vts_name',
                                            'created_by_user_obj__user__username', 'ip_address')

    if not vapps_obj:
        return HttpResponseBadRequest(f"No Vapps found for the specified org vdc: {org_vdc_id}")

    vapp_power_states = orgvdc_utils.get_power_state_of_vapps(
        client, org_vdc_id)
    vapp_resources = orgvdc_utils.get_vapp_vms(client, org_vdc_id)

    for vapp in vapps_obj:
        vapp_vcd_id = vapp['vcd_id']
        vapp['gateway'] = "" if not vapp['vts_name'] else vapp['vts_name'].split('.')[
            0]
        vapp['created_by'] = "" if not vapp['created_by_user_obj__user__username'] else vapp['created_by_user_obj__user__username']

        vapps_in_orgVdc.append({
            'name': vapp['name'],
            'status': vapp_power_states.get(vapp_vcd_id, {}).get('power_state'),
            'creation_date': vapp['created'],
            'number_of_vms': vapp_resources.get(vapp_vcd_id, {}).get('number_of_vms'),
            'vapp_id': vapp_vcd_id,
            'gateway_hostname': vapp['gateway'],
            'gateway_ipaddress': vapp['ip_address'],
            'owner': vapp['created_by'],
            'shared': vapp['shared'],
            'busy': redis_server.exists(vapp_vcd_id),
        })

    return Response(vapps_in_orgVdc)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def get_vapp_status(request, vAppName, org_vdc_id, api=False):
    """
    Returns the status given Vapps in the specified org vdc. Login is required to perform the action.

    Parameters:
    org_vdc_id (str): ID of the organization VDC
    vapp_vcd_id: ID of Vapp in given organization
    api (bool): Whether to return the data in API format or not

    Returns:
    list: List of Vapps in the specified org vdc
    """
    func_name = 'Get_VApp_Status'
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    try:
        vapp = Vapps.objects.values('vcd_id', 'name').get(name=vAppName)
        vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp['vcd_id'])

        if vapp_busy:
            logger.info(
                f"LMI Request: vApp {vapp['name']} is Busy")
            return Response(vapp_busy)

        logger.info(
            f"LMI Request: vApp {vapp['name']} is Ideal")
        return Response(vapp_busy)

    except Vapps.DoesNotExist:
        return Response(f"Vapp: {vapp['name']} does not exist")


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def start_vapp(request, vapp_vcd_id, org_vdc_id, api=False):
    """
    Start vapp function. Login is required to perform the action.

    **Context**

    ``Models used:``
        :model:`pyvcloud_project.vapps`

    **Template**

    :template:`vapps/vapp_index.html`
    """
    func_name = "Start_VApp"
    # Check if running in a test environment
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
    vapp_name = Vapps.objects.get(vcd_id=vapp_vcd_id).name

    # Has another user added this vapp to the busy cache
    vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
    if vapp_busy:
        msg = f"Vapp {vapp_name} is currently busy and is unable to start"
        if api:
            return HttpResponseBadRequest(msg)

        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    # Is the vapp in the correct power state to be started
    client = VMWareClientSingleton().client
    power_state = vapp_utils.is_vapp_powered_off(client, vapp_vcd_id)

    if power_state == PowerState.POWER_ON.value:
        msg = f"Vapp \"{vapp_name}\" is already on"
        if api:
            return HttpResponseBadRequest(msg)

        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    logger.info(
        f' user: {request.user} vapp_id: {vapp_vcd_id} orgvdc_id: {org_vdc_id}')

    extra_params = {'org_vdc_id': org_vdc_id, 'vapp_name': vapp_name}

    if api:
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=True, request_host=request_host)
    else:
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=False, request_host=request_host)

    utils.add_vapp_or_vm_to_busy_cache(vapp_vcd_id, 'Starting')
    utils.create_event_in_db(event_params)
    vapp_utils.start_vapp.delay(event_params)
    msg = f"You have requested the vApp \"{vapp_name}\" to start "
    messages.success(request, msg)
    return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def stop_vapp(request, vapp_vcd_id, org_vdc_id, api=False):
    """
    Stop vapp function. Login is required to perform the action.

    **Context**

    ``Models used:``
        :model:`pyvcloud_project.vapps`

    **Template**

    :template:`vapps/vapp_index.html`
    """
    func_name = "Stop_VApp"
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    msg = None

    vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
    vapp_name = Vapps.objects.get(vcd_id=vapp_vcd_id).name

    # Has another user added this vapp to the busy cache
    vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
    if vapp_busy:
        msg = f"Vapp {vapp_name} is currently busy and is unable to stop"
        if api:
            return HttpResponseBadRequest(msg)

        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    # Is the vapp in the correct power state to be stopped
    client = VMWareClientSingleton().client
    power_state = vapp_utils.is_vapp_powered_off(client, vapp_vcd_id)

    if power_state == PowerState.POWER_OFF.value:
        msg = f"Vapp \"{vapp_name}\" must be powered on to be stopped"
    if msg:
        logger.info(msg)
        if api:
            return HttpResponseBadRequest(msg)

        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    logger.info(
        f'user: {request.user} vapp_id: {vapp_vcd_id} orgvdc_id: {org_vdc_id}')

    extra_params = {'org_vdc_id': org_vdc_id, 'vapp_name': vapp_name}

    if api:
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=True, request_host=request_host)
    else:
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=False, request_host=request_host)

    utils.add_vapp_or_vm_to_busy_cache(vapp_vcd_id, 'Stopping')
    utils.create_event_in_db(event_params)
    if power_state == PowerState.MIXED.value:
        vapp_utils.poweroff_vapp.delay(event_params)
    else:
        vapp_utils.stop_vapp.delay(event_params)
    msg = f"You have requested the vApp \"{vapp_name}\" to stop "
    messages.success(request, msg)
    return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def delete_vapp(request, vapp_vcd_id, api=False):
    """
    Stop vapp function. Login is required to perform the action.

    **Context**

    ``Models used:``
        :model:`pyvcloud_project.vapps`

    **Template**

    :template:`vapps/vapp_index.html`
    """
    func_name = 'Delete_VApp'
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    vapp_obj = Vapps.objects.select_related(
        'org_vdc_obj').get(vcd_id=vapp_vcd_id)
    vapp_name = vapp_obj.name
    org_vdc_id = vapp_obj.org_vdc_obj.org_vdc_id
    # Has another user added this vapp to the busy cache
    vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
    if vapp_busy:
        msg = f"Vapp {vapp_name} is currently busy and is unable to be deleted"
        if api:
            return HttpResponseBadRequest(msg)

        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    # check if Vapp is Powered off
    client = VMWareClientSingleton().client
    power_state = vapp_utils.is_vapp_powered_off(client, vapp_vcd_id)
    if power_state != PowerState.POWER_OFF.value:
        msg = f"Vapp \"{vapp_name}\" is not powered off. Please power it off before deleting"
        utils.remove_vapp_or_vm_from_busy_cache(vapp_vcd_id)
        if api:
            return HttpResponseBadRequest(msg)

        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    logger.info(
        f'user: {request.user} vapp_id: {vapp_vcd_id} orgvdc_id: {org_vdc_id}')
    extra_params = {'org_vdc_id': org_vdc_id, 'vapp_name': vapp_name}

    if api:
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=True, request_host=request_host)
    else:
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=False, request_host=request_host)

    utils.add_vapp_or_vm_to_busy_cache(vapp_vcd_id, 'Powering Off & Deleting')
    utils.create_event_in_db(event_params)
    vapp_utils.delete_vapp.delay(event_params)
    msg = f"You have requested the vApp \"{vapp_name}\" to delete "
    messages.success(request, msg)
    return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def power_off_delete_vapp(request, vapp_vcd_id, api=False):
    """
    Stop vapp function. Login is required to perform the action.

    **Context**

    ``Models used:``
        :model:`pyvcloud_project.vapps`

    **Template**

    :template:`vapps/vapp_index.html`
    """
    func_name = 'Poweroff_and_delete'
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    vapp_obj = Vapps.objects.select_related(
        'org_vdc_obj').get(vcd_id=vapp_vcd_id)
    vapp_name = vapp_obj.name
    org_vdc_id = vapp_obj.org_vdc_obj.org_vdc_id
    # Has another user added this vapp to the busy cache
    vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
    if vapp_busy:
        msg = f"Vapp {vapp_name} is currently busy and is unable to be deleted"
        if api:
            return HttpResponseBadRequest(msg)

        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    logger.info(
        f'user: {request.user} vapp_id: {vapp_vcd_id} orgvdc_id: {org_vdc_id}')
    extra_params = {'org_vdc_id': org_vdc_id, 'vapp_name': vapp_name}

    event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                             event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=True, request_host=request_host)

    utils.add_vapp_or_vm_to_busy_cache(vapp_vcd_id, 'Powering Off & Deleting')
    utils.create_event_in_db(event_params)
    vapp_utils.poweroff_and_delete.delay(event_params)

    msg = f"You have requested the vApp \"{vapp_name}\" to be powered off & deleted"
    messages.success(request, msg)
    return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def poweroff_vapp(request, vapp_vcd_id, org_vdc_id, api=False):
    """
    Power Off Vapp function. Login is required to perform the action.

    **Context**

    ``Models used:``
        :model:`pyvcloud_project.vapps`

    **Template**

    :template:`vapps/vapp_index.html`
    """
    func_name = 'Poweroff_VApp'
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    # Has another user added this vapp to the busy cache
    vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
    vapp_name = Vapps.objects.get(vcd_id=vapp_vcd_id).name
    if vapp_busy:
        msg = f"Vapp {vapp_name} is currently busy and is unable to be powered off"
        if api:
            return HttpResponseBadRequest(msg)

        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    client = VMWareClientSingleton().client
    # check if Vapp is Powered off
    power_state = vapp_utils.is_vapp_powered_off(client, vapp_vcd_id)
    if power_state == PowerState.POWER_OFF.value:
        msg = f"Vapp \"{vapp_name}\" is already powered off."
        utils.remove_vapp_or_vm_from_busy_cache(vapp_vcd_id)
        if api:
            return HttpResponseBadRequest(msg)

        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    logger.info(
        f'user: {request.user} vapp_id: {vapp_vcd_id} orgvdc_id: {org_vdc_id}')
    extra_params = {'org_vdc_id': org_vdc_id, 'vapp_name': vapp_name}
    if api:
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=True, request_host=request_host)
    else:
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=False, request_host=request_host)

    utils.add_vapp_or_vm_to_busy_cache(vapp_vcd_id, 'Powering Off')
    utils.create_event_in_db(event_params)
    vapp_utils.poweroff_vapp.delay(event_params)

    msg = f"You have requested the vApp \"{vapp_name}\" to poweroff "
    messages.success(request, msg)
    return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))


@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
def add_vapp_to_catalog(request):
    """
    Displays add vapp to catalog page. Login is required to access the page.

    **Context**

    ``Extra parameters``
    \t
        str: vapp_vcd_id\n
        str: orgcatalogs\n
        str: new_template_name\n

    ``Models used:``
        :model:`pyvcloud_project.vapps`\n
        :model:`pyvcloud_project.catalogs`

    **Template**
        ``POST``
        :template:`vapps/vapp_index.html`

        ``GET``
        :template:`vapps/add_to_catalog.html`
    """
    func_name = "Add_VApp_To_Catalog"
    context = {}
    client = VMWareClientSingleton().client
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    if request.method == "POST":
        vapp_vcd_id = request.POST.get('vapp_vcd_id')
        catalog_name = request.POST.get('orgcatalogs')
        new_template_name = request.POST.get('new_template_name')
        org_vdc_id = Vapps.objects.get(
            vcd_id=vapp_vcd_id).org_vdc_obj.org_vdc_id
        vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
        vapp_name = Vapps.objects.get(vcd_id=vapp_vcd_id).name
        if vapp_busy:
            msg = f"Vapp {vapp_name} is currently busy and is unable to be added to catalog {catalog_name}"
            messages.error(request, msg)
            return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

        # check if template with same name already exists
        qfilter = f"isExpired==false;catalogName=={catalog_name}"
        fields = "name"
        resource_type = ResourceType.VAPP_TEMPLATE.value
        catalog_templates = utils.send_typed_query(
            client, resource_type, fields, qfilter)
        if not catalog_templates:
            messages.error(
                request, f"Error retrieving templates for catalog : {catalog_name}")
            return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

        # check if the catalog/orgvdc will allow more templates to be added
        catalog_obj = Catalogs.objects.get(name=catalog_name)
        if not len(catalog_templates) < catalog_obj.allowed_templates:
            messages.error(
                request, f"Catalog {catalog_name} already has the max allowed templates, {catalog_obj.allowed_templates}. One or more must be removed before more can be added")
            return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

        for template in catalog_templates:
            if template.get('name').lower() == new_template_name.lower():
                messages.error(
                    request, f"Template with name {new_template_name} already exists in Catalog {catalog_name}")
                return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

        # Get Org & Vapp href
        qfilter = f"id=={vapp_vcd_id}"
        fields = "org,status"
        resource_type = ResourceType.ADMIN_VAPP.value
        query_result = utils.send_typed_query(
            client, resource_type, fields, qfilter)
        if not query_result:
            messages.error(
                request, f"Error getting org details for vapp {vapp_name}, Cannot add vapp to catalog {catalog_name}. Please contact an Administrator")
            return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

        org_href = query_result[0].get('org')
        vapp_href = query_result[0].get('href')
        logger.info(
            f'user: {request.user} vapp_id: {vapp_vcd_id} orgvdc_id: {org_vdc_id}')
        extra_params = {'vapp_name': vapp_name, 'vapp_href': vapp_href, 'org_href': org_href,
                        'catalog_name': catalog_name, 'new_template_name': new_template_name, 'org_vdc_id': org_vdc_id, }
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=True, request_host=request_host)
        utils.add_vapp_or_vm_to_busy_cache(vapp_vcd_id, 'Adding To Catalog')
        utils.create_event_in_db(event_params)
        vapp_utils.add_vapp_to_catalog.delay(event_params)
        msg = f"vApp \"{vapp_name}\" is being added to catalog {catalog_name}"
        messages.success(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))
    else:
        vapp_vcd_id = request.GET.get('vapp_vcd_id')
        org_vdc_id = request.GET.get('org_vdc_id')
        vapp_name = request.GET.get('vapp_name')
        # Has another user added this vapp to the busy cache
        vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
        if vapp_busy:
            msg = f"Vapp {vapp_name} is currently busy and is unable to be added to a catalog"
            messages.error(request, msg)
            return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))
        # check if Vapp is Powered off
        msg = f"Vapp \"{vapp_name}\" is not powered off. Please power it off before adding it to a catalog"
        power_state = vapp_utils.is_vapp_powered_off(client, vapp_vcd_id)
        if power_state != PowerState.POWER_OFF.value:
            messages.error(request, msg)
            return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

        qfilter = f"id=={vapp_vcd_id}"
        fields = "org"
        resource_type = ResourceType.ADMIN_VAPP.value
        query_result = utils.send_typed_query(
            client, resource_type, fields, qfilter)

        if not query_result:
            messages.error(
                request, f"Error getting org details for vapp {vapp_name}. Please contact an Administrator")
            return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

        org_href = query_result[0].get('org')
        org_id = 'urn:vcloud:org:' + org_href.split('/')[-1]

        catalogs = Catalogs.objects.filter(org_obj__vcd_id=org_id)
        context['catalogs'] = catalogs
        context['vapp_vcd_id'] = vapp_vcd_id
        context['vapp_name'] = vapp_name

        return render(request, 'Vapps/add_to_catalog.html', context)


@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
def rename_vapp_form(request, vapp_vcd_id, vapp_name):
    """
    Displays rename vapp page. Login is required to access the page.

    :template:`vapps/rename_vapps.html`
    """
    context = {}
    context['vapp_vcd_id'] = vapp_vcd_id
    context['vapp_name'] = vapp_name
    return render(request, 'Vapps/rename_vapps.html', context)


@require_http_methods(['POST'])
@login_required(login_url='user_login')
def rename_vapp(request, vapp_vcd_id):
    """
    Rename vapp function. Login is required to perform the action.

    **Context**

    ``Models used:``
        :model:`pyvcloud_project.vapps`

    **Template**

    :template:`vapps/vapp_index.html`
    """
    func_name = request.resolver_match.view_name
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    vapp_obj = Vapps.objects.select_related(
        'org_vdc_obj').get(vcd_id=vapp_vcd_id)
    vapp_obj = Vapps.objects.select_related(
        'org_vdc_obj').get(vcd_id=vapp_vcd_id)
    org_vdc_id = vapp_obj.org_vdc_obj.org_vdc_id

    old_vapp_name = vapp_obj.name
    vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
    if vapp_busy:
        msg = f"Vapp {old_vapp_name} is currently busy and is unable to be renamed"
        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    messages.get_messages(request).used = True
    client = VMWareClientSingleton().client
    new_vapp_name = request.POST.get('new_vapp_name')

    vapp_name_exist = vapp_utils.is_vapp_name_unique_on_vcd(
        client, new_vapp_name)
    if vapp_name_exist:
        messages.error(
            request, f'Vapp with name {new_vapp_name} already exists')
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))
    if new_vapp_name.lower() == old_vapp_name.lower():
        message_level = 40
        message = f"New Vapp Name : '{old_vapp_name}' and Current Vapp Name : '{new_vapp_name}' must differ"
        messages.add_message(request, message_level, message)
    else:
        logger.info(
            f'user: {request.user} vapp_id: {vapp_vcd_id} orgvdc_id: {org_vdc_id}')
        extra_params = {'org_vdc_id': org_vdc_id,
                        'new_vapp_name': new_vapp_name, 'old_vapp_name': old_vapp_name}
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=True, request_host=request_host)
        utils.add_vapp_or_vm_to_busy_cache(vapp_vcd_id, 'Renaming')
        utils.create_event_in_db(event_params)
        vapp_utils.rename_vapp.delay(event_params)
        message = f"Vapp {old_vapp_name} has been placed in the queue and will be renamed soon"
        messages.success(request, message)
    return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))


def vapp_tasks(request, vapp_vcd_id=None):
    client = VMWareClientSingleton().client
    task_status = vapp_utils.get_vapp_status(client, vapp_vcd_id)
    return JsonResponse(task_status)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def vapp_poweroff_and_delete(request, vapp_vcd_id, org_vdc_id, vapp_name):
    """
    Power off and delete vapp function. Login is required to perform the action.

    **Template**

    :template:`vapps/vapp_index.html`
    """
    func_name = "VApp_PowerOff_And_Delete"
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
    if vapp_busy:
        msg = f"Vapp {vapp_name} is currently busy and is unable to be powered off or deleted"
        messages.error(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

    logger.info(
        f'user: {request.user} vapp_id: {vapp_vcd_id} orgvdc_id: {org_vdc_id}')
    extra_params = {'org_vdc_id': org_vdc_id, 'vapp_name': vapp_name}
    event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                             event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=True, request_host=request_host)
    utils.add_vapp_or_vm_to_busy_cache(vapp_vcd_id, 'Powering Off & Deleting')
    utils.create_event_in_db(event_params)
    vapp_utils.poweroff_and_delete.delay(event_params)
    msg = f"You have requested the vApp \"{vapp_name}\" to poweroff and delete "
    messages.success(request, msg)
    return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def toggle_vapp_shared_state(request, vapp_vcd_id, org_vdc_id, vapp_name, share_unshare):
    """
    Toggle vapp function. Login is required to perform the action.

    **Context**

    **Template**

    :template:`vapps/vapp_index.html`
    """
    msg = None
    vapp_shared = vapp_utils.toggle_vapp_shared_state(
        vapp_vcd_id, share_unshare)
    if vapp_shared:
        msg = f"vApp {vapp_name} is now being shared"
    else:
        msg = f"vApp {vapp_name} is no longer being shared"
    messages.success(request, msg)
    return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def vapp_diagram(request, vapp_id, container_name, page):
    """
    Display vapp network diagram. Login is required to view the page.

    **Template**

    :template:`vapps/vapp_diagram.html`
    """
    context = {}
    client = VMWareClientSingleton().client

    vm_list = vm_utils.get_vms(client, vapp_id)
    context['external_network_names'] = \
        vapp_network_utils.get_external_networks(client, vapp_id)
    context['internal_network_names'] = \
        vapp_network_utils.get_internal_networks(client, vapp_id)

    vms = defaultdict(list)
    for vm in vm_list:
        vm_obj = VM(client, vm.get('href'))
        nic_list = vm_obj.list_nics()
        nic_list.sort(key=lambda x: x['index'])
        context["nics"] = nic_list
        vms["vms"].append(
            {
                "container_name": vm.get('containerName'),
                "name": vm.get('name'),
                "nics": nic_list
            })

    context["vms"] = vms['vms']
    context['template_id'] = vapp_id
    context['container_name'] = container_name
    context['template_url'] = page

    return render(request, 'Vapps/vapp_diagram.html', context)


@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
def recompose_vapp(request, vapp_vcd_id, api=False):
    """
    Recompose vapp function. Login is required to perform the action.

    **Context**

    ``Models used:``
        :model:`pyvcloud_project.vapps`\n
        :model:`pyvcloud_project.sppuser`\n
        :model:`pyvcloud_project.groups`\n
        :model:`pyvcloud_project.catalogs`

    **Template**
        ``GET``
        :template:`vapps/recompose_vapp.html`

        ``POST``
        :template:`vapps/vapp_index.html`
    """
    func_name = request.resolver_match.view_name
    vapp_obj = Vapps.objects.select_related(
        'org_vdc_obj').get(vcd_id=vapp_vcd_id)
    vapp_name = vapp_obj.name
    client = VMWareClientSingleton().client
    request_host = 'TestCase' if settings.TEST else request.META['HTTP_HOST']

    if request.method == "GET":
        context = {}
        context['vapp_id'] = vapp_vcd_id

        spp_user = SppUser.objects.get(user=request.user)
        spp_user_ldap_groups = utils.get_user_ldap_groups(spp_user)
        permission_groups = Groups.objects.filter()

        user_catalogs = set()
        spp_user_admin_permission = spp_user.is_staff or spp_user.is_superuser
        if not spp_user_admin_permission:
            user_groups = []
            for group in permission_groups:
                group_cn = group.group_dn.split(',', 1)[0]
                if group_cn in spp_user_ldap_groups:
                    user_groups.append(group)

            for group in user_groups:
                if group.restrict_catalogs:
                    restricted_catalog_ids = group.unrestricted.split(',')
                    user_catalogs.update(Catalogs.objects.filter(
                        vcd_id__in=restricted_catalog_ids))
                else:
                    group_catalogs = Catalogs.objects.filter(
                        org_obj=group.org_obj)
                    user_catalogs.update(group_catalogs)
        else:
            user_catalogs.update(Catalogs.objects.filter())

        user_catalog_ids = [catalog.vcd_id for catalog in user_catalogs]

        catalog_templates = defaultdict(list)
        template_vm_dict = defaultdict(list)

        resource_type = ResourceType.ADMIN_VAPP_TEMPLATE.value
        fields = "status,name,creationDate,org,catalog,catalogName,catalogItem"
        qfilter = "isExpired==false"
        query_results = utils.send_typed_query(
            client, resource_type, fields, qfilter) or []

        for query_result in query_results:
            catalog_id = query_result.get('catalog').rsplit('/', 1)[1]
            if catalog_id not in user_catalog_ids:
                continue
            template_id = query_result.get(
                'href').rsplit('/', 1)[1].split('-', 1)[1]
            catalog_templates[catalog_id].append(
                (query_result.get('name'), template_id))
            resource_type = ResourceType.ADMIN_VM.value
            fields = "name"
            qfilter = f"container=={template_id}"
            template_vms = utils.send_typed_query(
                client, resource_type, fields, qfilter) or []
            for vm in template_vms:
                if 'master_gateway' in vm.get('name'):
                    continue
                vm_id = vm.get('href').rsplit('/', 1)[1].split('-', 1)[1]
                template_vm_dict[template_id].append((vm.get('name'), vm_id))

        catalog_templates.default_factory = None
        template_vm_dict.default_factory = None
        context['template_vms'] = template_vm_dict
        context['catalogs'] = user_catalogs
        context['templates'] = catalog_templates
        context['vapp_name'] = vapp_name

        return render(request, 'Vapps/recompose_vapp.html', context)
    else:
        # When using Ctrl-click to select vm's to recompose, the multiselect will send across an empty string that we need to handle
        if api:
            # Decode the bytes data and load it as a JSON object
            json_data = json.loads(request.body.decode('utf-8'))
            # Extract the "id" and "name" values and concatenate them in the required format
            template_vms = [
                f"{vm['id']}|{vm['name']}" for vm in json_data['vms']]
        else:
            template_vms = [template for template in request.POST.getlist(
                'recompose_vms') if template]

        org_vdc_id = vapp_obj.org_vdc_obj.org_vdc_id
        # Has another user added this vapp to the busy cache
        vapp_busy = vapp_utils.is_vapp_or_any_vm_busy(vapp_vcd_id)
        if vapp_busy:
            msg = f"Vapp {vapp_name} is currently busy and is unable to be recomposed"
            if api:
                return HttpResponseBadRequest(msg)

            messages.error(request, msg)
            return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))

        if not template_vms:
            msg = "You must select at least 1 Vm to recompose"
            if api:
                return HttpResponseBadRequest(msg)

            messages.error(request, msg)
            return redirect(reverse('Vapp:recompose_vapp', args=[vapp_vcd_id]))

        vapp_vcenter = vapp_utils.get_vapp_vcenter(vapp_vcd_id)
        for template_vm in template_vms:
            template_vm_id = template_vm.split('|')[0]
            vm_vcenter = vm_utils.get_vm_vcenter(template_vm_id)
            if vm_vcenter != vapp_vcenter or any('could not be found' in vcenter for vcenter in [vm_vcenter, vapp_vcenter]):
                msg = f"You cannot recompose a vapp with vms from another vcenter. (ie destination vApp is in {vapp_vcenter}  and source vm is in {vm_vcenter}). Please seek support if you believe this to be incorrect'"
                if api:
                    return HttpResponseBadRequest(msg)

                messages.error(request, msg)
                return redirect(reverse('Vapp:recompose_vapp', args=[vapp_vcd_id]))

        template_vm_names = []
        for vm in template_vms:
            _, vm_name = vm.split('|')
            template_vm_names.append(vm_name)

        if api:
            template_id = json_data.get('catalog_templates').split(':')[-1]
        else:
            template_id = request.POST.get('catalog_templates')

        template_href = vapp_utils.get_vapp_href(client, template_id)
        logger.info(
            f'user: {request.user} vapp_name {vapp_name} vapp_id: {vapp_vcd_id} orgvdc_id: {org_vdc_id}')
        extra_params = {'vapp_name': vapp_name, 'org_vdc_id': org_vdc_id,
                        'recompose_vms': template_vm_names, 'template_href': template_href, 'template_id': template_id, }
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                 event_stage='Start', created=datetime.now(), extra_params=extra_params, is_api=api, request_host=request_host)
        utils.add_vapp_or_vm_to_busy_cache(vapp_vcd_id, 'Recomposing')
        utils.create_event_in_db(event_params)
        if api:
            vapp_utils.recompose_vapp(event_params)
            remove_vapp_or_vm_from_busy_cache(vapp_vcd_id)
            event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_vcd_id, user=request.user, resource_type='vapp',
                                                     event_stage='End', created=datetime.now(), extra_params=extra_params, is_api=api, request_host=request_host, outcome='Completed')
            utils.create_event_in_db(event_params)
            return Response()
        else:
            vapp_utils.recompose_vapp.delay(event_params)
        msg = f"Vapp {vapp_name} has been added to the queue to be recomposed"
        messages.success(request, msg)
        return redirect(reverse('Vapp:vapp_index', args=[org_vdc_id]))
