import logging
from django.core.management.base import BaseCommand
from pyvcloud_project.utils import orgvdc_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        logger.info('Importing OrgVdcs')
        logger.info(self.style.SUCCESS(
            f'Finished : {orgvdc_utils.import_orgvdc()}'))
