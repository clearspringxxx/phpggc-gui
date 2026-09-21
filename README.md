# PHPGGC GUI

English | [中文](README.zh-CN.md)

A portable, out-of-the-box **GUI toolbox for PHPGGC on Windows**.

---

## Why

[PHPGGC](https://github.com/ambionics/phpggc) is the most complete collection of PHP unserialize() gadget chains — but it ships as a Linux/macOS command-line tool only. On Windows you have to install PHP and deal with settings like `phar.readonly` yourself, which is a real barrier.

**PHPGGC GUI solves exactly this**: both the PHP and Python runtimes are bundled inside the project. Clone it, double-click, done — no PATH changes, no registry edits, no system configuration touched.

<a href="picture/homepage.png"><img src="picture/homepage.png" alt="PHPGGC GUI main window" width="100%" /></a>

## Features

- **Native desktop UI** (PySide6) — dark, frameless, draggable title bar, double-click to maximize
- **45 frameworks / 170+ chains** — tree view, live search, filter by framework / type / vector
- **Dynamic parameter forms** — chain description and argument names parsed automatically
- **All options** — base64 / URL / JSON encoding, fast-destruct, ascii-strings, plus-numbers, session-encode, PHAR generation (incl. JPEG polyglot)
- **History** — last 200 payloads saved automatically, copy / export anytime
- **Custom command** — passthrough for any raw phpggc CLI arguments (e.g. `-w` wrapper)
- **Fully portable** — runtimes bundled; copy the folder to any machine and it works

## Getting Started

1. Double-click **`start.bat`**
2. If something breaks, launch via `debug mode.bat` to see the console

**Requirements**: Windows 10/11 x64 (runtimes are bundled, nothing to install)

## How It Works

- The GUI is written in **PySide6 (Qt6)** and drives `php phpggc` as a subprocess. phpggc itself is untouched — upgrade by replacing the `phpggc/` folder
- PHP runs as `php -n -d phar.readonly=0`: every php.ini is ignored, and the required extensions (phar/zlib/json/hash) are compiled into the Windows build — hence zero configuration
- Chain list comes from `phpggc -l`, per-chain arguments and descriptions from `phpggc -i <chain>`, payload generation is the plain CLI call
- Config / history live in `data/`, created on first run

## Layout

```
phpggc-gui/
├── app/                 # GUI source (PySide6)
├── runtime/
│   ├── php/             # bundled portable PHP
│   └── python/          # bundled Python + PySide6
├── phpggc/              # upstream phpggc (unmodified)
├── picture/             # screenshots for this README
├── tests/               # frameless window interaction tests
├── start.bat            # launch
└── debug mode.bat       # launch with console
```

> Note: most of the repo size comes from `runtime/` (~340MB). Source-only users may delete it and provide their own runtimes; keeping it is recommended for normal use.

## Disclaimer

This project is intended for **authorized** security testing, CTF competitions and security research only. Any consequences caused by using this tool are borne by the user.

## Credits

- [PHPGGC](https://github.com/ambionics/phpggc) — the gadget chain library by [ambionics](https://www.ambionics.io/); this project is adapted from it to work on Windows
