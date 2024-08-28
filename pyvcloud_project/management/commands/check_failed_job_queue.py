import logging
from django.core.management.base import BaseCommand
from pyvcloud_project.utils import pyvcloud_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    The jobs in RQ don't update the exception info (job.exc_info) in the redis cache until after the worker
    has completed. This means we can't get the exception information for failed jobs from inside the
    on_worker_failure function in pyvcloud_utils, if we're executing inside that function it hasn't been written to reddis yet.

    Need to regularly poll the failed jobs queue for new entries using cron, match them with the events in the db
    and then update the db event with the exception information from the failed job.
    The default TTL for a failed job in RQ is 1 year.  rq> defaults.py
    Won't need to run this too frequently in that case. Once a day should be fine. It can always be triggered manually with
    python manage.py check_failed_job_queue
    """

    def handle(self, *args, **kwargs):
        logger.info('Checking RQ Failed Job Queue')
        logger.info(self.style.SUCCESS(
            f'Finished : {pyvcloud_utils.update_failed_events_in_db()}'))
