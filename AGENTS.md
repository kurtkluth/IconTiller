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
- The public repository is [kurtkluth/IconTiller](https://github.com/kurtkluth/IconTiller), with `origin` configured and `main` as the default branch. The selected license is MIT, copyright 2026 Kurt Kluth; retain [LICENSE](LICENSE).
- Public history starts from a sanitized snapshot. Older local development branches contain private historical layout notes. Keep them local; never push all branches, mirror the repository, or merge the private history into public branches.
- Use the repository's configured GitHub no-reply author email for public commits.
- Publishing executable release assets requires a user request. Do not infer release publication from source publication or a local build request.

## UI and writing decisions

- Use a standard ASCII hyphen (-), not an em dash or en dash, in authored user-facing text and responses. Preserve exact source quotations and code syntax when needed.
- The main heading is `IconTiller`, the subtitle is `Arrange your apps. Keep your data local.`, and the title bar is `IconTiller - App Layout Editor`.
- Keep dialogs centered over the application's current position. Keep the larger folder chooser, aligned search-result columns, readable Apply review, and About dialog.
- Keep Find app aligned under Add page. Bottom editing controls share one row at normal widths; the selection label moves above them at narrow widths.
- Window size, position, and maximized state are maintained by `window_state.py`. A missing saved monitor falls back to (0, 0). Preferences stay in the legacy local-data directory.
- The selected icon is [assets/icontiller.png](assets/icontiller.png). Supply multiple PhotoImage sizes for Tk title bars; do not override them with iconbitmap. The ICO is used for executable packaging. Keep the alternate design and note in [assets/README.md](assets/README.md).
- Kurt explicitly approved [assets/icontiller-app.png](assets/icontiller-app.png) for the public README. That approval applies to this supplied image, not other personal screenshots or layouts.

## End-of-day handoff - 2026-09-12

- Initial public source publication (PR #1) and the branded README with screenshot (PR #2) are merged into `main`. Start future feature branches from current `origin/main`.
- The latest full automated suite passed all 55 tests. The packaged Windows smoke check also passed without accessing a phone. Later publication and README changes were documentation/assets/build-copy changes, checked with diffs and local links.
- A local Windows x64 portable build is in `dist/IconTiller`, with a companion ZIP in `dist`. These files are ignored by Git and have not been published as GitHub release assets.
- That ZIP predates the MIT/publication documentation updates. Before distributing a new release, rebuild with `build.ps1`, check `build/packaged-smoke.json`, and verify the package includes the current `README.txt` and `LICENSE.txt`. Do not assume the earlier ZIP contains them both.
- [DISTRIBUTION_README.txt](DISTRIBUTION_README.txt) is the maintained end-user setup and usage guide; `build.ps1` copies it beside the executable as `README.txt`.
- No new live-device testing was performed for the UI, artwork, About, window-preference, or packaging changes. Existing write restrictions and unresolved App Library removal still apply.
- No further implementation task is queued. Resume from Kurt's next request; do not publish a release or broaden device writes automatically.
