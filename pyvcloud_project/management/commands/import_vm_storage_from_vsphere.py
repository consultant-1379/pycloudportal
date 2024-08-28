import logging
from django.core.management.base import BaseCommand
from pyvcloud_project.utils import vsphere_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        logger.info('Importing Vm Storage details from Vsphere')
        logger.info(self.style.SUCCESS(
            f'Finished : {vsphere_utils.import_vm_storage_from_vsphere()}'))
