"""
Module containing utility functions for working with catalogs in vCloud Director.

"""

import logging
import os
import shutil
from datetime import datetime
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.exceptions import BadRequestException
from pyvcloud.vcd.client import ResourceType
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.utils import org_utils, pyvcloud_utils as utils
from pyvcloud_project.models import Catalogs, Orgs as OrgModel

logger = logging.getLogger(__name__)


def import_catalog():
    """
    Import catalogs from vCloud Director into the database.
    """
    client = VMWareClientSingleton().client
    orgs = client.get_org_list()
    vcloud_catalog_ids = set()
    for org in orgs:
        org_id = org.get('id')
        org_href = org.get('href')
        org_obj = Org(client, org_href)
        org_catalogs = org_obj.list_catalogs()
        org_name = org_catalogs[0]['orgName'] if org_catalogs else None
        for catalog in org_catalogs:
            catalog_name = catalog['name']
            catalog_id = catalog['id']
            vcloud_catalog_ids.add(catalog_id)
            org_queryset = OrgModel.objects.filter(
                vcd_id=org_id, name=org_name)
            if org_queryset.exists():
                for org in org_queryset:
                    # Process each org object individually
                    Catalogs.objects.update_or_create(
                        vcd_id=catalog_id,
                        defaults={
                            'name': catalog_name,
                            'org_obj': org
                        }
                    )
            else:
                logger.info(
                    f'Import_Catalog_Error: Org with name {org_name} and id {org_id} is not found in the database'
                )

    Catalogs.objects.exclude(vcd_id__in=vcloud_catalog_ids).delete()
    return "Catalogs have been imported"


def upload_iso_file(iso_file, catalog_name, org_name):
    """
    Upload an ISO file to a catalog.
    """
    directory = '/srv/isodiskmount/isodir'
    client = VMWareClientSingleton().client
    org_href = client.get_org_by_name(org_name).get('href')
    org = org_utils.get_org(client, href=org_href)
    date_time = str(datetime.now().microsecond)
    os.makedirs(name=directory + date_time, mode=0o755, exist_ok=True)
    cwd = os.getcwd()
    os.chdir(directory + date_time)

    with open(iso_file.name, 'wb') as output_file:
        for chunk in iso_file:
            output_file.write(chunk)
    try:
        org.upload_media(catalog_name=catalog_name, file_name=iso_file.name)
    except BadRequestException:
        shutil.rmtree(path=directory + date_time)
        return 40, f'Catalog item name {iso_file.name} is not unique within the catalog'
    finally:
        os.chdir(cwd)

    return 25, f'Media {iso_file.name} was uploaded to catalog {catalog_name} successfully'


def get_media_from_catalog(catalog_name, context):
    """
    Get a list of media items from a catalog.
    """
    client = VMWareClientSingleton().client
    context['media'] = []
    resource_type = ResourceType.MEDIA.value
    fields = "name,status,creationDate,storageB"
    qfilter = f"catalogName=={catalog_name}"
    all_media = utils.send_typed_query(client, resource_type, fields, qfilter)
    for media in all_media:
        context['media'].append(
            {
                'href': media.get('href'),
                'media_name': media.get('name'),
                'status': media.get('status'),
                'date_created': media.get('creationDate'),
                'size': round(int(media.get('storageB'))/pow(1024, 2), 2)
            }
        )
