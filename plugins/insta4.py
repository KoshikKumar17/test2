from pyrogram import Client, filters, enums
from config import Config
import requests

insta_regex = r"(?i)\b(?:https?:\/\/)?(?:www\.)?instagram\.com\b"

@Client.on_message(filters.text & filters.regex(insta_regex))
async def insta_downloader(client, message):
    if str(message.from_user.id) not in Config.AUTHJS:
        return
    try:
        link = message.text.strip()
        k = await message.reply_text("**Processing...**", quote=True)
        api_url = f"https://universaldownloaderapi.vercel.app/api/meta/download?url={link}"
        r = requests.get(api_url, timeout=20).json()

        # Access data safely
        media_list = r['data']['data'][]
        if not media_list:
            await k.edit_text("❌ No media found.")
            return

        for i, item in enumerate(media_list):
            media_url = item.get("url")
            if not media_url:
                continue

            # Try HEAD to detect MIME type
            try:
                head = requests.head(media_url, allow_redirects=True, timeout=15)
                mime = head.headers.get("Content-Type", "").lower()
            except Exception:
                mime = ""

            caption = f"""{link}\n\n@RKrishnaRoBot"""

            if "video" in mime:
                await message.reply_chat_action(enums.ChatAction.UPLOAD_VIDEO)
                await message.reply_video(media_url, caption=caption)
                await k.delete()
            else:
                await message.reply_chat_action(enums.ChatAction.UPLOAD_PHOTO)
                await message.reply_photo(media_url, caption=caption)
                await k.delete()

    except Exception as e:
        await k.edit_text(f"⚠️ Error: {str(e)}")
