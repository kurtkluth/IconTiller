import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from device import Snapshot, load_snapshot
from sync import prepare, apply, validate

METRICS = dict(homeScreenIconDockMaxCount=4, homeScreenIconMaxPages=15, homeScreenIconRows=6,
               homeScreenIconColumns=4, homeScreenIconFolderRows=3, homeScreenIconFolderColumns=3, homeScreenIconFolderMaxPages=15)

class Phone:
    name, version, device_id = 'Test', '27', 'id1'
    def __init__(self):
        self.layout = [[{'bundleIdentifier': 'dock'}], [{'bundleIdentifier': 'a'}, {'bundleIdentifier': 'b'}]]
        self.writes = 0
        self.mode = 'normal'
    async def read(self):
        if self.writes and self.mode == 'disconnect': raise ConnectionError()
        return deepcopy(self.layout)
    async def metrics(self): return METRICS
    async def write(self, value):
        self.writes += 1
        if self.mode not in ('ignore', 'disconnect'): self.layout = deepcopy(value)
        if self.mode == 'mismatch': self.layout[1].reverse()
        if self.mode == 'timeout': raise TimeoutError()
    @asynccontextmanager
    async def connection(self, expected=''):
        if expected and expected != self.device_id: raise ValueError('Wrong phone')
        yield self

class SyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.phone = Phone()
        self.baseline = deepcopy(self.phone.layout)
        self.target = Snapshot('Test', '27', [self.baseline[0], list(reversed(self.baseline[1]))], 'id1')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    async def plan(self): return await prepare(self.target, self.baseline, self.phone.connection)

    async def run_apply(self, plan):
        return await apply(plan, Path(self.tmp.name), self.phone.connection)

    async def test_verified_and_durable_backup(self):
        result = await self.run_apply(await self.plan())
        self.assertEqual(result.status, 'verified')
        self.assertEqual(load_snapshot(result.backup).layout, self.baseline)
        self.assertEqual(self.phone.writes, 1)

    async def test_stale_after_review_never_writes(self):
        plan = await self.plan()
        self.phone.layout[1].append({'bundleIdentifier': 'new'})
        with self.assertRaises(ValueError): await self.run_apply(plan)
        self.assertEqual(self.phone.writes, 0)

    async def test_wrong_phone_never_writes(self):
        plan = await self.plan()
        self.phone.device_id = 'other'
        with self.assertRaises(ValueError): await self.run_apply(plan)
        self.assertEqual(self.phone.writes, 0)

    async def test_backup_failure_never_writes(self):
        plan = await self.plan()
        with patch('sync.save_snapshot', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): await self.run_apply(plan)
        self.assertEqual(self.phone.writes, 0)

    async def test_acknowledged_but_ignored(self):
        self.phone.mode = 'ignore'
        result = await self.run_apply(await self.plan())
        self.assertEqual(result.status, 'not_applied')
        self.assertEqual(self.phone.writes, 1)

    async def test_write_timeout_but_readback_verifies(self):
        self.phone.mode = 'timeout'
        result = await self.run_apply(await self.plan())
        self.assertEqual(result.status, 'verified')

    async def test_disconnect_returns_recovery_path(self):
        self.phone.mode = 'disconnect'
        result = await self.run_apply(await self.plan())
        self.assertEqual(result.status, 'unknown')
        self.assertTrue(result.backup.exists())
        self.assertEqual(self.phone.writes, 1)

    async def test_restore_is_checked_and_verified(self):
        result = await self.run_apply(await self.plan())
        target = load_snapshot(result.backup)
        restore = await prepare(target, result.observed.layout, self.phone.connection)
        result = await self.run_apply(restore)
        self.assertEqual(result.status, 'verified')
        self.assertEqual(self.phone.layout, self.baseline)

    async def test_dropped_app_and_capacity_rejected(self):
        self.target.layout[1].pop()
        with self.assertRaises(ValueError): await self.plan()
        self.assertEqual(self.phone.writes, 0)

    async def test_real_usb_writes_are_blocked(self):
        plan = await self.plan()
        with self.assertRaisesRegex(ValueError, 'writes are paused'):
            await apply(plan)

    async def test_added_icons_are_mismatch_not_success(self):
        async def expanded_write(value):
            self.phone.writes += 1
            self.phone.layout = deepcopy(value)
            self.phone.layout[1].append({'bundleIdentifier': 'unexpected'})
        self.phone.write = expanded_write
        result = await self.run_apply(await self.plan())
        self.assertEqual(result.status, 'mismatch')
        self.assertEqual(self.phone.writes, 1)
        self.assertTrue(result.backup.with_name(result.backup.stem.replace('-before', '-observed') + '.plist').exists())

    async def test_folder_metadata_loss_is_mismatch(self):
        folder = {'displayName':'Work', 'listType':'folder', 'iconLists': [[{'bundleIdentifier':'c'}]], 'listMetadata': {'future':1}}
        self.phone.layout[1].append(folder)
        self.baseline = deepcopy(self.phone.layout)
        self.target.layout = [self.baseline[0], list(reversed(self.baseline[1]))]
        async def stripped_write(value):
            self.phone.writes += 1
            self.phone.layout = deepcopy(value)
            self.phone.layout[1][0].pop('listMetadata')
        self.phone.write = stripped_write
        result = await self.run_apply(await self.plan())
        self.assertEqual(result.status, 'mismatch')

if __name__ == '__main__': unittest.main()
