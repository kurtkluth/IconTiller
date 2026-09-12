"""Explicit live move experiment; production UI writes remain disabled.

Requires a previously captured baseline. Swaps two app entries, never removes
entries, and uses the existing stale checks, durable backup, and read-back.
No automatic retry or restore is performed. Use only for authorized live tests.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
import json
from pathlib import Path

from device import load_snapshot, save_snapshot, usb_connection
from editor import is_folder, title
from sync import apply, prepare, leaves


def swap_target(baseline, page, first, second, second_page=None):
    second_page = page if second_page is None else second_page
    if not baseline.device_id:
        raise ValueError('The baseline must identify the captured phone.')
    if any(p < 1 or p >= len(baseline.layout) for p in (page, second_page)):
        raise ValueError('Choose an existing Home Screen page; the dock is excluded.')
    if ((page, first) == (second_page, second) or min(first, second) < 0
            or first >= len(baseline.layout[page]) or second >= len(baseline.layout[second_page])):
        raise ValueError('Choose two different existing slots.')
    for p, index in ((page, first), (second_page, second)):
        item = baseline.layout[p][index]
        if not isinstance(item, dict) or is_folder(item) or not item.get('bundleIdentifier'):
            raise ValueError('This experiment swaps only ordinary app entries.')
    target = deepcopy(baseline)
    target.layout[page][first], target.layout[second_page][second] = target.layout[second_page][second], target.layout[page][first]
    return target


class LiveTestPhone:
    def __init__(self, adapter):
        self.adapter = adapter

    def __getattr__(self, name):
        return getattr(self.adapter, name)

    async def write(self, layout):
        from pymobiledevice3.services.springboard import SpringBoardServicesService
        async with SpringBoardServicesService(self.adapter.phone) as service:
            await service.set_icon_state(layout)


@asynccontextmanager
async def live_test_connection(expected_id):
    async with usb_connection(expected_id) as adapter:
        yield LiveTestPhone(adapter)


async def run(baseline_path, page, first, second, second_page=None):
    second_page = page if second_page is None else second_page
    baseline = load_snapshot(baseline_path)
    target = swap_target(baseline, page, first, second, second_page)
    plan = await prepare(target, baseline.layout, live_test_connection)
    # Exclusive files also prevent accidentally rerunning this experiment in place.
    save_snapshot(target, baseline_path.parent / 'desired.plist')
    print(f'Swapping {title(baseline.layout[page][first])} (page {page}, slot {first+1}) and {title(baseline.layout[second_page][second])} (page {second_page}, slot {second+1}).', flush=True)
    result = await apply(plan, baseline_path.parent, live_test_connection)
    report = {'status': result.status, 'detail': result.detail, 'backup': str(result.backup),
              'pages': [page, second_page], 'slots': [first + 1, second + 1]}
    if result.observed:
        save_snapshot(result.observed, baseline_path.parent / 'readback.plist')
        report['exact_match'] = result.observed.layout == target.layout
        report['added_leaf_entries'] = sum((leaves(result.observed.layout) - leaves(target.layout)).values())
        report['missing_leaf_entries'] = sum((leaves(target.layout) - leaves(result.observed.layout)).values())
        report['page_sizes'] = [len(p) for p in result.observed.layout]
    (baseline_path.parent / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--page', required=True, type=int)
    parser.add_argument('--second-page', type=int, help='Destination page; defaults to the first page')
    parser.add_argument('--first', required=True, type=int, help='First slot (1-based)')
    parser.add_argument('--second', required=True, type=int, help='Second slot (1-based)')
    args = parser.parse_args()
    asyncio.run(run(args.baseline, args.page, args.first - 1, args.second - 1, args.second_page))
