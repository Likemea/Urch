# Urch/rate_limiter.py
"""
Per-user token bucket rate limiter with dynamic global scaling.
- Per-user RPS and RPM limits, configurable per model tier.
- Global dynamic multiplier: loosens when few users are active, tightens under load.
- All settings are runtime-adjustable via the /safety control panel.
"""
import time
from collections import defaultdict

# ───────────────────────────────
# MODEL TIERS
# ───────────────────────────────
# tier_key -> { models: [...], rps: float, rpm: int }
DEFAULT_TIER_LIMITS = {
    "light": {
        "models": [
            "community/ZapGaming/llama3.1-8b-xturbo",
            "vendouple/muse-glimmer-30b:free",
            "mikl-shortcuts/ministral-3",
            "community/AkshayCoder48/gemini-2.5-flash",
            "community/AkshayCoder48/gpt-4o-latest",
            "community/AkshayCoder48/deepseek-v3",
            "community/AkshayCoder48/step-3.7-flash",
            "YoannDev90/poolside-laguna-s-2.1:free",
            "openai",
            "nova-fast",
            "nemotron-3.5-lightning",
            "gemma-4-26b-a4b-it",
            "gemma-4-31b-it",
            "gemini-3.5-flash-lite"
            ],
        "rps": 0.45,
        "rpm": 6
    },
    "medium": {
        "models": [
            "openai/gpt-oss-20b",
            "deepseek/deepseek-v4.1-flash",
            "qwen/qwen3.8-27b",
            "gpt-5.6-luna",
            "z-ai/glm-5.3-flash"
        ],
        "rps": 0.25,
        "rpm": 4
    },
    "heavy": {
        "models": [
            "openai/gpt-oss-120b",
            "minimax"
        ],
        "rps": 0.125,
        "rpm": 2
    }
}

class UserBucket:
    """Tracks a single user's request timestamps for RPS/RPM enforcement."""
    __slots__ = ('timestamps',)
    
    def __init__(self):
        self.timestamps: list[float] = []
    
    def _cleanup(self, now: float):
        """Remove timestamps older than 60 seconds."""
        cutoff = now - 60.0
        self.timestamps = [t for t in self.timestamps if t > cutoff]
    
    def check(self, now: float, rps: float, rpm: int) -> tuple[bool, float, str]:
        """
        Check if a request is allowed.
        Returns: (allowed, wait_seconds, reason)
        """
        self._cleanup(now)
        
        if len(self.timestamps) >= rpm:
            oldest = self.timestamps[0]
            wait = 60.0 - (now - oldest)
            return False, max(0.1, wait), f"{rpm} requests/minute reached."
        
        if rps > 0 and self.timestamps:
            last = self.timestamps[-1]
            min_interval = 1.0 / rps
            elapsed = now - last
            if elapsed < min_interval:
                wait = min_interval - elapsed
                return False, max(0.1, wait), f"Max {rps:.1f} requests/second."
        
        self.timestamps.append(now)
        return True, 0.0, ""
    
    def request_count_last_minute(self, now: float) -> int:
        self._cleanup(now)
        return len(self.timestamps)


class RateLimiter:
    """
    Combined per-user + dynamic global rate limiter.
    """
    def __init__(self):
        self.tier_limits = {k: dict(v) for k, v in DEFAULT_TIER_LIMITS.items()}
        self.users: dict[str, UserBucket] = defaultdict(UserBucket)
        self.enabled = True
        self.kill_switch = False
        
        self.dynamic_enabled = True
        self.low_usage_threshold = 2      
        self.high_usage_threshold = 5    
        self.low_multiplier = 1.5         
        self.high_multiplier = 0.5        
        
        self.total_requests = 0
        self.total_denied = 0
        self.start_time = time.time()
    
    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time
    
    def _get_active_users(self, now: float) -> int:
        """Count users with activity in the last 60 seconds."""
        return sum(1 for b in self.users.values() if b.request_count_last_minute(now) > 0)
    
    def _get_dynamic_multiplier(self, now: float) -> float:
        """Calculate the dynamic multiplier based on current usage."""
        if not self.dynamic_enabled:
            return 1.0
        
        active = self._get_active_users(now)
        
        if active <= self.low_usage_threshold:
            return self.low_multiplier
        elif active >= self.high_usage_threshold:
            return self.high_multiplier
        else:
            ratio = (active - self.low_usage_threshold) / (self.high_usage_threshold - self.low_usage_threshold)
            return self.low_multiplier + ratio * (self.high_multiplier - self.low_multiplier)
    
    def _get_tier_for_model(self, model_id: str) -> str:
        """Look up which tier a model belongs to. Default to 'medium'."""
        for tier_key, tier_data in self.tier_limits.items():
            if model_id in tier_data.get("models", []):
                return tier_key
        return "medium"
    
    def check(self, user_id: str, model_id: str = None) -> tuple[bool, float, str]:
        """
        Main entry point: check if user_id is allowed to make a request.
        Returns: (allowed, wait_seconds, reason)
        """
        if self.kill_switch:
            return False, 0.0, "⛔ AI responses are temporarily disabled."
        
        if not self.enabled:
            return True, 0.0, ""
        
        now = time.time()
        self.total_requests += 1
        
        tier_key = self._get_tier_for_model(model_id) if model_id else "medium"
        tier = self.tier_limits.get(tier_key, self.tier_limits["medium"])
        
        multiplier = self._get_dynamic_multiplier(now)
        effective_rps = tier["rps"] * multiplier
        effective_rpm = max(1, int(tier["rpm"] * multiplier))
        
        bucket = self.users[user_id]
        allowed, wait, reason = bucket.check(now, effective_rps, effective_rpm)
        
        if not allowed:
            self.total_denied += 1
        
        return allowed, wait, reason
    
    def get_stats(self) -> dict:
        """Return stats for the /safety dashboard."""
        now = time.time()
        active = self._get_active_users(now)
        multiplier = self._get_dynamic_multiplier(now)
        
        return {
            "enabled": self.enabled,
            "kill_switch": self.kill_switch,
            "dynamic_enabled": self.dynamic_enabled,
            "total_requests": self.total_requests,
            "total_denied": self.total_denied,
            "active_users": active,
            "dynamic_multiplier": round(multiplier, 2),
            "uptime_seconds": self.uptime_seconds,
            "tier_limits": {k: {"rps": v["rps"], "rpm": v["rpm"]} for k, v in self.tier_limits.items()}
        }
    
    def set_tier_limit(self, tier: str, rps: float = None, rpm: int = None):
        """Update tier limits at runtime."""
        if tier in self.tier_limits:
            if rps is not None:
                self.tier_limits[tier]["rps"] = rps
            if rpm is not None:
                self.tier_limits[tier]["rpm"] = rpm
    
    def get_user_stats(self, user_id: str) -> dict:
        """Get per-user rate limit info."""
        now = time.time()
        bucket = self.users.get(user_id)
        if not bucket:
            return {"requests_last_minute": 0}
        return {"requests_last_minute": bucket.request_count_last_minute(now)}
    
    def reset_user(self, user_id: str):
        """Reset a user's rate limit bucket."""
        if user_id in self.users:
            del self.users[user_id]

rate_limiter = RateLimiter()