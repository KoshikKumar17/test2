from pyrogram import Client, filters, enums
from pyrogram.types import InputMediaPhoto, InputMediaVideo
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

        # Safe JSON access
        media_list = r.get("data", {}).get("data", [])
        if not media_list:
            await k.edit_text("❌ No media found.")
            return

        caption = f"{link}\n\n@RKrishnaaRoBot"

        # ✅ Only one media
        if len(media_list) == 1:
            media_url = media_list[0].get("url")
            if not media_url:
                await k.edit_text("❌ Invalid media URL.")
                return

            try:
                head = requests.head(media_url, allow_redirects=True, timeout=10)
                mime = head.headers.get("Content-Type", "").lower()
            except Exception:
                mime = ""

            if "video" in mime:
                await message.reply_chat_action(enums.ChatAction.UPLOAD_VIDEO)
                await message.reply_video(media_url, caption=caption)
            else:
                await message.reply_chat_action(enums.ChatAction.UPLOAD_PHOTO)
                await message.reply_photo(media_url, caption=caption)

            await k.delete()
            return

        # ✅ Multiple media (photo + video both supported)
        album = []
        for item in media_list:
            media_url = item.get("url")
            if not media_url:
                continue

            try:
                head = requests.head(media_url, allow_redirects=True, timeout=10)
                mime = head.headers.get("Content-Type", "").lower()
            except Exception:
                mime = ""

            if "video" in mime:
                album.append(InputMediaVideo(media_url))
            else:
                album.append(InputMediaPhoto(media_url))

        if not album:
            await k.edit_text("❌ No valid media URLs found.")
            return

        # Add caption only to the first media in album
        album[0].caption = caption
        await message.reply_chat_action(enums.ChatAction.UPLOAD_PHOTO)
        await message.reply_media_group(album)
        await k.delete()

    except Exception as e:
        await k.edit_text(f"⚠️ Error: {str(e)}")
