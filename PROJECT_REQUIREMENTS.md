# Windows Desktop Floating Window Project Requirements

## Core Requirements

1. Before implementation, first look for similar GitHub projects and use them as references.
2. The final deliverable must be runnable as a Windows `.exe`.
3. The packaged result must stay portable after relocation:
   - Moving the packaged folder to another location must not break the app.
   - The program folder does not need to be placed on the Desktop.
   - The Desktop should only need a launch shortcut that points to the real EXE.
4. Do not depend on fixed absolute paths on the developer machine.

## Engineering Constraints

- Use relative paths based on the executable location.
- If the app needs assets, config files, or data files, load them relative to the executable directory.
- If packaging with Python, prefer a portable `onedir` release by default when external assets are involved.
- Avoid installer-only assumptions unless explicitly requested later.
- Any persistence logic must remain correct when the packaged folder is copied elsewhere and launched through a shortcut.

## Build And Verification Requirements

- The runnable output should be an `.exe`-based release package.
- Verify startup from the original output path.
- Verify startup again after copying the packaged folder to a different install location.
- Verify startup again through a Desktop-style shortcut that points to the relocated EXE.
- Confirm that runtime files such as `floating_window_settings.json` and `portable_runtime_report.json` are still written next to the EXE, not next to the shortcut.

## GitHub Reference Candidates

- FloatTrans
  https://github.com/nickwx97/FloatTrans
  A Windows floating transparent overlay project that explicitly uses an EXE plus local config layout.

- Zebar
  https://github.com/glzr-io/zebar
  A desktop widget / popup project that is useful for floating UI and packaging ideas.

- WindowTop
  https://github.com/WindowTop/WindowTop-App
  A Windows always-on-top utility that is useful for interaction ideas around floating windows.

- OnTop
  https://github.com/NeonOrbit/OnTop
  A lightweight always-on-top Windows utility that is useful for behavior and hotkey references.

## Current Default Decision

- Portable EXE first.
- Folder relocation must be supported.
- Desktop delivery uses a shortcut instead of copying the whole folder to the Desktop.
- GitHub reference check happens before implementation.
