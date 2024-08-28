"""
This module contains views and utility functions for managing
VMware Cloud Director Org VDCs, VApp templates etc.

"""
import csv
from enum import Enum
from datetime import datetime
import logging
import base64
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import auth, messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import user_passes_test
from django.http import HttpResponseBadRequest, HttpResponseNotFound, HttpResponse, HttpResponseServerError
from django.contrib.auth import authenticate
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from collections import defaultdict

from pyvcloud.vcd.client import ResourceType
from lxml import etree
import bleach
import os
from rest_framework.response import Response
from pyvcloud_project import forms
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.models import OrgVdcs, Catalogs, Groups, ProviderVdcs, SppUser, MigRas, Vapps, HistoricalReport
from pyvcloud_project.utils import pyvcloud_utils as utils, group_utils, orgvdc_utils, vapp_utils, catalog_utils

logger = logging.getLogger(__name__)


class VMwereAPI(Enum):
    VAPP_TEMPLATE = "/vAppTemplate/vappTemplate-"

def show_report(request):
    """
    Show report.
    Context:
        - reports: A list of report objects, each containing 'name', 'url', and 'description'.
    """
    return render(request, 'Reports/report.html')

def vapp_report(request):
    client = VMWareClientSingleton().client
    vapps_data = Vapps.objects.all()
    vapp_info_list = vapp_utils.get_vapp_resource_info(client, vapps_data)

    # Store the vapp_info_list in a session for download
    request.session['vapp_info_list_for_download'] = vapp_info_list
    context = {"vapp_info_list": vapp_info_list}
    return render(request, 'Reports/vapp_reports.html', context)

def datacenter_vapp_report(request, datacenter_name):
    client = VMWareClientSingleton().client
    vapps_data = Vapps.objects.filter(org_vdc_obj__name=datacenter_name)
    vapp_info_list = vapp_utils.get_vapp_resource_info(client, vapps_data)

    context = {
        "vapp_info_list": vapp_info_list,
        "datacenter_name": datacenter_name,
    }
    # Store the datacenter_vapp_info for download
    request.session['datacenter_vapp_info_list_for_download'] = vapp_info_list
    return render(request, 'Reports/vapp_reports.html', context)

def download_vapp_csv(request):
    vapp_info_list = request.session.get('vapp_info_list_for_download', [])
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="vapp_report.csv"'

    csv_writer = csv.writer(response)
    csv_writer.writerow([
        'Datacenter Name',
        'vApp Name',
        'Status',
        'Gateway',
        'Created By',
        'Creation Date',
        'Running CPUs',
        'Running Memory (GB)',
        'Origin Catalog Name',
        'Origin Template Name',
    ])

    for vapp_info in vapp_info_list:
        csv_writer.writerow([
            vapp_info['catalog_name'],
            vapp_info['name'],
            vapp_info['vapp_power_state'],
            vapp_info['gateway'],
            vapp_info['created_by'],
            vapp_info['creation_date'],
            vapp_info['running_cpu'],
            vapp_info['running_memory'],
            vapp_info['origin_catalog_name'],
            vapp_info['origin_template_name'],
        ])

    return response

def datacenter_report(request):
    org_vdcs = OrgVdcs.objects.all()
    client = VMWareClientSingleton().client
    datacenter_info = []

    for org_vdc in org_vdcs:
        orgvdc_id = org_vdc.org_vdc_id
        running_vapps, *_ = orgvdc_utils.count_vapps(client, orgvdc_id)
        total_cpu_on_count = 0
        total_memory_on_count = 0
        vapp_resources = orgvdc_utils.get_vapp_resources(client, orgvdc_id)

        for vapp_info in vapp_resources.items():
            vapp_data = vapp_info[1]
            total_cpu_on_count += vapp_data.get('cpu_on_count')
            total_memory_on_count += vapp_data.get('memory_on_count')

        datacenter_info.append({
            "datacenter_name": org_vdc.name,
            "provider_name": org_vdc.provider_vdc_obj,
            "running_cpus": total_cpu_on_count,
            "running_cpus_quota": org_vdc.cpu_limit,
            "unused_running_cpus_quota": (org_vdc.cpu_limit - total_cpu_on_count),
            "running_memory_gb": total_memory_on_count,
            "running_memory_quota_gb": org_vdc.memory_limit,
            "unused_running_memory_quota_gb": (org_vdc.memory_limit - total_memory_on_count),
            "running_vApps": running_vapps,
            "running_vApps_quota": org_vdc.running_tb_limit,
            "unused_running_vApps_quota": (org_vdc.running_tb_limit - running_vapps),
            "total_vApps": len(vapp_resources),
            "total_vApps_quota": org_vdc.stored_tb_limit,
            "unused_total_vApps_quota": (org_vdc.stored_tb_limit - len(vapp_resources)),
        })

    # Store the datacenter_info for downlaod
    request.session['datacenter_info_list_for_download'] = datacenter_info
    context = {"datacenter_info": datacenter_info}
    return render(request, 'Reports/datacenter_report.html', context)

def download_datacenter_csv(request):
    datacenter_info_list = request.session.get('datacenter_info_list_for_download', [])
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="datacenter_report.csv"'

    csv_writer = csv.writer(response)
    csv_writer.writerow([
        'Datacenter Name',
        'Provider Name',
        'Running CPUs',
        'Running CPUs Quota',
        'Unused Running CPUs Quota',
        'Running Memory (GB)',
        'Running Memory Quota (GB)',
        'Unused Running Memory Quota (GB)',
        'Running vApps',
        'Running vApps Quota',
        'Unused Running vApps Quota',
        'Total vApps',
        'Total vApps Quota',
        'Unused Total vApps Quota',
    ])

    for datacenter_info in datacenter_info_list:
        csv_writer.writerow([
            datacenter_info['datacenter_name'],
            datacenter_info['provider_name'],
            datacenter_info['running_cpus'],
            datacenter_info['running_cpus_quota'],
            datacenter_info['unused_running_cpus_quota'],
            datacenter_info['running_memory_gb'],
            datacenter_info['running_memory_quota_gb'],
            datacenter_info['unused_running_memory_quota_gb'],
            datacenter_info['running_vApps'],
            datacenter_info['running_vApps_quota'],
            datacenter_info['unused_running_vApps_quota'],
            datacenter_info['total_vApps'],
            datacenter_info['total_vApps_quota'],
            datacenter_info['unused_total_vApps_quota'],
        ])

    return response

def download_datacenter_vapp_csv(request, datacenter_name):
    vapp_info_list = request.session.get('datacenter_vapp_info_list_for_download', [])
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="datacenter_vapp_report.csv"'

    csv_writer = csv.writer(response)
    csv_writer.writerow([
        'Datacenter Name',
        'vApp Name',
        'Status',
        'Gateway',
        'Created By',
        'Creation Date',
        'Running CPUs',
        'Running Memory (GB)',
        'Origin Catalog Name',
        'Origin Template Name',
    ])

    for vapp_info in vapp_info_list:
        csv_writer.writerow([
            vapp_info['catalog_name'],
            vapp_info['name'],
            vapp_info['vapp_power_state'],
            vapp_info['gateway'],
            vapp_info['created_by'],
            vapp_info['creation_date'],
            vapp_info['running_cpu'],
            vapp_info['running_memory'],
            vapp_info['origin_catalog_name'],
            vapp_info['origin_template_name'],
        ])

    return response

def historical_reports(request):
    historical_reports_obj = HistoricalReport.objects.all()
    reports = [
        {
            'name': report.name,
            'created_date': report.created_date
        }
        for report in historical_reports_obj
    ]
    context = {"reports": reports}
    return render(request, 'Reports/historical_reports.html', context)

def historical_report_download(request, reportName):
    file_path = os.path.join('/opt/pycloudportal/HistoricalReports/', reportName)
    if os.path.exists(file_path):
        with open(file_path, 'rb') as file:
            response = HttpResponse(file.read(), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{reportName}"'
            return response
    else:
        messages.error(request, 'File not found!')

    return render(request, 'Reports/report.html')

@require_http_methods(['GET'])
@login_required(login_url='user_login')
def org_vdc_index(request):
    """
    Displays all org vdcs from OrgVdcs based on a user authentication settings.
    Columns are different for admin and non-admin users.
    (To access this page a user is required to be logged in.)

    **Context**

    ``OrgVdc``
        An instance of :model:`pyvcloud_project.orgvdcs`.

    **Template**

    :template:`orgvdc/index.html`
    """
    messages.get_messages(request).used = True
    context = {}
    context['columns'] = ['Running CPUs Quota (GB)',
                          'Running Memory Quota (GB)',
                          'Running vApp Quota', 'Total vApp Quota',
                          'RA', 'Actions']
    org_vdcs = OrgVdcs.objects.all().values("id", 'name', 'org_vdc_id',
                                            'running_tb_limit',
                                            'stored_tb_limit',
                                            'provider_vdc_obj__name',
                                            'vcenter', 'mig_ra_obj__name',
                                            'cpu_limit', 'memory_limit')
    if request.user.is_staff or request.user.is_superuser:
        context['columns'] = ['Provider Quota System', 'Provider',
                              'Provider Memory(GB)/CPU Ratio',
                              'OrgVdc Memory(GB)/CPU Ratio'] \
            + context['columns']

    groups = Groups.objects.all().values('group_dn', 'org_vdc_obj',
                                         'read_permission', 'org_obj')

    spp_user = SppUser.objects.get(user=request.user)
    context['org_vdcs'] = []
    ldap_groups = utils.get_user_ldap_groups(spp_user)
    if ldap_groups and not spp_user.is_superuser:
        for org_vdc in org_vdcs:
            if not org_vdc['mig_ra_obj__name']:
                org_vdc['mig_ra_obj__name'] = 'None'
            for group in groups:
                group_cn = group.get('group_dn').split(',', 1)[0]
                if group.get('org_vdc_obj') == org_vdc.get('id')\
                    and group.get('read_permission')\
                        and group_cn.lower() in ldap_groups.lower():
                    context['org_vdcs'].append(org_vdc)
                    break
    elif spp_user.is_staff or spp_user.is_superuser:
        for org_vdc in org_vdcs:
            if not org_vdc['mig_ra_obj__name']:
                org_vdc['mig_ra_obj__name'] = 'None'
        context['org_vdcs'] = org_vdcs
    provider_vdc = ProviderVdcs.objects.all().values()
    orgvdc_utils.set_organisation_data(provider_vdc, org_vdcs)

    return render(request, 'OrgVdc/index.html', context)


@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
def edit_orgvdc(request):
    """
    Displays orgvdc edit page.
    (To access this page a user is required to be logged in.)

    **Context**

    ``Parameters``
    \t
        str: org_vdc_id\n
        str: provider_ratio\n
        str: org_vdc_id\n
        str: org_vdc_ratio\n
        str: mig_ra_obj\n
        str: cpu_limit\n
        str: memory_limit\n
        str: running_tb_limit\n
        str: stored_tb_limit\n
        str: name

    **Template**

    :template:`orgvdc/edit_orgvdc.html`
    """
    context = {}
    messages.get_messages(request).used = True

    if request.method == 'POST':
        org_vdc_id = request.POST.get('org_vdc_id')
        provider_ratio = request.POST.get('provider_ratio')
        org_vdc_ratio = request.POST.get('org_vdc_ratio')
        try:
            org_vdc_obj = OrgVdcs.objects.get(org_vdc_id=org_vdc_id)
            form = forms.OrgvdcEdit(request.POST, instance=org_vdc_obj)
            if form.is_valid():
                mig_ra = MigRas.objects.get(id=request.POST.get('mig_ra_obj'))
                posted_values = {
                    'cpu_limit': int(request.POST.get('cpu_limit')),
                    'memory_limit': int(request.POST.get('memory_limit')),
                    'running_tb_limit': int(request.POST.get('running_tb_limit')),
                    'stored_tb_limit': int(request. POST.get('stored_tb_limit')),
                    'org_vdc_id': org_vdc_id,
                    'mig_ra_name': str(mig_ra),
                    'name': request.POST.get('name')
                }
                orgvdc_db_values = orgvdc_utils.get_org_vdc_db_values(
                    org_vdc_id)
                if orgvdc_db_values == posted_values:
                    messages.info(request, 'No values were updated.')
                    return redirect(reverse('edit_orgvdc') + '?org_vdc_id=' +
                                    org_vdc_id + '&provider_ratio=' + provider_ratio+'&org_vdc_ratio='+org_vdc_ratio)
                orgvdc_form = form.save(commit=False)
                orgvdc_form.save()
                orgvdc_utils.init_org_vdc_edit_page_values(org_vdc_id, context)
                messages.success(
                    request, 'The orgvdc has been updated successfully.')
                return redirect(reverse('org_vdc_index'))

            messages.error(
                request, 'The orgvdc could not be updated. Please, try again.')

        except OrgVdcs.DoesNotExist:
            messages.error(request, 'The orgvdc could not be found.')
            print(f'Orgvdc {org_vdc_id} does not exist')
    else:
        org_vdc_id = request.GET.get('org_vdc_id')
        context['org_vdc_ratio'] = request.GET.get('org_vdc_ratio')
        context['provider_ratio'] = request.GET.get('provider_ratio')
        # Retrieve the org_vdc object from the database
        try:
            OrgVdcs.objects.get(org_vdc_id=org_vdc_id)
            orgvdc_utils.init_org_vdc_edit_page_values(org_vdc_id, context)
        except OrgVdcs.DoesNotExist:
            # Handle the case when the org_vdc is not found
            messages.error(request, 'The OrgVDC could not be found.')
            print(f'Orgvdc {org_vdc_id} does not exist')

    return render(request, 'OrgVdc/edit_orgvdc.html', context)


@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
def vapp_templates(request, catalog_name, org_name, api=False):
    """
    Displays available vapp templates for the selected catalog.
    (To access this page a user is required to be logged in.)

    **Template**

    :template:`vapptemplates/index.html`
    """

    client = VMWareClientSingleton().client
    resource_type = ResourceType.VAPP_TEMPLATE.value
    fields = "name,status,creationDate,numberOfCpus,memoryAllocationMB"
    qfilter = f"isExpired==false;catalogName=={catalog_name}"
    templates = utils.send_typed_query(client, resource_type, fields, qfilter)

    if not templates and api:
        msg = f"No templates found in the catalog '{catalog_name}'. Please check if the catalog name is correct and contains templates."
        return HttpResponseBadRequest(msg)

    templates_list = []
    for template in templates:
        template_info = get_template_info(template)
        templates_list.append(template_info)

    if api:
        return Response(templates_list)

    context = {"templates": templates_list,
               "catalog_name": catalog_name, "org_name": org_name}
    return render(request, 'VappTemplates/index.html', context)


def get_template_info(template):
    """
    Extracts information from a vApp template.

    Parameters:
        template (dict): The vApp template dictionary.

    Returns:
        dict: A dictionary containing the extracted template information.
    """

    template_id = extract_template_id(template)
    template_name = str(template.get("name"))
    template_status = str(template.get("status"))
    template_creation_date = extract_template_creation_date(template)
    template_num_cpus = template.get("numberOfCpus")
    template_memory_allocation = int(template.get("memoryAllocationMB")) / 1024

    return {
        "id": template_id,
        "name": template_name,
        "status": template_status,
        "creationDate": str(template_creation_date),
        "numberOfCpus": template_num_cpus,
        "memoryAllocation": template_memory_allocation
    }


def extract_template_id(template):
    """
    Extracts the template ID from a vApp template.
    Parameters:
        template (dict): The vApp template dictionary.
    """
    template_href = template.get("href")
    template_id = template_href.rsplit('/', 1)[1].split('-', 1)[1]
    return template_id


def extract_template_creation_date(template):
    """
    Extracts the creation date from a vApp template.
    Parameters:
        template (dict): The vApp template dictionary.
    """
    template_creation_date_str = template.get("creationDate")
    # Check if the string contains a timezone offset (+/-HH:MM)
    if '+' in template_creation_date_str or '-' in template_creation_date_str:
        date_format = "%Y-%m-%dT%H:%M:%S.%f%z"
    else:
        date_format = "%Y-%m-%dT%H:%M:%S.%fZ"

    template_creation_date = datetime.strptime(template_creation_date_str, date_format).replace(microsecond=0)
    return template_creation_date

@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def vapp_templates_media(request, catalog_name, org_name):
    """
    Displays a list of all available media files. And allows to upload a new iso image to VMware.
    (To access this page a user must be logged in)

    **Template**

    :template:`vapptemplates/media.html`
    """
    context = {}
    context['catalog_name'] = catalog_name
    context['org_name'] = org_name
    if request.method == "POST":
        iso_form = forms.UploadISOForm(request.POST, request.FILES)
        if not catalog_name:
            messages.error(request, 'Catalog name was not provided.')
        elif request.FILES['file'].content_type != 'application/octet-stream':
            messages.error(request, 'File format is not acceptable')
        elif iso_form.is_valid():
            message_level, message = catalog_utils.upload_iso_file(request.FILES['file'],
                                                                   catalog_name, org_name)
            messages.add_message(request, message_level, message)
        else:
            messages.error(request, 'File was not selected!')
        return redirect('vapp_templates_media', catalog_name, org_name)

    form = forms.UploadISOForm()
    context['form'] = form

    catalog_utils.get_media_from_catalog(catalog_name, context)

    return render(request, 'VappTemplates/media.html', context)


@login_required(login_url='user_login')
def vapp_templates_delete(request, vapp_template_id):
    """
    Allows to delete a template.
    (To access this function a user must be logged in.)

    **Template**

    After deletion redirects back to:
    :template:`catalogs.html`
    """
    client = VMWareClientSingleton().client
    href = client.get_api_uri() + VMwereAPI.VAPP_TEMPLATE.value + vapp_template_id
    try:
        client.delete_resource(href)
        messages.success(request, "Template is deleted")
    except Exception:
        messages.error(request, "Failed to delete vApp template")

    return redirect('catalogs')


@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
def vapp_templates_rename(request, vapp_template_id):
    """
    Displays rename vapp template page.
    (To access this function a user must be logged in.)

    **Context**

    ``Additional parameters``
        \t
        str: vapp_template_name

    **Template**

    :template:`vapptemplates/rename.html`
    """
    func_name = request.resolver_match.view_name
    client = VMWareClientSingleton().client
    resource_type = ResourceType.VAPP_TEMPLATE.value
    qfilter = f"isExpired==false;id=={vapp_template_id}"
    # query_result None parameter is used for fields
    query_result = utils.send_typed_query(client, resource_type, None, qfilter)

    if not query_result:
        msg = f"Could not retrieve template from vmware for template id {vapp_template_id}"
        messages.error(request, msg)
        return redirect('catalogs')

    templates = query_result[0]
    vapp_template_name = templates.get('name')
    context = {
        "vapp_template_id": vapp_template_id,
        "vapp_template_name": vapp_template_name
    }

    if request.method == "POST":
        if request.POST.get('vapp_template_name') == templates.get('name'):
            return redirect(request.get_full_path())
        template_name = request.POST.get("vapp_template_name")
        templates.set("name", template_name)
        status = templates.get("status").replace(' ', '').replace('_', '')
        status_id = str(vapp_utils.get_status_number(status))
        contents = etree.tostring(templates)
        contents = contents.replace(templates.get(
            "status").encode(), status_id.encode())
        logger.info(
            f"user {request.user} requested that vapp with id {vapp_template_id} be renamed to {template_name}")
        extra_params = {'templates': templates,
                        'new template_name': {template_name},
                        'contents': contents}
        event_params = utils.create_event_params(func_name=func_name, resource_id=vapp_template_id,
                                                 user=request.user, resource_type='vapp', event_stage='Start',
                                                 created=datetime.now(), extra_params=extra_params)
        utils.add_vapp_or_vm_to_busy_cache(vapp_template_id, 'Renaming')
        vapp_utils.vapp_templates_rename.delay(event_params)
        messages.success(
            request, f"Template {template_name} has been placed in the queue and will be renamed soon")
        return redirect('catalogs')
    return render(request, 'VappTemplates/rename.html', context)


@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
def create_vapp_from_template(request, vapp_template_id):
    """
    Displays rename vapp template page.
    (To access this function a user must be logged in.)

    **Context**

    ``Additional parameters``
        \t
        str: VappTemplateName\n
        str: poweron\n
        str: orgvdc

    ``OrgVdc``
        An instance of :model:`pyvcloud_project.orgvdcs`

    ``User``
        An instance of :model:`pyvcloud_project.sppuser`

    ``Groups``
        An instance of :model:`pyvcloud_project.groups`

    **Template**

    ``On fail:``

    :template:`vapptemplates/deploy.html`

    ``On success:``

    :template:`catalogs.html`
    """
    if request.method == "POST":
        return vapp_template_creation_post_request(request, vapp_template_id)

    context = get_context(request)
    context["vapp_template_id"] = vapp_template_id

    return render(request, 'VappTemplates/deploy.html', context)


def vapp_template_creation_post_request(request, vapp_template_id):
    """
    Processes the POST request data and performs validations and checks for vApp creation.
    If all validations pass, it triggers the asynchronous task to create the vApp.

    Redirects:
        - To 'catalogs' on error or if the template cannot be retrieved.
        - To 'create_vapp_from_template' with the vapp_template_id on validation errors.
        - To 'catalogs' on successful vApp creation.

    """
    func_name = "Create_VApp_From_Template"
    error = False
    sppuser = SppUser.objects.get(user=request.user)
    client = VMWareClientSingleton().client

    query_result = get_vapp_template(client, vapp_template_id)
    if not query_result:
        msg = f"Could not retrieve template from vmware for template id {vapp_template_id}"
        messages.error(request, msg)
        return redirect('catalogs')

    templates = query_result[0]
    catalog_name = templates[0].get("catalogName")
    template_name = templates[0].get("name")
    vapp_name = get_vapp_name(request)
    power_on = request.POST.get("poweron")
    orgvdc_name = request.POST.get("orgvdc")

    if vapp_utils.is_vapp_name_unique_on_vcd(client, vapp_name):
        messages.error(
            request, f'Vapp with name {request.POST.get("VappTemplateName")} already exists')
        return redirect('create_vapp_from_template', vapp_template_id)

    if not all([catalog_name, template_name, vapp_name, orgvdc_name]):
        messages.error(
            request, "Failed to open catalog area. Check provided arguments")
        return redirect('create_vapp_from_template', vapp_template_id)

    orgvdc_obj = OrgVdcs.objects.select_related(
        'provider_vdc_obj').get(name=orgvdc_name)
    orgvdc_id = orgvdc_obj.org_vdc_id

    if orgvdc_obj.provider_vdc_obj.new_quota_system:
        if power_on and not vapp_utils.allowed_power_on_vapp_resources(client, orgvdc_id, template_name):
            messages.error(
                request, f"Starting this vApp {vapp_name} would bring you over the running Resource (CPU/Memory) quota, please power off other vApps first")
            error = True
        elif not vapp_utils.allowed_poweron_another_vapp(client, orgvdc_id):
            messages.error(
                request, "Choosing to power on this new vApp would bring you over the running vApp quota, please power off other vApps first")
            error = True
        elif not vapp_utils.allowed_create_another_vapp(client, orgvdc_id):
            messages.error(
                request, f"Creating this vApp {vapp_name} would bring you over the Total vApps quota, please delete other vApps first")
            error = True
    if error:
        return redirect('create_vapp_from_template', vapp_template_id)

    extra_params = {
        'org_vdc_id': orgvdc_obj.org_vdc_id, 'vapp_name': vapp_name, 'catalog_name': catalog_name,
        'template_name': template_name, 'power_on': power_on, 'org_vdc_name': orgvdc_name,
        'sppuser': sppuser
    }

    event_params = utils.create_event_params(
        func_name=func_name, resource_id=vapp_template_id, user=request.user,
        resource_type='vapp', event_stage='Start', created=datetime.now(),
        extra_params=extra_params
    )

    logger.info(
        f'user: {request.user} vapp_name {vapp_name} vapp_template_name: {template_name} vapp_template_id: {vapp_template_id} \
        catalog_name {catalog_name} orgvdc_name: {orgvdc_name} orgvdc_id: {orgvdc_obj.org_vdc_id}')

    utils.create_event_in_db(event_params)
    vapp_utils.create_vapp_from_template.delay(event_params)
    messages.success(
        request, f"Your vApp {vapp_name} is now being added to your cloud. You will receive an email when it's ready.")
    return redirect('catalogs')


def get_context(request):
    """
    Generates the context dictionary for the vApp creation page, including the available organization virtual data centers (OrgVdcs).
    Context:
        orgvdcs (list): List of organization virtual data centers (OrgVdcs) available for vApp creation.
        vapp_template_id (str): The ID of the vApp template.
    """
    context = {"orgvdcs": []}
    org_vdcs = OrgVdcs.objects.all().values("name", "org_vdc_id", "id")
    groups = Groups.objects.all().values(
        'group_dn', 'org_vdc_obj', 'write_permission', 'org_obj')
    spp_user = SppUser.objects.get(user=request.user)
    ldap_groups = utils.get_user_ldap_groups(spp_user)
    if ldap_groups and not spp_user.is_superuser:
        for org_vdc in org_vdcs:
            for group in groups:
                group_cn = group.get('group_dn').split(',', 1)[0]
                if group.get('org_vdc_obj') == org_vdc.get('id') and \
                   group.get('write_permission') and group_cn in ldap_groups:
                    context['orgvdcs'].append(org_vdc)
                    break
    elif spp_user.is_staff or spp_user.is_superuser:
        context['orgvdcs'] = org_vdcs

    return context


def get_vapp_name(request):
    """
    Retrieves the vApp name from the request POST data, ensuring it is not None and stripping any leading or trailing whitespace.
    Returns:
        str or None: The vApp name if provided, None otherwise.
    """
    vapp_name = request.POST.get("VappTemplateName")
    return vapp_name.strip() if vapp_name else None


def get_vapp_template(client, vapp_template_id):
    """
    Retrieves the vApp template information from the VMware server based on the provided vApp template ID.
    Returns:
        dict or None: The vApp template information if found, None otherwise.
    """
    resource_type = ResourceType.VAPP_TEMPLATE.value
    fields = 'catalogName,name'
    qfilter = f"isExpired==false;id=={vapp_template_id}"
    return utils.send_typed_query(client, resource_type, fields, qfilter)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def catalogs(request):
    """
    Displays all available catalogs.
    (To access this function a user must be logged in.)

    **Context**

    ``Catalogs``
        An instance of :model:`pyvcloud_project.catalogs`

    ``User``
        An instance of :model:`pyvcloud_project.sppuser`

    ``Groups``
        An instance of :model:`pyvcloud_project.groups`

    **Template**

    :template:`catalogs.html`
    """
    context = {}
    context['catalogs'] = None
    catalogs_db = Catalogs.objects.all().values("name", "org_obj__name", 'vcd_id')
    sppuser = SppUser.objects.get(user=request.user)
    sppuser_ldap_groups = utils.get_user_ldap_groups(sppuser)
    groups = Groups.objects.all().values('group_dn', 'unrestricted',
                                         'restrict_catalogs', 'org_obj__name')
    allowed_catalogs = []

    if not (sppuser.is_staff or sppuser.is_superuser):
        for group in groups:
            group_cn = group.get('group_dn').split(',', 1)[0]
            if group_cn in sppuser_ldap_groups:
                if group.get('restrict_catalogs'):
                    restricted_catalog_ids = group.get(
                        'unrestricted').split(',')
                    allowed_catalogs.extend(restricted_catalog_ids)
                else:
                    group_org_name = group.get('org_obj__name')
                    allowed_catalogs.extend([catalog.get('vcd_id') for catalog in catalogs_db if catalog.get(
                        'org_obj__name') == group_org_name])
        if allowed_catalogs:
            context['catalogs'] = [catalog for catalog in catalogs_db if catalog.get(
                'vcd_id') in allowed_catalogs]
    else:
        context['catalogs'] = catalogs_db
    if not context['catalogs']:
        messages.error(request, 'No catalogs were found')
    return render(request, 'catalogs.html', context)

@csrf_exempt
@require_http_methods(['GET'])
def login_for_LMI(request):
    try:
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        logger.debug("Performing Authentication...")
        if auth_header:
            auth_type, auth_data = auth_header.split(' ', 1)
            if auth_type.lower() == 'basic':
                auth_data = base64.b64decode(auth_data).decode('utf-8')
                username, password = auth_data.split(':', 1)

                user = authenticate(request, username=username, password=password)
                if user is not None:
                    response_xml = '<response><login>Success</login></response>'
                    logger.info("Response Content-Type: %s", 'application/xml')
                    logger.debug("Response Data: %s", response_xml)

                    return HttpResponse(response_xml, content_type='application/xml')
                else:
                    logger.warning("Authentication failed for user: %s", username)

        return HttpResponse(status=401)

    except Exception as e:
        logger.exception("An error occurred: %s", str(e))
        return HttpResponseServerError()


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def login(request):
    """
    Displays login page.

    **Context**

    ``Parameters``
        str: username\n
        str: password

    **Template**

    ``On success:``

    :template:`orgvdc/index.html`

    ``On fail:``

    :template:`login.html`
    """
    if request.method == "GET":
        if request.user.is_authenticated:
            return redirect("/OrgsVdcs")

    elif request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = auth.authenticate(username=username, password=password)

        if user is not None:
            auth.login(request, user)
            return redirect("/OrgsVdcs")
        messages.error(
            request, "Your username / password combination was incorrect")

    return render(request, "login.html")


@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def add_groups(request):
    """
    Displays add group page. Only admin can view the page.

    **Context**

    ``Extra parameters``
    \t
        str: group_dn\n
        str: read_permission\n
        str: write_permission\n
        str: orgvdc_name\n
        str: org_name\n
        str: admin_permission\n
        str: cat_restricted\n
        str:catalog_permissions

    ``Models Used``
        :model:`pyvcloud_project.catalogs`\n
        :model:`pyvcloud_project.orgvdcs`\n
        :model:`pyvcloud_project.groups`\n

    **Template**

    ``POST Request``

    ``On success:``
    :template:`groups/groups.html`

    ``On Fail:``
    :template:`groups/add_groups.html`

    ``GET Request``

    :template:`groups/add_groups.html`
    """
    context = {}
    messages.get_messages(request).used = True
    if request.method == 'POST':
        group_dn = bleach.clean(request.POST.get('group_dn'))
        params = {
            'group_dn': group_dn,
            'read_permission': request.POST.get('read_permission'),
            'write_permission': request.POST.get('write_permission'),
            'orgvdc_name': request.POST.get('orgvdc_name'),
            'org_name': request.POST.get('org_name'),
            'admin_permission': request.POST.get('admin_permission'),
            'cat_restricted': request.POST.get('cat_restricted'),
            'catalog_permissions': request.POST.getlist('catalog_permissions')
        }
        message_level, message = group_utils.add_group(params)
        messages.add_message(request, message_level, message)
        if message_level == 25:  # success
            return redirect(reverse('list_groups'))
        return redirect(reverse('add_groups'))
    if request.method == 'GET':
        context, _, _ = group_utils.get_group_form_values(context)
    return render(request, 'Groups/add_groups.html', context)


@require_http_methods(['GET', 'POST'])
@login_required(login_url='user_login')
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def edit_groups(request, group_id):
    """
    Displays edit group page. Only admin can view the page.

    **Context**

    ``Extra parameters``
    \t
        str: group_dn\n
        str: read_permission\n
        str: write_permission\n
        str: orgvdc_name\n
        str: org_name\n
        str: admin_permission\n
        str: cat_restricted\n
        str:catalog_permissions

    ``Models Used``
        :model:`pyvcloud_project.catalogs`\n
        :model:`pyvcloud_project.orgvdcs`\n
        :model:`pyvcloud_project.orgs`\n
        :model:`pyvcloud_project.groups`\n

    **Template**

    :template:`groups/groups.html`
    """
    context = {}
    if group_id:
        if request.method == 'GET':
            context, message_level, message = \
                group_utils.get_group_form_values(context, 'edit', group_id)
            if message_level == 25:
                return render(request, 'Groups/edit_groups.html', context)
            messages.add_message(request, message_level, message)
        elif request.method == 'POST':
            group_dn = bleach.clean(request.POST.get('group_dn'))
            params = {
                'pk': group_id,
                'group_dn': group_dn,
                'read_permission': request.POST.get('read_permission'),
                'write_permission': request.POST.get('write_permission'),
                'orgvdc_name': request.POST.get('orgvdc_name'),
                'org_name': request.POST.get('org_name'),
                'admin_permission': request.POST.get('admin_permission'),
                'cat_restricted': request.POST.get('cat_restricted'),
                'catalog_permissions': request.POST.getlist('catalog_permissions')
            }
            message_level, message = group_utils.update_group(params)
            messages.add_message(request, message_level, message)
    return redirect(reverse('list_groups'))


@require_http_methods(['GET'])
@login_required(login_url='user_login')
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def list_groups(request):
    """
    Displays list group page. Only admin can view the page.

    **Context**

    ``Models Used``
        :model:`pyvcloud_project.groups`\n

    **Template**

    :template:`groups/groups.html`
    """
    messages.get_messages(request).used = True
    context = {}
    all_groups = Groups.objects.all().values('pk', 'group_dn', 'org_vdc_obj__name',
                                             'org_obj__name', 'read_permission',
                                             'write_permission', 'admin_permission',
                                             'restrict_catalogs')
    for group in all_groups:
        group['group_dn'] = group['group_dn'].split(',', 1)[0].split('=', 1)[1]
        if group['admin_permission']:
            group['description'] = group['org_vdc_obj__name'] + '-Admin'
        elif group['write_permission']:
            group['description'] = group['org_vdc_obj__name'] + '-RW'
        elif group['read_permission']:
            group['description'] = group['org_vdc_obj__name'] + '-RO'
        else:
            group['description'] = group['org_vdc_obj__name']
        group['write_permission'] = int(group['write_permission'])
        group['read_permission'] = int(group['read_permission'])
        group['admin_permission'] = int(group['admin_permission'])
        group['restrict_catalogs'] = int(group['restrict_catalogs'])
    context['groups'] = all_groups
    return render(request, 'Groups/groups.html', context)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def delete_groups(request, group_id):
    """
    Displays delete group page. Only admin can view the page.

    **Context**

    ``Models Used``
        :model:`pyvcloud_project.groups`\n

    **Template**

    :template:`groups/groups.html`
    """
    messages.get_messages(request).used = True
    group_to_delete = \
        Groups.objects.filter(pk=group_id).values(
            'org_vdc_obj__name', 'org_obj__name')
    if group_to_delete:
        Groups.objects.get(pk=group_id).delete()
        messages.success(request, f'Group for orgvdc \
            {group_to_delete[0]["org_vdc_obj__name"]} and \
            org {group_to_delete[0]["org_obj__name"]}\
                was deleted successfully!')
    else:
        messages.error(request, 'Group to delete was not found!')

    return redirect(reverse('list_groups'))


def logout(request):
    """
    Log out user.

    **Template**

    :template:`login.html`
    """
    auth.logout(request)
    return redirect("/Users/login")


def page_not_found_view(request, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Page not found 404 page

    **Template**

    :template:`404.html`
    """
    return render(request, '404.html', status=404)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def get_org_vdcs(request, api=True):
    """
    Retrieves a list of organization virtual data centers (OrgVdcs) and their relevant information.
    This function is accessed through a GET request.

    Returns:
        Response: The HTTP response object containing the retrieved organization virtual data centers (OrgVdcs).
    """
    org_vdc_objs = OrgVdcs.objects.all()
    provider_vdc_objs = ProviderVdcs.objects.all().values()

    if not org_vdc_objs:
        msg = "No OrgVDC Found. Please check with administrator"
        return HttpResponseNotFound(msg)

    if not provider_vdc_objs:
        msg = "No Provider VDC Found. Please check with adminstrator"
        return HttpResponseNotFound(msg)

    org_vdcs = [{
        'name': org.name,
        'org_vdc_id': org.org_vdc_id,
        'running_tb_limit': org.running_tb_limit,
        'stored_tb_limit': org.stored_tb_limit,
        'provider_vdc_name': org.provider_vdc_obj.name if org.provider_vdc_obj else None,
        'mig_ra': org.mig_ra_obj.name if org.mig_ra_obj else None,
        'vcenter': org.vcenter,
        'cpu_limit': org.cpu_limit,
        'memory_limit': org.memory_limit,
        'created': org.created,
    } for org in org_vdc_objs]

    provider_vdcs = [{
        'id': provider_vdc['id'],
        'name': provider_vdc['name'],
        'vdc_id': provider_vdc['vdc_id'],
        'new_quota_system': provider_vdc['new_quota_system'],
        'cpu_multiplier': provider_vdc['cpu_multiplier'],
        'memory_multiplier': provider_vdc['memory_multiplier'],
        'available_cpus': provider_vdc['available_cpus'],
        'available_memory_gb': provider_vdc['available_memory_gb'],
    } for provider_vdc in provider_vdc_objs]

    response_data = {
        'org_vdcs': org_vdcs,
        'provider_vdcs': provider_vdcs,
    }

    return Response(response_data)


@require_http_methods(['GET'])
@login_required(login_url='user_login')
def get_catalogs(request, api=True):
    """
    Retrieves a list of catalogs and their relevant information. This function is accessed through a GET request.

    Returns:
        Response: The HTTP response object containing the retrieved catalogs.
    """
    catalogs_db = Catalogs.objects.all().values(
        "name", "org_obj__vcd_id", 'vcd_id', 'user', 'allowed_templates')

    return Response(catalogs_db)

@login_required(login_url='user_login')
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def provider_vdc_index(request):
    provider_vdc_queryset = ProviderVdcs.objects.all()
    provider_vdc_data = []

    for provider_vdc in provider_vdc_queryset:
        provider_vdc.resulting_cpus = provider_vdc.available_cpus * provider_vdc.cpu_multiplier
        provider_vdc.resulting_memory_gb = provider_vdc.available_memory_gb * provider_vdc.memory_multiplier
        provider_vdc_data.append(provider_vdc)

    context = {'provider_vdc_data': provider_vdc_data}
    return render(request, 'ProviderVDC/provider_vdc.html', context)

@login_required(login_url='user_login')
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def edit_provider_vdc(request, provider_vdc_id):
    provider_vdc = get_object_or_404(ProviderVdcs, id=provider_vdc_id)

    context = {
        'provider_vdc': provider_vdc,
        'cluster_name': provider_vdc.name,
    }
    return render(request, 'ProviderVDC/edit_provider_vdc.html', context)

@login_required(login_url='user_login')
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def save_provider_vdc(request):
    if request.method == 'POST':
        cluster_name = request.POST.get('cluster_name')
        provider_vdc = get_object_or_404(ProviderVdcs, name=cluster_name)

        provider_vdc.new_quota_system = bool(int(request.POST.get('new_quota_system', 0)))
        provider_vdc.cpu_multiplier = float(request.POST.get('cpu_multiplier', 1.0))
        provider_vdc.memory_multiplier = float(request.POST.get('memory_multiplier', 1.0))

        provider_vdc.save()

    return redirect('ProviderVdcs')
