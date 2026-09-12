"""Checked, single-attempt layout writes with durable backup and independent read-back."""
import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import plistlib
from uuid import uuid4
from device import Snapshot, save_snapshot, usb_connection, WRITE_BLOCK_REASON
from editor import is_folder


def encoded(value):
    return plistlib.dumps({'value': value}, fmt=plistlib.FMT_BINARY, sort_keys=True)


def leaves(layout):
    result = Counter()
    def visit(value):
        if isinstance(value, list):
            for item in value: visit(item)
        elif is_folder(value):
            visit(value['iconLists'])
        else: result[encoded(value)] += 1
    visit(layout)
    return result


def validate(current, desired, metrics):
    if not isinstance(desired, list) or len(desired) < 2 or any(not isinstance(p, list) for p in desired):
        raise ValueError('Layout must contain a dock and Home Screen pages.')
    required = ['homeScreenIconDockMaxCount', 'homeScreenIconMaxPages', 'homeScreenIconRows',
                'homeScreenIconColumns', 'homeScreenIconFolderRows', 'homeScreenIconFolderColumns', 'homeScreenIconFolderMaxPages']
    if any(not isinstance(metrics.get(k), (int, float)) or metrics[k] <= 0 for k in required):
        raise ValueError('The iPhone did not provide usable layout limits.')
    if len(desired[0]) > metrics[required[0]] or len(desired)-1 > metrics[required[1]]:
        raise ValueError('The draft exceeds the dock or page limit reported by this iPhone.')
    if any(len(p) > metrics[required[2]] * metrics[required[3]] for p in desired[1:]):
        raise ValueError('A page has too many items. Move some to another page.')
    if leaves(current) != leaves(desired):
        raise ValueError('App or special-item data differs from the phone. Read a fresh layout and edit it again.')
    for page in desired:
        for item in page:
            if is_folder(item):
                pages = item['iconLists']
                if not str(item.get('displayName', '')).strip() or not pages or len(pages) > metrics[required[6]]:
                    raise ValueError('A folder has no name or has an unsupported page count.')
                if any(not isinstance(p, list) or not p or len(p) > metrics[required[4]]*metrics[required[5]] for p in pages):
                    raise ValueError('A folder page is empty or exceeds the reported folder capacity.')
                if any(is_folder(child) for p in pages for child in p):
                    raise ValueError('Nested folders cannot be applied.')
    # Unknown metadata can encode widget geometry. Preserve it and keep special items stationary.
    for p, page in enumerate(current):
        for i, item in enumerate(page):
            if not isinstance(item, dict) or (not is_folder(item) and 'bundleIdentifier' not in item and 'webClipURL' not in item):
                if p >= len(desired) or i >= len(desired[p]) or desired[p][i] != item:
                    raise ValueError('A reserved or unrecognized item moved. Keep these slots unchanged for this release.')


@dataclass
class Plan:
    before: Snapshot
    desired: Snapshot
    changed_pages: list


@dataclass
class Result:
    status: str
    backup: Path | None
    observed: Snapshot | None
    detail: str = ''


async def prepare(desired, baseline, connection=usb_connection):
    if baseline is None:
        raise ValueError('Select the original, unedited layout backup for this older draft.')
    async with connection(desired.device_id) as phone:
        layout = await asyncio.wait_for(phone.read(), 15)
        if desired.name != phone.name or desired.version != phone.version:
            raise ValueError('The connected phone name or iOS version differs from this draft.')
        if layout != baseline:
            raise ValueError('The phone has changed since the original layout. Read a fresh layout before applying edits.')
        validate(layout, desired.layout, await asyncio.wait_for(phone.metrics(), 10))
        before = Snapshot(phone.name, phone.version, deepcopy(layout), phone.device_id)
        target = Snapshot(phone.name, phone.version, deepcopy(desired.layout), phone.device_id)
        changed = [i for i in range(max(len(layout), len(target.layout)))
                   if (layout[i] if i < len(layout) else None) != (target.layout[i] if i < len(target.layout) else None)]
        return Plan(before, target, changed)


def backup_directory():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'iPhoneScreenManager' / 'Backups'


async def apply(plan, directory=None, connection=usb_connection):
    if connection is usb_connection:
        raise ValueError(WRITE_BLOCK_REASON)
    if not plan.changed_pages: return Result('unchanged', None, plan.before, 'The draft already matches the phone.')
    directory = Path(directory) if directory is not None else backup_directory()
    backup = None
    write_error = ''
    write_started = False
    try:
        async with connection(plan.before.device_id) as phone:
            current = await asyncio.wait_for(phone.read(), 15)
            if current != plan.before.layout:
                raise ValueError('The phone layout changed after review. No layout was sent.')
            validate(current, plan.desired.layout, await asyncio.wait_for(phone.metrics(), 10))
            directory.mkdir(parents=True, exist_ok=True)
            backup = directory / (datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid4().hex[:8] + '-before.plist')
            save_snapshot(plan.before, backup)
            # A final read closes the time gap spent persisting the backup.
            if await asyncio.wait_for(phone.read(), 15) != current:
                raise ValueError('The layout changed while making the backup. No layout was sent.')
            write_started = True
            try:
                await asyncio.wait_for(phone.write(deepcopy(plan.desired.layout)), 10)
            except Exception as error:
                write_error = type(error).__name__
    except Exception as error:
        if not write_started:
            raise
        write_error = write_error or type(error).__name__
    # A fresh USB session ensures verification is not using cached request data.
    observed = None
    for attempt in range(3):
        try:
            async with connection(plan.before.device_id) as phone:
                layout = await asyncio.wait_for(phone.read(), 10)
                observed = Snapshot(phone.name, phone.version, layout, phone.device_id)
                if layout == plan.desired.layout:
                    return Result('verified', backup, observed, write_error)
        except Exception as error:
            write_error = write_error or type(error).__name__
        if attempt < 2: await asyncio.sleep(1)
    if observed is None:
        return Result('unknown', backup, None, 'Could not read the phone after the attempt. Reconnect and read it before retrying. ' + write_error)
    if observed.layout == plan.before.layout:
        return Result('not_applied', backup, observed, 'The phone still has its original layout. This iOS service may ignore layout writes. ' + write_error)
    try:
        save_snapshot(observed, backup.with_name(backup.stem.replace('-before', '-observed') + '.plist'))
    except OSError:
        write_error += ' Observed layout could not be saved.'
    return Result('mismatch', backup, observed, 'The phone returned a different layout. No automatic second write was attempted. The backup is preserved, but restoration through this protocol is not guaranteed. ' + write_error)


def prepare_sync(desired, baseline):
    return asyncio.run(asyncio.wait_for(prepare(desired, baseline), 40))


def apply_sync(plan):
    # Individual operations are bounded. Do not time out the transaction after a write,
    # which could discard the recovery path and leave the result ambiguous.
    return asyncio.run(apply(plan))
