import os
import uuid
import shutil
import aiohttp
import aiofiles
from pyrogram import Client, filters, enums
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from config import Config

insta_regex = r"(?i)\b(?:https?:\/\/)?(?:www\.)?instagram\.com\b"


async def download_file(session, url, folder):
    async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
        if response.status != 200:
            raise Exception(f"Failed to download file (HTTP {response.status})")

        # Try to extract filename safely
        try:
            cd = response.headers.get("Content-Disposition", "")
            filename = cd.split("filename=")[-1].strip().strip('"')
            if not filename:
                raise Exception("Filename not found")
        except Exception as e:
            raise Exception(f"Filename not found — {str(e)}")

        filepath = os.path.join(folder, filename)
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(await response.read())

    return filepath, filename


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

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=25) as resp:
                if resp.status != 200:
                    await k.edit_text(f"⚠️ API returned HTTP {resp.status}")
                    return
                r = await resp.json()

            media_list = r.get("data", {}).get("data", [])
            if not media_list:
                await k.edit_text("❌ No media found.")
                return

            files = []

            for item in media_list:
                media_url = item.get("url")
                if not media_url:
                    continue

                try:
                    filepath, filename = await download_file(session, media_url, download_dir)
                except Exception as e:
                    await k.edit_text(str(e))
                    return

                files.append(filepath)

        if not files:
            await k.edit_text("❌ Download failed for all media.")
            return

        # Send files according to extension
        if len(files) == 1:
            filepath = files[0]
            ext = filepath.split(".")[-1].lower()
            if ext == "mp4":
                await message.reply_chat_action(enums.ChatAction.UPLOAD_VIDEO)
                await message.reply_video(filepath, caption=caption)
            else:
                await message.reply_chat_action(enums.ChatAction.UPLOAD_PHOTO)
                await message.reply_photo(filepath, caption=caption)
        else:
            album = []
            for i, filepath in enumerate(files):
                ext = filepath.split(".")[-1].lower()
                if ext == "mp4":
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
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir, ignore_errors=True)
