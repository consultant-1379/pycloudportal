"""
Module: pvdc_utils
Description: Utility functions for working with PVDCs (Provider Virtual Data Centers).
"""

from lxml import etree
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.pvdc import PVDC
from pyvcloud.vcd.exceptions import InvalidParameterException
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.utils import pyvcloud_utils as utils
from pyvcloud_project.models import OrgVdcs, ProviderVdcs, MigRas


def import_pvdc():
    """
    Import PVDCs from vCloud Director.
    Returns:
        str: A message indicating the status of the import process.
    """
    client = VMWareClientSingleton().client
    admin_href = client.get_admin().get('href')
    admin_resource = client.get_resource(admin_href)
    platform = Platform(client)
    system = utils.get_system(client, admin_href, admin_resource)
    provider_vdcs = system.list_provider_vdcs()

    pvdc_ids = []
    for vdc in provider_vdcs:
        href = vdc.get('href')
        index = href.find('providervdc')
        href = href[:index] + 'extension/' + href[index:]
        pvdc = get_pvdc(client, href=href)
        if pvdc is not None:
            process_xml(pvdc, platform, pvdc_ids)

    filter_db(pvdc_ids)
    return 'PVDCs are imported'


def get_pvdc(client: Client, href):
    """
    Get a PVDC object from the vCloud Director.
    Args:
        client (Client): The vCloud Director client.
        href (str): The href of the PVDC.
    Returns:
        PVDC: The PVDC object.
    """
    pvdc = None
    try:
        pvdc = PVDC(client, href=href)
    except InvalidParameterException as error:
        print(f'method:get_pvdc()\n {error}')
    return pvdc


def get_root_element(pvdc_resource):
    """
    Get the root element from the PVDC resource.
    Args:
        pvdc_resource: The PVDC resource.
    Returns:
        Element: The root element of the PVDC resource.
    """
    tree = etree.ElementTree(etree.fromstring(etree.tostring(
        pvdc_resource, encoding='unicode')))
    return tree.getroot()


def process_xml(pvdc, platform: Platform, pvdc_ids: list):
    """
    Process the XML data of a PVDC and update the database.
    Args:
        pvdc: The PVDC object.
        platform (Platform): The vCloud Director platform object.
        pvdc_ids (list): A list to store the PVDC IDs.
    """
    pvdc_resources = pvdc.get_resource()
    host_references = pvdc_resources.HostReferences
    root = get_root_element(pvdc_resources)
    cpu_total = 0
    mem_total = 0
    pvdc_ids.append(pvdc_resources.get('id'))
    for host_ref in host_references.HostReference:
        host = platform.get_host(host_ref.get('name'))
        cpu_total += int(host.NumOfCpusLogical)
        mem_total += int(host.MemTotal)

    ProviderVdcs.objects.update_or_create(
        vdc_id=pvdc_resources.get('id'),
        defaults={
            'name': pvdc_resources.get('name'),
            'new_quota_system': bool(MigRas.objects.filter(name='ENM').exists()),
            'description': pvdc_resources.get('Description') if 'Description' in root.attrib else '',
            'available_cpus': cpu_total,
            'available_memory_gb': mem_total / 1024
        }
    )


def filter_db(pvdc_ids: list):
    """
    Filter the database and remove PVDCs that are not in the provided list.
    Args:
        pvdc_ids (list): A list of PVDC IDs.
    """
    pvdcs = ProviderVdcs.objects.all()
    for pvdc in pvdcs:
        if pvdc.vdc_id not in pvdc_ids:
            OrgVdcs.objects.filter(provider_vdc_obj=pvdc).delete()
            pvdc.delete()
