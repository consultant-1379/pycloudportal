"""
Module: models.py
Description: Contains the models for the pyvcloud_project module.
"""

from collections import namedtuple
from django.db import models
from django.contrib.auth.models import User
from rq import Retry
import django


class EventTypes(models.Model):
    """
    Model representing different types of events.
    """
    name = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Event types'

    def __str__(self):
        return str(self.name)


class MigCountTypes(models.Model):
    """
    Model representing different types of migration counts.
    """
    name = models.CharField(max_length=128)
    graphable_name = models.CharField(max_length=128)

    class Meta:
        verbose_name_plural = 'Mig count types'

    def __str__(self):
        return str(self.name)


class MigRas(models.Model):
    """
    Model representing migration resource allocation.
    """
    name = models.CharField(max_length=128, unique=True)

    class Meta:
        verbose_name_plural = 'Mig ras'

    def __str__(self):
        return str(self.name)


class MigTeams(models.Model):
    """
    Model representing migration teams.
    """
    name = models.CharField(max_length=128)
    mig_ra_obj = models.ForeignKey(MigRas, on_delete=models.PROTECT,
                                   blank=False, null=True)

    class Meta:
        verbose_name_plural = 'Mig teams'

    def __str__(self):
        return str(self.name)


class MigNightlyCounts(models.Model):
    """
    Model representing nightly migration counts.
    """
    mig_team_obj = models.ForeignKey(MigTeams, on_delete=models.PROTECT,
                                     null=True, blank=False)
    date = models.DateField()
    mig_count_type_obj = models.ForeignKey(MigCountTypes,
                                           on_delete=models.PROTECT,
                                           null=True, blank=False)
    count = models.IntegerField()

    class Meta:
        verbose_name_plural = 'Mig nightly counts'


class MigVsphereMappings(models.Model):
    """
    Model representing mappings between migration teams and vSphere clusters.
    """
    mig_team_obj = models.ForeignKey(MigTeams, on_delete=models.PROTECT,
                                     blank=False, null=True)
    vcenter_hostname = models.CharField(max_length=128)
    cluster_name = models.CharField(max_length=128)

    class Meta:
        verbose_name_plural = 'Mig vsphere mappings'


class Orgs(models.Model):
    """
    Model representing organizations.
    """
    name = models.CharField(max_length=45, blank=True, null=True)
    vcd_id = models.CharField(max_length=60)
    description = models.TextField(blank=True, null=True)
    href = models.CharField(max_length=300, blank=True, null=True)
    created = models.DateTimeField(editable=False,
                                   default=django.utils.timezone.now)

    class Meta:
        verbose_name_plural = 'Orgs'

    def __str__(self):
        return str(self.name)


class ProviderVdcs(models.Model):
    """
    Model representing provider virtual data centers.
    """
    name = models.CharField(max_length=45, blank=True, null=True)
    vdc_id = models.CharField(max_length=60)
    description = models.TextField(blank=True, null=True)
    new_quota_system = models.BooleanField()
    cpu_multiplier = models.DecimalField(blank=False, default=1,
                                         max_digits=10, decimal_places=5)
    memory_multiplier = models.DecimalField(blank=False, default=1,
                                            max_digits=10, decimal_places=5)
    available_cpus = models.IntegerField()
    available_memory_gb = models.IntegerField()

    class Meta:
        verbose_name_plural = 'Provider VDCs'

    def __str__(self):
        return str(self.name)


class OrgVdcs(models.Model):
    """
    Model representing organization virtual data centers.
    """
    name = models.CharField(max_length=45, blank=True, null=True)
    org_vdc_id = models.CharField(max_length=60, blank=False, null=True)
    running_tb_limit = models.IntegerField(blank=False, default=0)
    stored_tb_limit = models.IntegerField(blank=False, default=0)
    provider_vdc_obj = models.ForeignKey(ProviderVdcs,
                                         on_delete=models.CASCADE,
                                         blank=False, null=True)
    mig_ra_obj = models.ForeignKey(MigRas, on_delete=models.PROTECT,
                                   blank=True, null=True)
    vcenter = models.CharField(max_length=40, blank=True, null=True)
    cpu_limit = models.IntegerField(blank=False, default=0)
    memory_limit = models.IntegerField(blank=False, default=0)
    created = models.DateTimeField(editable=False,
                                   default=django.utils.timezone.now)

    class Meta:
        verbose_name_plural = 'Org VDCs'

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if not self.id:
            self.created = django.utils.timezone.now()
        return super().save(*args, **kwargs)

    def __str__(self):
        return str(self.name)


class Groups(models.Model):
    """
    Model representing groups.
    """
    group_dn = models.CharField(max_length=200)
    org_vdc_obj = models.ForeignKey(OrgVdcs, on_delete=models.CASCADE,
                                    blank=False, null=True)
    group_members = models.TextField(blank=True, null=True)
    read_permission = models.BooleanField(default=0, blank=False, null=True)
    write_permission = models.BooleanField(default=0, blank=False, null=True)
    admin_permission = models.BooleanField(default=0, blank=False, null=True)
    org_obj = models.ForeignKey(Orgs, on_delete=models.CASCADE,
                                blank=False, null=True)
    group_name = models.CharField(max_length=100)
    restrict_catalogs = models.BooleanField(default=0, blank=False, null=True)
    unrestricted = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Groups'

    def __str__(self):
        return str(self.group_dn)


class MigVcloudMappings(models.Model):
    """
    Model representing mappings between migration teams and vCloud instances.
    """
    mig_team_obj = models.ForeignKey(MigTeams, on_delete=models.PROTECT,
                                     blank=False, null=True)
    spp_hostname = models.CharField(max_length=128)
    orgvdc_obj = models.ForeignKey(OrgVdcs, on_delete=models.PROTECT,
                                   blank=False, null=True)

    class Meta:
        verbose_name_plural = 'Mig vcldoud mappings'


class SoftwareBuilds(models.Model):
    """
    Model representing software builds.
    """
    name = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Software builds'

    def __str__(self):
        return str(self.name)


class SoftwareLsvs(models.Model):
    """
    Model representing software Lsvs.
    """
    name = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Software Lsvs'

    def __str__(self):
        return str(self.name)


class SoftwareTypes(models.Model):
    """
    Model representing software types.
    """
    name = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Software types'

    def __str__(self):
        return str(self.name)


class SoftwareReleases(models.Model):
    """
    Model representing software releases.
    """
    name = models.CharField(max_length=45, blank=True, null=True)
    software_type_obj = models.ForeignKey(SoftwareTypes,
                                          on_delete=models.PROTECT,
                                          blank=False, null=True)

    class Meta:
        verbose_name_plural = 'Software releases'

    def __str__(self):
        return str(self.name)


class States(models.Model):
    """
    Model representing states.
    """
    name = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'States'

    def __str__(self):
        return str(self.name)


class TaskTypes(models.Model):
    """
    Model representing task types.
    """
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=128)
    resource_points = models.IntegerField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Task types'

    def __str__(self):
        return str(self.name)


class Teams(models.Model):
    """
    Model representing teams.
    """
    name = models.CharField(max_length=45, blank=True, null=True)
    org_obj = models.ForeignKey(Orgs, on_delete=models.PROTECT,
                                blank=False, null=True)

    class Meta:
        verbose_name_plural = 'Teams'

    def __str__(self):
        return str(self.name)


class ThrottlerSettings(models.Model):
    """
    Model representing throttler settings.
    """
    name = models.CharField(max_length=64)
    value = models.IntegerField()
    modified = models.DateTimeField(default=django.utils.timezone.now)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        self.modified = django.utils.timezone.now()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'Throttler settings'

    def __str__(self):
        return str(self.name)


class SppUser(models.Model):
    """
    Model representing SPP users.
    """
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    ldap_groups = models.TextField(blank=True, null=True)

    @property
    def username(self):
        """
        Returns the username of the associated User object.
        """
        return self.user.username

    @property
    def is_staff(self):
        """
        Returns True if the associated User is a staff member, False otherwise.
        """
        return self.user.is_staff

    @property
    def is_superuser(self):
        """
        Returns True if the associated User is a superuser member, False otherwise.
        """
        return self.user.is_superuser

    def __str__(self):
        """
        Returns a string representation of the SppUser object.
        """
        return str(self.user)


class Citags(models.Model):
    """
    Model representing Citags.
    """
    name = models.CharField(max_length=45, blank=True, null=True)
    org_vdc_obj = models.ForeignKey(OrgVdcs, on_delete=models.PROTECT,
                                    blank=True, null=True)
    created = models.DateTimeField(editable=False,
                                   default=django.utils.timezone.now)
    user = models.CharField(max_length=60, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Citags'

    def __str__(self):
        return str(self.name)


class Events(models.Model):
    """
    Model representing events.
    """
    class EventStages(models.TextChoices):
        Start = 'Start'
        End = 'End'

    class EventOutcomes(models.TextChoices):
        Completed = 'Completed'
        Failed = 'Failed'

    user = models.ForeignKey(SppUser, on_delete=models.PROTECT,
                             blank=False, null=True)
    function_name = models.CharField(max_length=45, blank=True, null=True)
    is_api = models.BooleanField(default=False, blank=False, null=True)
    function_parameters = models.TextField(blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    object_type = models.CharField(max_length=45, blank=True, null=True)
    job_id = models.CharField(max_length=45, blank=True, null=True)

    resource_id = models.CharField(max_length=150, blank=True, null=True)
    created = models.DateTimeField(editable=False,
                                   default=django.utils.timezone.now)
    event_type_obj = models.ForeignKey(EventTypes, on_delete=models.PROTECT,
                                       blank=True, null=True)
    modified = models.DateTimeField(default=django.utils.timezone.now)
    retries = models.IntegerField(default=0)
    event_stage = models.CharField(
        max_length=45, choices=EventStages.choices, default=EventStages.Start.value)
    outcome = models.CharField(
        max_length=45, choices=EventOutcomes.choices, blank=True, null=True)
    request_host = models.CharField(max_length=45, blank=True, null=True)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        # if not self.id:
        # self.created = django.utils.timezone.now()
        self.modified = django.utils.timezone.now()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'Events'

    def __str__(self):
        return str(self.function_name)


class Catalogs(models.Model):
    """
    Model representing catalogs.
    """
    name = models.CharField(max_length=60, blank=True, null=True)
    vcd_id = models.CharField(max_length=60)
    org_obj = models.ForeignKey(Orgs, on_delete=models.PROTECT, blank=False,
                                null=True)
    user = models.CharField(max_length=60, blank=True, null=True)
    allowed_templates = models.IntegerField(blank=False, null=False, default=1)

    class Meta:
        verbose_name_plural = 'Catalogs'

    def __str__(self):
        return str(self.name)


class Vapps(models.Model):
    """
    Model representing Vapps.
    """
    vcd_id = models.CharField(max_length=60)
    name = models.CharField(max_length=100)
    origin_catalog_name = models.CharField(max_length=100, blank=True, null=True)
    origin_template_name = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    state_id = models.IntegerField(blank=True, null=True)
    vts_name = models.CharField(max_length=45, blank=True, null=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    org_vdc_obj = models.ForeignKey(OrgVdcs, on_delete=models.PROTECT,
                                    blank=False, null=True)
    team_obj = models.ForeignKey(Teams, on_delete=models.PROTECT,
                                 blank=False, null=True)
    citag_obj = models.ForeignKey(Citags, on_delete=models.PROTECT,
                                  blank=False, null=True)
    software_type_obj = models.ForeignKey(SoftwareTypes,
                                          on_delete=models.PROTECT,
                                          blank=False, null=True)
    software_release_obj = models.ForeignKey(SoftwareReleases,
                                             on_delete=models.PROTECT,
                                             blank=False, null=True)
    software_lsv_obj = models.ForeignKey(SoftwareLsvs,
                                         on_delete=models.PROTECT,
                                         blank=False, null=True)
    created = models.DateTimeField(editable=False,
                                   default=django.utils.timezone.now)
    created_by_user_obj = models.ForeignKey(SppUser, on_delete=models.PROTECT,
                                            blank=False, null=True)
    modified = models.DateTimeField(default=django.utils.timezone.now)
    modified_by_id = models.IntegerField(blank=True, null=True)
    deployed_from_id = models.CharField(max_length=60, blank=True, null=True)
    shared = models.BooleanField(blank=False, null=True)
    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        self.modified = django.utils.timezone.now()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'Vapps'

    def __str__(self):
        return str(self.name)


class VappCitags(models.Model):
    """
    Model representing Vapps Catalogs.
    """
    citag_obj = models.ForeignKey(Citags, on_delete=models.PROTECT,
                                  blank=False, null=True)
    vapp_obj = models.ForeignKey(Vapps, on_delete=models.PROTECT, blank=False,
                                 null=True)
    is_active = models.BooleanField(blank=False, null=True)
    created = models.DateTimeField(editable=False,
                                   default=django.utils.timezone.now)
    user = models.CharField(max_length=60, blank=True, null=True)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if not self.id:
            self.created = django.utils.timezone.now()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'Vapp citags'


class Vms(models.Model):
    """
    Model representing Vm's.
    """
    vcd_id = models.CharField(max_length=60)
    name = models.CharField(max_length=45, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    state_obj = models.ForeignKey(States, on_delete=models.PROTECT,
                                  blank=True, null=True)
    vapp_obj = models.ForeignKey(Vapps, on_delete=models.CASCADE,
                                 blank=False, null=True)
    os_family = models.CharField(max_length=45, blank=True, null=True)
    os_name = models.CharField(max_length=45, blank=True, null=True)
    vmware_tools = models.CharField(max_length=45, blank=True, null=True)
    vsphere_name = models.CharField(max_length=45, blank=True, null=True)
    host_name = models.CharField(max_length=45, blank=True, null=True)
    datastore = models.CharField(max_length=45, blank=True, null=True)
    cpu = models.IntegerField(blank=True, null=True)
    memory = models.IntegerField(blank=True, null=True)
    memory_metric = models.CharField(max_length=45, blank=True, null=True)
    committed_storage = models.IntegerField(blank=True, null=True)
    provisioned_storage = models.IntegerField(blank=True, null=True)
    detailed_storage = models.TextField(blank=True, null=True)
    vm_attached_disks = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'VMS'

    def __str__(self):
        return str(self.name)


class AuthDetail(models.Model):
    """
    Model representing authentication details.
    """
    name = models.CharField(max_length=100, blank=True, null=True)
    host = models.CharField(max_length=100, blank=True, null=True)
    username = models.CharField(max_length=45, blank=True, null=True)
    password = models.CharField(max_length=45, blank=True, null=True)
    org = models.CharField(max_length=45, blank=True, null=True)
    api_version = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'AuthDetails'

    def __str__(self):
        return str(self.name)


class RetryIntervalManager(models.Manager):
    """
    Custom manager for RetryInterval model.
    """

    def get_retry_obj(self, name):
        """
        Retrieve the retry object for the given name.
        """
        retry_tuple = namedtuple('RetryInterval', ['args', 'kwargs'])
        try:
            self_obj = self.get(name=name)
        except RetryInterval.DoesNotExist:
            return retry_tuple('default', {
                'connection': None, 'timeout': 1800, 'retry': Retry(max=3, interval=30)
            })
        return retry_tuple(self_obj.queue, {'connection': None, 'timeout': self_obj.job_timeout,
                                            'retry': Retry(max=self_obj.max_retries,
                                                           interval=self_obj.retry_interval)})


class RetryInterval(models.Model):
    """
    Model representing retry intervals.
    """
    class Queue(models.TextChoices):
        DEFAULT = 'default'
        HIGH = 'high'
        LOW = 'low'

    name = models.CharField(max_length=100, blank=True, null=True)
    queue = models.CharField(max_length=100, blank=False,
                             null=False, choices=Queue.choices, default=Queue.DEFAULT)
    max_retries = models.IntegerField(blank=False, null=False, default=1)
    retry_interval = models.IntegerField(blank=False, null=False, default=1)
    job_timeout = models.IntegerField(blank=False, null=False, default=600)

    objects = RetryIntervalManager()

    class Meta:
        verbose_name_plural = 'RetryIntervals'

    def __str__(self):
        return str(self.name)

class HistoricalReport(models.Model):
    """
    Table to store historical reports
    """
    name = models.CharField(max_length=50)
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Historical Reports'

    def __str__(self):
        return str(self.name)