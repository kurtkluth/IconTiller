# IconTiller

**App Layout Editor by Kurt Kluth** | [MIT License](LICENSE)

Arrange your iPhone Home Screens from Windows, with real app icons, drag-and-drop editing, and checked USB writes.

**Development preview.** The current Python application supports app swaps and page reordering that preserve existing page sizes. Compatibility has been tested on one connected iPhone reporting iOS 27.0; broader device and iOS support is not established. Source code is available under the MIT License.

## What it does

- Read your Home Screen layout and app artwork through Apple's local USB connection.
- **Insert and shift:** drag an app between icons and shift the intervening entries across pages without changing their item counts.
- **Swap positions:** exchange two apps within a page, between pages, or between a page and a folder.
- Navigate while dragging: hold over a page number to jump, or near the top/bottom edge to scroll. A floating preview and gold insertion marker show the intended change. Escape cancels.
- Search apps and folders in a scrollable results list with locations aligned after the widest displayed name, inspect folder pages, and undo/redo local edits.
- Save and reopen layout drafts without overwriting existing files.
- Review changes before Apply, save a fresh backup, and compare the full layout returned by the phone afterward.
- Cache real app icons locally and show folder mosaics and artwork in drag previews.

No account, analytics, advertising, or cloud image service is built into the application. Choose **About** beneath **Demo** for the purpose of IconTiller and a summary of its local-data approach.

## Get started on Windows

You need Python **3.12** with Tkinter, Apple's mobile device drivers/software, and a USB cable. Connect one iPhone, unlock it, and accept its Trust prompt when required. Python 3.14 is not the supported development environment for this project.

From the project directory in PowerShell:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements-lock.txt
.\launch.cmd
```

Setup downloads dependencies from PyPI. The application itself uses local files and the USB device connection.

Choose **Read iPhone** to load the connected phone, **Open layout** for a saved draft, or **Demo** to explore sample data without connecting a phone.

On first launch, the client area is **1280 × 850**, with a **850 × 600** minimum. The app remembers its position, size, and maximized state when closed. If the saved display is unavailable or the position is off-screen, it reopens at (0, 0), with its size fitted to the primary display. Windows scaling and borders affect its overall displayed size. App dialogs open centered over the current application window. The folder naming dialog has a roomy, resizable name field and a minimum size of 540 × 300; native file pickers and alerts are owned by the application and positioned by Windows.

## Arrange and apply

1. Read the current iPhone layout.
2. Leave **Insert and shift** selected to drag an app before or after a tile. Choose **Swap positions** to exchange two apps instead.
3. To reach a distant screen while dragging, hold over its number in the **Go to page** row for about half a second, then continue dragging onto that page.
4. Review the draft. Use Undo to reverse an edit or Save draft to keep a local copy.
5. Click **Apply to iPhone** to open a centered, resizable review with a scrollable list of all affected positions and the backup folder. Choose **Apply to iPhone** to confirm or **Cancel** to keep editing. The app saves a backup and independently reads the layout back to verify it.

Insertion preserves each page's existing item count. Entries shift between the source and destination, including whole folders when necessary; those folders retain their contents. This does not create new capacity or add a new page. Reordering closes open folder windows because their locations may change.

The bottom editing controls share one row at normal window widths; the larger selection label moves above them in narrow windows. **Find app** sits directly below **Add page**. **Create / rename folder** opens a chooser even when no tile is selected; choose an app to wrap in a folder or an existing folder to rename. Folder creation and renaming remain local draft edits.

Multiple page reorders can be accumulated before Apply. An exchange involving folder contents is limited to one exact app swap. Other combinations of edits may remain draft-only until they satisfy the write validator.

## Current limits

| Operation | Status |
| --- | --- |
| Same-page and cross-page app swaps | Supported through checked Apply |
| App exchange between a page and a folder | Supported through checked Apply |
| Page insertion with automatic shifting | Supported while preserving page sizes and complete entries |
| Remove an icon to the App Library | Not supported |
| Insert an app into a folder without an exchange | Local draft only |
| Create/rename folders or add pages | Local draft only |
| Dock changes, widget editing, or full-layout restoration | Not enabled for Apply |
| Preserve or edit hidden-page visibility | Not exposed by the current reader |

The view is an ordered layout editor, not a pixel-perfect replica of the phone. Unavailable app artwork and web clips use fallback tiles. Theme and alternate-icon changes without an app version change do not automatically invalidate the icon cache.

Earlier experiments that reduced page occupancy caused iOS to add other entries. Current write validation therefore preserves the dock, page sizes, entry data, and folder metadata, except for a specifically validated app exchange. A mismatch or uncertain result is reported as such and disables further Apply until a fresh read. There is no automatic retry or restore, and a layout snapshot is **not a full-device backup**. See [protocol discovery notes](DISCOVERY.md) for the investigation history.

## Local data and privacy

Device communication uses [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) with Apple's installed USB transport. Icon PNGs come from the connected phone, including apps inside folders. Background requests are bounded and can stop between requests so layout operations can proceed.

For compatibility with earlier versions, local data continues to live under `%LOCALAPPDATA%/iPhoneScreenManager`:

- `Backups`: pre-write snapshots and mismatched read-backs.
- `window.json`: window size, position, display, and maximized preference.
- `Icons`: PNG cache scoped by device identity, app identifier, and app version.
- `WriteTests`, `VisibilityTests`, and `IconTests`: artifacts from developer-run experiments, if used.

Drafts are saved where you choose. They can contain app inventories, arrangements, device name, iOS version, a hashed device identifier, and baseline layout data. This application does not encrypt these files. Pairing records maintained by Apple's software or the library are also sensitive. Do not include personal snapshots, caches, pairing records, or identifying screenshots in issues or commits. Dependencies have not received a full independent security audit.

## Development and validation

The application uses **Python, Tkinter, and Pillow**. Run the automated suite with:

```powershell
.\.venv312\Scripts\python.exe -m unittest -v
```

The current suite contains 55 tests covering draft operations, metadata preservation, write boundaries, identity/stale checks, backup failures, unexpected read-backs, drag behavior, artwork caching, and GUI state. Tests use synthetic layouts and fake phone transports; they do not write to a connected phone.

Live checks have verified swaps, a page/folder exchange, and page insertion against complete read-backs. Several operations were also visually confirmed on the device. These results describe the tested device, not universal compatibility.

Main modules:

| File | Responsibility |
| --- | --- |
| `app.py`, `drag_ui.py` | Tkinter interface, drag feedback, navigation, and background UI updates |
| `editor.py` | Local draft operations and undo/redo |
| `device.py` | USB reads and lossless snapshot persistence |
| `icons.py` | Device icon requests, cache validation, and folder mosaics |
| `safe_swap.py` | Supported write boundary for swaps and page reorders |
| `sync.py` | Preflight checks, durable backups, write transaction, and read-back verification |
| `live_*_test.py` | Explicitly invoked live-device experiments, outside the automated suite |

Read [AGENTS.md](AGENTS.md) before making changes. Use synthetic reproductions for contributions and include validation relevant to the change.

## Application icon

The selected navy-and-mint app-tiles icon appears on the application and its dialogs and is configured for executable builds. The second, tiller-themed concept is retained with a note in [assets/README.md](assets/README.md).

## Windows executable

Running the build creates a portable Windows x64 development package under `dist/IconTiller`. Executables are not stored in this source repository. Extract or copy the entire folder and run `IconTiller.exe`. Its accompanying `README.txt` explains setup and use without Python. See [the packaged user guide](DISTRIBUTION_README.txt). Use `launch.cmd` when running from source.

To build the current source:

```powershell
.\build.ps1
```

The build installs pinned build dependencies, runs tests, packages the app with PyInstaller, and runs a packaged smoke check without accessing a phone. Output is `dist/IconTiller/IconTiller.exe`, its `_internal` folder, `README.txt`, and `LICENSE.txt`; keep the entire folder together. Python is bundled, but Apple's device drivers remain external. This is not a signed installer. Packaged smoke checks do not establish live-device compatibility.

## Contributing

Report bugs and propose changes through [GitHub issues](https://github.com/kurtkluth/IconTiller/issues) and pull requests. Include the application build or commit, Windows version, and steps to reproduce using Demo or synthetic data when possible. Do not upload personal layouts, device identifiers, pairing files, or private screenshots.

Changes to device writes must retain validation, durable backups, and independent read-back. Automated tests must not access a connected phone. See [AGENTS.md](AGENTS.md) for project guidance.

## Author and license

Created by **Kurt Kluth**. Repository: [kurtkluth/IconTiller](https://github.com/kurtkluth/IconTiller).

Copyright (c) 2026 Kurt Kluth. IconTiller's original source code and documentation are distributed under the [MIT License](LICENSE). You may use, modify, and redistribute them, including commercially, provided the copyright and license notice are retained. The software is provided without warranty.

Third-party dependencies retain their own licenses; the MIT License does not relicense them. See [requirements-lock.txt](requirements-lock.txt) for pinned dependencies. Generated icon artwork and its provenance are documented in [assets/README.md](assets/README.md).

This is an independent project and is not affiliated with Apple.
