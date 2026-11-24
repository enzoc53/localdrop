# LocalDrop

**[🇫🇷 Version française ci-dessous](#-version-française)**

Peer-to-peer local file sharing over Wi-Fi — no cloud, no account, and nothing to install on the other device. Compatible with **Windows, macOS, and Linux**.

<img width="757" height="583" alt="localdrop le vrai" src="https://github.com/user-attachments/assets/e66c8648-1cc9-40ad-94c0-c666792cb9e2" />


## Features

* **Fast sending:** Select individual files or entire folders (automatically compressed into a `.zip` archive).
* **Direct receiving:** Enable receiving to save files sent from a phone or another computer straight into your *Downloads* folder.
* **QR code connection:** Open the web interface on the other device with a single scan, featuring drag-and-drop uploads.
* **100% local & secure:** No files ever leave your local Wi-Fi network, and a unique session token is generated on every startup.

## Installation

Go to the **[Releases](../../releases)** page and download the build for your operating system:

* **Windows:** Download `LocalDrop.exe` and double-click it. *(Since the app is not digitally signed, Windows SmartScreen may show a warning: click **More info** → **Run anyway**).*
* **macOS:** Download `LocalDrop-macos.zip`, unzip it, then **right-click → Open** on first launch.
* **Linux:** Download `LocalDrop`, make it executable (`chmod +x LocalDrop`), and run it (`./LocalDrop`).

### Run from source

```bash
pip install qrcode
python3 localdrop_app.py
