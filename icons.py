"""Local, device-scoped icon cache and bounded USB reads. No web requests."""
import asyncio
import hashlib
from io import BytesIO
import os
from pathlib import Path
import time
from PIL import Image
from device import usb_connection
from editor import is_folder


def icon_key(item):
    if not isinstance(item, dict) or is_folder(item) or not item.get('bundleIdentifier'): return None
    return (str(item['bundleIdentifier']), str(item.get('bundleVersion', '')))


def apps_in(layout):
    found = set()
    def walk(value):
        if isinstance(value,list):
            for item in value: walk(item)
        elif is_folder(value): walk(value['iconLists'])
        else:
            key = icon_key(value)
            if key: found.add(key)
    walk(layout)
    return sorted(found)


def cache_path(device_id, key, directory=None):
    base = Path(directory) if directory else Path(os.environ.get('LOCALAPPDATA',Path.home())) / 'iPhoneScreenManager' / 'Icons'
    return base / hashlib.sha256(device_id.encode()).hexdigest() / (hashlib.sha256(repr(key).encode()).hexdigest()+'.png')


def validate_png(data):
    if len(data)>2_000_000 or not data.startswith(b'\x89PNG\r\n\x1a\n'): raise ValueError('Invalid icon image')
    with Image.open(BytesIO(data)) as img:
        if img.width>1024 or img.height>1024 or min(img.size)<1: raise ValueError('Invalid icon size')
        img.verify()
    return data


def load_icons(snapshot, output, stop, fetch=False, directory=None):
    missing = []
    for key in apps_in(snapshot.layout):
        if stop.is_set(): return
        path = cache_path(snapshot.device_id,key,directory)
        try:
            if path.stat().st_size>2_000_000: raise ValueError('Oversized cache entry')
            data = validate_png(path.read_bytes())
            output.put((key,data))
        except (OSError,ValueError,SyntaxError): missing.append(key)
    if not fetch or not missing or stop.is_set(): return
    async def read_missing():
        from pymobiledevice3.services.springboard import SpringBoardServicesService
        deadline = time.monotonic()+90
        async with usb_connection(snapshot.device_id) as phone:
            async with SpringBoardServicesService(phone.phone) as service:
                for key in missing:
                    if stop.is_set() or time.monotonic()>deadline: break
                    try:
                        data = await asyncio.wait_for(service.get_icon_pngdata(key[0]),3)
                    except Exception:
                        # A timeout can leave a reply in flight: close this service.
                        break
                    if not isinstance(data,bytes): continue
                    try: validate_png(data)
                    except (ValueError,OSError,SyntaxError): continue
                    path = cache_path(snapshot.device_id,key,directory)
                    try:
                        path.parent.mkdir(parents=True,exist_ok=True)
                        temp = path.with_suffix('.tmp')
                        temp.write_bytes(data)
                        temp.replace(path)
                    except OSError: pass
                    output.put((key,data))
    try: asyncio.run(asyncio.wait_for(read_missing(),110))
    except Exception: pass  # Layout editing remains available; missing artwork uses initials.


def tile_image(item, images, size=64):
    """Return a PIL image or None; GUI image creation remains on the Tk thread."""
    if is_folder(item):
        children = [x for page in item['iconLists'] for x in page][:9]
        if not any(icon_key(x) in images for x in children): return None
        mosaic = Image.new('RGBA',(size,size),(55,88,117,255))
        cell = (size-12)//3
        for i,child in enumerate(children):
            source=images.get(icon_key(child))
            x,y=5+(i%3)*(cell+1),5+(i//3)*(cell+1)
            if source:
                icon=source.resize((cell,cell),Image.Resampling.LANCZOS)
                mosaic.alpha_composite(icon,(x,y))
            else:
                mosaic.paste((110,135,160,255),(x,y,x+cell,y+cell))
        return mosaic
    source=images.get(icon_key(item))
    return source.resize((size,size),Image.Resampling.LANCZOS) if source else None
