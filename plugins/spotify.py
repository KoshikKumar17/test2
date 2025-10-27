import os
import uuid
import shutil
import aiohttp
import aiofiles
from urllib.parse import urlparse, parse_qs
from pyrogram import Client, filters, enums
from config import Config

spotify_regex = r"(?i)(https?:\/\/)?(open\.)?spotify\.com\/[\w\-/?=%.]*"

async def convert_duration(duration_str: str) -> int:
    """Convert Spotify duration like '4:7' to integer seconds (247)."""
    try:
        parts = duration_str.split(":")
        if len(parts) == 2:
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        return int(duration_str)
    except Exception:
        return 0


@Client.on_message(filters.text & filters.regex(spotify_regex))
async def spotify_downloader(client, message):
    if str(message.from_user.id) not in Config.AUTHJS:
        return

    link = message.text.strip()
    task_id = str(uuid.uuid4())[:8]
    download_dir = f"downloads/{task_id}"
    os.makedirs(download_dir, exist_ok=True)

    k = await message.reply_text("🎵 Processing Spotify link...", quote=True)

    try:
        api_url = f"https://universaldownloaderapi.vercel.app/api/spotify/download?url={link}"

        async with aiohttp.ClientSession() as session:
            # Fetch Spotify metadata
            async with session.get(api_url, timeout=15) as resp:
                if resp.status != 200:
                    await k.edit_text(f"⚠️ API returned HTTP {resp.status}")
                    return
                data = await resp.json()

            song_data = data.get("data", {})
            if not song_data:
                await k.edit_text("❌ Invalid API response.")
                return

            title = song_data.get("title", "Unknown")
            album = song_data.get("author", "Unknown")
            duration = await convert_duration(data.get("duration", "0:0"))
            download_links = song_data.get("downloadLinks", [])
            if not download_links:
                await k.edit_text("❌ No download link found.")
                return

            media_url = download_links[0].get("url")
            if not media_url:
                await k.edit_text("❌ Download URL missing.")
                return

            # Extract artist name from query
            parsed = urlparse(media_url)
            params = parse_qs(parsed.query)
            artist = params.get("artist", ["Unknown"])[0]

            # Download audio as title.mp3
            filename = f"{title} - {artist}.mp3"
            filepath = os.path.join(download_dir, filename)

            async with session.get(media_url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                if response.status != 200:
                    await k.edit_text(f"⚠️ Failed to download audio (HTTP {response.status})")
                    return

                async with aiofiles.open(filepath, "wb") as f:
                    await f.write(await response.read())

        await message.reply_chat_action(enums.ChatAction.UPLOAD_AUDIO)
        caption = f"""**Title:** {title}\n\n**Artists:** {artist}\n\n**Album:** {album}"""
        await message.reply_audio(
            audio=filepath,
            caption=caption,
            title=title,
            performer=artist,
            duration=duration)
        await k.delete()

    except Exception as e:
        await k.edit_text(f"⚠️ Error: {str(e)}")

    finally:
        # Delete temporary folder
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir, ignore_errors=True)
