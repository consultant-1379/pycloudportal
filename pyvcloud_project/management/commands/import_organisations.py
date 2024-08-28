import logging
from django.core.management.base import BaseCommand
from pyvcloud_project.utils import org_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        logger.info('Importing Organisations')
        logger.info(self.style.SUCCESS(
            f'Finished : {org_utils.import_orgs()}'))
