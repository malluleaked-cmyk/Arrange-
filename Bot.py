import os
import re
import time
import requests
import telebot

BOT_TOKEN = "YOUR_BOT_TOKEN"
API_ENDPOINT = "https://YOUR_API.com/api"

ADMIN_IDS = [6630347046, 7194569468]
DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=10)


def is_admin(user_id):
    return user_id in ADMIN_IDS


def extract_surl(url):
    patterns = [
        r"/s/([A-Za-z0-9_-]+)",
        r"surl=([A-Za-z0-9_-]+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            code = match.group(1)

            # TeraShare link usually starts with 1
            if code.startswith("1"):
                code = code[1:]

            return code

    return None


def safe_name(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def human_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{round(size, 2)} {unit}"
        size /= 1024
    return f"{round(size, 2)} TB"


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


def download_file(url, file_path):
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()

        total = 0

        with open(file_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)

        return total


@bot.message_handler(commands=["start"])
def start(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Admin only bot")
        return

    bot.reply_to(
        message,
        "🔥 TeraBox Video Bot Ready\n\n"
        "TeraBox / TeraShare link അയക്കൂ 😺"
    )


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
            f"✅ File Found\n\n"
            f"📄 {file_name}\n"
            f"📦 {result['size']}\n\n"
            f"⬇️ Downloading...",
            message.chat.id,
            status.message_id
        )

        start_time = time.time()

        total_size = download_file(
            result["download_url"],
            file_path
        )

        taken = round(time.time() - start_time, 2)

        bot.edit_message_text(
            f"✅ Download Complete\n\n"
            f"📦 {human_size(total_size)}\n"
            f"⚡ {taken}s\n\n"
            f"🚀 Uploading video...",
            message.chat.id,
            status.message_id
        )

        with open(file_path, "rb") as video:
            bot.send_video(
                chat_id=message.chat.id,
                video=video,
                caption=f"🔥 {file_name}\n\n⚡ Uploaded by bot",
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
