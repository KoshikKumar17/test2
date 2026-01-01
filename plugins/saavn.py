import os
import re
import html
import uuid
import shutil
import asyncio
import aiohttp
import requests
import aiofiles
from mutagen.mp4 import MP4, MP4Cover
from pyrogram import Client, filters, enums
from config import Config

saavn_regex = r"(?i)(https?:\/\/)?(www\.)?jiosaavn\.com\/[\w\-/?=%.]*"

def safe_fname(name: str) -> str:
    name = html.unescape(name)
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()

@Client.on_message(filters.text & filters.regex(saavn_regex))
async def jiosaavndl(client, message):
    if str(message.from_user.id) not in Config.AUTHJS:
        return
    task_id = str(uuid.uuid4())[:8]
    download_dir = f"downloads/{task_id}"
    os.makedirs(download_dir, exist_ok=True)  # Ensure the downloads folder exists
    await message.reply_chat_action(enums.ChatAction.TYPING)
    text = message.text.strip()
    api = f"https://jiosaavnsearch.vercel.app/songs?link={text}"
    
    if "jiosaavn.com/song" in text:
        k = await message.reply_text("**Processing...**", quote=True)
        
        # Fetch Song Metadata
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api) as response:
                    if response.status != 200:
                        await k.edit_text(f"**Error fetching song data:** `HTTP {response.status}`")
                        return
                    req = await response.json()
        except Exception as e:
            await k.edit_text(f"**Error fetching song data:** `{str(e)}`")
            return
        
        try:
            # Extracting Song Metadata
            res = req['data'][0]
            title = safe_fname(res['name'])
            artist = safe_fname(res['primaryArtists'])
            song_url = res['downloadUrl'][3]['link']
            duration = res['duration']
            album = safe_fname(res['album']['name'])
            year = res['year']
            copyright_info = res['copyright']
            img_url = res['image'][2]['link']  # URL for cover art
            cmnt = f"(c) Koshik Kumar - {res['url']}"
            
            # File paths
            afile = os.path.join(download_dir, f"{title}.mp4")
            #mp3_file = os.path.join(download_dir, f"{title}_temp.mp3")
            ofile = os.path.join(download_dir, f"{title} - {artist}.m4a")
            #cover_image_path = os.path.join(download_dir, f"{title}.jpg")
            
            # Download the Song
            async with aiohttp.ClientSession() as session:
                async with session.get(song_url) as response:
                    if response.status == 200:
                        async with aiofiles.open(afile, mode='wb') as f:
                            await f.write(await response.read())
                    else:
                        await k.edit_text(f"**Error downloading song:** `HTTP {response.status}`")
                        return
            
            # Rename the downloaded file to .mp3
            #os.rename(afile, mp3_file)

            #useless
            # Download the Cover Art
            #async with aiohttp.ClientSession() as session:
                #async with session.get(img_url) as response:
                    #if response.status == 200:
                        #async with aiofiles.open(cover_image_path, mode='wb') as f:
                            #await f.write(await response.read())
                    #else:
                        #cover_image_path = None
            #useless
            
            img_response = requests.get(img_url)
            cover_art = img_response.content if img_response.status_code == 200 else None
            
            try:
                audio = MP4(afile)
                audio["\xa9nam"] = title
                audio["\xa9alb"] = album
                audio["\xa9ART"] = artist
                audio["\xa9day"] = year
                audio["\xa9cmt"] = cmnt
                audio["cprt"] = copyright_info
                if cover_art:
                    audio["covr"] = [MP4Cover(cover_art, imageformat=MP4Cover.FORMAT_JPEG)]
                audio.save()
            except Exception as e:
                await k.edit_text(str(e))

            # Rename the file to .m4a
            os.rename(afile, ofile)

            
            # Step 5: Send the Song
            caption = f"""**Title:** {title}\n\n**Artists:** {artist}\n\n**Album:** {album}"""
            await message.reply_chat_action(enums.ChatAction.UPLOAD_AUDIO)
            await message.reply_audio(
                audio=ofile,
                duration=int(duration),
                caption=caption,
                performer=artist,
                quote=True,
                title=title
            )
            
            # Step 6: Cleanup
            try:
                shutil.rmtree(download_dir)
                
            except Exception as e:
                print(f"**Error deleting files:** `{str(e)}`")
            
            await k.delete()
        
        except Exception as e:
            await k.edit_text(f"**Error:** `{str(e)}`")
