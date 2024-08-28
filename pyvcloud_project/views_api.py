"""
This module contains API views for retrieving information from VMware Cloud Director.
"""

import logging
from django.http import HttpResponseBadRequest, HttpResponse
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from . import views
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def get_org_vdcs(request):
    """
    Retrieves info on all org VDCs from VMware Cloud Director.

    Parameters: None

    Returns:
        A list of dictionaries representing the org VDCs present from Director.
    """
    logger.info("Rest Call Received: Retrieving ORG_VDC Info")
    response = views.get_org_vdcs(request, api=True)

    if isinstance(response, HttpResponseBadRequest):
        message = {'message': f'Error {response.content}'}
        return Response(message, status=response.status_code)

    return Response({'message': 'Org VDCs retrieved successfully',
                     'org_vdcs': response.data['org_vdcs'],
                     'provider_vdcs': response.data['provider_vdcs']}, response.status_code)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def get_org_vdcs_xml(request):
    """
    Retrieves info on all org VDCs from VMware Cloud Director

    Parameters: None

    Returns:
        A list of dictionaries representing the org VDCs present from Director in XML
    """
    logging.info("LMI Request: XML Data return for Retrieving OrgVDC Info")
    response = views.get_org_vdcs(request, api=True)

    if isinstance(response, HttpResponseBadRequest):
        message = {'message': f'Error {response.content}'}
        return Response(message, status=response.status_code)

    # Create the root element for the XML response
    root = ET.Element('response')

    # Create the parent element for the org_vdcs
    db_orgvdcs = ET.SubElement(root, 'db_orgvdcs')

    # Retrieve the data from the response
    response_data = response.data

    # Create a dictionary to store provider_vdcs by provider_vdc_obj
    provider_vdcs_dict = {
        provider_vdc['name']: provider_vdc for provider_vdc in response_data['provider_vdcs']}

    # Process the org_vdcs data
    for item in response_data['org_vdcs']:
        org_vdc = ET.SubElement(db_orgvdcs, 'OrgVdc')

        ET.SubElement(org_vdc, 'name').text = item['name']
        ET.SubElement(org_vdc, 'running_tb_limit').text = str(
            item['running_tb_limit'])
        ET.SubElement(org_vdc, 'stored_tb_limit').text = str(
            item['stored_tb_limit'])
        ET.SubElement(org_vdc, 'cpu_limit').text = str(item['cpu_limit'])
        ET.SubElement(org_vdc, 'memory_limit').text = str(item['memory_limit'])
        ET.SubElement(org_vdc, 'vcd_id').text = item['org_vdc_id']

        provider_vdc_obj = item['provider_vdc_name']
        if provider_vdc_obj in provider_vdcs_dict:
            provider_vdc = provider_vdcs_dict[provider_vdc_obj]
            provider_vdc_element = ET.SubElement(db_orgvdcs, 'ProviderVdc')

            ET.SubElement(provider_vdc_element,
                          'name').text = provider_vdc['name']
            ET.SubElement(provider_vdc_element,
                          'vdc_id').text = provider_vdc['vdc_id']
            ET.SubElement(provider_vdc_element, 'new_quota_system').text = str(
                provider_vdc['new_quota_system'])
            ET.SubElement(provider_vdc_element, 'cpu_multiplier').text = str(
                provider_vdc['cpu_multiplier'])
            ET.SubElement(provider_vdc_element, 'memory_multiplier').text = str(
                provider_vdc['memory_multiplier'])
            ET.SubElement(provider_vdc_element, 'available_cpus').text = str(
                provider_vdc['available_cpus'])
            ET.SubElement(provider_vdc_element, 'available_memory_gb').text = str(
                provider_vdc['available_memory_gb'])

        mig_ra = item['mig_ra']
        if mig_ra is not None:
            mig_ra_element = ET.SubElement(db_orgvdcs, 'MigRa')
            ET.SubElement(mig_ra_element, 'name').text = mig_ra
        else:
            mig_ra_element = ET.SubElement(db_orgvdcs, 'MigRa')
            ET.SubElement(mig_ra_element, 'name')

    # Generate the XML response
    xml_response = ET.tostring(root, encoding='UTF-8', xml_declaration=True)

    # Return the XML response
    return HttpResponse(xml_response, content_type='application/xml')


@ api_view(['GET'])
@ authentication_classes([SessionAuthentication, BasicAuthentication])
@ permission_classes([IsAuthenticated])
def get_catalogs(request):
    """
    Retrieves info on all catalogs from VMware Cloud Director.

    Parameters: None

    Returns:
        A list of dictionaries representing the catalogs present from Director.
    """
    logger.info("Rest Call Received: Retrieving Catalogs Info")
    response = views.get_catalogs(request, api=True)

    if isinstance(response, HttpResponseBadRequest):
        message = {'message': f'Error {response.content}'}
        return Response(message, status=response.status_code)

    return Response({'message': 'Catalogs retrieved successfully',
                     'data': response.data}, response.status_code)


@ api_view(['GET'])
@ authentication_classes([SessionAuthentication, BasicAuthentication])
@ permission_classes([IsAuthenticated])
def get_catalogs_xml(request):
    """
    Retrieves info on all catalogs from VMware Cloud Director.

    Parameters: None

    Returns:
        A list of dictionaries representing the catalogs present from Director.
    """
    logging.info("LMI Request: XML Data return for Retrieving Catalogs Info")
    response = views.get_catalogs(request, api=True)

    if isinstance(response, HttpResponseBadRequest):
        message = {'message': f'Error {response.content}'}
        return Response(message, status=response.status_code)

    # Create the root element for the XML response
    root = ET.Element('response')

    # Create the parent element for the catalogs
    catalogs_element = ET.SubElement(root, 'catalogs')

    # Retrieve the data from the response
    catalogs_data = response.data

    # Process each catalog in the data
    for catalog in catalogs_data:
        catalog_element = ET.SubElement(catalogs_element, 'Catalog')

        ET.SubElement(catalog_element, 'id').text = '0'
        ET.SubElement(catalog_element, 'name').text = catalog.get('name', '')
        ET.SubElement(catalog_element, 'vcd_id').text = catalog['vcd_id']
        ET.SubElement(catalog_element,
                      'org_id').text = catalog['org_obj__vcd_id']
        ET.SubElement(catalog_element,
                      'user_id').text = catalog.get('user', '')

    # Generate the XML response
    xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n' + \
        ET.tostring(root, encoding='UTF-8', method='xml').decode()

    # Return the XML response
    return HttpResponse(xml_response, content_type='application/xml')


@ api_view(['GET'])
@ authentication_classes([SessionAuthentication, BasicAuthentication])
@ permission_classes([IsAuthenticated])
def get_templates_from_catalog(request, catalog_name):
    """
    Retrieves all templates from a catalog from VMware Cloud Director.

    Parameters:
        - catalog_name: The name of the catalog.

    Returns:
        A list of dictionaries containing all templates in the given catalog.
    """
    logger.info(
        "Rest Call Received: Retrieving Templates from Catalog %s", catalog_name)
    response = views.vapp_templates(request, catalog_name, None, api=True)

    if isinstance(response, HttpResponseBadRequest):
        message = {'message': f'Error {response.content}'}
        return Response(message, status=response.status_code)

    message = {
        'message': f'All templates from Catalog {catalog_name} retrieved successfully',
        'vapp_templates': response.data
    }
    return Response(message, response.status_code)


@ api_view(['GET'])
@ authentication_classes([SessionAuthentication, BasicAuthentication])
@ permission_classes([IsAuthenticated])
def get_templates_from_catalog_xml(request, catalog_name):
    """
    Retrieves all templates from a catalog from VMware Cloud Director.

    Parameters:
        - catalog_name: The name of the catalog.

    Returns:
        A list of dictionaries containing all templates in the given catalog.
    """
    logging.info(
        "LMI Request: XML Data return for Retrieving Templates from Catalog")
    response = views.vapp_templates(request, catalog_name, None, api=True)

    if isinstance(response, HttpResponseBadRequest):
        message = {'message': f'Error {response.content}'}
        return Response(message, status=response.status_code)

    # Construct the XML structure
    root = ET.Element('response')

    for template in response.data:
        templates_element = ET.SubElement(root, 'vapptemplates')
        ET.SubElement(templates_element,
                      'vapptemplate_name').text = template['name']
        ET.SubElement(templates_element, 'status').text = template['status']
        ET.SubElement(templates_element,
                      'creation_date').text = template['creationDate']
        ET.SubElement(templates_element,
                      'vapptemplate_id').text = 'urn:vcloud:vapptemplate:' + template['id']

    # Generate the XML response
    xml_string = ET.tostring(root, encoding='UTF-8')
    xml_response = b'<?xml version="1.0" encoding="UTF-8"?>' + xml_string

    return HttpResponse(xml_response, content_type='application/xml')
