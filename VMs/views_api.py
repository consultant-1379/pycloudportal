import logging
import socket
import atexit
import ssl
import xml.etree.ElementTree as ET

from django.http import HttpResponseBadRequest, HttpResponse
from django.views.decorators.http import require_http_methods

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl
from pyvcloud.vcd.client import ResourceType
from pyvcloud_project.utils import pyvcloud_utils as utils
from pyvcloud_project.utils import vm_utils
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.models import OrgVdcs, Vms, Vapps
from . import views

logger = logging.getLogger(__name__)

"""
""API View
- This API view respond to HTTP requests (GET Default) containing a JSON-formatted response.

**Authentication**

This API view requires authentication via session authentication or basic authentication.
- Session authentication: Uses the Django session framework for authentication. (Active session or not)
- Basic authentication: Uses a username and password to authenticate the user. (HTTP Basic authentication)

**Permissions**
- IsAuthenticated: Checks whether the user is authenticated (logged in) before allowing access to the view.

"""


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def get_vms(request, vapp_vcd_id):
    logger.info("Rest-Call Received: Getting VM's of Vapp With VCD_ID {}"
                .format(vapp_vcd_id))
    response = views.get_vms(request, vapp_vcd_id, api=True)
    if isinstance(response, HttpResponseBadRequest):
        message = {'message': 'Error {}'.format(str(response.content))}
        return Response(message, status=response.status_code)
    else:
        return Response({'message': 'VM\'s Retuned Successfully',
                         'VM_Details': response.data},
                        status=response.status_code)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def get_vms_xml(request, vapp_vcd_id):
    logger.info(
        f"LMI Request: XML Data return for getting VM's of a vApp {vapp_vcd_id}")

    response = views.get_vms(request, vapp_vcd_id, api=True)

    if isinstance(response, HttpResponseBadRequest):
        message = {'message': 'Error {}'.format(str(response.content))}
        return Response(message, status=response.status_code)

    # Create the root XML element
    root = ET.Element("response")

    for vm in response.data:
        # Create the VMs element
        vms_element = ET.SubElement(root, "vms")
        # Add the VM attributes
        ET.SubElement(vms_element, "name").text = vm["name"]
        ET.SubElement(vms_element, "status").text = vm["status"]
        ET.SubElement(vms_element, "vm_id").text = "urn:vcloud:vm:" + vm["id"]
        ET.SubElement(vms_element, "cpu_count").text = str(
            vm["number_of_cpus"])
        ET.SubElement(vms_element, "memory_mb").text = str(vm["memory_mb"])
        ET.SubElement(vms_element, "busy").text = str(vm["busy"])
        ET.SubElement(vms_element, "committed_storage").text = str(
            vm["committed_storage"])
        ET.SubElement(vms_element, "provisioned_storage").text = str(
            vm["provisioned_storage"])
        ET.SubElement(vms_element, "vsphere_name").text = vm["vsphere_name"]
        ET.SubElement(vms_element, "hostname").text = vm["hostname"]

    # Convert the XML tree to a string
    xml_string = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    return HttpResponse(xml_string, content_type="application/xml")


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def get_vms_from_template(request, template_id):
    logger.info(
        "Rest-Call Received: Getting VM's of template With template ID {}".format(template_id))
    return _get_vms_from_template(request, template_id, response_format='json')


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def get_vms_from_template_xml(request, template_id):
    logger.info(
        f"LMI Request: XML Data return for getting VM's of a vApp {template_id}")
    return _get_vms_from_template(request, template_id, response_format='xml')


def _get_vms_from_template(request, template_id, response_format='json'):
    client = VMWareClientSingleton().client
    qfilter = f"isExpired==false;container=={template_id}"
    fields = "name,status,numberOfCpus,memoryMB,vdc,containerName"
    resource_type = ResourceType.ADMIN_VM.value
    templates = utils.send_typed_query(client, resource_type, fields, qfilter)

    if not templates:
        msg = f"VM's not found for the given Vapp template ID {template_id}"
        return Response({'message': msg}, status=status.HTTP_400_BAD_REQUEST)

    vm_data = []
    for vm_in_template in templates:
        vm_id = 'urn:vcloud:vm:' + vm_in_template.get("href").split("vm-")[-1]

        vm_data.append({
            "vm_id": vm_id,
            "name": vm_in_template.get("name"),
            "status": vm_in_template.get("status"),
            "cpu_count": vm_in_template.get("numberOfCpus"),
            "memory_mb": vm_in_template.get("memoryMB")
        })

    if response_format == 'json':
        return Response({'message': 'VM\'s Returned Successfully', 'VM_Details': vm_data})
    elif response_format == 'xml':
        # Create the root XML element
        root = ET.Element('response')

        for vm_info in vm_data:
            vm_element = ET.SubElement(root, 'vms')
            ET.SubElement(vm_element, 'name').text = vm_info["name"]
            ET.SubElement(vm_element, 'status').text = vm_info["status"]
            ET.SubElement(vm_element, 'vm_id').text = vm_info["vm_id"]
            ET.SubElement(vm_element, 'cpu_count').text = vm_info["cpu_count"]
            ET.SubElement(vm_element, 'memory_mb').text = vm_info["memory_mb"]

        xml_data = ET.tostring(root, encoding='UTF-8', xml_declaration=True)
        return HttpResponse(xml_data, content_type='application/xml')


@api_view(['GET'])
def poweron_vm(request, vm_name):
    try:
        logger.info(f"Request: Powering on VM's of a vApp {vm_name}")
        vm_name = vm_name.split(".xml")[0]
        if 'master_' not in vm_name:
            vm_name = 'master_' + vm_name

        # Extract client IP address
        client_ip_address = vm_utils.get_client_ip(request)

        client_hostname, _, _ = socket.gethostbyaddr(client_ip_address)
        logger.info(f"Client IP Address for {vm_name} is {client_ip_address}")
        hostname = client_hostname.split('.')[0]
        logger.info(f"Hostname for {vm_name} vApp is {hostname}")

        vapp = Vapps.objects.filter(vts_name=hostname).first()

        if vapp:
            logger.info(f"Found matching Vapps object: {vapp.name}")
            logger.info(f"Querying for VM: vapp={vapp}, vm_name={vm_name}")
            vm = Vms.objects.filter(vapp_obj=vapp, name=vm_name).first()

            if vm:
                vapp_id = vapp.vcd_id
                vm_id = vm.vcd_id
                vm_utils.poweron_vm_api(request, vapp_id, vm_id, vm_name)
                return Response({'message': 'VM Powered on Successfully'}, status=200)
            else:
                return HttpResponseBadRequest({'message': 'VM not found'}, status=404)

    except socket.herror as e:
        error_msg = f"Error: Unable to resolve hostname for IP {client_ip_address}: {e}"
        logger.error(error_msg)
        return HttpResponseBadRequest({'message': error_msg}, status=400)

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(error_msg)
        return HttpResponseBadRequest({'message': error_msg}, status=400)


@api_view(['GET'])
def poweroff_vm(request, vm_name):
    try:
        logger.info(f"Request: Powering off VM of a vApp {vm_name}")
        vm_name = vm_name.split(".xml")[0]
        if 'master_' not in vm_name:
            vm_name = 'master_' + vm_name

        # Extract client IP address
        client_ip_address = vm_utils.get_client_ip(request)

        client_hostname, _, _ = socket.gethostbyaddr(client_ip_address)
        logger.info(f"Client IP Address for {vm_name} is {client_ip_address}")
        hostname = client_hostname.split('.')[0]
        logger.info(f"Hostname for {vm_name} vApp is {hostname}")

        vapp = Vapps.objects.filter(vts_name=hostname).first()

        if vapp:
            logger.info(f"Found matching Vapps object: {vapp.name}")
            logger.info(f"Querying for VM: vapp={vapp}, vm_name={vm_name}")
            vm = Vms.objects.filter(vapp_obj=vapp, name=vm_name).first()

            if not vm:
                logger.warning(f"No VM found for {vm_name} in vApp {vapp.name}")
                return Response({'message': f'No VM found for {vm_name} in vApp {vapp.name}'}, status=404)

            vapp_id = vapp.vcd_id
            vm_id = vm.vcd_id
            vm_utils.poweroff_vm_api(request, vapp_id, vm_id, vm_name)
            return Response({'message': 'VM Powered off Successfully'}, status=200)

    except socket.herror as e:
        error_msg = f"Error: Unable to resolve hostname for IP {client_ip_address}: {e}"
        logger.error(error_msg)
        return HttpResponseBadRequest({'message': error_msg}, status=400)

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(error_msg)
        return HttpResponseBadRequest({'message': error_msg}, status=400)

@api_view(['GET'])
def reset_vm(request, vm_name):
    try:
        logger.info(f"Request: Resetting {vm_name}")
        vm_name = vm_name.split(".xml")[0]

        # Extract client IP address
        client_ip_address = vm_utils.get_client_ip(request)

        client_hostname, _, _ = socket.gethostbyaddr(client_ip_address)
        logger.info(f"Client IP Address for {vm_name} is {client_ip_address}")
        hostname = client_hostname.split('.')[0]
        logger.info(f"Hostname for {vm_name} vApp is {hostname}")

        vapp = Vapps.objects.filter(vts_name=hostname).first()

        if vapp:
            logger.info(f"Found matching Vapps object: {vapp.name}")
            logger.info(f"Querying for VM: vapp={vapp}, vm_name={vm_name}")
            vm = Vms.objects.filter(vapp_obj=vapp, name=vm_name).first()

            if not vm:
                logger.warning(f"No VM found for {vm_name} in vApp {vapp.name}")
                return Response({'message': f'No VM found for {vm_name} in vApp {vapp.name}'}, status=404)

            vapp_id = vapp.vcd_id
            vm_id = vm.vcd_id
            vm_utils.reboot_vm_api(request, vapp_id, vm_id, vm_name)
            return Response({'message': 'VM reset Successfully'}, status=200)

    except socket.herror as e:
        error_msg = f"Error: Unable to resolve hostname for IP {client_ip_address}: {e}"
        logger.error(error_msg)
        return HttpResponseBadRequest({'message': error_msg}, status=400)

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(error_msg)
        return HttpResponseBadRequest({'message': error_msg}, status=400)

@api_view(['GET'])
def change_boot_order(request, boot_device, vm_name):
    """
    Change the boot order for a given VM.

    Args:
        request: Django REST framework request object.
        boot_device: Boot device type ("net" or "hd").
        vm_name: Name of the VM.

    Returns:
        Response: Django REST framework response object.
    """
    if 'master_' not in vm_name:
        vm_name = 'master_' + vm_name

    vm_name = vm_name.split(".xml")[0]
    client_ip_address = vm_utils.get_client_ip(request)
    client = VMWareClientSingleton().client
    admin_href = client.get_admin().get('href')
    system = utils.get_system(client, admin_href=admin_href)
    provider_vdcs = system.list_provider_vdcs()
    all_org_vdcs_db = OrgVdcs.objects.all()
    org_vdcs_from_vmware = []

    try:
        si = None
        try:
            # Create an SSL context that ignores SSL certificate verification
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            ssl_context.verify_mode = ssl.CERT_NONE
            logging.info("Trying to connect to VCENTER SERVER . . .")
            si = SmartConnect(host='atpoda1-vcen1.athtem.eei.ericsson.se', user='administrator@vsphere.local', pwd='VMware1!', sslContext=ssl_context)
        except IOError as e:
            pass
            atexit.register(Disconnect, si)

        logging.info("Connected to VCENTER SERVER !")
        content = si.RetrieveContent()

        vm = vm_utils.find_vm_by_ip(content, client_ip_address)

        # Check if vm is not None before proceeding
        if vm is None:
            return Response({'message': 'VM not found for IP address ' + client_ip_address}, status=404)

        parent = vm.parent
        cloudms = None
        children = []
        for child in parent.childEntity:
            logging.info(child.name)
            child_name = vm_utils.trim_vm_name(child.name)
            children.append(child_name)
            if child_name == vm_name:
                cloudms = child

        logging.info(cloudms)
        logging.info(children)

        if cloudms is None:
            logging.info("Could not find the VM!")
        else:
            logging.info("Found VM: %s", cloudms.name)

        if cloudms is None:
            return Response({'message': 'MS not found'}, status=404)

        # Defining the boot order
        if boot_device == "net":
            boot_order = [
                vim.vm.BootOptions.BootableEthernetDevice(deviceKey=4000),
                vim.vm.BootOptions.BootableDiskDevice(deviceKey=2000)
            ]
        elif boot_device == "hd":
            boot_order = [
                vim.vm.BootOptions.BootableDiskDevice(deviceKey=2000),
                vim.vm.BootOptions.BootableEthernetDevice(deviceKey=4000)
            ]
        else:
            return Response({'message': f'VM Boot Device {boot_device} Not Supported'}, status=400)

        config_spec = vim.vm.ConfigSpec()
        config_spec.bootOptions = vim.vm.BootOptions(bootOrder=boot_order)

        cloudms.ReconfigVM_Task(config_spec)
        atexit.register(lambda: SmartConnect.Disconnect(si))
        return Response({'message': f'VM Boot Order Changed to {boot_device} Successfully'}, status=200)

    except vmodl.MethodFault as e:
        logging.error("Caught vmodl fault: %s", e.msg)
        return Response({'message': 'An error occurred'}, status=500)
    except Exception as e:
        logging.error("Caught exception: %s", str(e))
        return Response({'message': 'An error occurred'}, status=500)