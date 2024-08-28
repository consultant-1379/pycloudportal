import logging
from django.core.management.base import BaseCommand
from pyvcloud_project.utils import vapp_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        logger.info('Importing Vapps')
        logger.info(self.style.SUCCESS(
            f'Finished : {vapp_utils.import_vapps()}'))
