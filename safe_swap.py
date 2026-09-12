"""Checked entry point for app swaps and count-preserving Home Screen reorders."""
import asyncio
from collections import Counter
from contextlib import asynccontextmanager
from device import usb_connection
from editor import is_folder, title
from sync import prepare, apply, encoded


def validate_swap(before, desired):
    changes = []
    def walk(a, b, path):
        if a == b: return
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b): raise ValueError('A swap must preserve every page and folder size.')
            for i, (old, new) in enumerate(zip(a, b)): walk(old, new, path + (i,))
        elif is_folder(a) and is_folder(b):
            if {k:v for k,v in a.items() if k != 'iconLists'} != {k:v for k,v in b.items() if k != 'iconLists'}:
                raise ValueError('Folder settings must remain unchanged.')
            walk(a['iconLists'], b['iconLists'], path)
        elif (isinstance(a, dict) and isinstance(b, dict) and not is_folder(a) and not is_folder(b)
              and a.get('bundleIdentifier') and b.get('bundleIdentifier') and path and path[0] != 0):
            changes.append((a, b, path))
        else: raise ValueError('Only ordinary app swaps outside the dock can be applied.')
    walk(before, desired, ())
    if len(changes) != 2 or changes[0][0] != changes[1][1] or changes[1][0] != changes[0][1]:
        raise ValueError('Make exactly one swap between two apps, then apply it before making another.')
    return changes


def describe_swap(before, desired):
    def location(path):
        if len(path) == 2: return f'page {path[0]}, slot {path[1]+1}'
        return f'page {path[0]}, {title(before[path[0]][path[1]])}, folder page {path[2]+1}, slot {path[3]+1}'
    first, second = validate_swap(before, desired)
    return f'{title(first[0])} → {location(second[2])}\n{title(second[0])} → {location(first[2])}'


async def prepare_swap(desired, baseline, connection=usb_connection):
    if not desired.device_id or baseline is None:
        raise ValueError('Read your iPhone first. This layout has no verified phone baseline.')
    validate_edit(baseline, desired.layout)
    return await prepare(desired, baseline, connection)


@asynccontextmanager
async def _swap_connection(expected_id, plan):
    async with usb_connection(expected_id) as phone:
        class SwapPhone:
            def __getattr__(self, name): return getattr(phone, name)
            async def write(self, layout):
                validate_edit(plan.before.layout, layout)
                if layout != plan.desired.layout or await phone.read() != plan.before.layout:
                    raise ValueError('The reviewed arrangement or phone layout changed. Read the phone again.')
                from pymobiledevice3.services.springboard import SpringBoardServicesService
                async with SpringBoardServicesService(phone.phone) as service:
                    await service.set_icon_state(layout)
        yield SwapPhone()


async def apply_swap(plan, directory=None, connection=None):
    if not plan.before.device_id or plan.before.device_id != plan.desired.device_id:
        raise ValueError('The arrangement must be bound to one phone.')
    validate_edit(plan.before.layout, plan.desired.layout)
    if connection is None:
        def connection(expected): return _swap_connection(expected, plan)
    return await apply(plan, directory, connection)


def prepare_swap_sync(desired, baseline):
    return asyncio.run(asyncio.wait_for(prepare_swap(desired, baseline), 40))


def apply_swap_sync(plan):
    return asyncio.run(apply_swap(plan))


def validate_edit(before, desired):
    try:
        validate_swap(before, desired)
        return 'swap'
    except ValueError:
        pass
    if (not isinstance(before, list) or not isinstance(desired, list) or before == desired
            or len(before) != len(desired) or not before or before[0] != desired[0]
            or any(not isinstance(a,list) or not isinstance(b,list) or len(a)!=len(b) for a,b in zip(before,desired))):
        raise ValueError('A page reorder must keep the dock and all page sizes unchanged.')
    inventory = lambda layout: Counter(encoded(item) for page in layout[1:] for item in page)
    if inventory(before) != inventory(desired):
        raise ValueError('A page reorder must preserve all apps, folders, and their complete metadata.')
    for p, page in enumerate(before[1:],1):
        for i,item in enumerate(page):
            if not isinstance(item,dict) or not (is_folder(item) or item.get('bundleIdentifier') or item.get('webClipURL')):
                if encoded(item) != encoded(desired[p][i]):
                    raise ValueError('Unsupported items must remain in their existing slots.')
    return 'reorder'


def describe_edit(before, desired, limit=10):
    if validate_edit(before, desired) == 'swap': return describe_swap(before, desired)
    changed = [(p,i,a,b) for p,(old,new) in enumerate(zip(before,desired)) for i,(a,b) in enumerate(zip(old,new)) if a!=b]
    pages = ', '.join(str(p) for p in sorted({p for p,_,_,_ in changed}))
    sample = '\n'.join(f'Page {p}, slot {i+1}: {title(a)} → {title(b)}' for p,i,a,b in changed[:limit])
    return f'Reorder {len(changed)} positions across pages {pages}.\n\n{sample}' + ('\n…additional positions shift too.' if limit is not None and len(changed)>limit else '')
