# Privacy Policy

**Last Updated:** May 19, 2026

Your privacy is extremely important to us. This Privacy Policy describes how the **Urch AI & RNG** Discord bot ("Urch", "we", "us", "our") collects, uses, stores, and protects your information.

By using the bot, you consent to the data practices described in this policy.

---

## 1. Information We Collect & Store

Urch collects only the minimum necessary data to perform its functions (AI dialogue, tool usage, gacha games, and upgrades). All user data is stored locally in an encrypted/secured SQLite database (`bot_data.db`) on our private virtual machine.

### A. Identification Data

- **Discord User ID:** Stored to associate your gacha progression, upgrades, custom settings, and conversation context.
- **Discord Guild (Server) & Channel IDs:** Stored for routing responses, managing server-wide conversation history, and logging rare rolls to dedicated channels.
- **Discord Message IDs:** Stored temporarily to handle edits, deletions, and message reactions (e.g., deleting responses or triggering regenerations).

### B. AI Settings & Customization

- **User Parameters:** Custom configurations like temperature, max completion tokens, and preferred model endpoints.
- **Personas:** Fictional "About You" and custom "AI Instructions" inputs defined by users to customize the AI's behavior.

### C. Conversation History

- **Short-Term Memory:** To provide natural, contextual multi-turn dialogue, Urch stores a brief history of your recent messages and the bot's responses.
- **Automatic Pruning:** The conversation history is automatically capped and pruned to a maximum of **10 messages** (for servers) or **10 messages** (for DMs) to conserve storage and respect privacy.

### D. RNG & Economy Progression

- **Gacha Stats:** Roll counts, highscores (highest rolled rarity), and discovery checklists.
- **Inventory & Currencies:** Fictional item balances, upgrades purchased, and clover token balances.

---

## 2. How Your Data is Used & Transmitted

We never sell, rent, or trade your data. Data is used solely to run the bot.

### A. Third-Party AI Providers

To provide generative AI features (such as conversation, images, audio, video, etc.), Urch transmits text prompts and image URLs (if provided) to external, secure endpoints:

- **Groq API** (for GPT and Qwen models).
- **Pollinations.ai** (for specialized image, audio, video, vision, coding, and other AI models).

_Note: Data sent to these APIs is subject to their respective terms and privacy policies. No personal Discord credentials or payment info are ever sent._

### B. Web Search & OCR Utilities

- When the AI triggers a web search tool, search terms are sent to search engine crawlers. No user identification data is sent alongside the search query.
- Images uploaded for Optical Character Recognition (OCR) are processed locally on our hosting VM using the open-source `Tesseract` engine and are not uploaded to third-party vision APIs unless a vision model is explicitly queried.

---

## 3. Data Control & Deletion Rights

We believe you should have complete control over your data. We provide built-in tools to delete or wipe your records.

### A. Clearing Conversation History (`/wipe`)

- **Direct Messages (DMs):** Any user can execute the `/wipe` command in DMs to instantly delete their entire conversation history from the database.
- **Guilds (Servers):** Discord administrators can run the `/wipe` command in a server to clear the channel memory for that guild.

### B. Complete Account Deletion

If you wish to delete all traces of your account—including roll counts, gacha inventories, custom settings, personas, and historical stats:

- You may request deletion by contacting the bot developers/owners (specifically Discord User ID `477168479812845568` or via the repository support).
- The bot owner can instantly wipe all database tables for a specific user ID via the admin `/safety` dashboard.

---

## 4. Data Security

The `bot_data.db` file is stored locally on a Debian Linux instance hosted on Google Cloud Platform. The environment is secured behind strict SSH keys and firewall rules. However, please remember that no transmission over the internet or database storage is 100% secure.

---

## 5. Contact Us

For any questions regarding this Privacy Policy, terms, or to request manual deletion of your user profile, please open an issue in the [Urch GitHub repository](https://github.com/Likemea/Urch).
