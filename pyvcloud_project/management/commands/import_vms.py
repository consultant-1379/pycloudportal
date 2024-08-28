import logging
from django.core.management.base import BaseCommand
from pyvcloud_project.utils import vm_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        logger.info('Importing Vms')
        logger.info(self.style.SUCCESS(f'Finished : {vm_utils.import_vms()}'))
