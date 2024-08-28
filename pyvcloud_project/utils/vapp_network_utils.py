"""
This module provides utility functions for importing networks from VMware vCloud Director (vCD) to a Django database.

"""
import socket
from typing import List
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM
from pyvcloud.vcd.client import ResourceType, EntityType
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.utils import pyvcloud_utils as utils
from pyvcloud_project.models import Vapps


def import_networks():
    """
    Imports networks from VMware vCD to the Django database.

    This function retrieves the list of organizations from the VMware client and iterates over each organization.
    For each organization, it retrieves the list of vDCs and iterates over each vDC.
    For each vDC, it retrieves the list of vApps and iterates over each vApp.
    For each vApp, it retrieves the vApp ID and the external IP address associated with it.
    It then tries to retrieve the corresponding Vapps object from the Django database.
    If the Vapps object exists, it updates the IP address and VTS name.
    If the Vapps object does not exist, it creates a new entry in the Django database with the vApp ID, IP address, and VTS name.

    Returns:
        str: A message indicating that the vApp networks have been imported.
    """
    client = VMWareClientSingleton().client
    organizations = client.get_org_list()

    for org_res in organizations:
        org = Org(client, resource=org_res)

        for vdc_data in org.list_vdcs():
            vdc_res = org.get_vdc(vdc_data["name"])
            vdc = VDC(client, resource=vdc_res)

            vapps = vdc.list_resources(EntityType.VAPP)
            for vapp_data in vapps:
                vapp_res = vdc.get_vapp(vapp_data["name"])
                vapp_id = vapp_res.get("id")
                vapp_href = vapp_res.get('href')
                ip_address = get_external_ip(client, vapp_href)
                vts_name = get_hostname_from_ip(ip_address)

                try:
                    vapp_obj = Vapps.objects.get(vcd_id=vapp_id)
                except Vapps.DoesNotExist:
                    vapp_obj = None

                if vapp_obj is not None:
                    Vapps.objects.update_or_create(
                        vcd_id=vapp_id,
                        defaults={
                            'ip_address': ip_address,
                            'vts_name': vts_name,
                        }
                    )

    return 'Vapp networks are imported'


def get_hostname_from_ip(ip_address):
    """
    Retrieves the hostname from the given IP address.

    Args:
        ip_address (str): The IP address.

    Returns:
        str: The hostname associated with the IP address, or None if the hostname cannot be retrieved.
    """
    try:
        # Support IPv6 addresses & IPv4 addresses
        result = socket.getnameinfo((ip_address, 80), socket.NI_NOFQDN)
        vts_name = result[0]
    except (socket.gaierror, socket.herror, TypeError) as e:
        vts_name = None
    return vts_name


def get_external_ip(client, vapp_href, gateway_vm_href=None):
    """
    Retrieves the external IP address associated with a vApp.

    Args:
        client: The VMware vCD client.
        vapp_href (str): The vApp href.
        gateway_vm_href (str, optional): The gateway VM href. Defaults to None.

    Returns:
        str: The external IP address associated with the vApp, or None if it cannot be retrieved.
    """
    gateway_vm_res = None
    external_nic = None
    gateway_ip = None

    if not gateway_vm_href:
        vdc_vapp = VApp(client, href=vapp_href)
        for vm_res in vdc_vapp.get_all_vms():
            if 'gateway' in vm_res.get('name'):
                gateway_vm_res = vm_res
                break
        if gateway_vm_res is None:
            return gateway_ip
        gateway_vm_href = gateway_vm_res.get('href')
    vcd_gateway_vm = VM(client, href=gateway_vm_href)
    try:
        gateway_nics = vcd_gateway_vm.list_nics()
        for nic in gateway_nics:
            if nic['primary']:
                external_nic = nic
                break
        if external_nic is None:
            return gateway_ip
        try:
            gateway_ip = external_nic['ip_address']
        except KeyError:
            return None
    except AttributeError:
        gateway_ip = 'error'
        # TODO logging
    return gateway_ip


def get_internal_networks(client, vapp_id: str) -> List:
    """
    Retrieves the list of internal networks associated with a vApp.

    Args:
        client: The VMware vCD client.
        vapp_id (str): The vApp ID.

    Returns:
        List: A list of internal network names.
    """
    qfilter = f'vApp=={vapp_id};isIpScopeInherited==0'
    fields = "name"
    resource_type = ResourceType.ADMIN_VAPP_NETWORK.value
    internal_networks = utils.send_typed_query(
        client, resource_type, fields, qfilter)
    return [name.get('name') for name in internal_networks]


def get_external_networks(client, vapp_id: str) -> List:
    """
    Retrieves the list of external networks associated with a vApp.

    Args:
        client: The VMware vCD client.
        vapp_id (str): The vApp ID.

    Returns:
        List: A list of external network names.
    """
    qfilter = f'vApp=={vapp_id};isIpScopeInherited==1'
    fields = "name"
    resource_type = ResourceType.ADMIN_VAPP_NETWORK.value
    external_networks = utils.send_typed_query(
        client, resource_type, fields, qfilter)
    return [name.get('name') for name in external_networks]
