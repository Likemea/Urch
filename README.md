# Urch AI & RNG Bot

![Urch Banner](https://img.shields.io/badge/Urch-AI%20%26%20RNG-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg?style=for-the-badge&logo=discord&logoColor=white)

**Urch** is a powerful, multi-functional Discord bot that seamlessly integrates advanced AI capabilities with an addictive luck-based RNG (Random Number Generation) gacha game. Whether you're looking for an intelligent assistant or a competitive rolling experience, Urch has you covered.

---

## 🚀 Features

### 🧠 1. Advanced AI Assistant (Urch AI)
Urch features a state-of-the-art AI system designed for contextual, multi-turn conversations.
- **Dynamic Model Routing**: Automatically picks the best model for your query (e.g., Llama 3.1 for quick chat, GPT-OSS for complex reasoning).
- **Persistent Memory (RAG)**: Remembers your preferences, facts about you, and previous conversations to provide a truly personalized experience.
- **Agentic Tools**:
  - **Web Search**: Real-time information retrieval from the internet.
  - **Image Generation**: Create stunning visuals directly from text prompts.
- **Custom Personas**: Define how the AI sees you and how it should behave using user and AI personas.

### 🎲 2. RNG & Gacha System
Inspired by "Sol's RNG" style games, Urch offers a deep progression system centered around luck.
- **Massive Rarity Table**: Roll for over 170+ unique rarities, from **Common** (1 in 2) to the near-impossible **Infinity** (1 in 1.79e307).
- **Luck & Progression**: Upgrade your luck, manage your inventory, and climb the global leaderboards.
- **Economy**: Collect rare pulls, upgrade your stats, and showcase your collection.

### 🖼️ 3. Image Utilities & OCR
- **OCR (Optical Character Recognition)**: Extract text from images or screenshots directly within Discord.
- **Dynamic Filters**: Apply "Glitch", "Pixel", and other artistic filters to images and even GIFs.
- **Avatar Tools**: Quickly fetch and manipulate user avatars.

---

## 🛠️ Technology Stack

Urch is built with a modern, asynchronous Python stack:

| Category | Libraries |
| :--- | :--- |
| **Framework** | `discord.py` |
| **AI/ML** | `Groq API`, `requests`, `sentence-transformers` |
| **Database** | `aiosqlite` (Async SQLite) |
| **Image Processing** | `Pillow` (PIL), `numpy` |
| **Computer Vision** | `pytesseract` (Tesseract OCR) |
| **Networking** | `aiohttp`, `requests` |

---

## ⚙️ Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/urch.git
   cd urch
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: You will also need to install the Tesseract OCR engine on your system for OCR features).*

3. **Configure Environment Variables**:
   Create a `.env` file or export the following variables:
   - `BOT_TOKEN`: Your Discord Bot Token.
   - `GROQ_API_KEY`: Your Groq Cloud API Key.

4. **Run the bot**:
   ```bash
   python main.py
   ```

---

## 📜 Project Structure

- `main.py`: The core entry point and AI orchestration logic.
- `commands/`: Contains all Discord slash commands and context menus.
- `functions/`: Core logic for AI tools (Web Search, Image Gen, Memory).
- `upgrades/`: Logic for the RNG gacha progression system.
- `database.py`: Database schema and connection management.
- `utils.py`: Shared helper functions and AI configuration.

---

## 🤝 Credits

Developed by **urghan2**, **Likemea**, and the **Urch AI** team.
