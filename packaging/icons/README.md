# Application icons

**These files are generated. Do not edit them by hand.**

Run the generator from the repository root to rebuild them:

```bash
python scripts/generate_icons.py
```

| File | Platform | Contents |
|---|---|---|
| `edsg.ico` | Windows | 16, 24, 32, 48, 64, 128, 256 px |
| `edsg.icns` | macOS | 16, 32, 64, 128, 256, 512, 1024 px |
| `edsg.png` | Linux | 512 px, for `.desktop` entries |

The build specifications reference `edsg.ico` and `edsg.icns` and fall back to
no icon when they are absent, so a build without them still succeeds — it just
produces a binary carrying the default system icon.

Both binaries share one icon set. To give the organizer and participant builds
different icons, add `edsg-organizer.*` and `edsg-participant.*` here and point
the `ICON` and `ICNS` paths in each spec file at them.
