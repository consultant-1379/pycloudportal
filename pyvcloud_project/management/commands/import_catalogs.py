import logging
from django.core.management.base import BaseCommand
from pyvcloud_project.utils import catalog_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        logger.info('Importing Catalogs')
        logger.info(self.style.SUCCESS(
            f'Finished : {catalog_utils.import_catalog()}'))
