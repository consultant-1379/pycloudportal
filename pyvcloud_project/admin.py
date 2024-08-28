"""
This module handles the administration interface for Django.
"""

from django.contrib import admin
from .models import (
    EventTypes, MigCountTypes, MigRas, MigTeams, MigNightlyCounts, MigVsphereMappings,
    Orgs, ProviderVdcs, OrgVdcs, Groups, MigVcloudMappings, SoftwareBuilds, SoftwareLsvs,
    SoftwareTypes, SoftwareReleases, States, TaskTypes, Teams, ThrottlerSettings, Citags,
    Events, Catalogs, Vapps, VappCitags, Vms, SppUser, AuthDetail, RetryInterval, HistoricalReport
)


class EventTypesAdmin(admin.ModelAdmin):
    """
    Admin class for managing EventTypes in the Django admin interface.
    """
    list_display = ('name',)


admin.site.register(EventTypes, EventTypesAdmin)


class MigCountyTypesAdmin(admin.ModelAdmin):
    """
    Admin class for managing MigCountyTypes in the Django admin interface.
    """
    list_display = ('name', 'graphable_name')


admin.site.register(MigCountTypes, MigCountyTypesAdmin)


class MigRasAdmin(admin.ModelAdmin):
    """
    Admin class for managing MigRas in the Django admin interface.
    """
    list_display = ('name',)


admin.site.register(MigRas, MigRasAdmin)


class MigTeamsAdmin(admin.ModelAdmin):
    """
    Admin class for managing MigTeams in the Django admin interface.
    """
    list_display = ('name', 'mig_ra_obj')


admin.site.register(MigTeams, MigTeamsAdmin)


class MigNightlyCountsAdmin(admin.ModelAdmin):
    """
    Admin class for managing MigNightlyCounts in the Django admin interface.
    """
    list_display = ('mig_team_obj', 'date', 'mig_count_type_obj')


admin.site.register(MigNightlyCounts, MigNightlyCountsAdmin)


class MigVsphereMappingsAdmin(admin.ModelAdmin):
    """
    Admin class for managing MigVsphereMappings in the Django admin interface.
    """
    list_display = ('mig_team_obj', 'vcenter_hostname', 'cluster_name')


admin.site.register(MigVsphereMappings, MigVsphereMappingsAdmin)


class OrgsAdmin(admin.ModelAdmin):
    """
    Admin class for managing Orgs in the Django admin interface.
    """
    list_display = ('name', 'vcd_id', 'description', 'href', 'created')


admin.site.register(Orgs, OrgsAdmin)


class ProviderAdmin(admin.ModelAdmin):
    """
    Admin class for managing ProviderVdcs in the Django admin interface.
    """
    list_display = ('name', 'vdc_id', 'description', 'new_quota_system',
                    'cpu_multiplier', 'memory_multiplier', 'available_cpus',
                    'available_memory_gb')


admin.site.register(ProviderVdcs, ProviderAdmin)


class OrgVdcsAdmin(admin.ModelAdmin):
    """
    Admin class for managing OrgVdcs in the Django admin interface.
    """
    list_display = ('name', 'org_vdc_id', 'running_tb_limit',
                    'stored_tb_limit', 'provider_vdc_obj', 'vcenter',
                    'mig_ra_obj', 'cpu_limit', 'memory_limit', 'created')


admin.site.register(OrgVdcs, OrgVdcsAdmin)


class GroupsAdmin(admin.ModelAdmin):
    """
    Admin class for managing Groups in the Django admin interface.
    """
    list_display = ('group_dn', 'org_vdc_obj', 'group_members',
                    'read_permission', 'write_permission',
                    'admin_permission', 'org_obj', 'group_name',
                    'restrict_catalogs', 'unrestricted')


admin.site.register(Groups, GroupsAdmin)


class MigVcloudMappingsAdmin(admin.ModelAdmin):
    """
    Admin class for managing MigVcloudMappings in the Django admin interface.
    """
    list_display = ('mig_team_obj', 'spp_hostname', 'orgvdc_obj')


admin.site.register(MigVcloudMappings, MigVcloudMappingsAdmin)


class SoftwareBuildsAdmin(admin.ModelAdmin):
    """
    Admin class for managing SoftwareBuilds in the Django admin interface.
    """
    list_display = ('name',)


admin.site.register(SoftwareBuilds, SoftwareBuildsAdmin)


class SoftwareLsvsAdmin(admin.ModelAdmin):
    """
    Admin class for managing SoftwareLsvs in the Django admin interface.
    """
    list_display = ('name',)


admin.site.register(SoftwareLsvs, SoftwareLsvsAdmin)


class SoftwareTypesAdmin(admin.ModelAdmin):
    """
    Admin class for managing SoftwareTypes in the Django admin interface.
    """
    list_display = ('name',)


admin.site.register(SoftwareTypes, SoftwareTypesAdmin)


class SoftwareReleasesAdmin(admin.ModelAdmin):
    """
    Admin class for managing SoftwareReleases in the Django admin interface.
    """
    list_display = ('name', 'software_type_obj')


admin.site.register(SoftwareReleases, SoftwareReleasesAdmin)


class StatesAdmin(admin.ModelAdmin):
    """
    Admin class for managing States in the Django admin interface.
    """
    list_display = ('name',)


admin.site.register(States, StatesAdmin)


class TaskTypesAdmin(admin.ModelAdmin):
    """
    Admin class for managing TaskTypes in the Django admin interface.
    """
    list_display = ('name', 'description', 'resource_points')


admin.site.register(TaskTypes, TaskTypesAdmin)


class TeamsAdmin(admin.ModelAdmin):
    """
    Admin class for managing Teams in the Django admin interface.
    """
    list_display = ('name', 'org_obj')


admin.site.register(Teams, TeamsAdmin)


class ThrottlerSettingsAdmin(admin.ModelAdmin):
    """
    Admin class for managing ThrottlerSettings in the Django admin interface.
    """
    list_display = ('name', 'value', 'modified')


admin.site.register(ThrottlerSettings, ThrottlerSettingsAdmin)


class CitagsAdmin(admin.ModelAdmin):
    """
    Admin class for managing Citags in the Django admin interface.
    """
    list_display = ('name', 'org_vdc_obj', 'created', 'user')


admin.site.register(Citags, CitagsAdmin)


class EventsAdmin(admin.ModelAdmin):
    """
    Admin class for managing Events in the Django admin interface.
    """
    list_display = ('function_name', 'resource_id', 'user', 'is_api', 'function_parameters',
                    'event_stage', 'outcome', 'created', 'retries')


admin.site.register(Events, EventsAdmin)


class CatalogsAdmin(admin.ModelAdmin):
    """
    Admin class for managing Catalogs in the Django admin interface.
    """
    list_display = ('name', 'vcd_id', 'org_obj', 'user', 'allowed_templates')


admin.site.register(Catalogs, CatalogsAdmin)


class VappsAdmin(admin.ModelAdmin):
    """
    Admin class for managing Vapps in the Django admin interface.
    """
    list_display = ('vcd_id', 'name', 'description', 'state_id', 'vts_name',
                    'ip_address', 'org_vdc_obj', 'team_obj', 'citag_obj',
                    'software_type_obj', 'software_release_obj',
                    'software_lsv_obj', 'created', 'created_by_user_obj',
                    'modified', 'modified_by_id', 'deployed_from_id', 'shared')


admin.site.register(Vapps, VappsAdmin)


class VappCitagsAdmin(admin.ModelAdmin):
    """
    Admin class for managing VappCitags in the Django admin interface.
    """
    list_display = ('citag_obj', 'vapp_obj', 'is_active', 'created',
                    'user')


admin.site.register(VappCitags, VappCitagsAdmin)


class VmsAdmin(admin.ModelAdmin):
    """
    Admin class for managing Vms in the Django admin interface.
    """
    list_display = ('vcd_id', 'name', 'description', 'state_obj', 'vapp_obj', 'vsphere_name',
                    'host_name', 'datastore', 'cpu', 'memory', 'detailed_storage',
                    'committed_storage', 'provisioned_storage', 'vm_attached_disks')


admin.site.register(Vms, VmsAdmin)


class SppUserAdmin(admin.ModelAdmin):
    """
    Admin class for managing SppUser in the Django admin interface.
    """
    list_display = ('user', 'ldap_groups')


admin.site.register(SppUser, SppUserAdmin)


class AuthDetailAdmin(admin.ModelAdmin):
    """
    Admin class for managing AuthDetail in the Django admin interface.
    """
    list_display = ('name', 'host', 'username',
                    'password', 'org', 'api_version')


admin.site.register(AuthDetail, AuthDetailAdmin)


class RetryIntervalAdmin(admin.ModelAdmin):
    """
    Admin class for managing RetryInterval in the Django admin interface.
    """
    list_display = ('name', 'max_retries', 'retry_interval')


admin.site.register(RetryInterval, RetryIntervalAdmin)


class HistoricalReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_date')

admin.site.register(HistoricalReport, HistoricalReportAdmin)