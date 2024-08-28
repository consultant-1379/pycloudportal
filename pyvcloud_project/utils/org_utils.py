"""
This module provides utility functions related to organizations in the vCloud Director.

"""

from pyvcloud.vcd.org import Org
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import InvalidParameterException
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.models import Orgs, Catalogs


def import_orgs():
    """
    Imports organizations from vCloud Director and updates the Orgs model in the database.

    Returns:
        str: A message indicating the successful import of organizations.
    """
    client = VMWareClientSingleton().client
    organizations = client.get_org_list()
    org_ids = []
    for org in organizations:
        org_ids.append(org.get('id'))
        Orgs.objects.update_or_create(
            vcd_id=org.get('id'),
            href=org.get('href'),
            defaults={
                'name': org.FullName,
                'description': org.Description,
            }
        )

    filter_db(org_ids)
    return 'Organizations are imported'


def get_org(client: Client, href=None, resource=None):
    """
    Retrieves an organization from the vCloud Director using the provided client, href, or resource.

    Returns:
        Org: The organization object.
    """
    org = None
    try:
        org = Org(client, href=href, resource=resource)
    except InvalidParameterException as error:
        print(f'method:get_org()\n {error}')
    return org


def filter_db(org_ids: list):
    """
    Filters the Orgs model in the database and deletes organizations that are not in the provided list of org_ids.

    Returns:
        None
    """
    orgs = Orgs.objects.all()
    for org in orgs:
        if org.vcd_id not in org_ids:
            Catalogs.objects.filter(org_obj=org).delete()
            org.delete()
