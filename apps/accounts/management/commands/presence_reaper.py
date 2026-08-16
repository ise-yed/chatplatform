import asyncio

from django.core.management.base import BaseCommand

from apps.accounts.services.presence import reap_stale_connections

REAPER_INTERVAL_SECONDS = 30


class Command(BaseCommand):
    help = 'Periodically cleans up presence state for connections that crashed without disconnecting cleanly.'

    def handle(self, *args, **options):
        asyncio.run(self._run_forever())

    async def _run_forever(self):
        self.stdout.write(self.style.SUCCESS('Presence reaper started.'))
        while True:
            await reap_stale_connections()
            await asyncio.sleep(REAPER_INTERVAL_SECONDS)