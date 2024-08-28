import logging
from django.core.management.base import BaseCommand
from pyvcloud_project.utils import pvdc_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        logger.info('Importing Provider Vdcs')
        logger.info(self.style.SUCCESS(
            f'Finished : {pvdc_utils.import_pvdc()}'))
