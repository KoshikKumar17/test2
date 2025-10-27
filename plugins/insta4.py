import os
import uuid
import shutil
import aiohttp
import aiofiles
from pyrogram import Client, filters, enums
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from config import Config

insta_regex = r"(?i)\b(?:https?:\/\/)?(?:www\.)?instagram\.com\b"


async def download_file(session, url, filename):
    """Download file asynchronously using aiohttp + aiofiles"""
    async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
        if resp.status != 200:
            raise Exception(f"Failed to download: HTTP {resp.status}")
        async with aiofiles.open(filename, "wb") as f:
            await f.write(await resp.read())
    return filename


@Client.on_message(filters.text & filters.regex(insta_regex))
async def insta_downloader(client, message):
    if str(message.from_user.id) not in Config.AUTHJS:
        return

    link = message.text.strip()
    task_id = str(uuid.uuid4())[:8]
    download_dir = f"downloads/{task_id}"
    os.makedirs(download_dir, exist_ok=True)

    k = await message.reply_text("**Processing...**", quote=True)
    caption = f"{link}\n\n@RKrishnaaRoBot"

    try:
        api_url = f"https://universaldownloaderapi.vercel.app/api/meta/download?url={link}"

        # Step 1: Fetch media metadata
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=20) as resp:
                if resp.status != 200:
                    await k.edit_text(f"⚠️ API returned HTTP {resp.status}")
                    return
                r = await resp.json()

            media_list = r.get("data", {}).get("data", [])
            if not media_list:
                await k.edit_text("❌ No media found.")
                return

            files = []

            # Step 2: Download all media files
            for i, item in enumerate(media_list):
                media_url = item.get("url")
                if not media_url:
                    continue

                # Detect MIME type
                try:
                    async with session.head(media_url, allow_redirects=True, timeout=10) as head:
                        mime = head.headers.get("Content-Type", "").lower()
                except Exception:
                    mime = ""

                ext = ".mp4" if "video" in mime else ".jpg"
                filename = f"instadl_rkrishnaarobot_{message.from_user.id}_{i}{ext}"
                filepath = os.path.join(download_dir, filename)

                try:
                    await download_file(session, media_url, filepath)
                    files.append((filepath, mime))
                except Exception as e:
                    print(f"Download error for {media_url}: {e}")
                    continue

        if not files:
            await k.edit_text("❌ Download failed for all media.")
            return

        # Step 3: Send to Telegram
        if len(files) == 1:
            filepath, mime = files[0]
            if "video" in mime:
                await message.reply_chat_action(enums.ChatAction.UPLOAD_VIDEO)
                await message.reply_video(filepath, caption=caption)
            else:
                await message.reply_chat_action(enums.ChatAction.UPLOAD_PHOTO)
                await message.reply_photo(filepath, caption=caption)
        else:
            album = []
            for i, (filepath, mime) in enumerate(files):
                if "video" in mime:
                    media = InputMediaVideo(filepath)
                else:
                    media = InputMediaPhoto(filepath)
                if i == 0:
                    media.caption = caption
                album.append(media)

            await message.reply_chat_action(enums.ChatAction.UPLOAD_PHOTO)
            await message.reply_media_group(album)

        await k.delete()

    except Exception as e:
        await k.edit_text(f"⚠️ Error: {str(e)}")

    finally:
        # Step 4: Clean up temp folder
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir, ignore_errors=True)
