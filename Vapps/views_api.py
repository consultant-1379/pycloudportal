import logging
import xml.etree.ElementTree as ET
from . import views
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponseBadRequest, HttpResponseServerError, HttpResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated

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
def start_vapp(request, vapp_vcd_id, org_vdc_id):
    logger.info(
        "Rest-Call Received: Starting VApp with VCD_ID {} & ORG_VDC_ID {}".format(vapp_vcd_id, org_vdc_id))
    response = views.start_vapp(request, vapp_vcd_id, org_vdc_id, api=True)

    if isinstance(response, HttpResponseBadRequest):
        message = {'message': 'Error {}'.format(str(response.content))}
        return Response(message, status=response.status_code)
    else:
        message = {'message': 'VApp Started Successfully'}
        return Response(message, status=response.status_code)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def start_vapp_xml(request, vapp_vcd_id, org_vdc_id):
    logger.info(
        f"LMI Request: Starting vApp {vapp_vcd_id} in OrgVdc {org_vdc_id}")
    response = views.start_vapp(request, vapp_vcd_id, org_vdc_id, api=True)

    root = ET.Element('response')
    obj_element = ET.SubElement(root, 'obj')

    if isinstance(response, HttpResponseBadRequest):
        obj_element.text = 'Error {}'.format(str(response.content))
        return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), status=400,
                            content_type='application/xml')

    obj_element.text = 'vapp successfully started'
    return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), content_type='application/xml')


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def stop_vapp(request, vapp_vcd_id, org_vdc_id):
    logger.info(
        "Rest-Call Received: Stopping VApp with VCD_ID {} & ORG_VDC_ID {}".format(vapp_vcd_id, org_vdc_id))
    response = views.stop_vapp(request, vapp_vcd_id, org_vdc_id, api=True)
    if isinstance(response, HttpResponseBadRequest):
        message = {'message': 'Error {}'.format(str(response.content))}
        return Response(message, status=response.status_code)
    else:
        message = {'message': 'VApp Stopped Successfully'}
        return Response(message, status=response.status_code)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def stop_vapp_xml(request, vapp_vcd_id, org_vdc_id):
    logger.info(
        f"LMI Request: Stopping vApp {vapp_vcd_id} in OrgVdc {org_vdc_id}")
    response = views.stop_vapp(request, vapp_vcd_id, org_vdc_id, api=True)

    root = ET.Element('response')
    obj_element = ET.SubElement(root, 'obj')

    if isinstance(response, HttpResponseBadRequest):
        obj_element.text = 'Error {}'.format(str(response.content))
        return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), status=400,
                            content_type='application/xml')

    obj_element.text = 'vapp sucessfully stopped'
    return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), content_type='application/xml')


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def delete_vapp(request, vapp_vcd_id):
    logger.info(
        "Rest-Call Received: Deleting VApp with VCD_ID {}".format(vapp_vcd_id))
    response = views.power_off_delete_vapp(request, vapp_vcd_id, api=True)
    if isinstance(response, HttpResponseBadRequest):
        message = {'message': 'Error {}'.format(str(response.content))}
        return Response(message, status=response.status_code)
    else:
        message = {'message': 'VApp Deleted Successfully'}
        return Response(message, status=response.status_code)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def delete_vapp_xml(request, vapp_vcd_id):
    logger.info(
        f"LMI Request: Deleting vApp {vapp_vcd_id}")
    response = views.power_off_delete_vapp(request, vapp_vcd_id, api=True)

    root = ET.Element('response')
    obj_element = ET.SubElement(root, 'obj')

    if isinstance(response, HttpResponseBadRequest):
        obj_element.text = 'Error {}'.format(str(response.content))
        return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), status=400,
                            content_type='application/xml')

    obj_element.text = 'vapp sucessfully deleted'
    return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), content_type='application/xml')


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def poweroff_vapp(request, vapp_vcd_id, org_vdc_id):
    logger.info(
        "Rest-Call Received: Powering Off VApp with VCD_ID {} & ORG_VDC_ID {}".format(vapp_vcd_id, org_vdc_id))
    response = views.poweroff_vapp(request, vapp_vcd_id, org_vdc_id, api=True)
    if isinstance(response, HttpResponseBadRequest):
        message = {'message': 'Error {}'.format(str(response.content))}
        return Response(message, status=response.status_code)
    else:
        message = {'message': 'VApp Powered-Off Successfully'}
        return Response(message, status=response.status_code)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def poweroff_vapp_xml(request, vapp_vcd_id, org_vdc_id):
    logger.info(
        f"LMI Request: Powering Off vApp {vapp_vcd_id} in OrgVDC {org_vdc_id}")
    response = views.poweroff_vapp(request, vapp_vcd_id, org_vdc_id, api=True)

    root = ET.Element('response')
    obj_element = ET.SubElement(root, 'obj')

    if isinstance(response, HttpResponseBadRequest):
        obj_element.text = 'Error {}'.format(str(response.content))
        return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), status=400,
                            content_type='application/xml')

    obj_element.text = 'vapp sucessfully powered-off'
    return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), content_type='application/xml')


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def get_vapps(request, org_vdc_id):
    logger.info(
        "Rest-Call Received: Getting All Vapp's In ORG_VDC_ID {}".format(org_vdc_id))
    response = views.get_vapps(request, org_vdc_id)
    if isinstance(response, HttpResponseBadRequest):
        message = {'message': 'Error {}'.format(str(response.content))}
        return Response(message, status=response.status_code)
    else:
        return Response({'message': 'VApp Details Retrieved Successfully', 'data': response.data}, status=response.status_code)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def get_vapps_xml(request, org_vdc_id):
    logger.info(
        f"LMI Request: Getting vApp's in OrgVDC {org_vdc_id}")
    response = views.get_vapps(request, org_vdc_id)
    if isinstance(response, HttpResponseBadRequest):
        message = {'message': 'Error {}'.format(str(response.content))}
        return Response(message, status=response.status_code)

    vm_elements = ET.Element('response')

    for vapp in response.data:
        vapp_element = ET.SubElement(vm_elements, 'vapps')
        ET.SubElement(vapp_element, 'name').text = vapp['name']
        ET.SubElement(vapp_element, 'status').text = vapp['status']
        ET.SubElement(
            vapp_element, 'creation_date').text = vapp['creation_date'].isoformat()
        ET.SubElement(vapp_element, 'number_of_vms').text = str(
            vapp.get('number_of_vms', ''))
        ET.SubElement(vapp_element, 'vapp_id').text = vapp['vapp_id']
        ET.SubElement(
            vapp_element, 'gateway_hostname').text = vapp['gateway_hostname']
        ET.SubElement(vapp_element, 'gateway_ipaddress').text = vapp.get(
            'gateway_ipaddress', '')
        ET.SubElement(vapp_element, 'owner').text = vapp['owner']
        ET.SubElement(vapp_element, 'shared').text = str(vapp['shared'])
        ET.SubElement(vapp_element, 'busy').text = str(vapp['busy'])

    xml_data = ET.tostring(vm_elements, encoding='UTF-8', xml_declaration=True)
    return HttpResponse(xml_data, content_type='application/xml')


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def get_vapp_status_xml(request, vAppName, org_vdc_id):
    logger.info(
        f"LMI Request: Getting vApp {vAppName} state; 0 -> Free, 1-> Busy")
    response = views.get_vapp_status(
        request, vAppName, org_vdc_id, api=True)

    root = ET.Element('response')
    result_element = ET.SubElement(root, 'result')

    if response.data:
        result_element.text = '1'
        return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), status=response.status_code,
                            content_type='application/xml')

    result_element.text = '0'
    return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), content_type='application/xml')


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def create_vapp_from_template(request):
    vapp_name = request.GET.get('vapp_name')
    power_on = (request.GET.get('power_state', 'off').lower() == 'on')
    vapp_template_id = request.GET.get('vapp_template_id')
    orgvdc_name = request.GET.get('org_vdc_name').replace(' ', '')

    logger.info("Rest-Call Received: Creating VApp {} from template with Template_ID {} and Power state as {} in Cloud {}".format(
        vapp_name, vapp_template_id, power_on, orgvdc_name))
    response = views.create_vapp_from_template(request)

    if isinstance(response, HttpResponseBadRequest):
        message = {'message': 'Error {}'.format(str(response.content))}
        return Response(message, status=response.status_code)
    else:
        return Response({'message': 'VApp Created Successfully', 'Additional_Information': str(response.data)}, status=response.status_code)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def create_vapp_from_template_xml(request):
    vapp_name = request.GET.get('vapp_name')
    power_on = (request.GET.get('power_state', 'off').lower() == 'on')
    vapp_template_id = request.GET.get('vapp_template_id')
    orgvdc_name = request.GET.get('org_vdc_name').replace(' ', '')

    logger.info(
        f"LMI Request: Creating vApp {vapp_name} from template with Template_ID {vapp_template_id} and Power state as {power_on} in Cloud {orgvdc_name}")
    response = views.create_vapp_from_template(request)

    root = ET.Element('response')
    message_element = ET.SubElement(root, 'vapp_details')

    if isinstance(response, HttpResponseBadRequest):
        message_element.text = 'Error {}'.format(str(response.content))
        return HttpResponse(ET.tostring(root, encoding='utf-8', xml_declaration=True), status=400,
                            content_type='application/xml')

    # Access the first dictionary element in the list if 'response.data' is a non-empty list,
    # otherwise assign the value of 'response.data'
    data = response.data[0] if hasattr(response, 'data') and response.data and isinstance(
        response.data, list) else response.data

    ET.SubElement(message_element, 'name').text = data['name']
    ET.SubElement(message_element, 'status').text = data['status']
    ET.SubElement(message_element,
                  'creation_date').text = data['creation_date'].isoformat()
    ET.SubElement(message_element, 'number_of_vms').text = str(
        data.get('number_of_vms', ''))
    ET.SubElement(message_element, 'vapp_id').text = data['vapp_id']

    gateway_details = ET.SubElement(message_element, 'gateway_details')
    ET.SubElement(gateway_details,
                  'gateway_hostname').text = data['gateway_hostname']
    ET.SubElement(gateway_details, 'gateway_ipaddress').text = data.get(
        'gateway_ipaddress', '')

    ET.SubElement(message_element, 'owner').text = data['owner']
    ET.SubElement(message_element, 'shared').text = str(data['shared'])
    ET.SubElement(message_element, 'busy').text = str(data['busy'])

    logger.info(
        f"LMI Request: Create vApp Request Completed. Sending 200 Response")

    return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), content_type='application/xml')


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def stop_and_add_vapp_to_catalog(request):
    vapp_vcd_id = request.GET.get('vapp_vcd_id')
    orgcatalogs = request.GET.get('orgcatalogs')
    new_template_name = request.GET.get('new_template_name')

    logger.info(
        f"LMI Request: Stopping vApp with ID: {vapp_vcd_id} and adding to OrgVDC {orgcatalogs} as {new_template_name}")
    response = views.stop_and_add_vapp_to_catalog(request)

    if isinstance(response, HttpResponseBadRequest):
        message = {'message': 'Error {}'.format(str(response.content))}
        return Response(message, status=response.status_code)
    else:
        return Response({'message': 'VApp Stopped & Added to Catalog Successfully', 'Additional_Information': str(response.data)}, status=response.status_code)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def stop_and_add_vapp_to_catalog_xml(request):
    vapp_vcd_id = request.GET.get('vapp_vcd_id')
    orgcatalogs = request.GET.get('orgcatalogs')
    new_template_name = request.GET.get('new_template_name')

    logger.info("Rest-Call Received: Stopping VApp {} and Adding to Org-Catalog {} with the name {}".format(
        vapp_vcd_id, orgcatalogs, new_template_name))
    response = views.stop_and_add_vapp_to_catalog(request)

    root = ET.Element('response')
    message_element = ET.SubElement(root, 'obj')
    additional_info_element = ET.SubElement(root, 'Additional_Information')

    if isinstance(response, HttpResponseBadRequest):
        message_element.text = 'Error {}'.format(str(response.content))
        return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), status=400,
                            content_type='application/xml')
    else:
        message_element.text = 'vApp Stopped & Added to Catalog Successfully'
        additional_info_element.text = str(
            response.data['Additional_Information'])
        return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), content_type='application/xml')


@api_view(['POST'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def recompose_vapp_xml(request, vapp_vcd_id):
    logger.info("Rest-Call Received: Recomposing vApp with ID {vapp_vcd_id}")

    response = views.recompose_vapp(request, vapp_vcd_id, api=True)

    root = ET.Element('response')
    result_element = ET.SubElement(root, 'result')

    if response.data:
        result_element.text = '1'
        return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), status=response.status_code,
                            content_type='application/xml')

    result_element.text = '0'
    return HttpResponse(ET.tostring(root, encoding='UTF-8', xml_declaration=True), content_type='application/xml')
