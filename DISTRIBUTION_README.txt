IconTiller - App Layout Editor
Arrange your apps. Keep your data local.

64-BIT WINDOWS PORTABLE DEVELOPMENT PREVIEW

IconTiller lets you arrange iPhone Home Screen apps from your Windows
computer using a local USB connection. This build targets Windows x64.
The package includes Python and the application dependencies. You do not
need to install Python.

1. SET UP AND LAUNCH

- Extract the entire ZIP into a folder on your computer before running it.
  If you received an already-extracted folder, keep its contents together.
- The folder must contain IconTiller.exe, the _internal folder, and this
  README.txt. Do not move the executable out of that folder.
- Apple mobile device software/drivers must already be installed for USB
  access. These drivers are not included in this package.
- Double-click IconTiller.exe. This is a portable app, not an installer.
  You can create a shortcut to the executable for easier access.
- Choose Demo to try the editor without a phone.

This preview is not digitally signed. Windows may show a publisher warning.
Only run a copy obtained from a source you trust.

2. CONNECT YOUR IPHONE

- Connect one iPhone with a USB data cable.
- Unlock the iPhone and accept its Trust prompt if one appears.
- Click Read iPhone. Wait for the layout and app artwork to load.
- Keep the phone connected during reads and Apply operations.

If the phone is not detected, check the cable and USB port, unlock the
phone, and check that Apple's installed software can recognize it.
Reconnect and try Read iPhone again. Demo remains available without USB.

3. ARRANGE YOUR APPS

- Click an app or folder to select it.
- Insert and shift: drag an app between tiles. Intervening entries shift
  across pages while each page keeps its existing item count.
- Swap positions: select this mode, then drag one app onto another.
  You can also use Swap selected with to choose the other app from a list.
- Hold a dragged item over a page number to jump to that page. Drag near
  the top or bottom edge to scroll. Press Escape to cancel a drag.
- Find app searches names and identifiers, including apps inside folders.
- Use Undo and Redo to revise local edits.
- Save draft writes a new local layout file. Open layout reopens one.
  Existing files are not overwritten when saving a draft.

Changes remain in the local draft until you use Apply to iPhone.

4. REVIEW AND APPLY

- Start with a fresh Read iPhone, make a supported edit, then click
  Apply to iPhone.
- Review all affected positions, the phone name, and the backup folder.
- Click Apply to iPhone in the review dialog to confirm, or Cancel.
- The app saves a fresh layout backup before writing, then independently
  reads the phone again and compares the full layout.
- Wait for the final result. A successful request alone is not proof that
  the layout changed as intended.

If the result is uncertain or mismatched, Apply is disabled until a fresh
read. Inspect the phone and use Read iPhone to see its actual state.
IconTiller does not automatically retry or restore after a mismatch.
A layout snapshot is not a full-device backup.

5. CURRENT LIMITATIONS

Supported Apply operations:
- One exact ordinary-app exchange outside the dock, including an exchange
  between a Home Screen page and an existing folder.
- Reordering complete Home Screen entries while preserving the dock,
  existing page sizes, and entry data. Multiple page reorders may be
  accumulated before Apply.

Local draft only:
- Creating or renaming folders, adding pages, and moving an app into a
  folder without an exchange. These edits can prevent Apply from becoming
  available. Undo them or reopen a compatible draft to apply supported edits.

Not enabled:
- Removing an icon to the App Library, dock changes, widget editing, and
  full-layout restoration. Restore previous layout is disabled.
- Hidden-page visibility is not preserved or edited by the current reader;
  pages may become visible after an Apply.

The layout is an ordered editor, not a pixel-perfect phone preview.
Compatibility has been tested with one phone reporting iOS 27.0.
Broader device and iOS compatibility is not established.

6. PRIVACY AND LOCAL FILES

IconTiller uses local files and the USB connection. No account, telemetry,
cloud uploads, or external image service is built into the app. Installing
Apple software or downloading this package may require internet access.

For compatibility, local files are stored under:
  %LOCALAPPDATA%\iPhoneScreenManager

Paste that path into File Explorer's address bar to open it.
- Backups: pre-write layouts and mismatched read-backs.
- Icons: artwork cached by device and app version.
- window.json: remembered window size, position, and maximized state.

Drafts are saved wherever you choose. Drafts and backups may contain app
inventories and personal layout/device information and are not encrypted.
Keep them private. Only share the supplied application package, not your
personal data folder or saved drafts.

7. WINDOW AND APPLICATION CONTROLS

The app remembers its size, location, and maximized state when closed.
If the saved display is missing, it opens at (0, 0) on the primary display.
Dialogs open centered over the application. About explains its purpose.

To update, close IconTiller and extract the new package into a separate
folder. Keep each executable with its matching _internal folder. Local
backups, icons, and preferences remain in the location described above.
To remove the portable app, close it and delete its extracted application
folder. Personal drafts and the local data folder remain on your computer.

8. VALIDATION OF THIS PACKAGE

The build runs the automated test suite and a packaged smoke check for
GUI startup, search, draft operations, saved layouts, and dependency imports.
Those checks do not access a phone. They do not establish live USB
compatibility for this executable on your computer.

IconTiller is an independent project and is not affiliated with Apple.

AUTHOR AND LICENSE

Created by Kurt Kluth. Copyright (c) 2026 Kurt Kluth.
IconTiller source code and documentation are licensed under the MIT License.
See LICENSE.txt. Third-party dependencies retain their own licenses.
Source: https://github.com/kurtkluth/IconTiller
