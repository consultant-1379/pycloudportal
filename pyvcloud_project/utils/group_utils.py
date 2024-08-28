"""
This module contains functions related to group management.
"""
from django.db.models.functions import Lower
from pyvcloud_project.models import Groups, OrgVdcs, Orgs, Catalogs


def add_group(params):
    """
    Adds a new group to the database.

    Returns:
        tuple: A tuple containing the status code and message.
    """
    if not params['group_dn'] or 'CN=PASTEHERE' in params['group_dn']:
        return 40, 'Group name is not valid! Check CN value'
    if not params['org_name'] and not params['orgvdc_name']:
        return 40, 'Orgvdc or Org was not selected!'

    catalogs = Catalogs.objects.filter(
        name__in=params['catalog_permissions']
    ).values_list('vcd_id', flat=True)

    org_vdc = OrgVdcs.objects.get(name=params['orgvdc_name'])
    org = Orgs.objects.get(name=params['org_name'])

    group, created = Groups.objects.get_or_create(
        org_vdc_obj=org_vdc.id,
        org_obj=org.id,
        group_dn=params['group_dn'],
        defaults={
            'org_vdc_obj': org_vdc,
            'read_permission': bool(params['read_permission']),
            'write_permission': bool(params['write_permission']),
            'admin_permission': bool(params['admin_permission']),
            'org_obj': org,
            'unrestricted': ','.join(catalogs),
            'restrict_catalogs': bool(params['cat_restricted']) and bool(catalogs),
        }
    )
    if not created:
        return 40, f"Group for org {params['org_name']} and orgvdc {params['orgvdc_name']} already exist"

    return 25, f"Group for {params.get('orgvdc_name')} and {params.get('org_name')} is created successfully!"


def update_group(params):
    """
    Updates an existing group in the database.

    Returns:
    tuple: A tuple containing the status code and message.
    """
    catalogs = Catalogs.objects.filter(
        name__in=params['catalog_permissions']).values_list('vcd_id', flat=True)
    org_vdc = OrgVdcs.objects.get(name=params['orgvdc_name'])
    org = Orgs.objects.get(name=params['org_name'])

    Groups.objects.filter(pk=params['pk']).update(
        group_dn=params['group_dn'],
        org_vdc_obj=org_vdc,
        read_permission=bool(params['read_permission']),
        write_permission=bool(params['write_permission']),
        admin_permission=bool(params['admin_permission']),
        org_obj=org,
        unrestricted=','.join(catalogs),
        restrict_catalogs=bool(params['cat_restricted'] and catalogs)
    )

    return 25, f"Group for {params.get('orgvdc_name')} and {params.get('org_name')} is updated successfully!"


def get_group_form_values(context, request_type='', group_id=''):
    """
    Retrieves the form values for group management.

    Returns:
        tuple: A tuple containing the updated context, status code, and message.
    """
    message = ''
    if request_type == 'edit':
        try:
            group = Groups.objects.get(pk=group_id)
            context['group_id'] = group_id
            context['ldap_group'] = group
            context['org_vdc_obj'] = str(group.org_vdc_obj)
            context['org_obj'] = str(group.org_obj)
            context['restricted_catalogs'] = group.unrestricted.split(',')
            context['read_permission'] = 'checked=""' if group.read_permission else ""
            context['write_permission'] = 'checked=""' if group.write_permission else ""
            context['admin_permission'] = 'checked=""' if group.admin_permission else ""
            context['catalog_permission'] = 'checked=""' if group.restrict_catalogs else ""
        except Groups.DoesNotExist:
            print(f'Group with id {group_id} not found')
            message = f'Group with id {group_id} not found'
            return context, 40, message

    org_vdcs = OrgVdcs.objects.all().order_by(Lower('name')).values('name')
    orgs = Orgs.objects.all().order_by(Lower('name')).values('name')
    catalogs = Catalogs.objects.all().distinct().order_by(
        Lower('name')).values('name', 'vcd_id')

    context['org_vdcs'] = org_vdcs
    context['orgs'] = orgs
    context['catalogs'] = catalogs

    return context, 25, message
