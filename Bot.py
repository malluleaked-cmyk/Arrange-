import os
import re
import time
import requests
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ENDPOINT = os.getenv("API_ENDPOINT", "https://YOUR_API.com/api")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing in Railway Variables")

ADMIN_IDS = [6630347046, 7194569468]
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=10)


def is_admin(user_id):
    return user_id in ADMIN_IDS


def extract_surl(url):
    match = re.search(r"/s/([A-Za-z0-9_-]+)", url)
    if not match:
        return None

    code = match.group(1)
    if code.startswith("1"):
        code = code[1:]
    return code


def safe_name(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def resolve_terabox(url):
    surl = extract_surl(url)

    if not surl:
        return {"ok": False, "message": "Invalid link"}

    try:
        api_url = f"{API_ENDPOINT}?surl={surl}"
        r = requests.get(api_url, timeout=60)
        data = r.json()

        if not data.get("success"):
            return {"ok": False, "message": "API resolve failed"}

        file_data = data.get("data", {})
        download_url = file_data.get("download_url")

        if not download_url:
            return {"ok": False, "message": "download_url missing"}

        return {
            "ok": True,
            "file_name": file_data.get("file_name", "video.mp4"),
            "size": file_data.get("size", "Unknown"),
            "download_url": download_url
        }

    except Exception as e:
        return {"ok": False, "message": str(e)}


def download_file(url, path):
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()

        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


@bot.message_handler(commands=["start"])
def start(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Admin only bot")
        return

    bot.reply_to(message, "🔥 TeraBox Bot Ready\n\nLink അയക്കൂ 😺")


@bot.message_handler(func=lambda m: True)
def handle_link(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Admin only bot")
        return

    url = message.text.strip()

    if "terabox" not in url and "terasharefile" not in url:
        bot.reply_to(message, "❌ Valid TeraBox / TeraShare link അയക്കൂ")
        return

    status = bot.reply_to(message, "🔎 Resolving link...")

    result = resolve_terabox(url)

    if not result["ok"]:
        bot.edit_message_text(
            f"❌ Failed\n\n{result['message']}",
            message.chat.id,
            status.message_id
        )
        return

    file_name = safe_name(result["file_name"])
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    try:
        bot.edit_message_text(
            f"✅ File Found\n\n📄 {file_name}\n📦 {result['size']}\n\n⬇️ Downloading...",
            message.chat.id,
            status.message_id
        )

        download_file(result["download_url"], file_path)

        bot.edit_message_text(
            "✅ Download Complete\n\n🚀 Uploading video...",
            message.chat.id,
            status.message_id
        )

        with open(file_path, "rb") as video:
            bot.send_video(
                message.chat.id,
                video,
                caption=f"🔥 {file_name}",
                supports_streaming=True
            )

        bot.delete_message(message.chat.id, status.message_id)

    except Exception as e:
        bot.edit_message_text(
            f"❌ Error\n\n{e}",
            message.chat.id,
            status.message_id
        )

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


print("🔥 Bot Running...")

bot.infinity_polling(
    skip_pending=True,
    timeout=60,
    long_polling_timeout=60
)
