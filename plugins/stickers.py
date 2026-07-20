import asyncio
import re
import zipfile
import random
import string
from pathlib import Path
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.raw.functions.messages import GetStickerSet
from pyrogram.raw.types import InputStickerSetShortName
from pyrogram.errors import StickersetInvalid

STICKER_LINK_REGEX = re.compile(r"(?:https?://)?t\.me/addstickers/([a-zA-Z0-9_]+)")

BASE_DOWNLOADS = Path("downloads")
BASE_DOWNLOADS.mkdir(exist_ok=True)


def generate_short_id(length=8):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=length))


async def convert_to_jpeg(input_path: Path, output_path: Path):
    """Convert static sticker to JPEG"""
    try:
        with Image.open(input_path) as img:
            if img.mode in ("RGBA", "P", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            
            img.save(output_path, "JPEG", quality=95, optimize=True)
        return True
    except Exception:
        import shutil
        shutil.copy(input_path, output_path)
        return False


async def download_sticker_pack(client: Client, short_name: str, message: Message):
    temp_id = generate_short_id(random.randint(6, 8))
    pack_dir = BASE_DOWNLOADS / temp_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    
    k = await message.reply_text("🔍 Checking sticker pack...")

    try:
        await k.edit_text(f"🔍 Fetching sticker pack: **{short_name}**...")

        sticker_set = await client.invoke(
            GetStickerSet(
                stickerset=InputStickerSetShortName(short_name=short_name),
                hash=0
            )
        )

        documents = sticker_set.documents
        if not documents:
            await k.edit_text("❌ No stickers found.")
            return

        # Filter out animated stickers (.tgs)
        static_documents = [doc for doc in documents if doc.mime_type != "application/x-tgsticker"]
        
        skipped = len(documents) - len(static_documents)
        
        if not static_documents:
            await k.edit_text("❌ This pack contains only animated stickers (.tgs).\nNo static stickers to download.")
            return

        await k.edit_text(f"📥 Downloading **{len(static_documents)}** static stickers (skipping {skipped} animated)...")

        jpeg_files = []
        for i, doc in enumerate(static_documents, 1):
            orig_path = pack_dir / f"orig_{i:03d}.webp"
            
            # Download the sticker
            await client.download_media(doc, file_name=str(orig_path))

            # Convert to JPEG
            jpeg_path = pack_dir / f"{i:03d}.jpg"
            await convert_to_jpeg(orig_path, jpeg_path)
            jpeg_files.append(jpeg_path)

            if i % 8 == 0:
                await k.edit_text(f"✅ Processed {i}/{len(static_documents)} static stickers...")

        # Create ZIP
        zip_path = BASE_DOWNLOADS / f"{short_name}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in jpeg_files:
                zipf.write(file, file.name)

        # Send ZIP
        await message.reply_document(
            document=str(zip_path),
            caption=f"✅ **Sticker Pack Downloaded**\n"
                    f"**Pack:** {short_name}\n"
                    f"**Static Stickers:** {len(static_documents)}\n"
                    f"**Skipped (Animated):** {skipped}\n"
                    f"**All converted to JPEG**"
        )

    except StickersetInvalid:
        await k.edit_text("❌ Invalid sticker pack.")
    except Exception as e:
        await k.edit_text(f"❌ Error: {str(e)}")
    finally:
        # Cleanup temporary folder
        if pack_dir.exists():
            for f in pack_dir.glob("**/*"):
                f.unlink(missing_ok=True)
            try:
                pack_dir.rmdir()
            except:
                pass
        # Cleanup ZIP
        if 'zip_path' in locals() and zip_path.exists():
            zip_path.unlink(missing_ok=True)


@Client.on_message(filters.text & filters.regex(STICKER_LINK_REGEX))
async def handle_sticker_link(client: Client, message: Message):
    match = STICKER_LINK_REGEX.search(message.text)
    if match:
        short_name = match.group(1)
        await download_sticker_pack(client, short_name, message)
