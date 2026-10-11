# ============================================================
#  SMS BLAST BOT — v4.0 APEX ULTRA
#  Live panel • 10x power • 10s scan • zero-off guaranteed
# ============================================================

import asyncio, json, logging, os, random, signal, string, sys, threading, time
from copy import deepcopy
from datetime import datetime
from html import escape as html_escape

import aiohttp
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile, CallbackQuery, FSInputFile,
    InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("BlastBot")

# ============================================================
#  CONFIG
# ============================================================
MAIN_OWNER = 7966027018
SUPER_ADMIN_NAME = "02"
SUPER_ADMIN_LINK = "0"
SUPER_ADMINS = [7966027018]

BOT_TOKEN = "8860454523:AAHYGLiLxzzHXN1Dzz2MGQ4XQP_TDYpkSFo"
LOG_CHANNEL_ID = -1003994612182

_DATA_FILE = "bla1st_data.json"
_BACKUP_FILE = _DATA_FILE + ".bak"
_TMP_FILE = _DATA_FILE + ".tmp"
_LOCK_FILE = ".bot.lock"
_HEARTBEAT_FILE = ".bot.heartbeat"

_VERSION = "5.0 Sanji-back"
_START_TIME = time.time()

_WATCHDOG_INTERVAL = 30
_HEARTBEAT_INTERVAL = 15
_WATCHDOG_MAX_FAILS = 5
_LOCK_STALE_SEC = 180
_CALLBACK_CONCURRENCY = 100
_USER_COOLDOWN_SEC = 0.5
_GLOBAL_BLAST_LIMIT = 500

SPEED_FAST = 0.001
SPEED_MEDIUM = 0.05
SPEED_SLOW = 0.2
SPEED_DEFAULT = SPEED_FAST
_SEND_CONCURRENCY = 70

CURRENT_POWER_MODE = 2
ALLOWED_POWER_MODES = (2, 3, 4, 5, 10)

# ---- FAST SCAN CONFIG ----
_FB_CONCURRENCY = 200
_DEV_CONCURRENCY = 400
_HTTP_CONNECT_TIMEOUT = 5
_HTTP_READ_TIMEOUT = 8
_HTTP_POOL_LIMIT = 1000
_HTTP_PER_HOST = 100
_DNS_CACHE_TTL = 600
_FB_RETRY_COUNT = 0
_DEVICE_BATCH = 100
_BACKGROUND_SCAN_INTERVAL = 10.0
_PROGRESS_UPDATE_INTERVAL = 3.0
_PANEL_REFRESH_INTERVAL = 15.0

# ============================================================
#  EMOJI
# ============================================================
EMOJI_FIRE     = "5289722755871162900"
EMOJI_STAR     = "5372849966689566579"
EMOJI_ROCKET   = "5359664288241829619"
EMOJI_CROWN    = "6237927637906364256"
EMOJI_SHIELD   = "6235476345451716705"
EMOJI_MONEY    = "6244678063775289843"
EMOJI_PHONE    = "6239930832128056797"
EMOJI_CHECK    = "4958689671950369798"
EMOJI_CROSS    = "4958900559139570572"
EMOJI_WARNING  = "4958526153955476488"
EMOJI_LOCK     = "4956719506027185156"
EMOJI_GIFT     = "5084613633418199991"
EMOJI_BELL     = "5098265504796115765"
EMOJI_GEAR     = "5116414868357907335"
EMOJI_VIDEO    = "5372849966689566579"
FIRE_EFFECT_ID = "5104841245755180586"

# ============================================================
#  HELPERS
# ============================================================
_SC_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ0123456789"
)

def sc(t): return (t or "").translate(_SC_MAP)
def em(eid, fb="⭐"): return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>' if eid else fb
def esc(v): return html_escape(str(v if v is not None else ""))

def btn(text, cb, eid=None, fb="", style=None):
    label = f"{fb} {sc(text)}".strip() if (fb and not eid) else sc(text)
    kwargs = {"text": label, "callback_data": cb}
    if eid:
        try: kwargs["icon_custom_emoji_id"] = eid
        except Exception: pass
    if style in ("primary", "success", "danger"):
        try: kwargs["style"] = style
        except Exception: pass
    try: return InlineKeyboardButton(**kwargs)
    except TypeError: return InlineKeyboardButton(text=label, callback_data=cb)

def btn_url(text, url, eid=None, fb="", style=None):
    label = f"{fb} {sc(text)}".strip() if (fb and not eid) else sc(text)
    kwargs = {"text": label, "url": url}
    if eid:
        try: kwargs["icon_custom_emoji_id"] = eid
        except Exception: pass
    if style in ("primary", "success", "danger"):
        try: kwargs["style"] = style
        except Exception: pass
    try: return InlineKeyboardButton(**kwargs)
    except TypeError: return InlineKeyboardButton(text=label, url=url)

# ============================================================
#  GLOBAL STATE
# ============================================================
_DB_LOCK = threading.RLock()
_DATA_CACHE = None
_HTTP_SESSION = None
_SHUTDOWN_REQUESTED = False

USER_SESSIONS = {}
SESSIONS_LOCK = asyncio.Lock()
CACHED_DEVICES = []
LAST_SCAN_TIME = 0.0
LAST_SCAN_DURATION = 0.0
SCANNING_IN_PROGRESS = False
DEVICE_HEALTH_LOG = []
FB_DEVICE_COUNTS = {}
SCAN_LOCK = asyncio.Lock()
PROTECTED_NUMBERS = {}
FB_SCAN_ERRORS = {}
LAST_KNOWN_DEVICE_COUNT = 0
LAST_KNOWN_FB_COUNTS = {}

_BG_TASKS = set()

CALLBACK_SEM = asyncio.Semaphore(_CALLBACK_CONCURRENCY)
GLOBAL_BLAST_SEM = asyncio.Semaphore(_GLOBAL_BLAST_LIMIT)
_USER_COOLDOWN = {}
_OWNER_PANEL_STATE = {}

def _spawn(coro):
    t = asyncio.create_task(coro)
    _BG_TASKS.add(t)
    t.add_done_callback(_BG_TASKS.discard)
    return t

# ============================================================
#  MIDDLEWARES
# ============================================================
class CallbackSemaphoreMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with CALLBACK_SEM:
            return await handler(event, data)

class UserCooldownMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            if isinstance(event, CallbackQuery) and event.from_user:
                uid = event.from_user.id
                now = time.time()
                last = _USER_COOLDOWN.get(uid, 0)
                if now - last < _USER_COOLDOWN_SEC:
                    try: await event.answer()
                    except Exception: pass
                    return
                _USER_COOLDOWN[uid] = now
                if len(_USER_COOLDOWN) > 10000:
                    cutoff = now - 60
                    for k in list(_USER_COOLDOWN.keys()):
                        if _USER_COOLDOWN[k] < cutoff:
                            _USER_COOLDOWN.pop(k, None)
        except Exception:
            pass
        return await handler(event, data)

class OwnerPanelResetMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            if isinstance(event, CallbackQuery) and event.from_user:
                uid = event.from_user.id
                st = _OWNER_PANEL_STATE.get(uid)
                if st:
                    st["last_user_action"] = time.time()
                    if event.data not in ("owner:home", "owner:refresh", "noop"):
                        st["active"] = False
        except Exception:
            pass
        return await handler(event, data)

# ============================================================
#  SINGLE INSTANCE LOCK
# ============================================================
def _acquire_lock():
    if os.path.exists(_LOCK_FILE):
        try:
            age = time.time() - os.path.getmtime(_LOCK_FILE)
            if age > _LOCK_STALE_SEC:
                log.warning(f"Stale lock ({int(age)}s), removing")
                try: os.remove(_LOCK_FILE)
                except Exception: pass
            else:
                with open(_LOCK_FILE, "r") as f:
                    old_pid = int(f.read().strip())
                if old_pid == os.getpid():
                    return
                if sys.platform == "win32":
                    try: os.remove(_LOCK_FILE)
                    except Exception: pass
                else:
                    try:
                        os.kill(old_pid, 0)
                        log.critical(f"Another instance PID={old_pid}. Exit.")
                        sys.exit(1)
                    except OSError:
                        try: os.remove(_LOCK_FILE)
                        except Exception: pass
        except Exception:
            try: os.remove(_LOCK_FILE)
            except Exception: pass
    try:
        with open(_LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        log.warning(f"Lock write failed: {e}")

def _release_lock():
    try:
        if os.path.exists(_LOCK_FILE): os.remove(_LOCK_FILE)
    except Exception: pass

def _heartbeat():
    try:
        with open(_HEARTBEAT_FILE, "w") as f:
            f.write(str(int(time.time())))
    except Exception: pass

# ============================================================
#  HTTP SESSION
# ============================================================
async def get_http_session():
    global _HTTP_SESSION
    if _HTTP_SESSION is None or _HTTP_SESSION.closed:
        connector = aiohttp.TCPConnector(
            limit=_HTTP_POOL_LIMIT, limit_per_host=_HTTP_PER_HOST,
            ttl_dns_cache=_DNS_CACHE_TTL, force_close=False,
            enable_cleanup_closed=True,
        )
        _HTTP_SESSION = aiohttp.ClientSession(connector=connector)
    return _HTTP_SESSION

async def close_http_session():
    global _HTTP_SESSION
    if _HTTP_SESSION and not _HTTP_SESSION.closed:
        try: await _HTTP_SESSION.close()
        except Exception: pass
    _HTTP_SESSION = None

# ============================================================
#  DATA LAYER
# ============================================================
def _default_data():
    return {
        "owners": [MAIN_OWNER], "admins": [], "banned": [],
        "free_mode": False, "approved": [], "firebases": [], "users": {},
        "stats": {"total_sent": 0, "total_failed": 0, "api_usage": {}},
        "premium": {"ref_credits": 3},
        "force_join": {"enabled": False, "channels": []},
        "pricing": {"plans": []}, "redeem_codes": {},
        "settings": {"ref_credits": 3, "max_owners": 6, "owner_display": SUPER_ADMIN_NAME},
        "sms_history": {}, "activity_log": [], "protected_numbers": {}, "videos": []
    }

def _merge(data, defaults):
    for k, v in defaults.items():
        if k not in data: data[k] = deepcopy(v)
        elif isinstance(v, dict) and isinstance(data.get(k), dict): _merge(data[k], v)
    return data

def _read_json(path):
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def _load_from_disk():
    if os.path.exists(_DATA_FILE):
        try:
            data = _read_json(_DATA_FILE)
            _merge(data, _default_data())
            if MAIN_OWNER not in data.get("owners", []):
                data["owners"].insert(0, MAIN_OWNER)
            for u in data.get("users", {}).values():
                u.setdefault("credits", 0); u.setdefault("sms_history", [])
                u.setdefault("manual_added_credits", 0); u.setdefault("uses", 0)
                u.setdefault("joined_at", int(time.time()))
            global PROTECTED_NUMBERS
            PROTECTED_NUMBERS = data.get("protected_numbers", {})
            return data
        except Exception as e:
            log.error(f"Primary load failed: {e}")
            if os.path.exists(_BACKUP_FILE):
                try:
                    data = _read_json(_BACKUP_FILE)
                    _merge(data, _default_data())
                    return data
                except Exception as e2: log.error(f"Backup failed: {e2}")
    d = _default_data()
    try:
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
    except Exception as e: log.error(f"Init write failed: {e}")
    return d

def load():
    global _DATA_CACHE
    with _DB_LOCK:
        if _DATA_CACHE is None: _DATA_CACHE = _load_from_disk()
        return _DATA_CACHE

def save(_d=None):
    with _DB_LOCK:
        d = _d if _d is not None else _DATA_CACHE
        if d is None: return
        d["protected_numbers"] = PROTECTED_NUMBERS
        try:
            with open(_TMP_FILE, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
                f.flush()
                try: os.fsync(f.fileno())
                except Exception: pass
            if os.path.exists(_DATA_FILE):
                try: os.replace(_DATA_FILE, _BACKUP_FILE)
                except Exception: pass
            os.replace(_TMP_FILE, _DATA_FILE)
        except Exception as e: log.error(f"Save failed: {e}")

# ============================================================
#  USER HELPERS
# ============================================================
def reg_user(uid, name, d):
    k = str(uid)
    if k not in d["users"]:
        d["users"][k] = {
            "name": str(name)[:64], "uses": 0, "credits": 0,
            "manual_added_credits": 0, "joined_at": int(time.time()),
            "refer_code": None, "referred_by": None, "sms_history": []
        }
        return True
    return False

def log_activity(d, action, uid, details=""):
    d.setdefault("activity_log", []).append({
        "timestamp": int(time.time()), "uid": uid, "action": action, "details": str(details)[:200]
    })
    if len(d["activity_log"]) > 1000: d["activity_log"] = d["activity_log"][-1000:]

def is_main_owner(uid): return uid == MAIN_OWNER
def is_owner(uid, d): return uid in d.get("owners", [MAIN_OWNER]) or uid in SUPER_ADMINS
def is_admin(uid, d): return is_owner(uid, d) or uid in d.get("admins", [])
def is_banned(uid, d): return uid in d.get("banned", [])

def can_use(uid, d):
    if is_banned(uid, d): return False
    if is_admin(uid, d): return True
    if d.get("free_mode"): return True
    if uid in d.get("approved", []): return True
    return False

def role_tag(uid, d):
    if is_main_owner(uid): return f"{em(EMOJI_CROWN, '👑')} ᴍᴀɪɴ ᴏᴡɴᴇʀ"
    if is_owner(uid, d): return f"{em(EMOJI_CROWN, '🔱')} ᴏᴡɴᴇʀ"
    if uid in d.get("admins", []): return f"{em(EMOJI_SHIELD, '🛡')} ᴀᴅᴍɪɴ"
    if uid in d.get("approved", []): return f"{em(EMOJI_CHECK, '✅')} ᴀᴘᴘʀᴏᴠᴇᴅ"
    if d.get("free_mode"): return f"{em(EMOJI_GIFT, '🆓')} ғʀᴇᴇ ᴜsᴇʀ"
    return f"{em(EMOJI_CROSS, '❌')} ɴᴏ ᴀᴄᴄᴇss"

def get_user_credits(uid, d): return int(d.get("users", {}).get(str(uid), {}).get("credits", 0))

def get_owner_display(d):
    val = d.get("settings", {}).get("owner_display", SUPER_ADMIN_NAME)
    if val is None: return ""
    return str(val).strip()

def get_user_send_limit(uid, d):
    v = d.get("users", {}).get(str(uid), {}).get("max_send_limit")
    if v is None: return None
    try: return int(v)
    except (TypeError, ValueError): return None

def set_user_send_limit(uid, limit, d):
    k = str(uid)
    if k not in d.get("users", {}):
        d["users"][k] = {"credits": 0, "manual_added_credits": 0, "name": "User"}
    if limit is None: d["users"][k].pop("max_send_limit", None)
    else: d["users"][k]["max_send_limit"] = int(limit)

def add_credits(uid, amount, d, is_manual=False):
    k = str(uid)
    if k not in d.get("users", {}):
        d["users"][k] = {"credits": 0, "manual_added_credits": 0}
    d["users"][k].setdefault("manual_added_credits", 0)
    d["users"][k]["credits"] = d["users"][k].get("credits", 0) + int(amount)
    if is_manual: d["users"][k]["manual_added_credits"] += int(amount)

def deduct_credits(uid, amount, d):
    k = str(uid)
    if k in d.get("users", {}):
        if d["users"][k].get("credits", 0) >= amount:
            d["users"][k]["credits"] -= amount
            return True
    return False

def generate_refer_code(uid, d):
    k = str(uid)
    if k in d.get("users", {}) and d["users"][k].get("refer_code"):
        return d["users"][k]["refer_code"]
    existing = {u.get("refer_code") for u in d.get("users", {}).values() if u.get("refer_code")}
    for _ in range(30):
        code = "REF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if code not in existing: break
    else: code = "REF" + str(int(time.time()))[-8:]
    if k in d.get("users", {}): d["users"][k]["refer_code"] = code
    return code

def process_referral(new_uid, code, d):
    referrer_uid = None
    for uid_str, udata in d.get("users", {}).items():
        if udata.get("refer_code") == code:
            referrer_uid = int(uid_str); break
    if not referrer_uid: return False, "Invalid", None
    if referrer_uid == new_uid: return False, "Self", None
    if d["users"].get(str(new_uid), {}).get("referred_by"): return False, "Already", None
    rc = int(d.get("settings", {}).get("ref_credits", 3))
    add_credits(new_uid, rc, d, False); add_credits(referrer_uid, rc, d, False)
    d["users"][str(new_uid)]["referred_by"] = referrer_uid
    save(d)
    return True, f"+{rc}", referrer_uid

# ============================================================
#  FORMATTERS
# ============================================================
def mask_number(number):
    n = str(number or "")
    if len(n) <= 4: return n
    return n[:2] + "******" + n[-4:]

def fmt_time(ts):
    try: return datetime.fromtimestamp(int(ts)).strftime("%d/%m/%Y %H:%M")
    except Exception: return "—"

def fmt_duration(seconds):
    s = int(seconds)
    if s < 60: return f"{s}s"
    if s < 3600: return f"{s // 60}m {s % 60}s"
    return f"{s // 3600}h {(s % 3600) // 60}m {s % 60}s"

def progress_bar(cur, total, w=20):
    if total <= 0: return "░" * w
    f = min(w, int(w * cur / total))
    return "█" * f + "░" * (w - f)

def progress_text(sent, failed, total, credits=None, speed_label="⚡"):
    bar = progress_bar(sent + failed, total)
    pct = int(((sent + failed) / total) * 100) if total > 0 else 0
    lines = [
        f"{em(EMOJI_WARNING, '⏳')} <b>{sc('sending sms...')}</b>\n",
        f"<code>{bar}</code> <b>{pct}%</b>\n",
        f"{em(EMOJI_CHECK, '✅')} sᴇɴᴛ   : <b>{sent}</b>",
        f"{em(EMOJI_CROSS, '❌')} ғᴀɪʟᴇᴅ : <b>{failed}</b>",
        f"{em(EMOJI_STAR, '📊')} ᴘʀᴏɢʀᴇss: <b>{sent + failed}</b> / <b>{total}</b>",
        f"{em(EMOJI_ROCKET, '⚡')} sᴘᴇᴇᴅ  : <b>{speed_label}</b>\n",
    ]
    if credits is not None:
        lines.append(f"{em(EMOJI_MONEY, '💳')} ᴄʀᴇᴅɪᴛs ʟᴇғᴛ: <b>{credits}</b>")
    lines.append(f"\n<i>{em(EMOJI_WARNING, '🛑')} sᴛᴏᴘ ʙᴜᴛᴛᴏɴ ᴅᴀʙᴀʏᴇɪɴ.</i>")
    return "\n".join(lines)

def get_scan_status():
    cur = len(CACHED_DEVICES) * CURRENT_POWER_MODE
    cnt = cur if cur > 0 else LAST_KNOWN_DEVICE_COUNT
    if SCANNING_IN_PROGRESS:
        return f"{em(EMOJI_WARNING, '🔍')} {cnt} ᴀᴘɪs • sᴄᴀɴɴɪɴɢ" if cnt else f"{em(EMOJI_WARNING, '🔍')} sᴄᴀɴɴɪɴɢ..."
    if cnt == 0: return f"{em(EMOJI_CROSS, '🔴')} ɴᴏ ᴅᴇᴠɪᴄᴇs"
    td = time.time() - LAST_SCAN_TIME if LAST_SCAN_TIME > 0 else 999
    if td < 30: return f"{em(EMOJI_CHECK, '🟢')} {cnt} ᴀᴘɪs"
    if td < 120: return f"{em(EMOJI_WARNING, '🟡')} {cnt} ᴀᴘɪs ({int(td)}s ᴏʟᴅ)"
    return f"{em(EMOJI_CROSS, '🔴')} {cnt} ᴀᴘɪs ({int(td / 60)}ᴍ ᴏʟᴅ)"

# ============================================================
#  FIREBASE
# ============================================================
async def fb_put(base_url, path, payload):
    url = base_url.rstrip("/") + path
    try:
        sess = await get_http_session()
        for attempt in range(2):
            try:
                async with sess.put(url, json=payload, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if 200 <= r.status < 300: return True
            except Exception: pass
            await asyncio.sleep(0.3 * (attempt + 1))
    except Exception: pass
    return False

def device_is_online(dd):
    return any([
        dd.get("isOnline"), dd.get("online"), dd.get("connected"),
        dd.get("status") in ("online", "active", True, 1)
    ])

async def _fetch_fb(sess, fb, dev_sem, results):
    url = fb["url"].rstrip("/") + "/clients.json?shallow=true"
    try:
        async with sess.get(url) as r:
            if r.status == 200:
                txt = (await r.text()).strip()
                if txt == "null" or not txt:
                    FB_SCAN_ERRORS.pop(fb["id"], None); return
                ids = json.loads(txt)
                if not isinstance(ids, dict):
                    FB_SCAN_ERRORS.pop(fb["id"], None); return

                async def fd(dev_id):
                    try:
                        u = fb["url"].rstrip("/") + f"/clients/{dev_id}.json"
                        async with dev_sem:
                            async with sess.get(u) as r2:
                                if r2.status == 200:
                                    t2 = (await r2.text()).strip()
                                    if t2 == "null" or not t2: return None
                                    dd = json.loads(t2)
                                    if isinstance(dd, dict) and device_is_online(dd):
                                        return {
                                            "fb_id": fb["id"], "fb_url": fb["url"],
                                            "fb_label": fb.get("label", fb["url"][:30]),
                                            "dev_id": dev_id,
                                            "dev_name": dd.get("deviceName") or dd.get("name") or dev_id[:16],
                                            "sims": dd.get("sims", [])
                                        }
                    except Exception: pass
                    return None

                dev_ids = list(ids.keys())
                for i in range(0, len(dev_ids), _DEVICE_BATCH):
                    batch = dev_ids[i:i + _DEVICE_BATCH]
                    rs = await asyncio.gather(*(fd(d) for d in batch), return_exceptions=True)
                    for x in rs:
                        if x and isinstance(x, dict): results.append(x)
                FB_SCAN_ERRORS.pop(fb["id"], None)
                return
            elif r.status in (401, 403): FB_SCAN_ERRORS[fb["id"]] = f"AUTH {r.status}"; return
            elif r.status == 404: FB_SCAN_ERRORS[fb["id"]] = "404"; return
            elif r.status in (429, 500, 502, 503, 504): FB_SCAN_ERRORS[fb["id"]] = f"RATE {r.status}"; return
            else: FB_SCAN_ERRORS[fb["id"]] = f"HTTP {r.status}"; return
    except asyncio.TimeoutError: FB_SCAN_ERRORS[fb["id"]] = "TIMEOUT"; return
    except aiohttp.ClientError as e: FB_SCAN_ERRORS[fb["id"]] = f"CLIENT {str(e)[:25]}"; return
    except Exception as e: FB_SCAN_ERRORS[fb["id"]] = f"ERR {str(e)[:25]}"; return

async def scan_all(d):
    fbs = d.get("firebases", [])
    if not fbs: return []
    results = []
    curr = {fb["id"] for fb in fbs}
    global CACHED_DEVICES
    CACHED_DEVICES = [x for x in CACHED_DEVICES if x.get("fb_id") in curr]
    for sid in list(FB_SCAN_ERRORS.keys()):
        if sid not in curr: FB_SCAN_ERRORS.pop(sid, None)

    fb_sem = asyncio.Semaphore(_FB_CONCURRENCY)
    dev_sem = asyncio.Semaphore(_DEV_CONCURRENCY)
    conn = aiohttp.TCPConnector(
        limit=_HTTP_POOL_LIMIT, limit_per_host=_HTTP_PER_HOST,
        ttl_dns_cache=_DNS_CACHE_TTL, force_close=False, enable_cleanup_closed=True
    )
    to = aiohttp.ClientTimeout(total=_HTTP_READ_TIMEOUT, connect=_HTTP_CONNECT_TIMEOUT)
    async with aiohttp.ClientSession(connector=conn, timeout=to) as s:
        async def w(fb):
            async with fb_sem:
                await _fetch_fb(s, fb, dev_sem, results)
        await asyncio.gather(*(w(fb) for fb in fbs), return_exceptions=True)

        if FB_SCAN_ERRORS and _FB_RETRY_COUNT > 0:
            rl = [fb for fb in fbs if fb["id"] in FB_SCAN_ERRORS
                  and not any(k in FB_SCAN_ERRORS[fb["id"]] for k in ("404", "AUTH"))]
            if rl:
                await asyncio.sleep(0.4)
                async def rw(fb):
                    async with fb_sem:
                        await _fetch_fb(s, fb, dev_sem, results)
                await asyncio.gather(*(rw(fb) for fb in rl), return_exceptions=True)
    return results

async def sms_via_device(fb_url, dev_id, sim_slot, to, message):
    ts = int(time.time())
    to_s = str(to).strip(); msg_s = str(message).strip()
    attempts = [
        (f"/clients/{dev_id}/webhookEvent/sendSms.json",
         {"from": sim_slot, "to": to_s, "message": msg_s, "isSended": False, "timestamp": ts}),
        (f"/clients/{dev_id}/webhookEvent/sendSms.json",
         {"from": str(sim_slot), "to": to_s, "message": msg_s, "isSended": False, "timestamp": ts}),
        (f"/clients/{dev_id}/messages.json",
         {"phone": to_s, "text": msg_s, "sim": sim_slot, "timestamp": ts}),
    ]
    for path, payload in attempts:
        if await fb_put(fb_url, path, payload): return True
    return False

# ============================================================
#  FSM
# ============================================================
class S(StatesGroup):
    send_number = State(); send_message = State(); send_speed = State(); send_count = State()
    owner_send_number = State(); owner_send_message = State(); owner_send_speed = State(); owner_send_count = State()
    admin_send_number = State(); admin_send_message = State(); admin_send_speed = State(); admin_send_count = State()
    redeem_code = State(); add_firebase = State(); add_firebase_file = State()
    add_owner = State(); add_admin = State(); ban_user = State(); broadcast = State()
    fj_add_channel = State(); fj_add_link = State()
    add_plan_name = State(); add_plan_price = State(); add_plan_credits = State(); add_plan_link = State()
    add_credits_uid = State(); add_credits_amount = State()
    deduct_credits_uid = State(); deduct_credits_amount = State()
    gen_redeem_credits = State(); gen_redeem_uses = State(); set_ref_credits = State()
    protect_number = State(); track_number = State()
    transfer_credits_uid = State(); transfer_credits_amount = State()
    add_all_credits_amount = State(); deduct_all_credits_amount = State()
    add_video = State(); set_limit_uid = State(); set_limit_value = State(); owner_edit_name = State()

# ============================================================
#  SESSION
# ============================================================
class UserSession:
    __slots__ = ("uid", "cancelled", "sent", "failed", "task", "start_time", "lock", "number", "blast_data")
    def __init__(self, uid):
        self.uid = uid; self.cancelled = False; self.sent = 0; self.failed = 0
        self.task = None; self.start_time = time.time()
        self.lock = asyncio.Lock(); self.number = None; self.blast_data = None

# ============================================================
#  KEYBOARDS
# ============================================================
def kb(*rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=c) for t, c in row] for row in rows
    ])

def speed_kb(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("fast", f"{prefix}:speed:fast", EMOJI_ROCKET, "🚀", style="danger"),
         btn("medium", f"{prefix}:speed:medium", EMOJI_STAR, "⚡", style="primary"),
         btn("slow", f"{prefix}:speed:slow", EMOJI_PHONE, "🐢", style="success")],
        [btn("cancel", f"{prefix}:home", EMOJI_CROSS, "❌", style="danger")]
    ])

def stop_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("stop sending", "user:stop_send", EMOJI_CROSS, "🛑", style="danger")]
    ])

def power_row():
    return [
        btn("2x", "owner:set_power:2", EMOJI_ROCKET, "🚀",
            style="success" if CURRENT_POWER_MODE == 2 else "primary"),
        btn("3x", "owner:set_power:3", EMOJI_FIRE, "🔥",
            style="success" if CURRENT_POWER_MODE == 3 else "primary"),
        btn("4x", "owner:set_power:4", EMOJI_FIRE, "💥",
            style="success" if CURRENT_POWER_MODE == 4 else "primary"),
        btn("5x", "owner:set_power:5", EMOJI_FIRE, "💣",
            style="success" if CURRENT_POWER_MODE == 5 else "primary"),
        btn("10x", "owner:set_power:10", EMOJI_FIRE, "☠️",
            style="danger" if CURRENT_POWER_MODE == 10 else "primary"),
    ]

def owner_kb(d):
    mode_btn = ((f"🔴 {sc('disable free mode')}", "owner:free:off")
                if d.get("free_mode") else (f"🟢 {sc('enable free mode')}", "owner:free:on"))
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("send sms", "owner:send", EMOJI_ROCKET, "📤", style="success"),
         btn("manage firebase", "owner:fb:menu:0", EMOJI_FIRE, "🔥", style="primary")],
        [btn("manage videos", "owner:videos:menu", EMOJI_VIDEO, "📹", style="primary"),
         btn("manage super admins", "owner:owners:menu", EMOJI_CROWN, "👑", style="primary")],
        [btn("manage admins", "owner:admins:menu", EMOJI_SHIELD, "🛡", style="primary"),
         btn("view users", "owner:users:list", EMOJI_STAR, "👥", style="primary")],
        [btn("ban user", "owner:ban", EMOJI_CROSS, "🚫", style="danger"),
         btn("unban user", "owner:unban:menu", EMOJI_CHECK, "✅", style="success")],
        [btn("broadcast", "owner:broadcast", EMOJI_BELL, "📢", style="primary"),
         btn("api stats", "owner:stats", EMOJI_STAR, "📊", style="primary")],
        [btn("activity log", "owner:activity", EMOJI_GEAR, "📜", style="primary"),
         btn("pricing plans", "owner:pricing:menu", EMOJI_MONEY, "💳", style="primary")],
        [btn("redeem codes", "owner:redeem:menu", EMOJI_GIFT, "🎁", style="primary"),
         btn("add credits", "owner:credits:add", EMOJI_MONEY, "💰", style="success")],
        [btn("deduct credits", "owner:credits:deduct", EMOJI_CROSS, "💰", style="danger"),
         btn("add credits all", "owner:add_all_credits", EMOJI_MONEY, "💰", style="success")],
        [btn("deduct all", "owner:deduct_all_credits", EMOJI_CROSS, "💰", style="danger"),
         btn("force join", "owner:fj:menu", EMOJI_BELL, "🔗", style="primary")],
        [btn("set user limit", "owner:set_limit", EMOJI_LOCK, "🔒", style="danger"),
         btn("view all limits", "owner:list_limits", EMOJI_LOCK, "📋", style="primary")],
        [btn("settings", "owner:settings", EMOJI_GEAR, "⚙️", style="primary"),
         btn("sms history", "owner:sms_history", EMOJI_STAR, "📋", style="primary")],
        [btn("export script", "owner:export_script", EMOJI_GEAR, "📤", style="primary"),
         btn("protect number", "owner:protect", EMOJI_LOCK, "🔒", style="danger")],
        [btn("protected list", "owner:protected_list", EMOJI_LOCK, "🔐", style="primary"),
         btn("track number", "owner:track", EMOJI_STAR, "📊", style="primary")],
        [btn("edit owner name", "owner:edit_name", EMOJI_CROWN, "✏️", style="primary")],
        [btn(f"🎚️ POWER MODE: {CURRENT_POWER_MODE}x — TAP TO CHANGE", "noop", None, "", style="success")],
        power_row(),
        [InlineKeyboardButton(text=mode_btn[0], callback_data=mode_btn[1])],
        [btn("refresh", "owner:refresh", EMOJI_GEAR, "🔄", style="primary")]
    ])

def admin_kb(d):
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("send sms", "admin:send", EMOJI_ROCKET, "📤", style="success"),
         btn("manage videos", "owner:videos:menu", EMOJI_VIDEO, "📹", style="primary")],
        [btn("view users", "admin:users:list", EMOJI_STAR, "👥", style="primary"),
         btn("api stats", "admin:stats", EMOJI_STAR, "📊", style="primary")],
        [btn("ban user", "admin:ban", EMOJI_CROSS, "🚫", style="danger"),
         btn("unban user", "admin:unban:menu", EMOJI_CHECK, "✅", style="success")],
        [btn("broadcast", "admin:broadcast", EMOJI_BELL, "📢", style="primary")],
        [btn("refresh", "admin:refresh", EMOJI_GEAR, "🔄", style="primary")]
    ])

def user_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("send sms", "user:send", EMOJI_ROCKET, "📤", style="success")],
        [btn("videos", "user:random_video", EMOJI_VIDEO, "📹", style="primary"),
         btn("credits", "user:credits", EMOJI_MONEY, "💳", style="primary")],
        [btn("redeem", "user:redeem", EMOJI_GIFT, "🎁", style="primary"),
         btn("refer", "user:refer", EMOJI_STAR, "👥", style="primary")],
        [btn("stats", "user:stats", EMOJI_STAR, "📊", style="primary"),
         btn("my sms history", "user:sms_history", EMOJI_STAR, "📜", style="primary")],
        [btn("buy credits", "user:pricing", EMOJI_MONEY, "💰", style="success")],
        [btn("transfer credits", "user:transfer", EMOJI_MONEY, "💸", style="primary")],
        [btn("info", "user:info", EMOJI_GEAR, "ℹ️", style="primary")]
    ])

def videos_menu_kb(d):
    vids = d.get("videos", [])
    rows = [
        [btn("add video", "owner:videos:add", EMOJI_CHECK, "➕")],
        [btn("bulk delete all", "owner:videos:bulk_del", EMOJI_CROSS, "🗑")]
    ]
    for idx in range(len(vids)):
        rows.append([btn(f"Video #{idx + 1}", "noop", EMOJI_VIDEO, "📹"),
                     btn("remove", f"owner:videos:del:{idx}", EMOJI_CROSS, "🗑")])
    rows.append([btn("back", "owner:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def fb_menu_kb(d, page=0):
    fbs = d.get("firebases", [])
    per = 8; tp = max(1, (len(fbs) + per - 1) // per)
    page = max(0, min(page, tp - 1)); start = page * per
    curr = fbs[start:start + per]
    rows = [[btn("add firebase", "owner:fb:add", EMOJI_CHECK, "➕"),
             btn("add via txt", "owner:fb:add_file", EMOJI_CHECK, "📄")]]
    for fb in curr:
        lbl = fb.get("label", fb["url"].replace("https://", ""))
        if len(lbl) > 16: lbl = lbl[:14] + ".."
        rows.append([btn(lbl, "noop", EMOJI_FIRE, "🔥"),
                     btn("remove", f"owner:fb:del:{fb['id']}:{page}", EMOJI_CROSS, "🗑")])
    nav = []
    if page > 0: nav.append(btn("prev", f"owner:fb:menu:{page - 1}", EMOJI_GEAR, "◀️"))
    if page < tp - 1: nav.append(btn("next", f"owner:fb:menu:{page + 1}", EMOJI_GEAR, "▶️"))
    if nav: rows.append(nav)
    rows.append([btn("back", "owner:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def owners_menu_kb(d):
    owners = d.get("owners", [])
    rows = []
    if len(owners) < 6: rows.append([btn("add super admin", "owner:owners:add", EMOJI_CHECK, "➕")])
    for oid in owners:
        if oid == MAIN_OWNER: rows.append([btn(f"{oid} (main)", "noop", EMOJI_CROWN, "👑")])
        else: rows.append([btn(f"{oid}", "noop", EMOJI_CROWN, "🔱"),
                          btn("remove", f"owner:owners:del:{oid}", EMOJI_CROSS, "🗑")])
    rows.append([btn("back", "owner:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admins_menu_kb(d):
    admins = d.get("admins", [])
    rows = [[btn("add admin", "owner:admins:add", EMOJI_CHECK, "➕")]]
    for aid in admins:
        rows.append([btn(f"{aid}", "noop", EMOJI_SHIELD, "🛡"),
                     btn("remove", f"owner:admins:del:{aid}", EMOJI_CROSS, "🗑")])
    rows.append([btn("back", "owner:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def unban_menu_kb(d, prefix):
    banned = d.get("banned", [])
    rows = []
    for bid in banned: rows.append([btn(f"{bid}", f"{prefix}:unban:do:{bid}", EMOJI_CHECK, "🔓")])
    rows.append([btn("back", f"{prefix}:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ============================================================
#  PANEL TEXT
# ============================================================
def _fb_summary():
    source = FB_DEVICE_COUNTS if FB_DEVICE_COUNTS else LAST_KNOWN_FB_COUNTS
    items = list(source.items())[:5]
    lines = []
    for fb_id, fd in items:
        age = int(time.time() - fd.get("last_update", 0))
        s = em(EMOJI_CHECK, "🟢") if age < 60 else em(EMOJI_WARNING, "🟡") if age < 300 else em(EMOJI_CROSS, "🔴")
        lines.append(f"  {s} {esc(str(fd.get('label', 'N/A'))[:20])}: <b>{int(fd.get('online', 0)) * CURRENT_POWER_MODE}</b> ᴀᴘɪs")
    if len(source) > 5: lines.append(f"  {em(EMOJI_STAR, '➕')} +{len(source) - 5} more...")
    return "\n".join(lines) if lines else f"  {em(EMOJI_WARNING, '😴')} ɴᴏ ᴅᴀᴛᴀ"

def owner_panel_text(d):
    fbs = d.get("firebases", [])
    owners = d.get("owners", [])
    admins = d.get("admins", [])
    users = d.get("users", {})
    stats = d.get("stats", {})
    mode = f"{em(EMOJI_CHECK, '🟢')} ғʀᴇᴇ" if d.get("free_mode") else f"{em(EMOJI_CROSS, '🔴')} ᴀᴘᴘʀᴏᴠᴀʟ"
    fj = d.get("force_join", {})
    fj_s = f"{em(EMOJI_CHECK, '🟢')} ᴏɴ" if fj.get("enabled") else f"{em(EMOJI_CROSS, '🔴')} ᴏғғ"
    active = len([s for s in USER_SESSIONS.values() if s.task and not s.task.done()])
    owner_disp = get_owner_display(d)
    owner_line = f"<b>Owner:</b> {esc(owner_disp)}\n" if owner_disp else ""
    return (
        f"╭───────────────────────╮\n"
        f"   {em(EMOJI_CROWN, '👑')} <b>{sc('owner panel')}</b> • {_VERSION}\n"
        f"╰───────────────────────╯\n"
        f"{owner_line}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{em(EMOJI_FIRE, '🔥')} ғɪʀᴇʙᴀsᴇ ᴅʙs  : <b>{len(fbs)}</b>\n"
        f"{em(EMOJI_STAR, '🔢')} ᴘᴏᴡᴇʀ ᴍᴏᴅᴇ    : <b>{CURRENT_POWER_MODE}x</b>\n"
        f"{em(EMOJI_CROWN, '👑')} sᴜᴘᴇʀ ᴀᴅᴍɪɴs  : <b>{len(owners)}</b>/6\n"
        f"{em(EMOJI_SHIELD, '🛡')} ᴀᴅᴍɪɴs        : <b>{len(admins)}</b>\n"
        f"{em(EMOJI_STAR, '👥')} ᴛᴏᴛᴀʟ ᴜsᴇʀs   : <b>{len(users)}</b>\n"
        f"{em(EMOJI_VIDEO, '📹')} ᴠɪᴅᴇᴏs        : <b>{len(d.get('videos', []))}</b>\n"
        f"{em(EMOJI_CHECK, '📤')} ᴛᴏᴛᴀʟ sᴇɴᴛ    : <b>{stats.get('total_sent', 0)}</b>\n"
        f"{em(EMOJI_CROSS, '❌')} ᴛᴏᴛᴀʟ ғᴀɪʟᴇᴅ : <b>{stats.get('total_failed', 0)}</b>\n"
        f"{em(EMOJI_ROCKET, '🚀')} ᴀᴄᴛɪᴠᴇ sᴇɴᴅs : <b>{active}</b>\n"
        f"{em(EMOJI_GIFT, '🔓')} ᴀᴄᴄᴇss ᴍᴏᴅᴇ   : {mode}\n"
        f"{em(EMOJI_BELL, '📢')} ғᴏʀᴄᴇ ᴊᴏɪɴ   : {fj_s}\n"
        f"{em(EMOJI_MONEY, '💳')} ᴘʟᴀɴs         : <b>{len(d.get('pricing', {}).get('plans', []))}</b>\n"
        f"{em(EMOJI_LOCK, '🔒')} ᴘʀᴏᴛᴇᴄᴛᴇᴅ    : <b>{len(PROTECTED_NUMBERS)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{em(EMOJI_PHONE, '📱')} <b>ᴘᴇʀ ғɪʀᴇʙᴀsᴇ</b>\n{_fb_summary()}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{em(EMOJI_GEAR, '🔄')} sᴄᴀɴɴᴇʀ: {get_scan_status()}\n"
        f"<i>🔄 auto-refresh every {_PANEL_REFRESH_INTERVAL:.0f}s</i>"
    )

def admin_panel_text(d):
    users = d.get("users", {}); stats = d.get("stats", {})
    mode = f"{em(EMOJI_CHECK, '🟢')} ғʀᴇᴇ" if d.get("free_mode") else f"{em(EMOJI_CROSS, '🔴')} ᴀᴘᴘʀᴏᴠᴀʟ"
    active = len([s for s in USER_SESSIONS.values() if s.task and not s.task.done()])
    return (
        f"╭───────────────────────╮\n"
        f"   {em(EMOJI_SHIELD, '🛡')} <b>{sc('admin panel')}</b> • {_VERSION}\n"
        f"╰───────────────────────╯\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{em(EMOJI_STAR, '👥')} ᴛᴏᴛᴀʟ ᴜsᴇʀs   : <b>{len(users)}</b>\n"
        f"{em(EMOJI_STAR, '🔢')} ᴘᴏᴡᴇʀ ᴍᴏᴅᴇ    : <b>{CURRENT_POWER_MODE}x</b>\n"
        f"{em(EMOJI_CROSS, '🚫')} ʙᴀɴɴᴇᴅ        : <b>{len(d.get('banned', []))}</b>\n"
        f"{em(EMOJI_CHECK, '📤')} ᴛᴏᴛᴀʟ sᴇɴᴛ    : <b>{stats.get('total_sent', 0)}</b>\n"
        f"{em(EMOJI_CROSS, '❌')} ᴛᴏᴛᴀʟ ғᴀɪʟᴇᴅ : <b>{stats.get('total_failed', 0)}</b>\n"
        f"{em(EMOJI_ROCKET, '🚀')} ᴀᴄᴛɪᴠᴇ sᴇɴᴅs : <b>{active}</b>\n"
        f"{em(EMOJI_FIRE, '🔥')} ғɪʀᴇʙᴀsᴇ ᴅʙs  : <b>{len(d.get('firebases', []))}</b>\n"
        f"{em(EMOJI_LOCK, '🔒')} ᴘʀᴏᴛᴇᴄᴛᴇᴅ    : <b>{len(PROTECTED_NUMBERS)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{em(EMOJI_PHONE, '📱')} <b>ᴘᴇʀ ғɪʀᴇʙᴀsᴇ</b>\n{_fb_summary()}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{em(EMOJI_GIFT, '🔓')} ᴀᴄᴄᴇss ᴍᴏᴅᴇ  : {mode}\n"
        f"{em(EMOJI_GEAR, '🔄')} sᴄᴀɴɴᴇʀ      : {get_scan_status()}"
    )

def user_home_text(uid, d):
    udata = d["users"].get(str(uid), {})
    credits = udata.get("credits", 0)
    real = len(CACHED_DEVICES)
    shown = real * CURRENT_POWER_MODE if real > 0 else LAST_KNOWN_DEVICE_COUNT
    limit = get_user_send_limit(uid, d)
    if is_admin(uid, d) or is_owner(uid, d) or limit is None:
        limit_line = f"{em(EMOJI_LOCK, '🔓')} ʟɪᴍɪᴛ : <b>ᴜɴʟɪᴍɪᴛᴇᴅ</b>"
    elif limit <= 0:
        limit_line = f"{em(EMOJI_CROSS, '🚫')} ʟɪᴍɪᴛ : <b>BLOCKED</b>"
    else:
        limit_line = f"{em(EMOJI_LOCK, '🔒')} ʟɪᴍɪᴛ : <b>{limit} sᴍs/ʀᴇǫ</b>"
    owner_disp = get_owner_display(d)
    owner_line = f"<b>Owner:</b> {esc(owner_disp)}\n" if owner_disp else ""
    return (
        f"╭───────────────────────╮\n"
        f"   {em(EMOJI_PHONE, '📱')} <b>{sc('sms blast bot')}</b>\n"
        f"        <i>{_VERSION}</i>\n"
        f"╰───────────────────────╯\n"
        f"{owner_line}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{em(EMOJI_STAR, '👤')} ʀᴏʟᴇ   : {role_tag(uid, d)}\n"
        f"{em(EMOJI_MONEY, '💰')} ᴄʀᴇᴅɪᴛs: <b>{credits}</b>\n"
        f"{em(EMOJI_STAR, '🔢')} ᴜsᴇs   : <b>{udata.get('uses', 0)}</b>\n"
        f"{limit_line}\n"
        f"{em(EMOJI_FIRE, '🔥')} ᴀᴘɪs   : <b>{shown}</b>\n"
        f"{em(EMOJI_GEAR, '🔄')} sᴄᴀɴɴᴇʀ: {get_scan_status()}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"ᴛᴀᴘ <b>{sc('send sms')}</b> ᴛᴏ sᴛᴀʀᴛ {em(EMOJI_ROCKET, '🚀')}"
    )

# ============================================================
#  BACKGROUND TASKS
# ============================================================
async def send_fire(bot, chat_id):
    try:
        s = await get_http_session()
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": "🔥", "message_effect_id": FIRE_EFFECT_ID}
        async with s.post(url, json=payload, timeout=5) as r:
            res = await r.json()
            if res.get("ok"):
                mid = res["result"]["message_id"]
                await asyncio.sleep(2)
                du = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
                await s.post(du, json={"chat_id": chat_id, "message_id": mid})
    except Exception: pass

async def send_log(bot, text):
    try:
        await bot.send_message(LOG_CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e: log.error(f"Channel log failed: {e}")

async def send_video(bot, chat_id, caption=""):
    try:
        d = load(); vids = d.get("videos", [])
        if vids: await bot.send_video(chat_id, video=random.choice(vids), caption=caption, parse_mode="HTML")
    except Exception: pass

async def backup_loop(bot):
    while True:
        try:
            await asyncio.sleep(3600)
            if os.path.exists(_DATA_FILE):
                sz = os.path.getsize(_DATA_FILE)
                if sz > 45 * 1024 * 1024: continue
                cap = (f"📦 <b>BACKUP</b>\n\n"
                       f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                       f"📂 {round(sz / 1024, 1)} KB")
                await bot.send_document(chat_id=LOG_CHANNEL_ID,
                                        document=FSInputFile(_DATA_FILE),
                                        caption=cap, parse_mode="HTML")
        except asyncio.CancelledError: raise
        except Exception as e:
            log.error(f"Backup failed: {e}"); await asyncio.sleep(60)

async def scanner_loop(bot):
    global CACHED_DEVICES, LAST_SCAN_TIME, LAST_SCAN_DURATION, SCANNING_IN_PROGRESS
    global LAST_KNOWN_DEVICE_COUNT, LAST_KNOWN_FB_COUNTS, DEVICE_HEALTH_LOG
    log.info("Scanner started (10s interval, 200 FB parallel)")
    first_done = False
    while True:
        async with SCAN_LOCK:
            if SCANNING_IN_PROGRESS: need_wait = True
            else: need_wait = False; SCANNING_IN_PROGRESS = True
        if need_wait:
            await asyncio.sleep(2); continue
        start = time.time()
        try:
            d = load()
            fbs = d.get("firebases", [])
            if not fbs:
                async with SCAN_LOCK: SCANNING_IN_PROGRESS = False
                await asyncio.sleep(_BACKGROUND_SCAN_INTERVAL); continue
            devices = await scan_all(d)
            dur = time.time() - start
            CACHED_DEVICES = devices
            LAST_SCAN_DURATION = dur
            # ✅ FIX: Sirf update karo agar devices mile
            if len(devices) > 0:
                new_counts = {}
                for fb in fbs:
                    fid = fb["id"]
                    online = sum(1 for x in devices if x["fb_id"] == fid)
                    new_counts[fid] = {
                        "label": fb.get("label", fb["url"][:30]),
                        "online": online, "last_update": int(time.time())
                    }
                FB_DEVICE_COUNTS.clear()
                FB_DEVICE_COUNTS.update(new_counts)
                LAST_KNOWN_FB_COUNTS = dict(new_counts)
                LAST_KNOWN_DEVICE_COUNT = len(devices) * CURRENT_POWER_MODE
                LAST_SCAN_TIME = time.time()
            DEVICE_HEALTH_LOG.append({
                "timestamp": int(time.time()), "devices_found": len(devices),
                "dbs_scanned": len(fbs), "duration_sec": round(dur, 2),
                "errors": len(FB_SCAN_ERRORS),
                "status": "healthy" if devices else "no_devices"
            })
            if len(DEVICE_HEALTH_LOG) > 100: DEVICE_HEALTH_LOG = DEVICE_HEALTH_LOG[-100:]
            log.info(f"[SCAN] {len(devices)} devices | {dur:.1f}s | err: {len(FB_SCAN_ERRORS)}")
            if devices and not first_done:
                try:
                    shown = len(devices) * CURRENT_POWER_MODE
                    await bot.send_message(MAIN_OWNER,
                        f"{em(EMOJI_ROCKET, '🚀')} <b>SCANNER ACTIVE!</b>\n\n"
                        f"{em(EMOJI_PHONE, '📱')} Devices: <b>{len(devices)}</b>\n"
                        f"{em(EMOJI_FIRE, '🔥')} APIs: <b>{shown}</b>\n"
                        f"{em(EMOJI_STAR, '🔢')} Mode: <b>{CURRENT_POWER_MODE}x</b>\n"
                        f"{em(EMOJI_GEAR, '🔄')} DBs: <b>{len(fbs)}</b>\n"
                        f"{em(EMOJI_WARNING, '⏱')} Time: <b>{dur:.1f}s</b>\n"
                        f"{em(EMOJI_CROSS, '❌')} Errors: <b>{len(FB_SCAN_ERRORS)}</b>",
                        parse_mode="HTML")
                except Exception as e: log.warning(f"Owner notify: {e}")
                first_done = True
        except Exception as e:
            log.error(f"[SCAN] Fatal: {e}", exc_info=True)
        finally:
            async with SCAN_LOCK: SCANNING_IN_PROGRESS = False
        elapsed = time.time() - start
        gap = max(0.0, _BACKGROUND_SCAN_INTERVAL - elapsed)
        if gap > 0: await asyncio.sleep(gap)

async def supervised(name, func, bot):
    backoff = 5
    while True:
        try:
            log.info(f"[SUP] Starting {name}")
            await func(bot)
        except asyncio.CancelledError: raise
        except Exception as e:
            log.error(f"[SUP] {name} crashed: {e}", exc_info=True)
            await asyncio.sleep(backoff); backoff = min(backoff * 2, 60)
        else:
            log.warning(f"[SUP] {name} ended, restarting")
            await asyncio.sleep(5)

async def watchdog_loop(bot):
    fails = 0
    while True:
        try:
            await asyncio.sleep(_WATCHDOG_INTERVAL)
            try:
                me = await asyncio.wait_for(bot.get_me(), timeout=15)
                if me is None: raise RuntimeError("get_me None")
                fails = 0
                log.debug(f"[WATCHDOG] OK @{me.username}")
            except asyncio.TimeoutError:
                fails += 1; log.warning(f"[WATCHDOG] Timeout ({fails}/{_WATCHDOG_MAX_FAILS})")
            except Exception as e:
                fails += 1; log.warning(f"[WATCHDOG] Fail ({fails}/{_WATCHDOG_MAX_FAILS}): {e}")
            if fails >= _WATCHDOG_MAX_FAILS:
                log.critical("[WATCHDOG] Max fails → restart")
                raise RuntimeError("Watchdog restart")
        except asyncio.CancelledError: raise
        except RuntimeError: raise
        except Exception as e:
            log.error(f"[WATCHDOG] Unexpected: {e}")
            fails += 1
            if fails >= _WATCHDOG_MAX_FAILS: raise RuntimeError("Watchdog unexpected")

async def heartbeat_loop():
    while True:
        try:
            _heartbeat(); await asyncio.sleep(_HEARTBEAT_INTERVAL)
        except asyncio.CancelledError: raise
        except Exception: await asyncio.sleep(5)

async def owner_panel_refresher(bot):
    """Auto-refresh owner panel every N seconds."""
    while True:
        try:
            await asyncio.sleep(_PANEL_REFRESH_INTERVAL)
            now = time.time()
            for uid, st in list(_OWNER_PANEL_STATE.items()):
                if not st.get("active"): continue
                if now - st.get("last_user_action", 0) < 2: continue
                try:
                    d = load()
                    if not is_owner(uid, d):
                        _OWNER_PANEL_STATE.pop(uid, None); continue
                    await bot.edit_message_text(
                        text=owner_panel_text(d),
                        chat_id=st["chat_id"],
                        message_id=st["msg_id"],
                        reply_markup=owner_kb(d),
                        parse_mode="HTML",
                    )
                except TelegramRetryAfter as e:
                    await asyncio.sleep(min(e.retry_after, 30))
                except TelegramBadRequest: pass
                except Exception as e: log.debug(f"Panel refresh {uid}: {e}")
        except asyncio.CancelledError: raise
        except Exception as e: log.error(f"Refresher loop: {e}")

# ============================================================
#  BLAST ENGINE
# ============================================================
async def blast(bot, msg, uid, number, message, count, devices, speed=SPEED_DEFAULT):
    global CURRENT_POWER_MODE
    if not devices:
        await msg.answer(f"{em(EMOJI_WARNING, '😴')} No APIs online!", parse_mode="HTML"); return
    pm = CURRENT_POWER_MODE
    cap = len(devices) * pm
    if count > cap:
        await msg.answer(f"{em(EMOJI_WARNING, '⚠️')} Max <b>{cap}</b>. Auto-adjust.", parse_mode="HTML")
        count = cap
    if count <= 0:
        await msg.answer(f"{em(EMOJI_CROSS, '❌')} Invalid.", parse_mode="HTML"); return
    if GLOBAL_BLAST_SEM.locked(): log.warning(f"[BLAST] Global limit wait uid={uid}")
    async with GLOBAL_BLAST_SEM:
        await _run_blast(bot, msg, uid, number, message, count, devices, speed, pm)

async def _run_blast(bot, msg, uid, number, message, count, devices, speed, pm):
    _spawn(send_video(bot, msg.chat.id, caption=f"💣 <b>Blast on {esc(mask_number(number))}!</b>"))
    async with SESSIONS_LOCK:
        if uid in USER_SESSIONS:
            old = USER_SESSIONS[uid]
            if old.task and not old.task.done():
                await msg.answer(f"{em(EMOJI_WARNING, '⚠️')} Blast already running!", parse_mode="HTML"); return
            del USER_SESSIONS[uid]
        session = UserSession(uid)
        session.number = number
        session.blast_data = load()
        USER_SESSIONS[uid] = session
    is_regular = not is_admin(uid, load()) and not is_owner(uid, load())
    init_credits = get_user_credits(uid, load()) if is_regular else None
    slabel = "🚀 FAST" if speed == SPEED_FAST else "⚡ MEDIUM" if speed == SPEED_MEDIUM else "🐢 SLOW"
    try:
        pmsg = await msg.answer(progress_text(0, 0, count, init_credits, slabel),
                                reply_markup=stop_kb(), parse_mode="HTML")
    except Exception as e:
        log.error(f"Progress msg: {e}")
        async with SESSIONS_LOCK: USER_SESSIONS.pop(uid, None)
        return
    sent_ok = 0; sent_fail = 0; msgs_left = count
    api_delta = {}; last_upd = time.time(); start = time.time()
    edit_lock = asyncio.Lock()
    eff_conc = min(len(devices), _SEND_CONCURRENCY)
    sem = asyncio.Semaphore(eff_conc)
    log.info(f"[BLAST] uid={uid} n={count} devs={len(devices)} pm={pm}x conc={eff_conc}")

    async def upd_progress(force=False):
        nonlocal last_upd
        async with edit_lock:
            now = time.time()
            if not force and now - last_upd < _PROGRESS_UPDATE_INTERVAL: return
            last_upd = now
            try:
                live = get_user_credits(uid, load()) if is_regular else None
                await pmsg.edit_text(
                    progress_text(sent_ok, sent_fail, count, live, slabel),
                    reply_markup=stop_kb() if not session.cancelled else None,
                    parse_mode="HTML")
            except TelegramRetryAfter as e: await asyncio.sleep(e.retry_after + 1)
            except (TelegramBadRequest, Exception): pass

    async def send_one(device, pass_num):
        nonlocal sent_ok, sent_fail, msgs_left
        async with sem:
            async with session.lock:
                if session.cancelled or msgs_left <= 0: return
                msgs_left -= 1
            fb_id = device["fb_id"]; fb_url = device["fb_url"]
            dev_id = device["dev_id"]; sims = device.get("sims", [])
            sim_slots = [s.get("simSlotIndex", 0) for s in sims if isinstance(s, dict)] if sims else [0]
            if not sim_slots: sim_slots = [0]
            sim = sim_slots[pass_num % len(sim_slots)]
            ok = False
            try: ok = await sms_via_device(fb_url, dev_id, sim, number, message)
            except asyncio.CancelledError: raise
            except Exception as e: log.warning(f"[SEND] {str(dev_id)[:12]}: {str(e)[:80]}")
            async with session.lock:
                if ok:
                    sent_ok += 1
                    if is_regular:
                        deduct_credits(uid, 1, session.blast_data)
                        session.blast_data["stats"]["total_sent"] = session.blast_data["stats"].get("total_sent", 0) + 1
                        k = str(uid)
                        if k in session.blast_data["users"]:
                            session.blast_data["users"][k]["uses"] = session.blast_data["users"][k].get("uses", 0) + 1
                        session.blast_data.setdefault("sms_history", {}).setdefault(str(uid), []).append({
                            "number": number, "message": str(message)[:100],
                            "timestamp": int(time.time()), "status": "sent"
                        })
                else: sent_fail += 1
                if fb_id not in api_delta: api_delta[fb_id] = {"sent": 0, "failed": 0}
                api_delta[fb_id]["sent" if ok else "failed"] += 1
            await upd_progress()

    async def do_send():
        try:
            for pass_num in range(pm):
                if msgs_left <= 0: break
                async with session.lock:
                    if session.cancelled: break
                tasks = []
                for device in devices:
                    async with session.lock:
                        if msgs_left <= 0 or session.cancelled: break
                    tasks.append(send_one(device, pass_num))
                if tasks: await asyncio.gather(*tasks, return_exceptions=True)
                if speed > 0: await asyncio.sleep(speed)
        except asyncio.CancelledError: raise
        except Exception as e: log.error(f"[LOOP] uid={uid}: {e}", exc_info=True)
        finally:
            async with session.lock:
                session.sent = sent_ok; session.failed = sent_fail

    task = asyncio.create_task(do_send())
    session.task = task
    try: await task
    except asyncio.CancelledError: session.cancelled = True
    except Exception as e: log.error(f"[BLAST] task uid={uid}: {e}")
    finally:
        try:
            if not is_regular:
                df = session.blast_data if session.blast_data else load()
                df["stats"]["total_sent"] = df["stats"].get("total_sent", 0) + sent_ok
                df["stats"]["total_failed"] = df["stats"].get("total_failed", 0) + sent_fail
                for fid, dl in api_delta.items():
                    df["stats"].setdefault("api_usage", {}).setdefault(fid, {"sent": 0, "failed": 0})
                    df["stats"]["api_usage"][fid]["sent"] += dl["sent"]
                    df["stats"]["api_usage"][fid]["failed"] += dl["failed"]
                k = str(uid)
                if k in df["users"]:
                    df["users"][k]["uses"] = df["users"][k].get("uses", 0) + sent_ok
                df.setdefault("sms_history", {}).setdefault(str(uid), []).append({
                    "number": number, "message": str(message)[:100],
                    "timestamp": int(time.time()),
                    "status": "completed" if not session.cancelled else "stopped"
                })
                save(df)
            else:
                df = session.blast_data if session.blast_data else load()
                df["stats"]["total_failed"] = df["stats"].get("total_failed", 0) + sent_fail
                for fid, dl in api_delta.items():
                    df["stats"].setdefault("api_usage", {}).setdefault(fid, {"sent": 0, "failed": 0})
                    df["stats"]["api_usage"][fid]["failed"] += dl["failed"]
                save(df)
        except Exception as e: log.error(f"[BLAST] save failed: {e}")
        finally:
            async with SESSIONS_LOCK: USER_SESSIONS.pop(uid, None)

    was_cancel = session.cancelled
    await upd_progress(force=True)
    dur = max(1, int(time.time() - start))
    rate = sent_ok / dur
    log_activity(load(), "sms_blast", uid,
                 f"sent={sent_ok} failed={sent_fail} total={count} dur={dur}s rate={rate:.1f} pm={pm}x")
    save()
    try:
        ci = await bot.get_chat(uid)
        u_name = ci.full_name or "Unknown"
        u_uname = f"@{ci.username}" if ci.username else "None"
    except Exception:
        u_name = load().get("users", {}).get(str(uid), {}).get("name", "Unknown")
        u_uname = "None"
    _spawn(send_log(bot,
        f"🚀 <b>SMS BLAST</b>\n\n"
        f"👤 {esc(u_name)}\n🆔 <code>{uid}</code>\n🌐 {esc(u_uname)}\n"
        f"📞 <code>{esc(number)}</code>\n💬 <code>{esc(str(message)[:100])}</code>\n"
        f"✅ {sent_ok} | ❌ {sent_fail} | 📊 {count}\n"
        f"🔢 {pm}x | ⚡ {rate:.1f}/s | ⏱ {fmt_duration(dur)}\n"
        f"🛑 {'STOPPED' if was_cancel else 'COMPLETED'}"))
    icon = em(EMOJI_CHECK, "✅") if sent_fail == 0 and sent_ok > 0 else em(EMOJI_WARNING, "⚠️") if sent_ok > 0 else em(EMOJI_CROSS, "❌")
    ctxt = ""
    if is_regular:
        ctxt = f"\n{em(EMOJI_MONEY, '💰')} Used: <b>{sent_ok}</b> | Left: <b>{get_user_credits(uid, load())}</b>"
    stxt = f"\n{em(EMOJI_CROSS, '🛑')} <b>Stopped!</b>" if was_cancel else ""
    if is_owner(uid, load()):
        back = [btn("owner panel", "owner:home", EMOJI_GEAR, "🔙", style="primary")]
    elif is_admin(uid, load()):
        back = [btn("admin panel", "admin:home", EMOJI_GEAR, "🔙", style="primary")]
    else:
        back = [btn("send another", "user:send", EMOJI_ROCKET, "📤", style="success"),
                btn("home", "user:home", EMOJI_STAR, "🏠", style="primary")]
    try:
        await pmsg.edit_text(
            f"{icon} <b>Blast Result</b>{stxt}\n\n"
            f"{em(EMOJI_PHONE, '📞')} <code>{esc(mask_number(number))}</code>\n"
            f"{em(EMOJI_STAR, '💬')} <code>{esc(str(message)[:50])}</code>\n"
            f"{em(EMOJI_CHECK, '✅')} Sent: <b>{sent_ok}</b>\n"
            f"{em(EMOJI_CROSS, '❌')} Failed: <b>{sent_fail}</b>\n"
            f"{em(EMOJI_STAR, '🔢')} Power: <b>{pm}x</b>\n"
            f"{em(EMOJI_ROCKET, '⚡')} Rate: <b>{rate:.1f}/s</b>\n"
            f"{em(EMOJI_GEAR, '⏱')} {fmt_duration(dur)}{ctxt}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[back]), parse_mode="HTML")
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        try:
            await pmsg.edit_text(f"{icon} Done. Sent: {sent_ok} | Failed: {sent_fail}",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=[back]), parse_mode="HTML")
        except Exception: pass
    except Exception as e: log.error(f"Final edit: {e}")

# ============================================================
#  FORCE JOIN
# ============================================================
async def check_member(bot, uid, ch_id):
    try:
        cid = int(str(ch_id).strip())
        m = await bot.get_chat_member(cid, uid)
        return m.status in ("member", "administrator", "creator")
    except Exception: return False

async def joined_all(bot, uid, d):
    if is_owner(uid, d): return True, []
    fj = d.get("force_join", {})
    if not fj.get("enabled", False): return True, []
    missing = []
    for ch in fj.get("channels", []):
        if ch.get("required", True):
            if not await check_member(bot, uid, ch["id"]): missing.append(ch)
    return len(missing) == 0, missing

def fj_text(missing):
    lines = [f"{em(EMOJI_CROSS, '⛔')} <b>Pehle join karein!</b>\n", f"{em(EMOJI_BELL, '👇')} ᴊᴏɪɴ:"]
    for ch in missing: lines.append(f"\n• <a href='{esc(ch['link'])}'>{esc(ch.get('title', 'Channel'))}</a>")
    lines.append(f"\n\n<i>Join ke baad /start karein.</i>")
    return "\n".join(lines)

def fj_kb(missing):
    rows = []
    for ch in missing:
        rows.append([btn_url(f"join {ch.get('title', 'Channel')}", ch["link"], EMOJI_BELL, "🔔", style="success")])
    rows.append([btn("refresh / check", "fj:check", EMOJI_GEAR, "🔄", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ============================================================
#  ROUTER
# ============================================================
R = Router()

@R.message(Command("start"))
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    _spawn(send_fire(m.bot, m.chat.id))
    d = load()
    is_new = reg_user(uid, m.from_user.full_name or "User", d)
    args = (m.text or "").split()
    code = args[1] if len(args) > 1 else ""
    if code.startswith("REF") and not d["users"].get(str(uid), {}).get("referred_by"):
        ok, _, referrer = process_referral(uid, code, d)
        if ok and referrer:
            try:
                await m.bot.send_message(referrer,
                    f"{em(EMOJI_GIFT, '🎉')} <b>Referral!</b> +{d['settings']['ref_credits']} credits!",
                    parse_mode="HTML")
            except Exception: pass
    save()
    if is_new:
        _spawn(send_log(m.bot,
            f"🆕 <b>NEW USER</b>\n\n"
            f"👤 {esc(m.from_user.full_name or 'User')}\n"
            f"🆔 <code>{uid}</code>\n🌐 @{esc(m.from_user.username or 'None')}\n"
            f"📅 {fmt_time(int(time.time()))}"))
    joined, missing = await joined_all(m.bot, uid, d)
    if not joined:
        await m.answer(fj_text(missing), reply_markup=fj_kb(missing),
                       parse_mode="HTML", disable_web_page_preview=True); return
    owner_disp = get_owner_display(d)
    cap = f"{em(EMOJI_ROCKET, '🚀')} Welcome!"
    if owner_disp: cap += f"\nOwner: {owner_disp}"
    _spawn(send_video(m.bot, m.chat.id, caption=cap))
    if is_owner(uid, d):
        sent = await m.answer(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
        _OWNER_PANEL_STATE[uid] = {"chat_id": sent.chat.id, "msg_id": sent.message_id,
                                    "active": True, "last_user_action": time.time()}
        return
    if is_admin(uid, d):
        await m.answer(admin_panel_text(d), reply_markup=admin_kb(d), parse_mode="HTML"); return
    if is_banned(uid, d):
        await m.answer(f"{em(EMOJI_CROSS, '🚫')} <b>Banned.</b>", parse_mode="HTML"); return
    if not can_use(uid, d):
        await m.answer(f"{em(EMOJI_CROSS, '⛔')} <b>No access.</b>", parse_mode="HTML"); return
    await m.answer(user_home_text(uid, d), reply_markup=user_kb(), parse_mode="HTML")

@R.callback_query(F.data == "fj:check")
async def fj_check(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    d = load()
    joined, missing = await joined_all(cq.bot, uid, d)
    if not joined:
        try: await cq.answer("❌ Not joined yet!", show_alert=True)
        except Exception: pass
        try:
            await cq.message.edit_text(fj_text(missing), reply_markup=fj_kb(missing),
                                       parse_mode="HTML", disable_web_page_preview=True)
        except Exception: pass
        return
    try: await cq.answer("✅ Verified!")
    except Exception: pass
    owner_disp = get_owner_display(d)
    cap = f"{em(EMOJI_ROCKET, '🚀')} Welcome!"
    if owner_disp: cap += f"\nOwner: {owner_disp}"
    _spawn(send_video(cq.bot, cq.message.chat.id, caption=cap))
    try:
        if is_owner(uid, d):
            await cq.message.answer(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
        elif is_admin(uid, d):
            await cq.message.answer(admin_panel_text(d), reply_markup=admin_kb(d), parse_mode="HTML")
        else:
            await cq.message.answer(user_home_text(uid, d), reply_markup=user_kb(), parse_mode="HTML")
    except Exception: pass

# ----- USER SEND -----
@R.callback_query(F.data == "user:send")
async def user_send_start(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    joined, missing = await joined_all(cq.bot, uid, d)
    if not joined:
        try: await cq.answer("⛔ Join first!", show_alert=True)
        except Exception: pass
        try:
            await cq.message.edit_text(fj_text(missing), reply_markup=fj_kb(missing),
                                       parse_mode="HTML", disable_web_page_preview=True)
        except Exception: pass
        return
    if not can_use(uid, d):
        try: await cq.answer("🚫 Denied!", show_alert=True)
        except Exception: pass
        return
    if not is_admin(uid, d) and not is_owner(uid, d):
        ulim = get_user_send_limit(uid, d)
        if ulim is not None and ulim <= 0:
            try: await cq.answer("🚫 Limit 0.", show_alert=True)
            except Exception: pass
            return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.send_number)
    try:
        await cq.message.edit_text(
            f"{em(EMOJI_PHONE, '📞')} <b>{sc('step 1/4')} — {sc('number')}</b>\n\n"
            f"Jis number pe SMS bhejna hai:\n<i>Example: +919876543210</i>",
            reply_markup=kb([(f"{sc('cancel')}", "user:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.send_number)
async def user_got_number(m: Message, state: FSMContext):
    number = (m.text or "").strip()
    clean = number.replace("+", "").replace(" ", "").replace("-", "")
    if not clean.isdigit() or len(clean) < 7:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Invalid number.", parse_mode="HTML"); return
    if number in PROTECTED_NUMBERS:
        d = load(); puid = PROTECTED_NUMBERS[number]
        if not is_owner(m.from_user.id, d) and m.from_user.id != puid:
            await m.answer(f"{em(EMOJI_LOCK, '🔒')} Protected number!", parse_mode="HTML"); return
    await state.update_data(number=number)
    await state.set_state(S.send_message)
    await m.answer(
        f"{em(EMOJI_CHECK, '✅')} Number: <code>{esc(mask_number(number))}</code>\n\n"
        f"{em(EMOJI_STAR, '💬')} <b>{sc('step 2/4')} — {sc('message')}</b>\n\nMessage:",
        reply_markup=kb([(f"{sc('cancel')}", "user:cancel")]), parse_mode="HTML")

@R.message(S.send_message)
async def user_got_message(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if not txt:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Empty.", parse_mode="HTML"); return
    if len(txt) > 1000:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Too long (max 1000).", parse_mode="HTML"); return
    await state.update_data(message=txt)
    await state.set_state(S.send_speed)
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Saved!\n\n{em(EMOJI_ROCKET, '⚡')} <b>{sc('step 3/4')} — {sc('speed')}</b>",
                   reply_markup=speed_kb("user"), parse_mode="HTML")

@R.callback_query(F.data.in_({"user:speed:fast", "user:speed:medium", "user:speed:slow"}))
async def user_speed_sel(cq: CallbackQuery, state: FSMContext):
    try: await cq.answer()
    except Exception: pass
    d = load(); uid = cq.from_user.id
    smap = {"user:speed:fast": SPEED_FAST, "user:speed:medium": SPEED_MEDIUM, "user:speed:slow": SPEED_SLOW}
    sel = smap.get(cq.data, SPEED_FAST)
    label = "🚀 FAST" if sel == SPEED_FAST else "⚡ MEDIUM" if sel == SPEED_MEDIUM else "🐢 SLOW"
    await state.update_data(send_speed=sel)
    await state.set_state(S.send_count)
    devices = CACHED_DEVICES[:] if CACHED_DEVICES else []
    if not devices:
        try: devices = await scan_all(d)
        except Exception: devices = []
    real = len(devices)
    cnt = real * CURRENT_POWER_MODE if real > 0 else LAST_KNOWN_DEVICE_COUNT
    cinfo = ""
    if not is_admin(uid, d) and not is_owner(uid, d):
        uc = get_user_credits(uid, d)
        cinfo = f"\n{em(EMOJI_MONEY, '💰')} Credits: <b>{uc}</b>"
        ulim = get_user_send_limit(uid, d)
        if ulim is not None and ulim > 0: cinfo += f"\n{em(EMOJI_LOCK, '🔒')} Limit: <b>{ulim} SMS/req</b>"
        elif ulim is not None and ulim <= 0: cinfo += f"\n{em(EMOJI_CROSS, '🚫')} <b>BLOCKED</b>"
        else: cinfo += f"\n{em(EMOJI_LOCK, '🔓')} Limit: <b>Unlimited</b>"
        cinfo += "\n"
    try:
        await cq.message.edit_text(
            f"{label} <b>selected!</b>\n\n"
            f"{em(EMOJI_STAR, '📊')} <b>{sc('step 4/4')} — {sc('count')}</b>\n\n"
            f"{em(EMOJI_FIRE, '🔥')} Online APIs : <b>{cnt}</b>\n"
            f"{em(EMOJI_CHECK, '📤')} Max SMS     : <b>{cnt}</b>{cinfo}\n\nKitne SMS?",
            reply_markup=kb([(f"{sc('cancel')}", "user:cancel")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.send_count)
async def user_got_count(m: Message, state: FSMContext):
    d = load(); uid = m.from_user.id
    fsmd = await state.get_data()
    try:
        cnt = int((m.text or "").strip())
        if cnt < 1: raise ValueError
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Number bhejo.", parse_mode="HTML"); return
    await state.clear()
    number = fsmd.get("number", ""); msg_text = fsmd.get("message", "")
    speed = fsmd.get("send_speed", SPEED_DEFAULT)
    if not is_admin(uid, d) and not is_owner(uid, d):
        cr = get_user_credits(uid, d)
        if cr <= 0:
            await m.answer(f"{em(EMOJI_CROSS, '❌')} <b>No credits!</b>",
                           reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML"); return
        if cnt > cr:
            await m.answer(f"{em(EMOJI_WARNING, '⚠️')} Only {cr} credits.", parse_mode="HTML")
            cnt = cr
        ulim = get_user_send_limit(uid, d)
        if ulim is not None:
            if ulim <= 0:
                await m.answer(f"{em(EMOJI_CROSS, '🚫')} <b>Limit 0!</b>",
                               reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML"); return
            if cnt > ulim:
                await m.answer(f"{em(EMOJI_LOCK, '🔒')} Limit: {ulim}.", parse_mode="HTML")
                cnt = ulim
    devices = CACHED_DEVICES[:] if CACHED_DEVICES else []
    if not devices:
        try: devices = await scan_all(d)
        except Exception: devices = []
    if not devices:
        await m.answer(f"{em(EMOJI_WARNING, '😴')} No APIs!",
                       reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML"); return
    await blast(m.bot, m, uid, number, msg_text, cnt, devices, speed)

# ----- OWNER SEND -----
@R.callback_query(F.data == "owner:send")
async def owner_send_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.owner_send_number)
    try:
        await cq.message.edit_text(f"{em(EMOJI_CROWN, '👑')} <b>Owner SMS</b>\n\n<b>Step 1/4 — Number</b>",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.owner_send_number)
async def owner_got_number(m: Message, state: FSMContext):
    number = (m.text or "").strip()
    clean = number.replace("+", "").replace(" ", "").replace("-", "")
    if not clean.isdigit() or len(clean) < 7:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Invalid.", parse_mode="HTML"); return
    await state.update_data(number=number)
    await state.set_state(S.owner_send_message)
    await m.answer(f"{em(EMOJI_CHECK, '✅')} <code>{esc(number)}</code>\n\n<b>Step 2/4 — Message</b>",
                   reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")

@R.message(S.owner_send_message)
async def owner_got_message(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if not txt:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Empty.", parse_mode="HTML"); return
    await state.update_data(message=txt)
    await state.set_state(S.owner_send_speed)
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Saved!\n\n<b>Step 3/4 — Speed</b>",
                   reply_markup=speed_kb("owner"), parse_mode="HTML")

@R.callback_query(F.data.in_({"owner:speed:fast", "owner:speed:medium", "owner:speed:slow"}))
async def owner_speed_sel(cq: CallbackQuery, state: FSMContext):
    try: await cq.answer()
    except Exception: pass
    smap = {"owner:speed:fast": SPEED_FAST, "owner:speed:medium": SPEED_MEDIUM, "owner:speed:slow": SPEED_SLOW}
    sel = smap.get(cq.data, SPEED_FAST)
    label = "🚀 FAST" if sel == SPEED_FAST else "⚡ MEDIUM" if sel == SPEED_MEDIUM else "🐢 SLOW"
    await state.update_data(send_speed=sel)
    await state.set_state(S.owner_send_count)
    devices = CACHED_DEVICES[:] if CACHED_DEVICES else []
    if not devices:
        try: devices = await scan_all(load())
        except Exception: devices = []
    cnt = len(devices) * CURRENT_POWER_MODE if devices else LAST_KNOWN_DEVICE_COUNT
    try:
        await cq.message.edit_text(f"{label} selected!\n\n<b>Step 4/4</b>\n\n🔥 APIs: <b>{cnt}</b>\n\nKitne?",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.owner_send_count)
async def owner_got_count(m: Message, state: FSMContext):
    fsmd = await state.get_data()
    try:
        cnt = int((m.text or "").strip())
        if cnt < 1: raise ValueError
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Number bhejo.", parse_mode="HTML"); return
    await state.clear()
    number = fsmd.get("number", ""); msg_text = fsmd.get("message", "")
    speed = fsmd.get("send_speed", SPEED_DEFAULT)
    devices = CACHED_DEVICES[:] if CACHED_DEVICES else []
    if not devices:
        try: devices = await scan_all(load())
        except Exception: devices = []
    if not devices:
        await m.answer(f"{em(EMOJI_WARNING, '😴')} No APIs!",
                       reply_markup=kb([(f"{sc('owner panel')}", "owner:home")]), parse_mode="HTML"); return
    await blast(m.bot, m, m.from_user.id, number, msg_text, cnt, devices, speed)

# ----- ADMIN SEND -----
@R.callback_query(F.data == "admin:send")
async def admin_send_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.admin_send_number)
    try:
        await cq.message.edit_text(f"{em(EMOJI_SHIELD, '🛡')} <b>Admin SMS</b>\n\n<b>Step 1/4 — Number</b>",
                                   reply_markup=kb([(f"{sc('cancel')}", "admin:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.admin_send_number)
async def admin_got_number(m: Message, state: FSMContext):
    number = (m.text or "").strip()
    clean = number.replace("+", "").replace(" ", "").replace("-", "")
    if not clean.isdigit() or len(clean) < 7:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Invalid.", parse_mode="HTML"); return
    if number in PROTECTED_NUMBERS:
        puid = PROTECTED_NUMBERS[number]
        if not is_owner(m.from_user.id, load()) and m.from_user.id != puid:
            await m.answer(f"{em(EMOJI_LOCK, '🔒')} Protected!", parse_mode="HTML"); return
    await state.update_data(number=number)
    await state.set_state(S.admin_send_message)
    await m.answer(f"{em(EMOJI_CHECK, '✅')} <code>{esc(mask_number(number))}</code>\n\n<b>Step 2/4 — Message</b>",
                   reply_markup=kb([(f"{sc('cancel')}", "admin:home")]), parse_mode="HTML")

@R.message(S.admin_send_message)
async def admin_got_message(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if not txt:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Empty.", parse_mode="HTML"); return
    await state.update_data(message=txt)
    await state.set_state(S.admin_send_speed)
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Saved!\n\n<b>Step 3/4 — Speed</b>",
                   reply_markup=speed_kb("admin"), parse_mode="HTML")

@R.callback_query(F.data.in_({"admin:speed:fast", "admin:speed:medium", "admin:speed:slow"}))
async def admin_speed_sel(cq: CallbackQuery, state: FSMContext):
    try: await cq.answer()
    except Exception: pass
    smap = {"admin:speed:fast": SPEED_FAST, "admin:speed:medium": SPEED_MEDIUM, "admin:speed:slow": SPEED_SLOW}
    sel = smap.get(cq.data, SPEED_FAST)
    label = "🚀 FAST" if sel == SPEED_FAST else "⚡ MEDIUM" if sel == SPEED_MEDIUM else "🐢 SLOW"
    await state.update_data(send_speed=sel)
    await state.set_state(S.admin_send_count)
    devices = CACHED_DEVICES[:] if CACHED_DEVICES else []
    if not devices:
        try: devices = await scan_all(load())
        except Exception: devices = []
    cnt = len(devices) * CURRENT_POWER_MODE if devices else LAST_KNOWN_DEVICE_COUNT
    try:
        await cq.message.edit_text(f"{label} selected!\n\n<b>Step 4/4</b>\n\n🔥 APIs: <b>{cnt}</b>\n\nKitne?",
                                   reply_markup=kb([(f"{sc('cancel')}", "admin:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.admin_send_count)
async def admin_got_count(m: Message, state: FSMContext):
    fsmd = await state.get_data()
    try:
        cnt = int((m.text or "").strip())
        if cnt < 1: raise ValueError
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Number bhejo.", parse_mode="HTML"); return
    await state.clear()
    number = fsmd.get("number", ""); msg_text = fsmd.get("message", "")
    speed = fsmd.get("send_speed", SPEED_DEFAULT)
    devices = CACHED_DEVICES[:] if CACHED_DEVICES else []
    if not devices:
        try: devices = await scan_all(load())
        except Exception: devices = []
    if not devices:
        await m.answer(f"{em(EMOJI_WARNING, '😴')} No APIs!",
                       reply_markup=kb([(f"{sc('admin panel')}", "admin:home")]), parse_mode="HTML"); return
    await blast(m.bot, m, m.from_user.id, number, msg_text, cnt, devices, speed)

# ----- STOP -----
@R.callback_query(F.data == "user:stop_send")
async def stop_blast(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    async with SESSIONS_LOCK:
        s = USER_SESSIONS.get(uid)
        if not s or (s.task and s.task.done()):
            try: await cq.answer("✅ No active blast!", show_alert=True)
            except Exception: pass
            return
        s.cancelled = True
    try: await cq.answer("🛑 Stop signal sent!", show_alert=True)
    except Exception: pass
    try:
        async with s.lock: cs, cf = s.sent, s.failed
        await cq.message.edit_text(f"{em(EMOJI_CROSS, '🛑')} <b>Stopping...</b>\n\n✅ {cs} | ❌ {cf}", parse_mode="HTML")
    except Exception: pass

# ----- POWER MODE -----
@R.callback_query(F.data.startswith("owner:set_power:"))
async def set_power(cq: CallbackQuery, state: FSMContext):
    global CURRENT_POWER_MODE, LAST_KNOWN_DEVICE_COUNT
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try:
        mult = int(cq.data.split("owner:set_power:", 1)[1])
        if mult not in ALLOWED_POWER_MODES: raise ValueError
    except Exception:
        try: await cq.answer("❌ Invalid", show_alert=True)
        except Exception: pass
        return
    old = CURRENT_POWER_MODE
    CURRENT_POWER_MODE = mult
    real = len(CACHED_DEVICES)
    if real > 0: LAST_KNOWN_DEVICE_COUNT = real * mult
    desc = {2: "Safe", 3: "Fast", 4: "Aggressive", 5: "MAXIMUM", 10: "NUCLEAR"}[mult]
    icon = {2: "🚀", 3: "🔥", 4: "💥", 5: "💣", 10: "☠️"}[mult]
    log.info(f"[POWER] {old}x → {mult}x")
    try: await cq.answer(f"{icon} Power: {mult}x\n{desc}", show_alert=True)
    except Exception: pass
    try:
        await cq.message.edit_text(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
        uid = cq.from_user.id
        _OWNER_PANEL_STATE[uid] = {"chat_id": cq.message.chat.id, "msg_id": cq.message.message_id,
                                    "active": True, "last_user_action": time.time()}
    except TelegramBadRequest: pass
    except Exception as e: log.warning(f"Power re-render: {e}")

# ----- OWNER NAME -----
@R.callback_query(F.data == "owner:edit_name")
async def edit_name_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.owner_edit_name)
    cur = get_owner_display(d); cur_s = cur if cur else "<i>(hidden)</i>"
    try:
        await cq.message.edit_text(
            f"{em(EMOJI_CROWN, '✏️')} <b>EDIT OWNER NAME</b>\n\nCurrent: <b>{cur_s}</b>\n\n"
            f"• Text → set\n• <code>null</code>/<code>hide</code> → hide\n• <code>cancel</code>",
            reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.owner_edit_name)
async def edit_name_done(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    raw = (m.text or "").strip(); low = raw.lower()
    if low in ("cancel", "/cancel"):
        await state.clear()
        await m.answer("❌ Cancelled.", reply_markup=owner_kb(d), parse_mode="HTML"); return
    if low in ("null", "none", "empty", "hide", "-", "0"):
        d.setdefault("settings", {})["owner_display"] = None
        save(); await state.clear()
        await m.answer(f"{em(EMOJI_CHECK, '✅')} <b>Hidden!</b>", reply_markup=owner_kb(d), parse_mode="HTML")
        log_activity(d, "owner_name_changed", m.from_user.id, "hidden"); save(); return
    if not raw:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Use <code>null</code>.", parse_mode="HTML"); return
    val = raw[:64]
    d.setdefault("settings", {})["owner_display"] = val
    save(); await state.clear()
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Updated: {esc(val)}", reply_markup=owner_kb(d), parse_mode="HTML")
    log_activity(d, "owner_name_changed", m.from_user.id, f"name={val}"); save()

# ----- LIMIT -----
@R.callback_query(F.data == "owner:set_limit")
async def set_limit_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.set_limit_uid)
    try:
        await cq.message.edit_text(f"{em(EMOJI_LOCK, '🔒')} <b>SET LIMIT</b>\n\nUser ID:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.set_limit_uid)
async def set_limit_uid(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    txt = (m.text or "").strip()
    if txt.lower() in ("cancel", "/cancel"):
        await state.clear()
        await m.answer("❌ Cancelled.", reply_markup=owner_kb(d), parse_mode="HTML"); return
    try: target = int(txt)
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Numeric ID.", parse_mode="HTML"); return
    if str(target) not in d.get("users", {}):
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Not found.", parse_mode="HTML"); return
    await state.update_data(limit_target_uid=target)
    cur = get_user_send_limit(target, d)
    cs = "Unlimited" if cur is None else ("🚫 BLOCKED" if cur <= 0 else f"{cur} SMS/req")
    ud = d["users"][str(target)]
    await state.set_state(S.set_limit_value)
    await m.answer(
        f"{em(EMOJI_LOCK, '🔒')} <b>{esc(str(ud.get('name', '?'))[:30])}</b>\n"
        f"🆔 <code>{target}</code>\n💰 {ud.get('credits', 0)}\n🔒 Current: <b>{cs}</b>\n\n"
        f"Number / <code>0</code> / <code>off</code> / <code>cancel</code>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")

@R.message(S.set_limit_value)
async def set_limit_val(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    txt = (m.text or "").strip().lower()
    if txt in ("cancel", "/cancel"):
        await state.clear()
        await m.answer("❌ Cancelled.", reply_markup=owner_kb(d), parse_mode="HTML"); return
    fsmd = await state.get_data()
    target = fsmd.get("limit_target_uid")
    if not target:
        await state.clear()
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Expired.", reply_markup=owner_kb(d), parse_mode="HTML"); return
    if txt in ("off", "unlimited", "remove", "none", "reset"):
        set_user_send_limit(target, None, d); save(); await state.clear()
        try: await m.bot.send_message(target, f"{em(EMOJI_LOCK, '🔓')} Limit removed!", parse_mode="HTML")
        except Exception: pass
        await m.answer(f"{em(EMOJI_CHECK, '✅')} Unlimited", reply_markup=owner_kb(d), parse_mode="HTML")
        log_activity(d, "limit_removed", m.from_user.id, f"user={target}"); save(); return
    try:
        lv = int(txt)
        if lv < 0: raise ValueError
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Invalid.", parse_mode="HTML"); return
    set_user_send_limit(target, lv, d); save(); await state.clear()
    if lv == 0:
        try: await m.bot.send_message(target, f"{em(EMOJI_CROSS, '🚫')} Limit 0.", parse_mode="HTML")
        except Exception: pass
        st = "🚫 BLOCKED"
    else:
        try: await m.bot.send_message(target, f"{em(EMOJI_LOCK, '🔒')} Limit: {lv} SMS/req", parse_mode="HTML")
        except Exception: pass
        st = f"🔒 {lv} SMS/req"
    await m.answer(f"{em(EMOJI_CHECK, '✅')} <code>{target}</code> → {st}",
                   reply_markup=owner_kb(d), parse_mode="HTML")
    log_activity(d, "limit_set", m.from_user.id, f"user={target} limit={lv}"); save()

@R.callback_query(F.data == "owner:list_limits")
async def list_limits(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    lst = []
    for us, u in d.get("users", {}).items():
        lim = u.get("max_send_limit")
        if lim is not None:
            try: lst.append((int(us), str(u.get("name", "?")), int(lim)))
            except Exception: pass
    if not lst:
        try: await cq.message.edit_text(f"{em(EMOJI_LOCK, '📋')} None limited.",
                                        reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")
        except Exception: pass
        return
    lines = [f"{em(EMOJI_LOCK, '📋')} <b>Limits ({len(lst)})</b>\n"]
    for uid, nm, lim in lst[:30]:
        st = "🚫" if lim <= 0 else f"🔒{lim}"
        lines.append(f"• <code>{uid}</code> — {esc(nm[:18])} — <b>{st}</b>")
    if len(lst) > 30: lines.append(f"<i>+{len(lst) - 30} more</i>")
    try: await cq.message.edit_text("\n".join(lines),
                                    reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

# ----- OWNER HOME -----
@R.callback_query(F.data.in_({"owner:home", "owner:refresh"}))
async def owner_home(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load(); uid = cq.from_user.id
    if not is_owner(uid, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    try:
        await cq.message.edit_text(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
        _OWNER_PANEL_STATE[uid] = {"chat_id": cq.message.chat.id, "msg_id": cq.message.message_id,
                                    "active": True, "last_user_action": time.time()}
    except TelegramBadRequest: pass
    except Exception: pass

# ----- FIREBASE -----
@R.callback_query(F.data.startswith("owner:fb:menu"))
async def fb_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    await state.clear()
    try: await cq.answer()
    except Exception: pass
    parts = cq.data.split(":")
    page = int(parts[3]) if len(parts) > 3 else 0
    try:
        await cq.message.edit_text(f"{em(EMOJI_FIRE, '🔥')} <b>Firebase Manager</b>\n\nTotal: <b>{len(d.get('firebases', []))}</b>",
                                   reply_markup=fb_menu_kb(d, page), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:fb:add")
async def fb_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.add_firebase)
    try:
        await cq.message.edit_text(f"{em(EMOJI_FIRE, '🔥')} <b>Add Firebase</b>\n\n<i>Format: Label | URL</i>",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:fb:menu:0")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.add_firebase)
async def fb_add_done(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    txt = (m.text or "").strip()
    if "|" in txt:
        parts = txt.split("|", 1); label, url = parts[0].strip(), parts[1].strip()
    else:
        url = txt; label = url.replace("https://", "").split(".")[0][:20]
    if not url.startswith("http"):
        await m.answer(f"{em(EMOJI_CROSS, '❌')} URL must start with http.", parse_mode="HTML"); return
    url = url.rstrip("/")
    fbs = d.get("firebases", [])
    if any(fb["url"] == url for fb in fbs):
        await state.clear()
        await m.answer(f"{em(EMOJI_WARNING, '⚠️')} Already!", reply_markup=fb_menu_kb(d), parse_mode="HTML"); return
    fid = str(int(time.time() * 1000))
    existing = {fb["id"] for fb in fbs}
    while fid in existing: fid = str(int(time.time() * 1000) + random.randint(1000, 9999))
    fbs.append({"id": fid, "url": url, "label": label, "added_at": int(time.time())})
    d["firebases"] = fbs
    save(); await state.clear()
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Added!\n{esc(label)}\n<code>{esc(url)}</code>",
                   reply_markup=fb_menu_kb(load()), parse_mode="HTML")

@R.callback_query(F.data == "owner:fb:add_file")
async def fb_add_file_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.add_firebase_file)
    try:
        await cq.message.edit_text(f"{em(EMOJI_FIRE, '🔥')} <b>Bulk Add</b>\n\nUpload .txt file.",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:fb:menu:0")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.add_firebase_file, F.document)
async def fb_add_file_done(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    doc = m.document
    if not doc.file_name.endswith(".txt"):
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Only .txt", parse_mode="HTML"); return
    try:
        fi = await m.bot.get_file(doc.file_id)
        downloaded = await m.bot.download_file(fi.file_path)
        raw = downloaded.read() if hasattr(downloaded, "read") else downloaded
        content = raw.decode("utf-8", errors="ignore")
    except Exception: await m.answer(f"{em(EMOJI_CROSS, '❌')} Read failed.", parse_mode="HTML"); return
    fbs = d.get("firebases", [])
    existing_urls = {fb["url"].rstrip("/") for fb in fbs}
    existing_ids = {fb["id"] for fb in fbs}
    added = skipped = 0; seen = set()
    for line in content.splitlines():
        line = line.strip()
        if not line: continue
        if "|" in line:
            p = line.split("|", 1); label, url = p[0].strip(), p[1].strip()
        else:
            url = line; label = url.replace("https://", "").replace("http://", "").split(".")[0][:20]
        if not (url.startswith("http://") or url.startswith("https://")): continue
        url = url.rstrip("/")
        if url in existing_urls or url in seen: skipped += 1; continue
        seen.add(url); existing_urls.add(url)
        fid = str(int(time.time() * 1000) + random.randint(10000, 99999))
        while fid in existing_ids: fid = str(int(time.time() * 1000) + random.randint(10000, 99999))
        existing_ids.add(fid)
        fbs.append({"id": fid, "url": url, "label": label, "added_at": int(time.time())})
        added += 1
    d["firebases"] = fbs; save(); await state.clear()
    await m.answer(f"{em(EMOJI_CHECK, '✅')} <b>Done!</b>\n\n🔥 {added}\n⚠️ {skipped}\n📊 {len(fbs)}",
                   reply_markup=fb_menu_kb(load()), parse_mode="HTML")

@R.message(S.add_firebase_file)
async def fb_add_file_invalid(m: Message):
    await m.answer(f"{em(EMOJI_CROSS, '❌')} Send .txt", parse_mode="HTML")

@R.callback_query(F.data.startswith("owner:fb:del:"))
async def fb_del(cq: CallbackQuery, state: FSMContext):
    global CACHED_DEVICES, FB_DEVICE_COUNTS, LAST_KNOWN_FB_COUNTS
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    parts = cq.data.split(":")
    fid = parts[3]; page = int(parts[4]) if len(parts) > 4 else 0
    d["firebases"] = [fb for fb in d["firebases"] if fb["id"] != fid]
    save()
    CACHED_DEVICES = [x for x in CACHED_DEVICES if x.get("fb_id") != fid]
    FB_DEVICE_COUNTS.pop(fid, None); LAST_KNOWN_FB_COUNTS.pop(fid, None); FB_SCAN_ERRORS.pop(fid, None)
    try: await cq.answer("🗑 Removed!")
    except Exception: pass
    try:
        await cq.message.edit_text(f"{em(EMOJI_FIRE, '🔥')} <b>Firebase Manager</b>\n\nTotal: <b>{len(d['firebases'])}</b>",
                                   reply_markup=fb_menu_kb(d, page), parse_mode="HTML")
    except Exception: pass

# ----- STATS -----
def _api_stats(d):
    stats = d.get("stats", {}); api = stats.get("api_usage", {})
    fbs = {fb["id"]: fb for fb in d.get("firebases", [])}
    lines = [f"{em(EMOJI_STAR, '📊')} <b>API Stats</b>\n",
             f"📤 Sent: <b>{stats.get('total_sent', 0)}</b>",
             f"❌ Failed: <b>{stats.get('total_failed', 0)}</b>\n", "━━━━━━━━━━━━━━━━━━━━"]
    if not api: lines.append("  😴 No usage.")
    for fid, s in api.items():
        fb = fbs.get(fid)
        lbl = esc(fb.get("label", fid[:20]) if fb else fid[:20])
        lines.append(f"🔥 {lbl}\n   ✅ {s.get('sent', 0)} | ❌ {s.get('failed', 0)}")
    return "\n".join(lines)

@R.callback_query(F.data == "owner:stats")
async def stats_owner(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer("⏳")
    except Exception: pass
    curr = {fb["id"] for fb in d.get("firebases", [])}
    global CACHED_DEVICES
    CACHED_DEVICES = [x for x in CACHED_DEVICES if x.get("fb_id") in curr]
    devices = CACHED_DEVICES[:] if CACHED_DEVICES else []
    if not devices:
        try: devices = await scan_all(d)
        except Exception: devices = []
    txt = _api_stats(d)
    dl = [f"\n{em(EMOJI_CHECK, '🟢')} <b>APIs ({len(devices) * CURRENT_POWER_MODE})</b>\n"]
    if not devices: dl.append("  😴 None")
    for dv in devices[:30]:
        dl.append(f"  📱 {esc(str(dv.get('dev_name', ''))[:20])} — 🔥 {esc(str(dv.get('fb_label', ''))[:20])}")
    if len(devices) > 30: dl.append(f"  ...+{len(devices) - 30}")
    full = txt + "\n" + "\n".join(dl)
    if len(full) > 4000: full = full[:3990] + "\n<i>...</i>"
    try:
        await cq.message.edit_text(full,
            reply_markup=kb([(f"{sc('refresh')}", "owner:stats"), (f"{sc('back')}", "owner:home")]),
            parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "admin:stats")
async def stats_admin(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    if not is_admin(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer("⏳")
    except Exception: pass
    devices = CACHED_DEVICES[:] if CACHED_DEVICES else []
    if not devices:
        try: devices = await scan_all(d)
        except Exception: devices = []
    txt = _api_stats(d)
    dl = [f"\n{em(EMOJI_CHECK, '🟢')} <b>APIs ({len(devices) * CURRENT_POWER_MODE})</b>\n"]
    for dv in devices[:30]:
        dl.append(f"  📱 {esc(str(dv.get('dev_name', ''))[:20])} — 🔥 {esc(str(dv.get('fb_label', ''))[:20])}")
    full = txt + "\n" + "\n".join(dl)
    if len(full) > 4000: full = full[:3990] + "\n<i>...</i>"
    try:
        await cq.message.edit_text(full,
            reply_markup=kb([(f"{sc('refresh')}", "admin:stats"), (f"{sc('back')}", "admin:home")]),
            parse_mode="HTML")
    except Exception: pass

# ----- OWNERS / ADMINS -----
@R.callback_query(F.data == "owner:owners:menu")
async def owners_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    try:
        await cq.message.edit_text(f"{em(EMOJI_CROWN, '👑')} <b>Super Admins</b>\n\nTotal: <b>{len(d.get('owners', []))}/6</b>",
                                   reply_markup=owners_menu_kb(d), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:owners:add")
async def owners_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    if len(d.get("owners", [])) >= 6:
        try: await cq.answer("❌ Max 6!", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.add_owner)
    try:
        await cq.message.edit_text(f"{em(EMOJI_CROWN, '👑')} <b>Add Super Admin</b>\n\nChat ID:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:owners:menu")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.add_owner)
async def owners_add_done(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    try: nid = int((m.text or "").strip())
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid ID.", parse_mode="HTML"); return
    if is_owner(nid, d):
        await state.clear()
        await m.answer(f"{em(EMOJI_WARNING, '⚠️')} Already!", reply_markup=owners_menu_kb(d), parse_mode="HTML"); return
    if len(d.get("owners", [])) >= 6:
        await state.clear()
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Max 6!", reply_markup=owners_menu_kb(d), parse_mode="HTML"); return
    d["owners"].append(nid); save(); await state.clear()
    await m.answer(f"{em(EMOJI_CHECK, '✅')} <code>{nid}</code>", reply_markup=owners_menu_kb(load()), parse_mode="HTML")
    try: await m.bot.send_message(nid, f"{em(EMOJI_CROWN, '🔱')} <b>Super Admin!</b>", parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.startswith("owner:owners:del:"))
async def owners_del(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    try: did = int(cq.data.split("owner:owners:del:", 1)[1])
    except Exception:
        try: await cq.answer("❌", show_alert=True)
        except Exception: pass
        return
    if not is_owner(uid, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    if did == MAIN_OWNER or did in SUPER_ADMINS:
        try: await cq.answer("❌ Can't remove!", show_alert=True)
        except Exception: pass
        return
    if did in d["owners"]:
        d["owners"].remove(did); save()
        try: await cq.answer("🗑 Removed!")
        except Exception: pass
    try:
        await cq.message.edit_text(f"{em(EMOJI_CROWN, '👑')} <b>Owners</b>\n\nTotal: <b>{len(d['owners'])}/6</b>",
                                   reply_markup=owners_menu_kb(d), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:admins:menu")
async def admins_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    try:
        await cq.message.edit_text(f"{em(EMOJI_SHIELD, '🛡')} <b>Admins</b>\n\nTotal: <b>{len(d.get('admins', []))}</b>",
                                   reply_markup=admins_menu_kb(d), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:admins:add")
async def admins_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.add_admin)
    try:
        await cq.message.edit_text(f"{em(EMOJI_SHIELD, '🛡')} <b>Add Admin</b>\n\nUser ID:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:admins:menu")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.add_admin)
async def admins_add_done(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    try: nid = int((m.text or "").strip())
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid ID.", parse_mode="HTML"); return
    if nid in d.get("admins", []) or is_owner(nid, d):
        await state.clear()
        await m.answer(f"{em(EMOJI_WARNING, '⚠️')} Already!", reply_markup=admins_menu_kb(d), parse_mode="HTML"); return
    d["admins"].append(nid); save(); await state.clear()
    await m.answer(f"{em(EMOJI_CHECK, '✅')} <code>{nid}</code>", reply_markup=admins_menu_kb(load()), parse_mode="HTML")
    try: await m.bot.send_message(nid, f"{em(EMOJI_SHIELD, '🛡')} <b>Admin!</b>", parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.startswith("owner:admins:del:"))
async def admins_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: did = int(cq.data.split("owner:admins:del:", 1)[1])
    except Exception:
        try: await cq.answer("❌", show_alert=True)
        except Exception: pass
        return
    if did in d.get("admins", []):
        d["admins"].remove(did); save()
        try: await cq.answer("🗑 Removed!")
        except Exception: pass
    try:
        await cq.message.edit_text(f"{em(EMOJI_SHIELD, '🛡')} <b>Admins</b>\n\nTotal: <b>{len(d['admins'])}</b>",
                                   reply_markup=admins_menu_kb(d), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.in_({"owner:free:on", "owner:free:off"}))
async def free_toggle(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    d["free_mode"] = (cq.data == "owner:free:on"); save()
    try: await cq.answer("Done!", show_alert=True)
    except Exception: pass
    try: await cq.message.edit_text(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
    except Exception: pass

# ----- USERS LIST -----
def _users_list(d, prefix, page=0):
    users = d.get("users", {}); items = list(users.items())
    per = 10; start = page * per; chunk = items[start:start + per]
    appr = d.get("approved", []); ban = d.get("banned", [])
    lines = [f"{em(EMOJI_STAR, '👥')} <b>Users ({len(items)})</b>\n"]
    for us, ud in chunk:
        uid = int(us); nm = esc(str(ud.get("name", "?"))[:18])
        st = em(EMOJI_CROSS, "🚫") if uid in ban else em(EMOJI_CHECK, "✅") if uid in appr \
             else em(EMOJI_CROWN, "👑") if is_owner(uid, d) else em(EMOJI_SHIELD, "🛡") \
             if uid in d.get("admins", []) else em(EMOJI_STAR, "👤")
        ulim = ud.get("max_send_limit")
        lim = "" if ulim is None else (" 🚫" if ulim <= 0 else f" 🔒{ulim}")
        lines.append(f"{st} <code>{uid}</code> — {nm} | 💰{ud.get('credits', 0)} | 📤{ud.get('uses', 0)}{lim}")
    rows = []; nav = []
    if page > 0: nav.append(btn("prev", f"{prefix}:users:pg:{page - 1}", EMOJI_GEAR, "◀️"))
    if start + per < len(items): nav.append(btn("next", f"{prefix}:users:pg:{page + 1}", EMOJI_GEAR, "▶️"))
    if nav: rows.append(nav)
    rows.append([btn("back", f"{prefix}:home", EMOJI_GEAR, "🔙")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)

@R.callback_query(F.data.in_({"owner:users:list", "admin:users:list"}))
async def users_list(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    prefix = "owner" if is_owner(uid, d) else "admin"
    if not is_admin(uid, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    txt, mk = _users_list(d, prefix, 0)
    try: await cq.message.edit_text(txt, reply_markup=mk, parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.regexp(r"^(owner|admin):users:pg:(\d+)$"))
async def users_page(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    if not is_admin(uid, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    p = cq.data.split(":")
    txt, mk = _users_list(d, p[0], int(p[3]))
    try: await cq.message.edit_text(txt, reply_markup=mk, parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.in_({"owner:ban", "admin:ban"}))
async def ban_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.ban_user)
    back = "owner:home" if is_owner(cq.from_user.id, d) else "admin:home"
    try:
        await cq.message.edit_text(f"{em(EMOJI_CROSS, '🚫')} <b>Ban</b>\n\nTelegram ID:",
                                   reply_markup=kb([(f"{sc('cancel')}", back)]), parse_mode="HTML")
    except Exception: pass

@R.message(S.ban_user)
async def ban_done(m: Message, state: FSMContext):
    d = load(); uid = m.from_user.id
    if not is_admin(uid, d):
        await state.clear(); return
    try: bid = int((m.text or "").strip())
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    if is_owner(bid, d) or is_admin(bid, d):
        await state.clear()
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Can't ban!", parse_mode="HTML"); return
    if bid not in d.get("banned", []):
        d.setdefault("banned", []).append(bid); save()
    await state.clear()
    bk = owner_kb(d) if is_owner(uid, d) else admin_kb(d)
    await m.answer(f"{em(EMOJI_CROSS, '🚫')} Banned <code>{bid}</code>", reply_markup=bk, parse_mode="HTML")
    try: await m.bot.send_message(bid, f"{em(EMOJI_CROSS, '🚫')} Banned.", parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.in_({"owner:unban:menu", "admin:unban:menu"}))
async def unban_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    banned = d.get("banned", [])
    if not banned:
        try: await cq.answer("✅ None!", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    prefix = "owner" if is_owner(cq.from_user.id, d) else "admin"
    try:
        await cq.message.edit_text(f"{em(EMOJI_CHECK, '🔓')} <b>Unban</b>\n\nBanned: <b>{len(banned)}</b>",
                                   reply_markup=unban_menu_kb(d, prefix), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.regexp(r"^(owner|admin):unban:do:(\d+)$"))
async def unban_do(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    if not is_admin(uid, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    bid = int(cq.data.split(":")[-1])
    if bid in d.get("banned", []):
        d["banned"].remove(bid); save()
    try: await cq.answer("✅ Unbanned!", show_alert=True)
    except Exception: pass
    bt = owner_panel_text(d) if is_owner(uid, d) else admin_panel_text(d)
    bk = owner_kb(d) if is_owner(uid, d) else admin_kb(d)
    try: await cq.message.edit_text(bt, reply_markup=bk, parse_mode="HTML")
    except Exception: pass
    try: await cq.bot.send_message(bid, f"{em(EMOJI_CHECK, '✅')} Unbanned.", parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.in_({"owner:broadcast", "admin:broadcast"}))
async def bc_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.broadcast)
    back = "owner:home" if is_owner(cq.from_user.id, d) else "admin:home"
    try:
        await cq.message.edit_text(f"{em(EMOJI_BELL, '📢')} <b>Broadcast</b>\n\nMessage:",
                                   reply_markup=kb([(f"{sc('cancel')}", back)]), parse_mode="HTML")
    except Exception: pass

@R.message(S.broadcast)
async def bc_do(m: Message, state: FSMContext):
    d = load(); uid = m.from_user.id
    if not is_admin(uid, d):
        await state.clear(); return
    await state.clear()
    users = d.get("users", {})
    wait = None
    try: wait = await m.answer(f"📤 Sending to <b>{len(users)}</b>...", parse_mode="HTML")
    except Exception: pass
    ok = fail = 0
    for us in list(users.keys()):
        try:
            t = int(us)
            if m.text:
                await m.bot.send_message(t, f"{em(EMOJI_BELL, '📢')} <b>Broadcast</b>\n\n{m.text}", parse_mode="HTML")
            else: await m.copy_to(t)
            ok += 1
        except Exception: fail += 1
        await asyncio.sleep(0.05)
    if wait:
        try: await wait.delete()
        except Exception: pass
    bk = owner_kb(d) if is_owner(uid, d) else admin_kb(d)
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Done!\n✅ {ok} | ❌ {fail}", reply_markup=bk, parse_mode="HTML")

@R.callback_query(F.data == "owner:export_script")
async def export_script(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer("📤...")
    except Exception: pass
    try:
        sp = os.path.abspath(__file__)
        if not os.path.exists(sp):
            try: await cq.answer("❌ Not found!", show_alert=True)
            except Exception: pass
            return
        await cq.message.reply_document(document=FSInputFile(sp),
            caption=f"{em(EMOJI_GEAR, '📤')} <b>{_VERSION}</b>", parse_mode="HTML")
    except Exception as e:
        try: await cq.answer(f"❌ {str(e)[:40]}", show_alert=True)
        except Exception: pass

@R.callback_query(F.data.in_({"admin:home", "admin:refresh"}))
async def admin_home(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    if not is_admin(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    try: await cq.message.edit_text(admin_panel_text(d), reply_markup=admin_kb(d), parse_mode="HTML")
    except Exception: pass

# ----- FORCE JOIN -----
@R.callback_query(F.data == "owner:fj:menu")
async def fj_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    fj = d.get("force_join", {}); chs = fj.get("channels", [])
    st = f"{em(EMOJI_CHECK, '🟢')} ON" if fj.get("enabled") else f"{em(EMOJI_CROSS, '🔴')} OFF"
    txt = f"{em(EMOJI_BELL, '🔗')} <b>Force Join</b>\n\nStatus: {st}\nChannels: <b>{len(chs)}</b>\n\n"
    for c in chs: txt += f"• {esc(c.get('title', 'Channel'))} (<code>{esc(c['id'])}</code>)\n"
    rows = [
        [btn("add channel", "owner:fj:add", EMOJI_CHECK, "➕")],
        [btn("remove channel", "owner:fj:remove", EMOJI_CROSS, "🗑")],
        [InlineKeyboardButton(
            text=f"🟢 {sc('enable')}" if not fj.get("enabled") else f"🔴 {sc('disable')}",
            callback_data="owner:fj:toggle")],
        [btn("back", "owner:home", EMOJI_GEAR, "🔙")]
    ]
    try: await cq.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:fj:add")
async def fj_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.fj_add_channel)
    try:
        await cq.message.edit_text(f"{em(EMOJI_BELL, '🔗')} <b>Add Channel</b>\n\nStep 1/2: ID:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:fj:menu")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.fj_add_channel)
async def fj_add_channel(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    try: cid = int((m.text or "").strip())
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid ID.", parse_mode="HTML"); return
    await state.update_data(fj_channel_id=cid)
    await state.set_state(S.fj_add_link)
    await m.answer(f"{em(EMOJI_BELL, '🔗')} <b>Step 2/2</b>\n\nInvite link:",
                   reply_markup=kb([(f"{sc('cancel')}", "owner:fj:menu")]), parse_mode="HTML")

@R.message(S.fj_add_link)
async def fj_add_link(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    link = (m.text or "").strip()
    if not link.startswith("http"):
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid link.", parse_mode="HTML"); return
    fsmd = await state.get_data(); cid = str(fsmd.get("fj_channel_id"))
    try:
        ch = await m.bot.get_chat(int(cid)); title = ch.title or "Channel"
    except Exception: title = "Channel"
    chs = d.setdefault("force_join", {}).setdefault("channels", [])
    chs = [c for c in chs if str(c["id"]) != cid]
    chs.append({"id": cid, "link": link, "title": title, "required": True})
    d["force_join"]["channels"] = chs; save(); await state.clear()
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Added: {esc(title)}",
                   reply_markup=kb([(f"{sc('back')}", "owner:fj:menu")]), parse_mode="HTML")

@R.callback_query(F.data == "owner:fj:remove")
async def fj_remove_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    chs = d.get("force_join", {}).get("channels", [])
    if not chs:
        try: await cq.answer("❌ None!", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    rows = []
    for c in chs:
        rows.append([btn(f"{c.get('title', 'Channel')[:25]}", f"owner:fj:del:{c['id']}", EMOJI_CROSS, "🗑")])
    rows.append([btn("back", "owner:fj:menu", EMOJI_GEAR, "🔙")])
    try:
        await cq.message.edit_text(f"{em(EMOJI_CROSS, '🗑')} <b>Remove</b>",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.startswith("owner:fj:del:"))
async def fj_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    cid = cq.data.split("owner:fj:del:", 1)[1]
    chs = d.get("force_join", {}).get("channels", [])
    d["force_join"]["channels"] = [c for c in chs if str(c["id"]) != cid]; save()
    try: await cq.answer("🗑 Removed!")
    except Exception: pass
    await fj_menu(cq, state)

@R.callback_query(F.data == "owner:fj:toggle")
async def fj_toggle(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    fj = d.setdefault("force_join", {})
    fj["enabled"] = not fj.get("enabled", False); save()
    try: await cq.answer(f"Force Join {'ON' if fj['enabled'] else 'OFF'}!", show_alert=True)
    except Exception: pass
    await fj_menu(cq, state)

# ----- PRICING -----
@R.callback_query(F.data == "owner:pricing:menu")
async def pricing_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    plans = d.get("pricing", {}).get("plans", [])
    txt = f"{em(EMOJI_MONEY, '💳')} <b>Pricing Plans</b>\n\nTotal: <b>{len(plans)}</b>\n\n"
    for i, p in enumerate(plans, 1):
        txt += f"{i}. <b>{esc(p['name'])}</b>\n   {p['price']} {p.get('currency', 'INR')} = {p['credits']}\n   {esc(p['payment_link'])}\n\n"
    rows = [
        [btn("add plan", "owner:pricing:add", EMOJI_CHECK, "➕")],
        [btn("remove plan", "owner:pricing:remove", EMOJI_CROSS, "🗑")],
        [btn("back", "owner:home", EMOJI_GEAR, "🔙")]
    ]
    try: await cq.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:pricing:add")
async def pricing_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.add_plan_name)
    try:
        await cq.message.edit_text(f"{em(EMOJI_MONEY, '💳')} <b>Add Plan</b>\n\nStep 1/4: Name:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:pricing:menu")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.add_plan_name)
async def pricing_name(m: Message, state: FSMContext):
    if not is_owner(m.from_user.id, load()):
        await state.clear(); return
    nm = (m.text or "").strip()[:64]
    if not nm:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Empty.", parse_mode="HTML"); return
    await state.update_data(plan_name=nm)
    await state.set_state(S.add_plan_price)
    await m.answer("Step 2/4: Price:", reply_markup=kb([(f"{sc('cancel')}", "owner:pricing:menu")]), parse_mode="HTML")

@R.message(S.add_plan_price)
async def pricing_price(m: Message, state: FSMContext):
    if not is_owner(m.from_user.id, load()):
        await state.clear(); return
    try:
        p = float((m.text or "").strip())
        if p < 0: raise ValueError
        await state.update_data(plan_price=p)
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    await state.set_state(S.add_plan_credits)
    await m.answer("Step 3/4: Credits:", reply_markup=kb([(f"{sc('cancel')}", "owner:pricing:menu")]), parse_mode="HTML")

@R.message(S.add_plan_credits)
async def pricing_credits(m: Message, state: FSMContext):
    if not is_owner(m.from_user.id, load()):
        await state.clear(); return
    try:
        c = int((m.text or "").strip())
        if c <= 0: raise ValueError
        await state.update_data(plan_credits=c)
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    await state.set_state(S.add_plan_link)
    await m.answer("Step 4/4: Link:", reply_markup=kb([(f"{sc('cancel')}", "owner:pricing:menu")]), parse_mode="HTML")

@R.message(S.add_plan_link)
async def pricing_link(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    link = (m.text or "").strip()
    if not link.startswith("http"):
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid URL.", parse_mode="HTML"); return
    fsmd = await state.get_data()
    plan = {"id": str(int(time.time() * 1000)), "name": fsmd.get("plan_name", "Plan"),
            "price": fsmd.get("plan_price", 0), "credits": fsmd.get("plan_credits", 0),
            "currency": "INR", "payment_link": link}
    d.setdefault("pricing", {}).setdefault("plans", []).append(plan); save(); await state.clear()
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Added!", reply_markup=kb([(f"{sc('back')}", "owner:pricing:menu")]), parse_mode="HTML")

@R.callback_query(F.data == "owner:pricing:remove")
async def pricing_remove(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    plans = d.get("pricing", {}).get("plans", [])
    if not plans:
        try: await cq.answer("❌ None!", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    rows = []
    for p in plans:
        rows.append([btn(p['name'][:25], f"owner:pricing:del:{p['id']}", EMOJI_CROSS, "🗑")])
    rows.append([btn("back", "owner:pricing:menu", EMOJI_GEAR, "🔙")])
    try: await cq.message.edit_text(f"{em(EMOJI_CROSS, '🗑')} <b>Remove</b>",
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.startswith("owner:pricing:del:"))
async def pricing_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    pid = cq.data.split("owner:pricing:del:", 1)[1]
    plans = d.get("pricing", {}).get("plans", [])
    d["pricing"]["plans"] = [p for p in plans if p["id"] != pid]; save()
    try: await cq.answer("🗑 Removed!")
    except Exception: pass
    await pricing_menu(cq, state)

# ----- REDEEM -----
@R.callback_query(F.data == "owner:redeem:menu")
async def redeem_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    codes = d.get("redeem_codes", {})
    txt = f"{em(EMOJI_GIFT, '🎁')} <b>Redeem Codes</b>\n\nTotal: <b>{len(codes)}</b>\n\n"
    for code, cd in list(codes.items())[:10]:
        st = "✅" if cd.get("uses_left", 0) > 0 else "❌"
        txt += f"<code>{esc(code)}</code> — {cd['credits']} — {st} ({cd.get('uses_left', 0)})\n"
    rows = [
        [btn("generate", "owner:redeem:gen", EMOJI_CHECK, "➕")],
        [btn("delete", "owner:redeem:del", EMOJI_CROSS, "🗑")],
        [btn("back", "owner:home", EMOJI_GEAR, "🔙")]
    ]
    try: await cq.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:redeem:gen")
async def redeem_gen_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.gen_redeem_credits)
    try:
        await cq.message.edit_text(f"{em(EMOJI_GIFT, '🎁')} <b>Generate</b>\n\nStep 1/2: Credits:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:redeem:menu")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.gen_redeem_credits)
async def redeem_credits(m: Message, state: FSMContext):
    if not is_owner(m.from_user.id, load()):
        await state.clear(); return
    try:
        c = int((m.text or "").strip())
        if c <= 0: raise ValueError
        await state.update_data(gen_credits=c)
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    await state.set_state(S.gen_redeem_uses)
    await m.answer("Step 2/2: Uses:", reply_markup=kb([(f"{sc('cancel')}", "owner:redeem:menu")]), parse_mode="HTML")

@R.message(S.gen_redeem_uses)
async def redeem_uses(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    try:
        u = int((m.text or "").strip())
        if u < 1: raise ValueError
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    fsmd = await state.get_data(); credits = fsmd.get("gen_credits", 10)
    for _ in range(20):
        code = "GIFT" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if code not in d.get("redeem_codes", {}): break
    else: code = "GIFT" + str(int(time.time()))[-8:]
    d.setdefault("redeem_codes", {})[code] = {
        "credits": credits, "uses_left": u,
        "created_by": m.from_user.id, "created_at": int(time.time()), "used_by": []
    }
    save(); await state.clear()
    await m.answer(f"{em(EMOJI_GIFT, '🎉')} <b>Code!</b>\n\n<code>{esc(code)}</code>\n💰 {credits}\n🔢 {u}",
                   reply_markup=kb([(f"{sc('back')}", "owner:redeem:menu")]), parse_mode="HTML")

@R.callback_query(F.data == "owner:redeem:del")
async def redeem_del_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    codes = d.get("redeem_codes", {})
    if not codes:
        try: await cq.answer("❌ None!", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    rows = []
    for code in list(codes.keys())[:20]:
        rows.append([btn(code, f"owner:redeem:deldo:{code}", EMOJI_CROSS, "🗑")])
    rows.append([btn("back", "owner:redeem:menu", EMOJI_GEAR, "🔙")])
    try: await cq.message.edit_text(f"{em(EMOJI_CROSS, '🗑')} <b>Delete</b>",
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.startswith("owner:redeem:deldo:"))
async def redeem_del_do(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    code = cq.data.split("owner:redeem:deldo:", 1)[1]
    if code in d.get("redeem_codes", {}):
        del d["redeem_codes"][code]; save()
    try: await cq.answer("🗑")
    except Exception: pass
    await redeem_menu(cq, state)

# ----- CREDITS -----
@R.callback_query(F.data == "owner:credits:add")
async def credits_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.add_credits_uid)
    try:
        await cq.message.edit_text(f"{em(EMOJI_MONEY, '💰')} <b>Add Credits</b>\n\nStep 1/2: User ID:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.add_credits_uid)
async def credits_add_uid(m: Message, state: FSMContext):
    if not is_owner(m.from_user.id, load()):
        await state.clear(); return
    try:
        uid = int((m.text or "").strip())
        await state.update_data(credit_uid=uid)
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    await state.set_state(S.add_credits_amount)
    await m.answer("Step 2/2: Amount:", reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")

@R.message(S.add_credits_amount)
async def credits_add_amt(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    try: amt = int((m.text or "").strip())
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    fsmd = await state.get_data(); uid = fsmd.get("credit_uid")
    add_credits(uid, amt, d, is_manual=True); save(); await state.clear()
    try:
        await m.bot.send_message(uid, f"{em(EMOJI_MONEY, '💰')} <b>+{amt} credits!</b>\nBalance: {get_user_credits(uid, d)}", parse_mode="HTML")
    except Exception: pass
    await m.answer(f"{em(EMOJI_CHECK, '✅')} {amt} added. Balance: {get_user_credits(uid, d)}",
                   reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")

@R.callback_query(F.data == "owner:credits:deduct")
async def credits_deduct_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.deduct_credits_uid)
    try:
        await cq.message.edit_text(f"{em(EMOJI_MONEY, '💰')} <b>Deduct</b>\n\nStep 1/2: User ID:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.deduct_credits_uid)
async def credits_deduct_uid(m: Message, state: FSMContext):
    if not is_owner(m.from_user.id, load()):
        await state.clear(); return
    try:
        uid = int((m.text or "").strip())
        await state.update_data(deduct_uid=uid)
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    await state.set_state(S.deduct_credits_amount)
    await m.answer("Step 2/2: Amount:", reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")

@R.message(S.deduct_credits_amount)
async def credits_deduct_amt(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    try: amt = int((m.text or "").strip())
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    fsmd = await state.get_data(); uid = fsmd.get("deduct_uid")
    ok = deduct_credits(uid, amt, d); save(); await state.clear()
    if ok:
        try: await m.bot.send_message(uid, f"{em(EMOJI_WARNING, '⚠️')} -{amt} credits. Balance: {get_user_credits(uid, d)}", parse_mode="HTML")
        except Exception: pass
        await m.answer(f"{em(EMOJI_CHECK, '✅')} Deducted. New: {get_user_credits(uid, d)}",
                       reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")
    else:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Insufficient. {get_user_credits(uid, d)} left.",
                       reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")

@R.callback_query(F.data == "owner:add_all_credits")
async def add_all_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.add_all_credits_amount)
    try:
        await cq.message.edit_text(f"{em(EMOJI_MONEY, '💰')} <b>Add to ALL</b>\n\nAmount:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.add_all_credits_amount)
async def add_all_amt(m: Message, state: FSMContext):
    d = load(); uid = m.from_user.id
    if not is_owner(uid, d):
        await state.clear(); return
    try:
        amt = int((m.text or "").strip())
        if amt <= 0: raise ValueError
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid positive.", parse_mode="HTML"); return
    await state.clear()
    users = d.get("users", {})
    if not users:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} No users.", reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML"); return
    for us in list(users.keys()): add_credits(int(us), amt, d, is_manual=True)
    save()
    note = f"{em(EMOJI_MONEY, '💰')} <b>+{amt} credits!</b>"
    okc = 0
    for us in list(users.keys()):
        try:
            await m.bot.send_message(int(us), note, parse_mode="HTML")
            okc += 1; await asyncio.sleep(0.05)
        except Exception: pass
    await m.answer(f"{em(EMOJI_CHECK, '✅')} {amt} × {len(users)}\nNotified: {okc}",
                   reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")
    log_activity(d, "add_credits_all", uid, f"{amt} x {len(users)}"); save()

@R.callback_query(F.data == "owner:deduct_all_credits")
async def deduct_all_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.deduct_all_credits_amount)
    try:
        await cq.message.edit_text(f"{em(EMOJI_MONEY, '💰')} <b>Deduct from ALL</b>\n\nAmount:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.deduct_all_credits_amount)
async def deduct_all_confirm(m: Message, state: FSMContext):
    d = load(); uid = m.from_user.id
    if not is_owner(uid, d):
        await state.clear(); return
    try:
        amt = int((m.text or "").strip())
        if amt < 0: raise ValueError
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    await state.update_data(deduct_all_amount=amt)
    cf = InlineKeyboardMarkup(inline_keyboard=[[
        btn("YES", "owner:deduct_all_yes", EMOJI_CHECK, "✅", style="success"),
        btn("NO", "owner:home", EMOJI_CROSS, "❌", style="danger")
    ]])
    await m.answer(f"{em(EMOJI_WARNING, '⚠️')} Deduct <b>{amt}</b> from all?", reply_markup=cf, parse_mode="HTML")

@R.callback_query(F.data == "owner:deduct_all_yes")
async def deduct_all_yes(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    if not is_owner(uid, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    data = await state.get_data(); amt = data.get("deduct_all_amount", 0)
    await state.clear()
    cnt = 0; tot = 0
    owners = d.get("owners", [MAIN_OWNER]); admins = d.get("admins", [])
    for us, ud in d.get("users", {}).items():
        iu = int(us)
        if iu in owners or iu in admins: continue
        cur = ud.get("credits", 0); man = ud.get("manual_added_credits", 0)
        pool = max(0, cur - man)
        if pool > 0:
            td = min(amt, pool)
            if td > 0:
                ud["credits"] = cur - td; cnt += 1; tot += td
    save()
    try:
        await cq.message.edit_text(f"{em(EMOJI_CHECK, '✅')} Deducted <b>{tot}</b> from <b>{cnt}</b> users.",
                                   reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass
    log_activity(d, "deduct_all", uid, f"{tot} from {cnt}"); save()

# ----- TRANSFER / REDEEM / REFER / STATS -----
@R.callback_query(F.data == "user:transfer")
async def transfer_start(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    if is_banned(uid, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    if not can_use(uid, d):
        try: await cq.answer("⛔", show_alert=True)
        except Exception: pass
        return
    cur = get_user_credits(uid, d)
    if cur < 2:
        try: await cq.answer("❌ Min 2 credits!", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.transfer_credits_uid)
    try:
        await cq.message.edit_text(
            f"{em(EMOJI_MONEY, '💸')} <b>Transfer</b>\n\nYour Credits: <b>{cur}</b>\nHalf transfer.\n\nStep 1/2: Target ID:",
            reply_markup=kb([(f"{sc('cancel')}", "user:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.transfer_credits_uid)
async def transfer_uid(m: Message, state: FSMContext):
    d = load(); uid = m.from_user.id
    try: t = int((m.text or "").strip())
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid ID.", parse_mode="HTML"); return
    if t == uid:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Self!", parse_mode="HTML"); return
    if str(t) not in d.get("users", {}):
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Not found!", parse_mode="HTML"); return
    cur = get_user_credits(uid, d)
    if cur < 2:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Min 2!", parse_mode="HTML"); return
    await state.update_data(transfer_target=t)
    await state.set_state(S.transfer_credits_amount)
    half = cur // 2
    await m.answer(f"{em(EMOJI_MONEY, '💸')} Step 2/2\nTo: <code>{t}</code>\nMax: <b>{half}</b>\n\nAmount:",
                   reply_markup=kb([(f"{sc('cancel')}", "user:home")]), parse_mode="HTML")

@R.message(S.transfer_credits_amount)
async def transfer_amt(m: Message, state: FSMContext):
    d = load(); uid = m.from_user.id
    try:
        a = int((m.text or "").strip())
        if a <= 0: raise ValueError
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    fsmd = await state.get_data(); t = fsmd.get("transfer_target")
    cur = get_user_credits(uid, d); mt = cur // 2
    if a > mt:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Max {mt}!", parse_mode="HTML"); return
    if not deduct_credits(uid, a, d):
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Insufficient.", parse_mode="HTML"); return
    add_credits(t, a, d, is_manual=False); save(); await state.clear()
    try: await m.bot.send_message(t, f"{em(EMOJI_MONEY, '💸')} <b>+{a} credits from {uid}</b>", parse_mode="HTML")
    except Exception: pass
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Sent {a} to <code>{t}</code>.", reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML")
    log_activity(d, "transfer", uid, f"{a} to {t}"); save()

@R.callback_query(F.data == "user:redeem")
async def redeem_user_start(cq: CallbackQuery, state: FSMContext):
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.redeem_code)
    try:
        await cq.message.edit_text(f"{em(EMOJI_GIFT, '🎁')} <b>Redeem</b>\n\nCode:",
                                   reply_markup=kb([(f"{sc('cancel')}", "user:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.redeem_code)
async def redeem_user_done(m: Message, state: FSMContext):
    d = load(); uid = m.from_user.id
    code = (m.text or "").strip().upper()
    await state.clear()
    codes = d.get("redeem_codes", {})
    if code not in codes:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Invalid!", reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML"); return
    cd = codes[code]
    if cd.get("uses_left", 0) <= 0:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Expired!", reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML"); return
    if uid in cd.get("used_by", []):
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Already!", reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML"); return
    c = cd["credits"]
    add_credits(uid, c, d, is_manual=False)
    cd["uses_left"] = cd.get("uses_left", 1) - 1
    cd.setdefault("used_by", []).append(uid)
    save()
    await m.answer(f"{em(EMOJI_GIFT, '🎉')} <b>+{c} credits!</b>\nBalance: {get_user_credits(uid, d)}",
                   reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML")

@R.callback_query(F.data == "user:refer")
async def user_refer(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    code = generate_refer_code(uid, d); save()
    try: await cq.answer()
    except Exception: pass
    rc = d.get("settings", {}).get("ref_credits", 3)
    try: me = await cq.bot.get_me()
    except Exception: me = None
    un = me.username if me else "bot"
    try:
        await cq.message.edit_text(
            f"{em(EMOJI_STAR, '👥')} <b>Referral</b>\n\nEach = <b>{rc}</b> credits!\n\n"
            f"{em(EMOJI_GIFT, '🎁')} <code>{esc(code)}</code>\n\n"
            f"{em(EMOJI_GEAR, '🔗')} https://t.me/{un}?start={code}",
            reply_markup=kb([(f"{sc('back')}", "user:home")]), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "user:stats")
async def user_stats(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    try: await cq.answer()
    except Exception: pass
    ud = d["users"].get(str(uid), {}); st = d.get("stats", {})
    try:
        await cq.message.edit_text(
            f"{em(EMOJI_STAR, '📊')} <b>Your Stats</b>\n\n"
            f"💰 Credits: <b>{ud.get('credits', 0)}</b>\n"
            f"📤 Sent: <b>{ud.get('uses', 0)}</b>\n"
            f"📅 Joined: <b>{fmt_time(ud.get('joined_at', 0))}</b>\n\n"
            f"📈 Bot Total: <b>{st.get('total_sent', 0)}</b>",
            reply_markup=kb([(f"{sc('back')}", "user:home")]), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "user:sms_history")
async def user_hist(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    try: await cq.answer()
    except Exception: pass
    h = d.get("sms_history", {}).get(str(uid), [])[-10:]
    if not h:
        txt = f"{em(EMOJI_GEAR, '📜')} <b>History</b>\n\nEmpty."
    else:
        lines = [f"{em(EMOJI_GEAR, '📜')} <b>Your History</b> (last 10)\n"]
        for i, e in enumerate(reversed(h), 1):
            ts = fmt_time(e.get("timestamp", 0)); nm = e.get("number", "?")
            mp = esc(str(e.get("message", ""))[:30]); st = e.get("status", "?")
            ic = em(EMOJI_CHECK, "✅") if st == "sent" else em(EMOJI_CROSS, "🛑") if st == "stopped" else em(EMOJI_WARNING, "⏳")
            lines.append(f"{i}. [{ts}] {ic} <code>{esc(mask_number(nm))}</code> — {mp}...")
        txt = "\n".join(lines)
    try: await cq.message.edit_text(txt, reply_markup=kb([(f"{sc('back')}", "user:home")]), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "user:pricing")
async def user_pricing(cq: CallbackQuery, state: FSMContext):
    d = load(); plans = d.get("pricing", {}).get("plans", [])
    if not plans:
        try: await cq.answer("❌ No plans!", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    txt = f"{em(EMOJI_MONEY, '💰')} <b>Buy Credits</b>\n\n"
    for p in plans:
        txt += f"{em(EMOJI_STAR, '📋')} <b>{esc(p['name'])}</b>\n   💰 {p['price']} {p.get('currency', 'INR')} = {p['credits']}\n\n"
    rows = []
    for p in plans:
        rows.append([btn_url(f"Buy {p['name'][:20]}", p['payment_link'], EMOJI_MONEY, "💳", style="success")])
    rows.append([btn("back", "user:home", EMOJI_GEAR, "🔙")])
    try: await cq.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "user:info")
async def user_info(cq: CallbackQuery, state: FSMContext):
    d = load()
    try: await cq.answer()
    except Exception: pass
    od = get_owner_display(d)
    ol = f"{em(EMOJI_CROWN, '👤')} Owner: <a href='{SUPER_ADMIN_LINK}'>{esc(od)}</a>\n" if od else ""
    try:
        await cq.message.edit_text(
            f"{em(EMOJI_GEAR, 'ℹ️')} <b>SMS Blast Bot {_VERSION}</b>\n\n{ol}\n<i>Credits chahiye. Referral se free!</i>",
            reply_markup=kb([(f"{sc('back')}", "user:home")]),
            parse_mode="HTML", disable_web_page_preview=True)
    except Exception: pass

@R.callback_query(F.data == "noop")
async def noop(cq: CallbackQuery):
    try: await cq.answer()
    except Exception: pass

# ----- VIDEOS -----
@R.callback_query(F.data == "owner:videos:menu")
async def vids_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    try:
        await cq.message.edit_text(f"{em(EMOJI_VIDEO, '📹')} <b>Videos</b>\n\nTotal: <b>{len(d.get('videos', []))}</b>",
                                   reply_markup=videos_menu_kb(d), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:videos:add")
async def vids_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.add_video)
    try:
        await cq.message.edit_text(f"{em(EMOJI_VIDEO, '📹')} <b>Add Video</b>\n\nSend video/URL:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:videos:menu")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.add_video)
async def vids_add_done(m: Message, state: FSMContext):
    d = load()
    if not is_admin(m.from_user.id, d):
        await state.clear(); return
    vid = None
    if m.video: vid = m.video.file_id
    elif m.document and m.document.mime_type and m.document.mime_type.startswith("video"): vid = m.document.file_id
    elif m.text: vid = m.text.strip()
    if not vid:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid video.", parse_mode="HTML"); return
    d.setdefault("videos", []).append(vid); save(); await state.clear()
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Saved!", reply_markup=videos_menu_kb(load()), parse_mode="HTML")

@R.callback_query(F.data.startswith("owner:videos:del:"))
async def vids_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: idx = int(cq.data.split("owner:videos:del:", 1)[1])
    except Exception:
        try: await cq.answer("❌", show_alert=True)
        except Exception: pass
        return
    vids = d.get("videos", [])
    if 0 <= idx < len(vids):
        vids.pop(idx); d["videos"] = vids; save()
        try: await cq.answer("🗑 Removed!")
        except Exception: pass
    await vids_menu(cq, state)

@R.callback_query(F.data == "owner:videos:bulk_del")
async def vids_bulk_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    d["videos"] = []; save()
    try: await cq.answer("🗑 All deleted!", show_alert=True)
    except Exception: pass
    await vids_menu(cq, state)

@R.callback_query(F.data == "user:random_video")
async def user_vid(cq: CallbackQuery, state: FSMContext):
    d = load(); vids = d.get("videos", [])
    if not vids:
        try: await cq.answer("❌ No videos!", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer("📹 Sending...")
    except Exception: pass
    await send_video(cq.bot, cq.message.chat.id, caption=f"{em(EMOJI_VIDEO, '📹')} Enjoy!")

# ----- SETTINGS / PROTECTED / TRACK -----
@R.callback_query(F.data == "owner:settings")
async def settings_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    s = d.get("settings", {})
    od = get_owner_display(d) or "<i>(hidden)</i>"
    txt = (f"{em(EMOJI_GEAR, '⚙️')} <b>Settings</b>\n\n👤 Owner: <b>{od}</b>\n"
           f"🎁 Ref Credits: <b>{s.get('ref_credits', 3)}</b>\n👑 Max Owners: <b>{s.get('max_owners', 6)}</b>")
    rows = [
        [btn("edit owner name", "owner:edit_name", EMOJI_CROWN, "✏️", style="primary")],
        [btn("set referral credits", "owner:settings:ref", EMOJI_GIFT, "🎁")],
        [btn("back", "owner:home", EMOJI_GEAR, "🔙")]
    ]
    try: await cq.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:settings:ref")
async def settings_ref(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.set_ref_credits)
    try:
        await cq.message.edit_text(f"{em(EMOJI_GIFT, '🎁')} <b>Ref Credits</b>\n\nAmount:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:settings")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.set_ref_credits)
async def settings_ref_done(m: Message, state: FSMContext):
    d = load()
    if not is_owner(m.from_user.id, d):
        await state.clear(); return
    try:
        c = int((m.text or "").strip())
        if c < 0: raise ValueError
    except Exception:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Valid.", parse_mode="HTML"); return
    d.setdefault("settings", {})["ref_credits"] = c; save(); await state.clear()
    await m.answer(f"{em(EMOJI_CHECK, '✅')} Ref credits: {c}",
                   reply_markup=kb([(f"{sc('back')}", "owner:settings")]), parse_mode="HTML")

@R.callback_query(F.data == "owner:protect")
async def protect_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.protect_number)
    try:
        await cq.message.edit_text(f"{em(EMOJI_LOCK, '🔒')} <b>Protect</b>\n\nNumber:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.protect_number)
async def protect_done(m: Message, state: FSMContext):
    d = load(); uid = m.from_user.id
    if not is_owner(uid, d):
        await state.clear(); return
    num = (m.text or "").strip()
    cl = num.replace("+", "").replace(" ", "").replace("-", "")
    if not cl.isdigit() or len(cl) < 7:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Invalid.", parse_mode="HTML"); return
    PROTECTED_NUMBERS[num] = uid
    d["protected_numbers"] = PROTECTED_NUMBERS; save(); await state.clear()
    await m.answer(f"{em(EMOJI_LOCK, '🔒')} Protected: <code>{esc(num)}</code>",
                   reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")
    log_activity(d, "protect", uid, num); save()

@R.callback_query(F.data == "owner:protected_list")
async def protected_list(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    if not is_owner(uid, d) and not is_admin(uid, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    pr = d.get("protected_numbers", {})
    if not pr:
        try:
            await cq.message.edit_text(f"{em(EMOJI_LOCK, '🔐')} <b>Protected</b>\n\n❌ None.",
                                       reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")
        except Exception: pass
        return
    lines = [f"{em(EMOJI_LOCK, '🔐')} <b>Protected</b>\n"]
    owner_u = is_owner(uid, d) or is_main_owner(uid)
    for num, pu in pr.items():
        disp = num if owner_u else mask_number(num)
        pd_ = d.get("users", {}).get(str(pu), {})
        pn = esc(str(pd_.get("name", "?"))[:20])
        lines.append(f"📞 <code>{esc(disp)}</code> — 🔒 {pu} ({pn})")
    rows = []
    if owner_u: rows.append([btn("remove protection", "owner:protected_remove", EMOJI_CROSS, "🗑")])
    rows.append([btn("back", "owner:home", EMOJI_GEAR, "🔙")])
    try: await cq.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:protected_remove")
async def protected_remove_menu(cq: CallbackQuery, state: FSMContext):
    d = load(); uid = cq.from_user.id
    if not is_owner(uid, d) and not is_main_owner(uid):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    pr = d.get("protected_numbers", {})
    if not pr:
        try: await cq.answer("❌ None!", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    rows = []
    for num in pr.keys(): rows.append([btn(num, f"owner:protected_del:{num}", EMOJI_CROSS, "🗑")])
    rows.append([btn("back", "owner:protected_list", EMOJI_GEAR, "🔙")])
    try: await cq.message.edit_text(f"{em(EMOJI_CROSS, '🗑')} <b>Remove</b>",
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data.startswith("owner:protected_del:"))
async def protected_del(cq: CallbackQuery, state: FSMContext):
    global PROTECTED_NUMBERS
    d = load(); uid = cq.from_user.id
    if not is_owner(uid, d) and not is_main_owner(uid):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    num = cq.data.split("owner:protected_del:", 1)[1]
    if num in d.get("protected_numbers", {}):
        del d["protected_numbers"][num]; save()
        PROTECTED_NUMBERS = d["protected_numbers"]
        try: await cq.answer("✅ Removed!")
        except Exception: pass
    else:
        try: await cq.answer("❌ Not found!")
        except Exception: pass
    await protected_list(cq, state)

@R.callback_query(F.data == "owner:track")
async def track_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    await state.set_state(S.track_number)
    try:
        await cq.message.edit_text(f"{em(EMOJI_STAR, '📊')} <b>Track</b>\n\nNumber:",
                                   reply_markup=kb([(f"{sc('cancel')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.message(S.track_number)
async def track_done(m: Message, state: FSMContext):
    d = load(); uid = m.from_user.id
    if not is_owner(uid, d):
        await state.clear(); return
    num = (m.text or "").strip()
    cl = num.replace("+", "").replace(" ", "").replace("-", "")
    if not cl.isdigit() or len(cl) < 7:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Invalid.", parse_mode="HTML"); return
    await state.clear()
    hist = d.get("sms_history", {}); who = []
    for us, hl in hist.items():
        for e in hl:
            if e.get("number") == num:
                ud = d.get("users", {}).get(us, {})
                who.append({"uid": int(us), "name": ud.get("name", "?"), "ts": e.get("timestamp", 0)})
                break
    if not who:
        await m.answer(f"{em(EMOJI_STAR, '📊')} Track\n\n<code>{esc(num)}</code>\n\n❌ None.",
                       reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML"); return
    lines = [f"{em(EMOJI_STAR, '📊')} <b>{esc(num)}</b>\n"]
    for e in who[:50]:
        lines.append(f"• <code>{e['uid']}</code> — {esc(str(e['name'])[:20])} — {fmt_time(e['ts'])}")
    if len(who) > 50: lines.append(f"<i>+{len(who) - 50} more</i>")
    await m.answer("\n".join(lines), reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")

@R.callback_query(F.data == "owner:activity")
async def activity(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    ent = d.get("activity_log", [])[-20:]
    if not ent:
        txt = f"{em(EMOJI_GEAR, '📜')} <b>Activity</b>\n\nEmpty."
    else:
        lines = [f"{em(EMOJI_GEAR, '📜')} <b>Recent</b>\n"]
        for e in reversed(ent):
            ts = fmt_time(e.get("timestamp", 0))
            lines.append(f"[{ts}] <code>{e.get('uid', 0)}</code> {e.get('action', '?')} — {esc(str(e.get('details', ''))[:60])}")
        txt = "\n".join(lines)
    try:
        await cq.message.edit_text(txt, reply_markup=kb([(f"{sc('refresh')}", "owner:activity"), (f"{sc('back')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "owner:sms_history")
async def sms_hist(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        try: await cq.answer("🚫", show_alert=True)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass
    allh = d.get("sms_history", {}); tot = sum(len(v) for v in allh.values())
    try:
        await cq.message.edit_text(f"{em(EMOJI_STAR, '📋')} <b>Global History</b>\n\nTotal: <b>{tot}</b>",
                                   reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")
    except Exception: pass

# ----- USER HOME -----
@R.callback_query(F.data.in_({"user:home", "user:cancel"}))
async def user_home(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load(); uid = cq.from_user.id
    try: await cq.answer()
    except Exception: pass
    joined, missing = await joined_all(cq.bot, uid, d)
    if not joined:
        try:
            await cq.message.edit_text(fj_text(missing), reply_markup=fj_kb(missing),
                                       parse_mode="HTML", disable_web_page_preview=True)
        except Exception: pass
        return
    try:
        if is_owner(uid, d):
            await cq.message.edit_text(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
        elif is_admin(uid, d):
            await cq.message.edit_text(admin_panel_text(d), reply_markup=admin_kb(d), parse_mode="HTML")
        elif not can_use(uid, d):
            await cq.message.edit_text(f"{em(EMOJI_CROSS, '⛔')} No access.", parse_mode="HTML")
        else:
            await cq.message.edit_text(user_home_text(uid, d), reply_markup=user_kb(), parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "user:credits")
async def user_credits(cq: CallbackQuery, state: FSMContext):
    d = load(); cr = get_user_credits(cq.from_user.id, d)
    try: await cq.answer(f"💰 Credits: {cr}", show_alert=True)
    except Exception: pass

# ----- /logs -----
@R.message(Command("logs"))
async def cmd_logs(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id; d = load()
    if not is_owner(uid, d):
        await m.answer(f"{em(EMOJI_CROSS, '❌')} Owner only!", parse_mode="HTML"); return
    lines = ["=" * 60, "SMS BLAST BOT — LOG", "=" * 60]
    lines.append(f"Version: {_VERSION} | Power: {CURRENT_POWER_MODE}x")
    lines.append(f"Owner: {get_owner_display(d) or '(hidden)'}")
    lines.append(f"Uptime: {fmt_duration(int(time.time() - _START_TIME))}")
    lines.append(f"Last scan: {LAST_SCAN_DURATION:.2f}s | Count: {LAST_KNOWN_DEVICE_COUNT}")
    lines.append("")
    lines.append(f"[OWNERS] {d.get('owners', [])}")
    lines.append(f"[ADMINS] {d.get('admins', [])}")
    lines.append(f"[BANNED] {d.get('banned', [])}")
    lines.append("")
    fbs = d.get("firebases", [])
    lines.append(f"[FIREBASES] {len(fbs)}")
    for fb in fbs[:50]:
        fc = FB_DEVICE_COUNTS.get(fb["id"], {})
        lines.append(f"  {fb.get('label', '?')} | {fb['url']} | online: {fc.get('online', 0)}")
        if fb["id"] in FB_SCAN_ERRORS: lines.append(f"    err: {FB_SCAN_ERRORS[fb['id']]}")
    if len(fbs) > 50: lines.append(f"  ...+{len(fbs) - 50} more")
    lines.append("")
    users = d.get("users", {})
    lines.append(f"[USERS] {len(users)}")
    for us, ud in list(users.items())[:200]:
        lim = ud.get("max_send_limit"); ls = "unlim" if lim is None else str(lim)
        lines.append(f"  {us}: {ud.get('name', '?')} | c={ud.get('credits', 0)} | u={ud.get('uses', 0)} | lim={ls}")
    if len(users) > 200: lines.append(f"  ...+{len(users) - 200} more")
    lines.append("")
    st = d.get("stats", {})
    lines.append(f"[STATS] Sent={st.get('total_sent', 0)} Failed={st.get('total_failed', 0)}")
    if FB_SCAN_ERRORS:
        lines.append(f"\n[FB ERRORS] {len(FB_SCAN_ERRORS)}")
        for fid, err in list(FB_SCAN_ERRORS.items())[:30]: lines.append(f"  {fid}: {err}")
    lines.append("=" * 60)
    txt = "\n".join(lines); payload = txt.encode("utf-8")
    fname = f"blast_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    try:
        await m.answer_document(document=BufferedInputFile(payload, filename=fname),
                                caption=f"{em(EMOJI_GEAR, '📜')} <b>Log</b> — {_VERSION}",
                                parse_mode="HTML")
    except Exception as e:
        await m.answer(f"{em(EMOJI_CROSS, '❌')} {esc(str(e)[:60])}", parse_mode="HTML")

# ============================================================
#  SHUTDOWN / SESSION
# ============================================================
async def _shutdown(bot):
    log.info("Shutting down...")
    try:
        if _DATA_CACHE is not None: save(_DATA_CACHE)
    except Exception: pass
    for t in list(_BG_TASKS): t.cancel()
    if _BG_TASKS: await asyncio.gather(*_BG_TASKS, return_exceptions=True)
    try: await close_http_session()
    except Exception: pass
    try: await bot.session.close()
    except Exception: pass

async def run_session():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.callback_query.outer_middleware(CallbackSemaphoreMiddleware())
    dp.callback_query.outer_middleware(UserCooldownMiddleware())
    dp.callback_query.outer_middleware(OwnerPanelResetMiddleware())
    dp.include_router(R)

    for attempt in range(5):
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            log.info("Webhook cleared"); break
        except Exception as e:
            log.warning(f"delete_webhook try {attempt + 1}: {e}")
            await asyncio.sleep(2)

    me = await bot.get_me()
    log.info(f"@{me.username} — {_VERSION} online (PID {os.getpid()})")

    scanner_task = asyncio.create_task(supervised("scanner", scanner_loop, bot))
    backup_task = asyncio.create_task(supervised("backup", backup_loop, bot))
    watchdog_task = asyncio.create_task(watchdog_loop(bot))
    heartbeat_task = asyncio.create_task(heartbeat_loop())
    panel_task = asyncio.create_task(owner_panel_refresher(bot))
    _BG_TASKS.add(scanner_task); _BG_TASKS.add(backup_task)
    _BG_TASKS.add(watchdog_task); _BG_TASKS.add(heartbeat_task)
    _BG_TASKS.add(panel_task)

    try:
        await bot.send_message(
            MAIN_OWNER,
            f"{em(EMOJI_ROCKET, '🚀')} <b>{_VERSION} Online</b>\n"
            f"@{me.username}\n<code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
            f"PID: <code>{os.getpid()}</code>\n\n"
            f"⚡ Mode: <b>{CURRENT_POWER_MODE}x</b>\n"
            f"🛡 Watchdog: <b>ACTIVE</b>\n"
            f"💓 Heartbeat: <b>ACTIVE</b>\n"
            f"🔒 Lock: <b>ACTIVE</b>\n"
            f"🚦 Callback Limit: <b>{_CALLBACK_CONCURRENCY}</b>\n"
            f"⏱ Cooldown: <b>{_USER_COOLDOWN_SEC}s</b>\n"
            f"🎯 Blast Limit: <b>{_GLOBAL_BLAST_LIMIT}</b>\n"
            f"🔍 Scan: <b>{_BACKGROUND_SCAN_INTERVAL:.0f}s</b>\n"
            f"🔄 Panel Refresh: <b>{_PANEL_REFRESH_INTERVAL:.0f}s</b>\n"
            f"⚙️ Power Modes: <b>2/3/4/5/10x</b>",
            parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e: log.warning(f"Owner notify: {e}")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(),
                               polling_timeout=30, handle_signals=False)
    finally:
        try:
            watchdog_task.cancel(); heartbeat_task.cancel(); panel_task.cancel()
        except Exception: pass
        await _shutdown(bot)

async def main():
    _acquire_lock()
    log.info(f"[MAIN] Starting PID={os.getpid()}")
    attempt = 0
    while True:
        if _SHUTDOWN_REQUESTED:
            log.info("[MAIN] Shutdown requested")
            _release_lock(); return
        attempt += 1
        try:
            log.info(f"[MAIN] Session #{attempt}")
            await run_session()
            log.warning("[MAIN] Session ended, restart in 5s")
            for _ in range(5):
                if _SHUTDOWN_REQUESTED: break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            if _SHUTDOWN_REQUESTED: _release_lock(); return
            raise
        except KeyboardInterrupt:
            _release_lock(); raise
        except SystemExit:
            if _SHUTDOWN_REQUESTED: _release_lock(); return
            raise
        except Exception as e:
            backoff = min(5 + attempt * 2, 60)
            log.error(f"[MAIN] Crash #{attempt}: {e} — restart in {backoff}s", exc_info=True)
            for _ in range(backoff):
                if _SHUTDOWN_REQUESTED: break
                await asyncio.sleep(1)

# ============================================================
#  ENTRY
# ============================================================
if __name__ == "__main__":
    def _sigterm_handler(signum, frame):
        global _SHUTDOWN_REQUESTED
        log.warning(f"Signal {signum} — graceful shutdown")
        _SHUTDOWN_REQUESTED = True

    try: signal.signal(signal.SIGTERM, _sigterm_handler)
    except Exception: pass
    try: signal.signal(signal.SIGINT, _sigterm_handler)
    except Exception: pass

    while True:
        if _SHUTDOWN_REQUESTED:
            log.info("[BOOT] Clean exit"); _release_lock(); break
        try:
            asyncio.run(main())
            if _SHUTDOWN_REQUESTED:
                log.info("[BOOT] Clean shutdown"); _release_lock(); break
            log.warning("[BOOT] Restart in 5s")
            for _ in range(5):
                if _SHUTDOWN_REQUESTED: break
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("[BOOT] Stopped by user"); _release_lock(); break
        except SystemExit:
            if _SHUTDOWN_REQUESTED: _release_lock()
            break
        except Exception as e:
            log.critical(f"[BOOT] Fatal: {e} — restart in 10s", exc_info=True)
            for _ in range(10):
                if _SHUTDOWN_REQUESTED: break
                time.sleep(1)