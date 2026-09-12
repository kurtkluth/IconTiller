"""USB-only transport and local snapshot persistence."""
import asyncio
import hashlib
import os
import plistlib
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

WRITE_BLOCK_REASON = ('Unrestricted layout writes are paused. Only reviewed swaps and page reorders can be applied. '
                      'Folder insertion, removal, and full-layout restoration have not been verified.')


@dataclass
class Snapshot:
    name: str
    version: str
    layout: list
    device_id: str = ''
    baseline: list | None = None


async def read_phone() -> Snapshot:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.springboard import SpringBoardServicesService

    async with await create_using_usbmux(connection_type="USB", pair_timeout=0) as phone:
        async with SpringBoardServicesService(phone) as service:
            layout = await service.get_icon_state()
        if not isinstance(layout, list) or not layout:
            raise ValueError("The iPhone did not return a supported Home Screen layout.")
        return Snapshot(str(phone.all_values.get("DeviceName", "iPhone")),
                        str(phone.all_values.get("ProductVersion", "Unknown")), layout,
                        hashlib.sha256(str(phone.udid).encode()).hexdigest())


def capture() -> Snapshot:
    return asyncio.run(asyncio.wait_for(read_phone(), timeout=25))


def save_snapshot(snapshot: Snapshot, path: Path) -> None:
    # Binary plist preserves unfamiliar fields and byte values without translation.
    data = {"formatVersion": 1, "deviceName": snapshot.name,
            "iosVersion": snapshot.version, "iconState": snapshot.layout}
    if snapshot.device_id: data['deviceIdHash'] = snapshot.device_id
    if snapshot.baseline is not None: data['baselineIconState'] = snapshot.baseline
    payload = plistlib.dumps(data,
                            fmt=plistlib.FMT_BINARY, sort_keys=False)
    # Exclusive creation prevents accidentally overwriting an earlier backup.
    with path.open("xb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())


def load_snapshot(path: Path) -> Snapshot:
    if path.stat().st_size > 20_000_000:
        raise ValueError("Layout file is too large (maximum 20 MB).")
    with path.open("rb") as source:
        data = plistlib.load(source)
    if not isinstance(data, dict) or data.get("formatVersion") != 1:
        raise ValueError("This is not a supported layout backup.")
    layout = data.get("iconState")
    if not isinstance(layout, list) or not layout:
        raise ValueError("The backup has no supported layout.")
    baseline = data.get('baselineIconState')
    if baseline is not None and not isinstance(baseline, list):
        raise ValueError('Invalid baseline in draft.')
    return Snapshot(str(data.get("deviceName", "iPhone")),
                    str(data.get("iosVersion", "Unknown")), layout,
                    str(data.get('deviceIdHash', '')), baseline)


class UsbPhone:
    def __init__(self, phone):
        self.phone = phone
        self.device_id = hashlib.sha256(str(phone.udid).encode()).hexdigest()
        self.name = str(phone.all_values.get('DeviceName', 'iPhone'))
        self.version = str(phone.all_values.get('ProductVersion', 'Unknown'))

    async def read(self):
        from pymobiledevice3.services.springboard import SpringBoardServicesService
        async with SpringBoardServicesService(self.phone) as service:
            return await service.get_icon_state()

    async def metrics(self):
        from pymobiledevice3.services.springboard import SpringBoardServicesService
        async with SpringBoardServicesService(self.phone) as service:
            return await service.get_homescreen_icon_metrics()

    async def write(self, layout):
        # Do not re-enable on a personal device without first verifying preservation
        # of App Library-only apps and folder metadata on a disposable test device.
        raise ValueError(WRITE_BLOCK_REASON)


@asynccontextmanager
async def usb_connection(expected_id=''):
    from pymobiledevice3 import usbmux
    from pymobiledevice3.lockdown import create_using_usbmux
    devices = [d for d in await asyncio.wait_for(usbmux.list_devices(), 10) if d.connection_type == 'USB']
    if len(devices) != 1:
        raise ValueError('Connect exactly one iPhone by USB.')
    phone = await asyncio.wait_for(create_using_usbmux(serial=devices[0].serial, connection_type='USB', pair_timeout=0), 15)
    try:
        adapter = UsbPhone(phone)
        if expected_id and adapter.device_id != expected_id:
            raise ValueError('A different iPhone is connected. No layout was sent.')
        yield adapter
    finally:
        await asyncio.wait_for(phone.close(), 5)
