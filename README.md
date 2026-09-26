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

## Features

### 1. AI Assistant

Urch has an AI chat system with multiple models.

* **Model Routing:** A `Qwen3.8 27B` router picks a model based on the prompt.
* **Model Tiers:** Models are available through **Groq** and **Pollinations.ai**:

  * **Light:** `DeepSeek V4 Flash`
  * **Medium:** `Qwen3.8 27B`
  * **Heavy:** `GPT-5.6 Luna`
* **Personas:** Save up to 10 custom personas using "About You" and "Custom Instructions".
* **Memory:** The bot keeps the last 10 messages of conversation history.

### 2. AI Safety

Urch checks both user messages and AI responses.

* **Safety Model:** Uses `gpt-oss-safeguard-20b`, with `qwen-safety` as a fallback.
* **Classifications:** Each interaction can be marked as:

  * `safe`: Normal operation.
  * `unsafe_input`: The user's message is considered unsafe.
  * `unsafe_output`: The AI generated an unsafe response.
  * `unsafe_both`: Both the input and output were flagged.
* **Blocking:** Flagged responses are blocked and the channel is shown a policy warning.

### 3. Tools

Urch can use several external tools:

* **🔎 Web Search:** Search the internet for current information.
* **🎨 Image Generation:** Generate images using `DreamShaper`, `FLUX Schnell`, `Z-Image Turbo`, etc.
* **🐍 Code Execution:** Run Python code for various tasks, such as math, data analysis, plotting, string manipulation, or file operations.

### 4. RNG & Gacha

Inspired by **Sol's RNG**, Urch has its own RNG game.

* **170+ Unique Rarities:** From **Common** (1 in 2) to **Infinity** (1 in 1.79e308).
* **Luck Upgrades:** Increase your luck multiplier.
* **Roll Upgrades:** Improve roll rates, unlock multi-rolls, and increase rolling capacity.
* **Clover Upgrades:** Increase clover earnings. Unlocked at 1,000+ Luck.
* **Economy & Leaderboard:** Collect items, complete the checklist, earn clovers, and compete on the leaderboards.
* **🤖 Autoroll:** `/autoroll` can roll automatically in the background. Rare pulls can be logged to a webhook channel.

### 5. Image Utilities

* **OCR:** Extract text from uploaded images using a local Tesseract pipeline.
* **Image Filters:** Apply effects such as **Glitch**, **Pixelate**, and color transformations to images and GIFs.

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
| 🧠 **AI Settings**     | `/settings`    | Change model settings, token limits, and personas.                    |
|                        | `/ask`         | Ask a single-turn question.                                           |
|                        | `/wipe`        | Clear your short-term message history.                                |
| 🛡️ **Administration** | `/safety`      | Staff-only settings for the AI system, rate limits, and user records. |
| 🖼️ **Utilities**      | `/ocr`         | Extract text from an image.                                           |
|                        | `/filter`      | Apply a visual filter.                                                |
|                        | `/glitch`      | Glitch an image or animated GIF.                                      |
|                        | `/pixel`       | Pixelate an image or animated GIF.                                    |
|                        | `/txt2img`     | Generate an image using a selected model.                             |
|                        | `/txt2aud`     | Generate speech or music.                                             |

---

## 🛠️ Technology Stack

Urch is written in asynchronous Python.

* **Framework:** `discord.py 2.6.4`
* **Database:** `aiosqlite`
* **AI:** `Groq API`, `Pollinations.ai`
* **OCR:** `pytesseract`
* **Image Processing:** `Pillow` & `numpy`
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
GROQ_API_KEY=your_groq_api_key_here
POLLINATIONS_API_KEY=optional_pollinations_key_here
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

## 🌐 GitHub Pages Integration

You can use GitHub Pages to host the Terms of Service and Privacy Policy.

1. In the repository, open **Settings** → **Pages**.
2. Set the source to **Deploy from a branch**.
3. Select your main branch and `/` as the directory.
4. Click **Save**.

The files can then be accessed through your GitHub Pages site:

* **Terms of Service:** `https://<your-username>.github.io/Urch/TERMS.md`
* **Privacy Policy:** `https://<your-username>.github.io/Urch/PRIVACY.md`
