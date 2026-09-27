# Privacy Policy

**Last Updated:** May 19, 2026

This Privacy Policy explains what information **Urch AI & RNG** ("Urch", "we", "us", or "our") stores, why it is stored, and how you can delete it.

By using Urch, you agree to the data practices described below.

---

## 1. Information We Store

Urch stores the information it needs for its AI features, RNG system, settings, and other bot features. Data is stored in a SQLite database (`bot_data.db`) on our private virtual machine.

### A. Discord Information

* **Discord User ID:** Used to associate your account with your rolls, upgrades, settings, and conversation history.
* **Discord Guild and Channel IDs:** Used to keep track of where the bot is being used, manage server conversation history, and log rare rolls.
* **Discord Message IDs:** Stored temporarily for features such as handling message edits, deletions, and reactions.

### B. AI Settings

Urch can store settings that you choose for its AI features, including:

* Temperature and maximum completion tokens.
* Preferred model endpoints.
* Custom personas.
* "About You" and custom AI instruction text.

### C. Conversation History

Urch stores a short amount of conversation history so that its AI features can keep track of recent messages.

Conversation history is limited to **10 messages** and is automatically pruned when the limit is reached. This applies to both servers and DMs.

### D. RNG and Economy Data

Urch stores your game progress, including:

* Roll counts and highest rolled rarity.
* Discovery checklists.
* Inventory items and fictional currencies.
* Purchased upgrades.
* Clover token balances.

---

## 2. How Data Is Used

Your data is used to run Urch and provide its features. We do not sell, rent, or trade your data.

### A. AI Providers

Some Urch features send data to external AI services.

Depending on the feature being used, Urch may send text prompts or image URLs to:

* **Groq API** — Used for GPT and Qwen models.
* **Pollinations.ai** — Used for image, audio, video, vision, coding, and other AI models.

Data sent to these services is subject to their own terms and privacy policies.

Urch does not send your Discord login credentials or payment information to these services.

### B. Web Search and OCR

When Urch performs a web search, the search query is sent to the search service being used. Urch does not intentionally include your Discord User ID or other identifying Discord information in the search query.

Images used with Urch's OCR features are processed locally on the hosting VM using **Tesseract**. They are not sent to a third-party vision API unless you explicitly use a vision model.

---

## 3. Deleting Your Data

Urch provides commands for deleting conversation history and allows you to request deletion of your stored data.

### A. Clearing Conversation History (`/wipe`)

* **DMs:** Users can run `/wipe` in DMs to delete their conversation history from the database.
* **Servers:** Discord administrators can run `/wipe` in a server to clear the conversation history for that guild.

### B. Deleting Your Account Data

If you want your stored Urch data deleted, including rolls, inventories, settings, personas, and stats, you can contact the bot developers/owners.

You can request deletion through:

* Discord User ID: `477168479812845568`
* The Urch GitHub repository

The bot owner can remove a user's stored data through the admin `/safety` dashboard.

---

## 4. Data Security

Urch runs on a Debian Linux virtual machine hosted on Google Cloud Platform.

Access to the server is restricted using SSH keys and firewall rules. However, no system connected to the internet can be guaranteed to be completely secure.

---

## 5. Contact

If you have questions about this Privacy Policy or want to request deletion of your data, you can open an issue in the [Urch GitHub repository](https://github.com/Likemea/Urch).
