# Project working agreements

## Scope and architecture

IconTiller is a Windows desktop iPhone Home Screen editor written in Python 3.12 with Tkinter and Pillow. Follow the user's current instructions and established session authorization; continue routine implementation and verification without repeated permission questions.

- Keep local draft transformations in `editor.py`, USB/snapshot work in `device.py`, and artwork/cache work in `icons.py`.
- Keep supported-write validation in `safe_swap.py` and transaction safeguards in `sync.py`. Despite its historical name, `safe_swap.py` handles both app exchanges and page reorders.
- Keep Tk operations and PhotoImage creation on the UI thread. Background workers must not update widgets directly. Preserve image references and cancel scheduled drag/icon callbacks when their owning view closes or changes.
- Keep drag feedback responsive. Repaint affected tiles rather than rebuilding the whole layout after every drop. Preserve scroll position and close stale folder views when folder positions change.
- Prefer simple changes consistent with the existing codebase. Do not change language, UI framework, project name, or packaging strategy without a task that calls for it.

## Device writes

- Ordinary automated tests must use synthetic snapshots and fake transports, never a connected user's phone.
- Live reads and writes should follow the user's authorized task scope. Existing explicit session authorization for live tests persists; do not treat this file as requiring another confirmation for already authorized work.
- Before an authorized live write, capture an identified baseline and make the exact intended change reviewable. Preserve capacity, identity and stale-layout checks, durable backup before writing, and full independent read-back afterward.
- Current Apply permits one exact ordinary-app exchange or a permutation of complete Home Screen entries with unchanged dock and page sizes. Preserve unknown metadata and keep unsupported entries stationary.
- Do not loosen validation merely to make a test pass. Do not label a successful API reply as a verified layout change. Treat read-back differences as a mismatch and preserve the observations.
- Do not automatically retry or restore after a mismatch. A layout snapshot is not a full-device backup. Follow up from the actual observed state.
- App Library removal is unresolved. In this project, user-requested removal means keeping the app installed and removing only its Home Screen placement, unless the user explicitly says otherwise. Do not substitute uninstalling the app.
- Hidden-page preservation is not a current prerequisite: the user accepts pages becoming visible. This does not authorize unrelated placement changes.

## Privacy and data

- Keep the runtime local: no telemetry, cloud uploads, account sign-in, or external image service unless expressly requested.
- Keep device snapshots, app inventories, pairing records, backups, caches, and private screenshots outside Git. Use synthetic fixtures in tests and documentation examples.
- Do not commit raw device identifiers, secrets, credentials, or personal layouts. Review staged content before committing and review history before public publication.
- Preserve the legacy iPhoneScreenManager local-data directory so existing backups and artwork remain accessible after the IconTiller rename.
- Use device/app-version-scoped caches. Validate image format and dimensions, bound USB requests, and retain fallback artwork on failure.
- Preserve user files and unrelated changes. Never overwrite an existing snapshot or silently discard an unsaved draft when opening a revised UI.

## Verification

Use the project's Python environment:

```powershell
.\.venv312\Scripts\python.exe -m unittest -v
```

Run relevant tests for changes and the complete suite when changing shared editor/write behavior. Add meaningful tests for new invariants and failure modes; documentation-only edits need a diff/link check, not a full runtime test. Do not broaden device writes as part of routine UI testing.

Use `build.ps1` when an executable build is requested. Check its packaged smoke result. Source and the previously built executable may differ; state which was tested, and do not imply packaged live USB access was verified from import-only checks.

Update README feature descriptions and limitations when behavior changes. Keep historical experiments in `DISCOVERY.md`, not mixed into the current feature guide. Keep implementation details out of user-facing controls unless they help the user decide what to do.

## Git and publication

- Create a `codex/` feature branch before implementation, or continue the relevant existing feature branch.
- Commit meaningful milestones with clear messages, scoped to the requested work.
- Push checkpoints to the configured remote feature branch and open a pull request when ready for review.
- Wait for Kurt's explicit approval before merging; never merge or enable auto-merge without it.
- If there is no repository or remote, report that limitation rather than creating or publishing one without direction.
- The intended GitHub owner is `kurtkluth`; the selected project name is IconTiller. Do not rename, create the public repository, choose a license, publish release artifacts, or claim license/name availability solely from these notes. Follow the user's selection and task authorization.
