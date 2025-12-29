# Urch/functions/memory.py
import json
import os
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime

try:
    from sentence_transformer import SentenceTransformer # disabled for x10 faster startup
    HAS_EMBEDDINGS = False
    # Load a lightweight, high-performance local model
    print("⏳ Loading Embedding Model (all-MiniLM-L6-v2)...")
    #embedder = SentenceTransformer('all-MiniLM-L6-v2')
    print("✅ Embedding Model Loaded.")
except ImportError:
    HAS_EMBEDDINGS = False
    print("⚠️ 'sentence-transformers' not installed. RAG Memory will be disabled.")

MEMORY_FILE = "memories.json"

class MemoryManager:
    def __init__(self):
        self.memories = self.load_memories()

    def load_memories(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading memories: {e}")
        return {"users": {}, "servers": {}}

    def save_memories(self):
        # atomic save
        temp = MEMORY_FILE + ".tmp"
        with open(temp, 'w', encoding='utf-8') as f:
            json.dump(self.memories, f, indent=2)
        os.replace(temp, MEMORY_FILE)

    def _get_embedding(self, text: str) -> List[float]:
        if not HAS_EMBEDDINGS:
            return []
        return embedder.encode(text).tolist()

    def get_all_memories(self, user_id: str) -> List[Dict]:
        uid = str(user_id)
        return self.memories["users"].get(uid, {}).get("entries", [])

    def add_memory(self, user_id: str, text: str, source: str = "summary"):
        if not HAS_EMBEDDINGS:
            return

        uid = str(user_id)
        if uid not in self.memories["users"]:
            self.memories["users"][uid] = {"entries": []}

        embedding = self._get_embedding(text)
        
        entry = {
            "text": text,
            "embedding": embedding,
            "timestamp": datetime.now().isoformat(),
            "source": source
        }
        
        self.memories["users"][uid]["entries"].append(entry)
        self.save_memories()
        print(f"[Memory] Added for {uid}: {text[:30]}...")

    def add_memory_manual(self, user_id: str, text: str) -> bool:
        """Manually add a memory (used by Settings)."""
        if not HAS_EMBEDDINGS:
            return False
        try:
            self.add_memory(user_id, text, source="user_manual")
            return True
        except Exception as e:
            print(f"Error adding memory: {e}")
            return False

    def edit_memory(self, user_id: str, index: int, new_text: str) -> bool:
        """Edits the text of a memory and regenerates its embedding."""
        uid = str(user_id)
        if uid not in self.memories["users"]:
            return False
        
        entries = self.memories["users"][uid]["entries"]
        if 0 <= index < len(entries):
            if not HAS_EMBEDDINGS:
                return False
            
            entries[index]["text"] = new_text
            entries[index]["embedding"] = self._get_embedding(new_text)
            self.save_memories()
            return True
        return False

    def delete_memory(self, user_id: str, index: int) -> bool:
        """Deletes a memory at the specific index."""
        uid = str(user_id)
        if uid not in self.memories["users"]:
            return False
        
        entries = self.memories["users"][uid]["entries"]
        if 0 <= index < len(entries):
            entries.pop(index)
            self.save_memories()
            return True
        return False

    def get_relevant_memories(self, user_id: str, query: str, limit: int = 1, threshold: float = 0.5) -> List[str]:
        if not HAS_EMBEDDINGS:
            return []

        uid = str(user_id)
        user_mem = self.memories["users"].get(uid, {})
        entries = user_mem.get("entries", [])

        if not entries:
            return []

        query_vec = embedder.encode(query)

        scores = []
        for entry in entries:
            mem_vec = np.array(entry["embedding"])
            norm_q = np.linalg.norm(query_vec)
            norm_m = np.linalg.norm(mem_vec)
            
            if norm_q == 0 or norm_m == 0:
                score = 0
            else:
                score = np.dot(query_vec, mem_vec) / (norm_q * norm_m)
            
            scores.append((score, entry["text"]))

        scores.sort(key=lambda x: x[0], reverse=True)

        relevant = [s[1] for s in scores if s[0] > threshold][:limit]
        
        if relevant:
            print(f"[Memory] Retrieved for {uid} (>{threshold}): found {len(relevant)}")
            
        return relevant

memory_manager = MemoryManager()