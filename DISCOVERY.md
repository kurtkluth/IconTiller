# Layout protocol discovery - 2026-09-12

These notes summarize historical experiments. They describe evidence and limitations, not the current feature list; see README.md for supported behavior. Personal app names and placements have been omitted from the public notes.

## Subsequent exchange and insertion results

Same-page, cross-page, and page/folder app exchanges produced independent read-backs that matched the requested complete layout. The user also confirmed the visible changes. These results support restricted exchanges on the tested device; they do not establish general compatibility or removal-to-App-Library support.

In a folder-insertion experiment, the requested move occurred, but iOS filled the newly vacant Home Screen slot with an additional entry. The full result therefore did not match the requested layout. A later read confirmed the observed state. No automatic restore or retry was attempted.

This is why current Apply validation preserves page occupancy and complete entry data. No inference is made about the additional entry's prior visibility or installation state.

## Result

Apple's Windows transport is available. A lossless AirTraffic layout operation or USB page-visibility switch has **not** been established. This historical discovery pass did not justify broadening device writes. This discovery pass inspected local binaries as data, public source code, and an existing snapshot; it sent no device commands, loaded no Apple DLL into a process, and executed no downloaded code.

## Local evidence

The installed x64 Apple Mobile Device Support directory contains `MobileDevice.dll` and `AirTrafficHost.dll`. Windows reports a valid Apple Inc. signature for AirTrafficHost. MobileDevice's observed file version is 1827.100.17.2.

AirTrafficHost contains `com.apple.atc` and synchronization vocabulary including `HostInfo`, `Dataclasses`, `DataclassAnchors`, `RequestingSync`, `SyncTypes`, and `FinishedSyncingMetadata`. Its exports include connection creation, reading/sending messages, requesting synchronization, and reporting asset completion. These are evidence of a general synchronization interface, not a layout schema. No icon-layout or hidden-page command was identified in the inspected printable strings and exports. Absence from this scan does not prove absence from the protocol.

MobileDevice contains `SpringBoardIconLayoutData` near installation/streaming-archive options such as `InstallTransferredDirectory` and `InstallOptionsDictionary`. Its role is unknown. It must not be assumed to be a readable lockdown property or a page-visibility switch.

SHA-256 fingerprints for reproducibility:

- AirTrafficHost.dll: `0d38b01c21d57a9f3ca32c15d4b2b8aa0557d43a724b4745f1fb122322f4eecd`
- MobileDevice.dll: `de08e3324f24dbcbc0597b78f797670f18f53faa58819cda3c32fa3cebcb9d39`

## Configurator claim audit

Apple documents a Home Screen layout editor in [Configurator for Mac](https://support.apple.com/en-ae/guide/apple-configurator-mac/cadbf9c2a0/mac). That documentation does not identify its transport or promise preservation of page visibility.

The [iphone-layout-tool repository](https://github.com/tmad4000/iphone-layout-tool/tree/4d9ca9eb19bc451b61ba61d812c4e9995dab1752) claims Configurator uses AirTraffic and reports testing on iOS 17. Its tree contains only a README, converter, shell wrapper, and gitignore. No protocol capture, message schema, or AirTraffic implementation is supplied. Its broad claim that SpringBoard writes are ignored does not describe our iOS 27 experiment, which changed the returned layout.

The [converter source](https://github.com/tmad4000/iphone-layout-tool/blob/4d9ca9eb19bc451b61ba61d812c4e9995dab1752/convert_layout.py) treats any dictionary with `iconLists` as a folder. A reviewed snapshot contained ordinary app dictionaries with that field, so inspection showed they would become folder-shaped entries. The conversion also drops unknown fields, including folder metadata. We did not run this converter or apply its output.

The [go-ios implementation](https://github.com/danielpaulus/go-ios/blob/7e82aa2c83959beadca3f45993398d2a5c236321/ios/springboard/client.go) uses `com.apple.springboardservices` with `getIconState` and `setIconState`. This is the same command family already used here, not evidence for a separate AirTraffic solution.

## Visibility and prior test interpretation

The earlier user-performed page-visibility toggle produced identical before/after `getIconState` snapshots. This establishes that this particular read did not reveal that visibility change. It does not establish which returned pages are visible or that every hidden page is always returned.

Additional serialized leaf entries from an earlier write are not proof that apps were installed or became visible. The original on-device layout has not been restored. Private recovery lists must not be treated as instructions to remove apps without checking their actual state.

## Next evidence needed

Scope clarified by Kurt after discovery: all Home Screen pages may become visible. Preserving hidden-page state is not a release prerequisite. Required actions are moving/reordering icons and removing a Home Screen icon while keeping the app installed and available in the App Library. Uninstallation is not the requested removal behavior. Acceptance of visible pages does not imply acceptance of repopulating removed icons or unrelated arrangement changes.

1. Obtain a trace identifying the actual service and layout messages used by a current Configurator build, with its version recorded. The repository's prose is insufficient to construct a Windows request.
2. Prioritize App Library-only placement: establish a removal operation that keeps the app installed and does not put its icon back onto a page. Also determine preservation of unrelated positions, widgets, and folder metadata. A successful command reply alone is insufficient.
3. Test on a disposable device with a known layout: one move, then removal of one icon to the App Library, then another move to check that removal persists. Verify installed-app status, actual screen placement, and returned data. Pages becoming visible is acceptable; removed icons returning is not.

Apple lists [AirTraffic logging instructions](https://developer.apple.com/feedback-assistant/profiles-and-logs/). The linked PDF redirected to Apple sign-in during this pass; its contents were not accessible. Logging has not been enabled. A trace may help establish the service, but is not guaranteed to contain a complete message payload.

The missing artifact is a verified protocol trace/schema, not another USB driver. No working Windows AirTraffic layout implementation was found in the sources inspected; this is a bounded search result, not a claim that none exists.
