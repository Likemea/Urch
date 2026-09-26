# Urch

<div align="center">

![Urch Banner](https://img.shields.io/badge/Urch-AI%20%26%20RNG-5765F2?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/python-3.11.2-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Discord.py](https://img.shields.io/badge/discord.py-2.6.4-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![Database](https://img.shields.io/badge/SQLite-WAL%20Mode-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Hosting](https://img.shields.io/badge/Google%20Cloud-e2--micro%20Debian-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)
![Process Manager](https://img.shields.io/badge/PM2-Managed-2B037A?style=for-the-badge&logo=pm2&logoColor=white)

**Urch** is a silly Discord bot inspired by RNG/aura rolling games. It has over 200+ rarities, 20+ upgrades, and other neat stuff like checklist, clovers, leaderboard, and potions.

[Terms of Service](TERMS.md) • [Privacy Policy](PRIVACY.md)

</div>

---

### 1. RNG & Gacha

Inspired by **Sol's RNG**, Urch has its own RNG game.

* **170+ Unique Rarities:** From **Common** (1 in 2) to **Infinity** (1 in 1.79e308).
* **Luck Upgrades:** Increase your luck multiplier.
* **Roll Upgrades:** Improve roll rates, unlock multi-rolls, and increase rolling capacity.
* **Clover Upgrades:** Increase clover earnings. Unlocked at 1,000+ Luck.
* **Economy & Leaderboard:** Collect items, complete the checklist, earn clovers, and compete on the leaderboards.
* **Autoroll:** `/autoroll` can roll automatically in the background. Rare pulls can be logged to a webhook channel.

### 2. Image Utilities

* **OCR:** Extract text from uploaded images using Tesseract.
* **Image Filters:** Apply effects such as **Glitch**, **Pixelate**, etc. to images and GIFs.

---

## 🎮 Command Index

| Category               | Command        | Description                                                           |
| :--------------------- | :------------- | :-------------------------------------------------------------------- |
| 🎲 **RNG & Gacha**     | `/roll`        | Roll for a rarity and increase your luck.                             |
|                        | `/autoroll`    | Toggle background rolling.                                            |
|                        | `/upgrades`    | Open the upgrade menu.                                                |
|                        | `/inventory`   | View your rolled rarities.                                            |
|                        | `/checklist`   | View your checklist and its bonuses.                                  |
|                        | `/leaderboard` | View global leaderboards.                                             |
|                        | `/stats`       | View bot stats such as uptime, latency, servers, CPU, and RAM usage.  |
| 🧠 **Urch Settings**   | `/settings`    | Change model settings, token limits, and personas.                    |
|                        | `/ask`         | Ask a single question.                                                |
|                        | `/wipe`        | Clear your message history.                                           |
| 🛡️ **Administration**  | `/safety`      | Staff-only settings for rate limits and user records.                 |
| 🖼️ **Utilities**      | `/ocr`         | Extract text from an image.                                           |
|                        | `/filter`      | Apply a selected filter.                                              |
|                        | `/glitch`      | Glitch an image or GIF.                                               |
|                        | `/pixel`       | Pixelate an image or GIF.                                             |

---

## 🛠️ Technology Stack

Urch is written in asynchronous Python.

* **Framework:** `discord.py 2.6.4`
* **Database:** `aiosqlite`
* **OCR:** `pytesseract`
* **Image Processing:** `Pillow`, `numpy`, `ffmpeg`
* **Process Manager:** `PM2`

---

## ⚙️ Installation & Self-Hosting Guide

### Prerequisites

* **Python 3.11.2** (or later)
* **Tesseract OCR** installed on the host system:

  * **Debian/Ubuntu:** `sudo apt install tesseract-ocr`
  * **Windows:** Install Tesseract from UB Mannheim and add it to your PATH.
* A **Discord Developer Account** with a registered bot and **Message Content Intent** enabled.

### 1. Clone & Set Up Directory

```bash
git clone https://github.com/Likemea/Urch.git
cd Urch
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the root directory:

```env
BOT_TOKEN=your_discord_bot_token_here
```

### 4. Database Setup

Urch automatically creates `bot_data.db` and its tables on first startup.

### 5. Running the Bot

For local testing:

```bash
python main.py
```

For a server, you can use PM2:

```bash
pm2 start main.py --name "urch-bot" --interpreter python3
pm2 save
pm2 startup
```

---