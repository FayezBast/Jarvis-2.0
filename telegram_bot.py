"""
Jarvis-2.0 Telegram Bot (Hardened)

Security layers:
- Authorized user allowlist (required)
- Rate limiting
- Blocked command patterns (never execute)
- Dangerous commands require:
    1) Local out-of-band approval code generated on Mac
    2) Telegram confirmation (yes)
- Local approvals are bound to a specific request_id and expire
- No secrets/approval codes ever logged
"""

import os
import sys
import logging
import asyncio
import hashlib
import hmac
import time
import re
from datetime import datetime
from typing import Optional, Dict, Set, Tuple
from collections import defaultdict

# -------- Logging --------
_default_log_dir = os.path.join(os.path.dirname(__file__), "logs")
_log_dir = os.getenv("JARVIS_LOG_DIR") or (_default_log_dir if os.path.isdir(_default_log_dir) else os.path.dirname(__file__))
LOG_FILE = os.path.join(_log_dir, "jarvis_telegram.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# -------- Telegram imports --------
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError:
    print("❌ python-telegram-bot not installed!\nRun: pip install python-telegram-bot")
    sys.exit(1)

# -------- Your agent imports --------
from dotenv import load_dotenv
from core.agent import create_agent
from config import get_config
from prompts import system_prompt

load_dotenv()

# ================= SECURITY CONFIGURATION =================

MAX_MESSAGE_LENGTH = 2000
MAX_EXECUTION_TIME = 60
MAX_OUTPUT_LENGTH = 100000

DANGEROUS_PATTERNS = [
    r'\brm\b', r'\bdelete\b', r'\bremove\b',
    r'\bsudo\b', r'\bchmod\b', r'\bchown\b',
    r'\bformat\b', r'\bwipe\b', r'\bkill\b',
    r'\bpassword\b', r'\bsecret\b', r'\btoken\b', r'\bapi.?key\b',
    r'\bssh\b', r'\bcurl\b', r'\bwget\b',
    r'\beval\b', r'\bexec\b',
    r'\.env\b', r'\.ssh', r'\.aws',
    r'\binstall\b', r'\bpip\b', r'\bapt\b',
    r'/etc/', r'/sys/', r'/proc/',
]

BLOCKED_PATTERNS = [
    r'rm\s+-rf\s+[/~]',
    r'>\s*/dev/s?d',
    r'mkfs\.',
    r'dd\s+if=',
    r':\(\)\s*\{\s*:\s*\|\s*:\s*;\s*\}\s*;:',  # fork bomb variants
    r'while\s+true',
    r'nc\s+-l',
    r'bash\s+-i',
]

DEFAULT_ALLOWED_TOOLS = [
    "get_files_info",
    "get_file_content",
    "write_file",
    "search_files",
    "git_status",
    "git_diff",
    "git_log",
    "calculate",
    "datetime",
]

# ================= Helpers =================

def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")

def _safe_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

# ================= Rate Limiter =================

class RateLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: Dict[int, list] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        cutoff = now - self.window
        self.requests[user_id] = [t for t in self.requests[user_id] if t > cutoff]
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        self.requests[user_id].append(now)
        return True

    def time_until_allowed(self, user_id: int) -> int:
        if not self.requests[user_id]:
            return 0
        oldest = min(self.requests[user_id])
        return max(0, int(self.window - (time.time() - oldest)))

# ================= Security Manager =================

class SecurityManager:
    """
    Flow:
    - Dangerous message => create pending_local_approvals[user_id] with request_id + message + timestamp
    - User runs local generator on Mac that reads request_id and signs it with local secret => produces CODE like ABCD1234-EF90ABCD
    - User sends CODE => bot verifies signature against secret file + request_id
    - If ok => bot then asks Telegram confirmation "yes"
    """

    def __init__(self, sandbox_dir: Optional[str] = None):
        self.pending_confirmations: Dict[int, dict] = {}
        self.pending_local_approvals: Dict[int, dict] = {}
        self.failed_attempts: Dict[int, list] = defaultdict(list)
        self.blocked_users: Set[int] = set()
        self.sandbox_dir = os.path.abspath(sandbox_dir) if sandbox_dir else None

    # ---------- auth blocking ----------
    def check_blocked(self, user_id: int) -> bool:
        cutoff = time.time() - 600
        recent_failures = [t for t in self.failed_attempts[user_id] if t > cutoff]
        self.failed_attempts[user_id] = recent_failures
        if len(recent_failures) >= 5:
            self.blocked_users.add(user_id)
            return True
        return user_id in self.blocked_users

    def record_failed_attempt(self, user_id: int):
        self.failed_attempts[user_id].append(time.time())
        logger.warning(f"🚨 Failed auth attempt (hash: {self._hash_id(user_id)})")

    def block_user(self, user_id: int):
        self.blocked_users.add(user_id)
        logger.warning(f"🚫 User blocked (hash: {self._hash_id(user_id)})")

    # ---------- pattern checks ----------
    def is_dangerous(self, message: str) -> bool:
        m = message.lower()
        return any(re.search(p, m) for p in DANGEROUS_PATTERNS)

    def is_blocked_command(self, message: str) -> bool:
        m = message.lower()
        return any(re.search(p, m) for p in BLOCKED_PATTERNS)

    # ---------- local approval (out-of-band) ----------
    def request_local_approval(self, user_id: int, message: str) -> str:
        # request_id is public and safe to show
        request_id = hashlib.sha256(f"{user_id}:{time.time()}:{message}".encode()).hexdigest()[:8].upper()
        self.pending_local_approvals[user_id] = {
            "message": message,
            "request_id": request_id,
            "timestamp": time.time(),
        }
        return request_id

    def clear_local_approval(self, user_id: int):
        self.pending_local_approvals.pop(user_id, None)

    def _local_secret_file(self) -> Optional[str]:
        path = os.getenv("TELEGRAM_LOCAL_SECRET_FILE", "").strip()
        if not path:
            return None
        return os.path.abspath(os.path.expanduser(path))

    def _read_local_secret(self) -> Optional[bytes]:
        path = self._local_secret_file()
        if not path:
            return None
        try:
            with open(path, "rb") as f:
                data = f.read().strip()
            return data if data else None
        except Exception:
            return None

    def _local_code_file(self) -> Optional[str]:
        path = os.getenv("TELEGRAM_LOCAL_APPROVAL_FILE", "").strip()
        if not path:
            return None
        return os.path.abspath(os.path.expanduser(path))

    def _local_file_fresh(self, path: str, ttl_seconds: int) -> bool:
        if ttl_seconds <= 0:
            return True
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            return False
        return (time.time() - mtime) <= ttl_seconds

    def _read_local_code(self) -> Optional[str]:
        # File contains only the CODE (single line)
        path = self._local_code_file()
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip().upper() or None
        except Exception:
            return None

    @staticmethod
    def _parse_code(code: str) -> Optional[Tuple[str, str]]:
        # CODE format: RAW-SIG
        code = code.strip().upper()
        if "-" not in code:
            return None
        raw, sig = code.split("-", 1)
        if len(raw) != 8 or len(sig) != 8:
            return None
        return raw, sig

    def check_local_approval(self, user_id: int, user_text: str) -> Optional[str]:
        """
        Validates that:
        - user has a pending local request
        - pending request not expired
        - local code file exists and is fresh (file TTL)
        - local secret exists
        - code signature matches HMAC(secret, raw + request_id)
        If ok, clears local pending and returns original message.
        """
        pending = self.pending_local_approvals.get(user_id)
        if not pending:
            return None

        req_ttl = _safe_int("TELEGRAM_LOCAL_APPROVAL_REQUEST_TTL", 300)  # 5 min
        if req_ttl > 0 and (time.time() - pending["timestamp"]) > req_ttl:
            self.pending_local_approvals.pop(user_id, None)
            return None

        code_file = self._local_code_file()
        if not code_file or not os.path.exists(code_file):
            return None

        file_ttl = _safe_int("TELEGRAM_LOCAL_APPROVAL_TTL", 600)  # 10 min file freshness
        if not self._local_file_fresh(code_file, file_ttl):
            return None

        secret = self._read_local_secret()
        if not secret:
            return None

        parsed = self._parse_code(user_text)
        if not parsed:
            return None
        raw, sig = parsed

        request_id = pending["request_id"]
        expected = hmac.new(secret, f"{raw}{request_id}".encode(), hashlib.sha256).hexdigest()[:8].upper()

        if hmac.compare_digest(sig, expected):
            msg = pending["message"]
            self.pending_local_approvals.pop(user_id, None)
            return msg

        return None

    # ---------- confirmation ----------
    def request_confirmation(self, user_id: int, message: str) -> str:
        confirm_id = hashlib.sha256(f"{user_id}{time.time()}{message}".encode()).hexdigest()[:8]
        self.pending_confirmations[user_id] = {
            "message": message,
            "confirm_id": confirm_id,
            "timestamp": time.time(),
        }
        return confirm_id

    def check_confirmation(self, user_id: int, confirm_text: str) -> Optional[str]:
        pending = self.pending_confirmations.get(user_id)
        if not pending:
            return None

        if time.time() - pending["timestamp"] > 300:
            self.pending_confirmations.pop(user_id, None)
            return None

        if confirm_text.lower() in ("yes", "y", "confirm", pending["confirm_id"]):
            msg = pending["message"]
            self.pending_confirmations.pop(user_id, None)
            return msg

        return None

    def clear_all_pending(self, user_id: int):
        self.pending_confirmations.pop(user_id, None)
        self.pending_local_approvals.pop(user_id, None)

    # ---------- input validation ----------
    def validate_input(self, message: str) -> Tuple[bool, str]:
        if len(message) > MAX_MESSAGE_LENGTH:
            return False, f"Message too long (max {MAX_MESSAGE_LENGTH} chars)"
        if "\x00" in message:
            return False, "Invalid characters detected"
        return True, ""

    @staticmethod
    def _hash_id(user_id: int) -> str:
        return hashlib.sha256(str(user_id).encode()).hexdigest()[:12]

    @staticmethod
    def sanitize_output(text: str) -> str:
        if len(text) > MAX_OUTPUT_LENGTH:
            text = text[:MAX_OUTPUT_LENGTH] + "\n\n... [Output truncated for security]"

        patterns = [
            (r'(api[_-]?key\s*[=:]\s*)[^\s\n]+', r'\1[REDACTED]'),
            (r'(password\s*[=:]\s*)[^\s\n]+', r'\1[REDACTED]'),
            (r'(token\s*[=:]\s*)[^\s\n]+', r'\1[REDACTED]'),
            (r'(secret\s*[=:]\s*)[^\s\n]+', r'\1[REDACTED]'),
            (r'(Bearer\s+)[^\s\n]+', r'\1[REDACTED]'),
            (r'(Authorization:\s*)[^\n]+', r'\1[REDACTED]'),
            (r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b(?!\.(0|255))', r'[IP_ADDRESS]'),
        ]
        for pattern, repl in patterns:
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        return text

# ================= Telegram Jarvis =================

class TelegramJarvis:
    def __init__(self):
        self.config = get_config()
        self.agent = None
        self.authorized_users: Set[int] = set()

        self.require_confirm = _env_bool("TELEGRAM_REQUIRE_CONFIRM", True)
        self.local_approval_required = _env_bool("TELEGRAM_LOCAL_APPROVAL_REQUIRED", False)

        self.allowed_tools = self._load_allowed_tools()

        self.working_dir = os.getenv("JARVIS_WORKING_DIR", os.getcwd())
        self.rate_limiter = RateLimiter(max_requests=_safe_int("TELEGRAM_RATE_LIMIT_PER_MIN", 30))
        self.security = SecurityManager(sandbox_dir=self.working_dir)

        self._load_authorized_users()
        self._validate_environment()

    def _load_allowed_tools(self) -> Set[str]:
        raw = os.getenv("TELEGRAM_ALLOWED_TOOLS", "").strip()
        if raw:
            return {t.strip() for t in raw.split(",") if t.strip()}
        return set(DEFAULT_ALLOWED_TOOLS)

    def _load_authorized_users(self):
        users = os.getenv("TELEGRAM_AUTHORIZED_USERS", "")
        if not users:
            logger.error("❌ TELEGRAM_AUTHORIZED_USERS not set! Refusing to start.")
            sys.exit(1)
        try:
            self.authorized_users = {int(u.strip()) for u in users.split(",") if u.strip()}
            logger.info(f"✅ Loaded {len(self.authorized_users)} authorized user(s)")
        except Exception:
            logger.error("❌ Invalid TELEGRAM_AUTHORIZED_USERS format!")
            sys.exit(1)

    def _validate_environment(self):
        if not os.path.exists(self.working_dir):
            logger.error(f"❌ Working directory does not exist: {self.working_dir}")
            sys.exit(1)

        if not _env_bool("JARVIS_DRY_RUN", False):
            logger.warning("⚠️  JARVIS_DRY_RUN is OFF - bot can make real changes!")

        if not self.require_confirm:
            logger.warning("⚠️  TELEGRAM_REQUIRE_CONFIRM is OFF - dangerous!")

        if self.local_approval_required:
            # Require both file paths for "proof" mode
            if not os.getenv("TELEGRAM_LOCAL_APPROVAL_FILE", "").strip():
                logger.error("❌ TELEGRAM_LOCAL_APPROVAL_REQUIRED is ON but TELEGRAM_LOCAL_APPROVAL_FILE is not set.")
                sys.exit(1)
            if not os.getenv("TELEGRAM_LOCAL_SECRET_FILE", "").strip():
                logger.error("❌ TELEGRAM_LOCAL_APPROVAL_REQUIRED is ON but TELEGRAM_LOCAL_SECRET_FILE is not set.")
                sys.exit(1)

    def is_authorized(self, user_id: int) -> bool:
        return user_id in self.authorized_users

    async def _check_access(self, update: Update) -> bool:
        user_id = update.effective_user.id

        if self.security.check_blocked(user_id):
            return False

        if not self.is_authorized(user_id):
            self.security.record_failed_attempt(user_id)
            if _env_bool("TELEGRAM_BLOCK_UNAUTHORIZED_IMMEDIATE", False):
                self.security.block_user(user_id)
            await update.message.reply_text("⛔ Access denied.")
            return False

        if not self.rate_limiter.is_allowed(user_id):
            wait_time = self.rate_limiter.time_until_allowed(user_id)
            await update.message.reply_text(f"⏳ Rate limited. Try again in {wait_time} seconds.")
            return False

        return True

    def _get_agent(self):
        if self.agent is None:
            telegram_prompt = (
                f"{system_prompt}\n\n"
                "## Telegram Safety Override\n"
                f"- Allowed tools: {', '.join(sorted(self.allowed_tools))}\n"
                "- Never call any tool outside this list.\n"
                "- Prefer read-only operations; ask before writing files."
            )
            self.agent = create_agent(
                api_key=self.config.gemini_api_key,
                system_prompt=telegram_prompt,
                working_directory=self.working_dir,
                model_name=self.config.model_name,
                dry_run=_env_bool("JARVIS_DRY_RUN", False),
                verbose=False,
            )
            from tools.registry import get_registry
            removed = get_registry().filter_tools(list(self.allowed_tools))
            if removed:
                logger.info(f"🔒 Telegram tool allowlist active ({removed} tools disabled)")
        return self.agent

    # ---------- commands ----------
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_access(update):
            return
        await update.message.reply_text(
            "👋 Jarvis is online.\n"
            "/status, /reset, /cancel\n\n"
            "Send a message to interact.\n"
            "⚠️ Dangerous ops require local approval + confirmation.",
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_access(update):
            return
        dry_run = _env_bool("JARVIS_DRY_RUN", False)
        await update.message.reply_text(
            "🖥️ Status\n"
            f"- Dry run: {'ON' if dry_run else 'OFF'}\n"
            f"- Confirm: {'ON' if self.require_confirm else 'OFF'}\n"
            f"- Local approval: {'ON' if self.local_approval_required else 'OFF'}"
        )

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_access(update):
            return
        if self.agent:
            self.agent.reset()
        self.security.clear_all_pending(update.effective_user.id)
        await update.message.reply_text("🗑️ Reset done.")

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_access(update):
            return
        self.security.clear_all_pending(update.effective_user.id)
        await update.message.reply_text("❌ Cancelled.")

    # ---------- main message handler ----------
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_access(update):
            return

        user_id = update.effective_user.id
        message = (update.message.text or "").strip()
        if not message:
            return

        ok, err = self.security.validate_input(message)
        if not ok:
            await update.message.reply_text(f"🚫 {err}")
            return

        # 1) If waiting for LOCAL approval, treat incoming message as CODE attempt
        if user_id in self.security.pending_local_approvals:
            approved_message = self.security.check_local_approval(user_id, message)
            if approved_message:
                # Move into confirmation flow for the approved message
                self.security.request_confirmation(user_id, approved_message)
                await update.message.reply_text(
                    "✅ Local approval accepted.\n"
                    "Reply **yes** to confirm this action (or **no** to cancel).",
                    parse_mode="Markdown"
                )
                return

            if message.lower() in ("no", "n", "cancel"):
                self.security.clear_all_pending(user_id)
                await update.message.reply_text("❌ Cancelled.")
                return

            pending = self.security.pending_local_approvals.get(user_id, {})
            rid = pending.get("request_id", "????????")
            await update.message.reply_text(
                "🔐 Local approval required.\n"
                f"Request ID: `{rid}`\n"
                "Generate a code on your Mac and paste it here.\n"
                "Or reply **cancel**.",
                parse_mode="Markdown"
            )
            return

        # 2) If waiting for confirmation, handle YES/NO
        if user_id in self.security.pending_confirmations:
            original = self.security.check_confirmation(user_id, message)
            if original:
                message = original  # proceed to execution
            elif message.lower() in ("no", "n", "cancel"):
                self.security.clear_all_pending(user_id)
                await update.message.reply_text("❌ Cancelled.")
                return
            else:
                await update.message.reply_text(
                    "⚠️ Confirmation pending.\nReply **yes** to confirm or **no** to cancel.",
                    parse_mode="Markdown"
                )
                return

        # 3) Blocked commands
        if self.security.is_blocked_command(message):
            await update.message.reply_text("🚫 This command is blocked for security reasons.")
            return

        # 4) Dangerous: require local approval (if enabled) then confirmation
        if self.require_confirm and self.security.is_dangerous(message):
            if self.local_approval_required:
                request_id = self.security.request_local_approval(user_id, message)
                await update.message.reply_text(
                    "🔐 **Local approval required.**\n"
                    f"Request ID: `{request_id}`\n"
                    "On your Mac, generate a code for this request ID and paste it here.\n"
                    "Then you’ll still confirm with **yes**.",
                    parse_mode="Markdown"
                )
                return

            # If local approval not required, fall back to confirmation
            self.security.request_confirmation(user_id, message)
            await update.message.reply_text(
                "⚠️ **Sensitive operation detected.**\n"
                "Reply **yes** to confirm or **no** to cancel.\n"
                "(Expires in 5 minutes)",
                parse_mode="Markdown"
            )
            return

        # 5) Normal (non-dangerous) processing
        await update.message.chat.send_action("typing")

        try:
            agent = self._get_agent()
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, agent.process, message),
                timeout=MAX_EXECUTION_TIME
            )
            response = self.security.sanitize_output(response)

            if len(response) > 4000:
                for i in range(0, len(response), 4000):
                    await update.message.reply_text(response[i:i+4000])
            else:
                await update.message.reply_text(response)

        except asyncio.TimeoutError:
            await update.message.reply_text(f"⏱️ Timed out after {MAX_EXECUTION_TIME} seconds.")
        except Exception:
            logger.exception("Error processing message")
            await update.message.reply_text("❌ An error occurred. Check logs for details.")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Error: {context.error}")

# ================= main =================

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN missing in .env")
        sys.exit(1)

    if len(token) < 40 or ":" not in token:
        print("❌ TELEGRAM_BOT_TOKEN looks invalid")
        sys.exit(1)

    jarvis = TelegramJarvis()

    print("🤖 Starting Jarvis Telegram Bot...")
    print("📝 Logs:", LOG_FILE)

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", jarvis.start_command))
    app.add_handler(CommandHandler("status", jarvis.status_command))
    app.add_handler(CommandHandler("reset", jarvis.reset_command))
    app.add_handler(CommandHandler("cancel", jarvis.cancel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, jarvis.handle_message))
    app.add_error_handler(jarvis.error_handler)

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
