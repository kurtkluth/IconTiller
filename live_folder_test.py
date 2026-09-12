"""Authorized folder-move experiment; separate from production UI writes."""
import argparse
import asyncio
import json
from pathlib import Path

from device import load_snapshot, save_snapshot
from editor import Draft, is_folder
from live_move_test import live_test_connection
from sync import prepare, apply, leaves


def folder_move_target(baseline, source, index, destination, position=None, exchange=False):
    if not baseline.device_id:
        raise ValueError('An identified baseline is required.')
    if sorted((len(source), len(destination))) != [1, 3]:
        raise ValueError('Move between a Home Screen page and a folder page.')
    for path in (source, destination):
        if path[0] < 1 or any(i < 0 for i in path):
            raise ValueError('Invalid path or dock selected.')
    draft = Draft(baseline)
    entries = draft.container(source)
    if not 0 <= index < len(entries):
        raise ValueError('Invalid source slot.')
    item = entries[index]
    if not isinstance(item, dict) or is_folder(item) or not item.get('bundleIdentifier'):
        raise ValueError('Select an ordinary app.')
    if exchange:
        target_entries = draft.container(destination)
        if position is None or not 0 <= position < len(target_entries):
            raise ValueError('Choose an existing destination slot for a swap.')
        other = target_entries[position]
        if not isinstance(other, dict) or is_folder(other) or not other.get('bundleIdentifier'):
            raise ValueError('Both swap entries must be ordinary apps.')
        entries[index], target_entries[position] = other, item
    else:
        draft.move(source, index, destination, position)
    return draft.snapshot()


def parse_path(value):
    parts = tuple(int(p) for p in value.split(','))
    if len(parts) not in (1, 3) or any(p < 1 for p in parts):
        raise argparse.ArgumentTypeError('Use page or page,folder-slot,folder-page (all 1-based).')
    return (parts[0],) + tuple(p - 1 for p in parts[1:])


async def run(args):
    baseline = load_snapshot(args.baseline)
    target = folder_move_target(baseline, args.source, args.slot - 1, args.destination,
                                None if args.position is None else args.position - 1, args.swap)
    plan = await prepare(target, baseline.layout, live_test_connection)
    save_snapshot(target, args.baseline.parent / 'desired.plist')
    result = await apply(plan, args.baseline.parent, live_test_connection)
    report = {'status': result.status, 'detail': result.detail, 'backup': str(result.backup),
              'operation': 'swap' if args.swap else 'move',
              'source': list(args.source), 'source_index': args.slot - 1,
              'destination': list(args.destination),
              'destination_index': None if args.position is None else args.position - 1}
    if result.observed:
        save_snapshot(result.observed, args.baseline.parent / 'readback.plist')
        report.update(exact_match=result.observed.layout == target.layout,
                      added_leaf_entries=sum((leaves(result.observed.layout) - leaves(target.layout)).values()),
                      missing_leaf_entries=sum((leaves(target.layout) - leaves(result.observed.layout)).values()),
                      page_sizes=[len(p) for p in result.observed.layout])
    (args.baseline.parent / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--source', type=parse_path, required=True)
    parser.add_argument('--slot', type=int, required=True)
    parser.add_argument('--destination', type=parse_path, required=True)
    parser.add_argument('--position', type=int)
    parser.add_argument('--swap', action='store_true', help='Exchange with the destination app instead of inserting')
    asyncio.run(run(parser.parse_args()))
