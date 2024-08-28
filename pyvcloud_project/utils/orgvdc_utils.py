"""
This module contains various functions and imports related to OrgVDC.
"""

import urllib.parse
import socket
import math
from django.db.models import Sum
from pyvcloud.vcd.client import ResourceType
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.utils import pvdc_utils, pyvcloud_utils as utils
from pyvcloud_project.models import OrgVdcs, ProviderVdcs, Vapps
from pyvcloud_project import forms
from pyvcloud_project.utils.pyvcloud_utils import PowerState


def import_orgvdc():
    """
    Imports organization VDCs from VMware and updates the OrgVdcs database table.

    Returns:
        str: A message indicating the successful import of OrgVdcs.
    """
    client = VMWareClientSingleton().client
    admin_href = client.get_admin().get('href')
    system = utils.get_system(client, admin_href=admin_href)
    provider_vdcs = system.list_provider_vdcs()
    all_org_vdcs_db = OrgVdcs.objects.all()
    org_vdcs_from_vmware = []
    for provider in provider_vdcs:
        try:
            pvdc = pvdc_utils.get_pvdc(client, provider.get('href'))
            pvdc_refs = pvdc.get_vdc_references().VdcReference
            provider_id = pvdc.resource.get('id')
            org_vdcs = [(ref.get('name'), ref.get('id')) for ref in pvdc_refs]
            org_vdcs_from_vmware.append(org_vdcs)
            pvdc_db = ProviderVdcs.objects.get(vdc_id=provider_id)
            provider_org_vdcs_db = all_org_vdcs_db.filter(
                provider_vdc_obj=pvdc_db)
            vc_ip = get_vcenter_ip(pvdc_refs, provider_org_vdcs_db)

            for org_vdc in org_vdcs:
                org_vdc_name = org_vdc[0]
                org_vdc_id = org_vdc[1]
                OrgVdcs.objects.update_or_create(
                    org_vdc_id=org_vdc_id,
                    provider_vdc_obj=pvdc_db,
                    vcenter=vc_ip,
                    defaults={
                        'name': org_vdc_name,
                    }
                )

        except AttributeError as err:
            add_error_to_email(err)
            continue
        except ProviderVdcs.DoesNotExist as err:
            add_error_to_email(err)
            continue

    clean_up_db(provider_org_vdcs_db, org_vdcs_from_vmware)
    return "OrgVdcs have been imported"

# Later TODO implement email functionality


def add_error_to_email(error):
    """
    Later TODO: Add error to email
    """
    pass


def clean_up_db(org_vdcs_db, org_vdcs_from_vmware):
    """
    Cleans up the database by removing organization VDCs and associated vApps that are not present in the org_vdcs_from_vmware list.
    """
    org_ids = [org[1] for provider in org_vdcs_from_vmware for org in provider]
    for org_vdc in org_vdcs_db:
        if org_vdc.org_vdc_id not in org_ids:
            Vapps.objects.filter(org_vdc_obj=org_vdc).delete()
            org_vdc.delete()


def orgvdcs_not_in_db(org_vdcs_db, org_vdcs) -> list:
    """
    Returns a list of organization VDCs that are not present in the database.
    """
    results = []
    for org_id in org_vdcs:
        if not org_vdcs_db.filter(org_vdc_id=org_id[1]):
            results.append(org_id)
    return results


def get_vcenter_ip(pvdc_ref, org_vdcs_db) -> str:
    """
    Returns the vCenter IP address for an organization VDC.
    """
    vcenter_ip = ''
    for org_vdc in org_vdcs_db:
        if org_vdc.vcenter:
            vcenter_ip = org_vdc.vcenter
            break
    if not vcenter_ip:
        try:
            vcenter_href = pvdc_ref.get('href')
            vcenter_hostname = urllib.parse.urlparse(vcenter_href).netloc
            vcenter_ip = socket.gethostbyname(vcenter_hostname)
        except Exception:
            pass

    return vcenter_ip


def set_organisation_data(provider_vdc, org_vdcs):
    """
    Sets the organization data based on the provider VDC and organization VDC information.

    Args:
        provider_vdc (list): List of provider VDCs.
        org_vdcs (list): List of organization VDCs.
    """
    for provider in provider_vdc:
        cpu_limit = provider['available_cpus'] * provider['cpu_multiplier']
        for org_vdc in org_vdcs:
            if provider['name'] == org_vdc['provider_vdc_obj__name']:
                if provider['new_quota_system']:
                    org_vdc['quota_system'] = 'Running CPUs / Memory'
                    org_vdc_cpu = org_vdc['cpu_limit']
                    org_vdc_memory = org_vdc['memory_limit']
                    running_vapp_limit = 'NA'
                else:
                    org_vdc['quota_system'] = 'Running vApps'
                    org_vdc_cpu = 'NA'
                    org_vdc_memory = 'NA'
                    running_vapp_limit = org_vdc['running_tb_limit']

                if cpu_limit == 0:
                    org_vdc['provider_ratio'] = '1/1'
                else:
                    memory_limit = provider['available_memory_gb'] * \
                        provider['memory_multiplier']
                    vdc_ratio = str(round(memory_limit/cpu_limit, 2)) + '/1'
                    org_vdc['provider_ratio'] = vdc_ratio

                if org_vdc_cpu in (0, 'NA'):
                    org_vdc['org_vdc_ratio'] = '1/1'
                else:
                    orgvdc_ratio = str(
                        round(org_vdc_memory / org_vdc_cpu, 2)) + '/1'
                    org_vdc['org_vdc_ratio'] = orgvdc_ratio
                org_vdc['cpu_limit'] = org_vdc['cpu_limit']
                org_vdc['memory_limit'] =  org_vdc['memory_limit']
                org_vdc['vapp_quota'] = running_vapp_limit


def init_org_vdc_edit_page_values(org_vdc_id, context):
    """
    Initializes the organization VDC edit page values.

    Args:
        org_vdc_id: The ID of the organization VDC.
        context: The context object.
    """
    org_vdc = OrgVdcs.objects.filter(org_vdc_id=org_vdc_id).values(
        'name',
        'running_tb_limit',
        'stored_tb_limit',
        'cpu_limit',
        'memory_limit',
        'provider_vdc_obj',
        'provider_vdc_obj__available_cpus',
        'provider_vdc_obj__available_memory_gb',
        'provider_vdc_obj__cpu_multiplier',
        'provider_vdc_obj__memory_multiplier',
        'mig_ra_obj__name'
    ).first()

    initial_data = {
        'cpu_limit': org_vdc['cpu_limit'],
        'memory_limit': org_vdc['memory_limit'],
        'running_tb_limit': org_vdc['running_tb_limit'],
        'stored_tb_limit': org_vdc['stored_tb_limit'],
        'org_vdc_id': org_vdc_id,
        'mig_ra_name': org_vdc['mig_ra_obj__name'],
        'name': org_vdc['name']
    }

    orgvdc_objs = OrgVdcs.objects.filter(
        provider_vdc_obj=org_vdc['provider_vdc_obj']).values('cpu_limit',
                                                             'memory_limit',
                                                             'name')
    cpu_limit = orgvdc_objs.aggregate(Sum('cpu_limit'))
    memory_limit = orgvdc_objs.aggregate(Sum('memory_limit'))
    form = forms.OrgvdcEdit(initial=initial_data)

    context['total_cpus'] = int(
        org_vdc['provider_vdc_obj__available_cpus'] *
        org_vdc['provider_vdc_obj__cpu_multiplier'])
    context['total_memory'] = int(
        org_vdc['provider_vdc_obj__available_memory_gb'] *
        org_vdc['provider_vdc_obj__memory_multiplier'])
    context['cpu_limit'] = cpu_limit['cpu_limit__sum']
    context['memory_limit'] = memory_limit['memory_limit__sum']
    context['orgvdcs'] = orgvdc_objs
    context['form'] = form
    context['name'] = org_vdc['name']


def get_org_vdc_db_values(orgvdc_id) -> dict:
    """
    Retrieves database values for a specific organization VDC.

    Returns:
        dict: A dictionary containing the database values for the organization VDC.
    """
    org_vdc = OrgVdcs.objects.filter(org_vdc_id=orgvdc_id).values(
        'name',
        'running_tb_limit',
        'stored_tb_limit',
        'cpu_limit',
        'memory_limit',
        'mig_ra_obj__name'
    ).first()

    db_values = {
        'cpu_limit': org_vdc['cpu_limit'],
        'memory_limit': org_vdc['memory_limit'],
        'running_tb_limit': org_vdc['running_tb_limit'],
        'stored_tb_limit': org_vdc['stored_tb_limit'],
        'org_vdc_id': orgvdc_id,
        'mig_ra_name': org_vdc['mig_ra_obj__name'],
        'name': org_vdc['name']
    }

    return db_values


def count_vapps(client, orgvdc_id):
    """
    Counts the number of running and not running vApps in an organization VDC.

    Returns:
        list: A list containing the count of running and not running vApps.
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


def get_vapp_resources(client, org_vdc_id):
    """
    Retrieves resource information for vApps in an organization VDC.

    Returns:
        dict: A dictionary containing the resource information for vApps.
    """
    resource_type = ResourceType.ADMIN_VM.value
    fields = "status,numberOfCpus,memoryMB,container"
    qfilter = f"isVAppTemplate==false;vdc=={org_vdc_id}"
    query_results = utils.send_typed_query(
        client, resource_type, fields, qfilter)

    vapp_hrefs = [vm_result.get('container') for vm_result in query_results]

    vapp_resources = {}
    for vapp_href in vapp_hrefs:
        number_of_vms = 0
        cpu_on_count = 0
        cpu_total = 0
        memory_on_count = 0
        memory_total = 0
        for vm_result in query_results:
            if vm_result.get('container') == vapp_href:
                number_of_vms = number_of_vms + 1
                if vm_result.get('status') == 'POWERED_ON':
                    cpu_on_count = cpu_on_count + \
                        int(vm_result.get('numberOfCpus'))
                    memory_on_count = memory_on_count + \
                        math.ceil(int(vm_result.get('memoryMB')) / 1024)
                cpu_total = cpu_total + int(vm_result.get('numberOfCpus'))
                memory_total = memory_total + \
                    math.ceil(int(vm_result.get('memoryMB')) / 1024)
        vapp_vcd_id = utils.href_to_id(vapp_href)
        vapp_resources[vapp_vcd_id] = {'cpu_on_count': cpu_on_count, 'cpu_total': cpu_total,
                                       'memory_on_count': memory_on_count, 'memory_total': memory_total, 'number_of_vms': number_of_vms}

    return vapp_resources


def get_vapp_vms(client, org_vdc_id):
    """
    Retrieves VM count for vApps in an organization VDC.

    Returns:
        dict: A dictionary containing the VM count for vApps.
    """
    resource_type = ResourceType.ADMIN_VM.value
    fields = "container"
    qfilter = f"isVAppTemplate==false;vdc=={org_vdc_id}"
    query_results = utils.send_typed_query(
        client, resource_type, fields, qfilter)

    vapp_hrefs = [vm_result.get('container') for vm_result in query_results]

    vapp_resources = {}
    for vapp_href in vapp_hrefs:
        number_of_vms = sum(vm_result.get('container') ==
                            vapp_href for vm_result in query_results)
        vapp_vcd_id = utils.href_to_id(vapp_href)
        vapp_resources[vapp_vcd_id] = {'number_of_vms': number_of_vms}

    return vapp_resources


def get_power_state_of_vapps(client, org_vdc_id):
    """
    Retrieves the power state of vApps in an organization VDC.

    Returns:
        dict: A dictionary containing the power state of vApps.
    """
    resource_type = ResourceType.ADMIN_VAPP.value
    fields = "status,isDeployed"
    qfilter = f"vdc=={org_vdc_id}"
    query_results = utils.send_typed_query(
        client, resource_type, fields, qfilter)
    vapp_power_states = {}
    for query_result in query_results:
        vapp_urn = utils.href_to_id(query_result.get('href'))
        status = query_result.get('status')
        isdeployed = query_result.get('isDeployed')
        vapp_power_state = create_vapp_status_string(status, isdeployed)
        vapp_power_states[vapp_urn] = {'power_state': vapp_power_state}

    return vapp_power_states

def create_vapp_status_string(vapp_power_state, is_vapp_deployed):
    """
    Creates the final power state string based on the input vApp power state and whether the vApp is deployed.

    Returns:
        str: The final power state string. If the input vApp power state is "MIXED" and
        the vApp is deployed, the final power state is set to 'PARTIALLY_POWERED_OFF'.
        Otherwise, it returns the input vApp power state.
    """
    final_power_state = vapp_power_state
    if vapp_power_state == "MIXED" and is_vapp_deployed == 'true':
        final_power_state = 'PARTIALLY_POWERED_OFF'
    return final_power_state


def get_vdc_href(client, orgvdc_id):
    """
    Generates the vDC href (URL) based on the provided orgvdc_id.

    Returns:
        str: The generated vDC href.
    """
    api_uri = client.get_api_uri()
    vapp_uri_segment = utils.get_api_url('orgvdc')
    extracted_orgvdc_id = orgvdc_id.split(':')[-1]
    href = api_uri + vapp_uri_segment.format(extracted_orgvdc_id)
    return href
