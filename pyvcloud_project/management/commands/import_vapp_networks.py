import logging
from django.core.management.base import BaseCommand
from pyvcloud_project.utils import vapp_network_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        logger.info('Importing Vapp Networks')
        logger.info(self.style.SUCCESS(
            f'Finished : {vapp_network_utils.import_networks()}'))
