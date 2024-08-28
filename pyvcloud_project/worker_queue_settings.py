"""
This module provides a RetryIntervalLimits class that retrieves retry intervals
for different operations.

The RetryIntervalLimits class retrieves retry intervals from the RetryInterval model
in the SPP. It initializes class attributes for various operations,
such as starting a vApp, stopping a vApp, powering off a vApp, deleting a vApp, and more.

If the RetryInterval model is not available (e.g., during initial migrations),
default retry intervals are used.

"""

from collections import namedtuple
from django.db.utils import OperationalError
from rq import Retry
from pyvcloud_project.models import RetryInterval


class RetryIntervalLimits:
    """
    Class representing retry interval limits for different operations.
    The RetryIntervalLimits class retrieves retry interval limits for various operations,
    such as starting a vApp, stopping a vApp, powering off a vApp, deleting a vApp, and more.
    """
    try:
        start_vapp = RetryInterval.objects.get_retry_obj('start_vapp')
        stop_vapp = RetryInterval.objects.get_retry_obj('stop_vapp')
        poweroff_vapp = RetryInterval.objects.get_retry_obj('poweroff_vapp')
        delete_vapp = RetryInterval.objects.get_retry_obj('delete_vapp')
        poweroff_and_delete_vapp = RetryInterval.objects.get_retry_obj(
            'poweroff_and_delete_vapp')
        rename_vapp = RetryInterval.objects.get_retry_obj('rename_vapp')
        rename_vapp_template = RetryInterval.objects.get_retry_obj(
            'rename_vapp')
        add_to_catalog_vapp = RetryInterval.objects.get_retry_obj(
            'add_to_catalog_vapp')
        create_from_template_vapp = RetryInterval.objects.get_retry_obj(
            'create_from_template_vapp')
        recompose_vapp = RetryInterval.objects.get_retry_obj(
            'create_from_template_vapp')
        power_on_vm = RetryInterval.objects.get_retry_obj('power_on_vm')
        power_off_vm = RetryInterval.objects.get_retry_obj('power_off_vm')
        reboot_vm = RetryInterval.objects.get_retry_obj('reboot_vm')
        shutdown_vm = RetryInterval.objects.get_retry_obj('shutdown_vm')
        delete_vm = RetryInterval.objects.get_retry_obj('delete_vm')
    except OperationalError:
        # On first run, before migrations have been properly set up.
        # This can throw an operational error as the table has not been created yet.
        # Once migrations have been applied, this code is no longer used.
        retry_tuple = namedtuple('RetryInterval', ['args', 'kwargs'])
        start_vapp = stop_vapp = poweroff_vapp = delete_vapp = poweroff_and_delete_vapp = \
            rename_vapp = rename_vapp_template = add_to_catalog_vapp = recompose_vapp = \
            create_from_template_vapp = retry_tuple(
                'default', {'connection': None, 'timeout': 1800,
                            'retry': Retry(max=3, interval=30)}
            )

        power_on_vm = power_off_vm = reboot_vm = shutdown_vm = delete_vm = retry_tuple(
            'default', {'connection': None, 'timeout': 593, 'retry': Retry(max=3, interval=30)})
