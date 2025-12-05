<p align="center">
  <img src="temp.png" width="220" alt="Transfer Bot Logo">
</p>

------------------------------------------------------------------------

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg) ![Telegram
Bot](https://img.shields.io/badge/Telegram%20Bot-Enabled-0088cc.svg)
![Dropbox](https://img.shields.io/badge/Dropbox-API%20Integration-0061FF.svg)
![Google
Drive](https://img.shields.io/badge/Google%20Drive-OAuth2-yellow.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Contributions](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg)

------------------------------------------------------------------------

## ✨ Features

✔ Supports Google Drive links\
✔ Direct HTTP/HTTPS file URLs\
✔ Chunked upload to Dropbox (large file support)\
✔ Live progress (Speed, %, ETA, CPU/RAM usage)\
✔ Queue system → stable downloads\
✔ `/storage` → check Dropbox usage\
✔ Interactive `/start` UI menu

📌 Power By stw_hypex Engine
------------------------------------------------------------------------

## 🛠️ Tech Stack

-   python-telegram-bot v20\
-   Dropbox API\
-   Google Drive API (OAuth)\
-   psutil (system usage stats)

------------------------------------------------------------------------

## 📁 Project Structure

    ├── main.py
    ├── requirements.txt
    ├── credentials.json   (user added)
    └── token.json         (auto generated)

------------------------------------------------------------------------

## 🔧 Installation

``` bash
pip install -r requirements.txt
```

------------------------------------------------------------------------

## ▶️ Usage

Send any Google Drive or any file URL --- bot will auto transfer to Dropbox!

### Commands:

  Command               Description
  --------------------- -----------------------------------
  `/start`              Show main controls
  `/auth`               Begin Google Drive authentication
  `/code <AUTH_CODE>`   Complete OAuth
  `/storage`            Check Dropbox storage

------------------------------------------------------------------------

## 📜 License

MIT License --- free for everyone!

------------------------------------------------------------------------

## 👨‍💻 Developer

**Made with ❤️ by Anubhav** From India 🇮🇳
