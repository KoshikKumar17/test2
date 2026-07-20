import os
import re
import tempfile
import shutil
import zipfile

from pyrogram import Client, filters
from pyrogram.types import Message
from PIL import Image

STICKER_LINK_REGEX = re.compile(r"(?:https?://)?t\.me/addstickers/([a-zA-Z0-9_]+)")

def extract_pack_name(text: str) -> str | None:
    text = (text or "").strip()
    match = re.search(r"t\.me/(?:addstickers|addemoji)/([A-Za-z0-9_]+)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_]+", text):
        return text
    return None


@Client.on_message(filters.text & filters.regex(STICKER_LINK_REGEX))
async def handle_message(client: Client, message: Message):
    pack_name = extract_pack_name(message.text)

    if not pack_name:
        await message.reply_text(
            "That doesn't look like a sticker pack link. "
            "Send something like https://t.me/addstickers/PackName"
        )
        return

    status_msg = await message.reply_text(f"Looking up pack '{pack_name}'...")

    try:
        sticker_set = await client.get_stickers_set(pack_name)
    except Exception as e:
        await status_msg.edit_text(
            "Couldn't find that sticker pack. Double-check the link and try again."
        )
        return

    stickers = sticker_set.stickers
    if not stickers:
        await status_msg.edit_text("That pack has no stickers.")
        return

    await status_msg.edit_text(
        f"Found '{sticker_set.title}' ({len(stickers)} stickers). Downloading and converting..."
    )

    # Use a temp directory for both downloads and the final zip; removed in `finally`.
    temp_dir = tempfile.mkdtemp(prefix="stickerpack_")
    downloads_dir = os.path.join(temp_dir, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    converted_count = 0
    skipped_count = 0

    try:
        for idx, sticker in enumerate(stickers, start=1):
            # Skip animated (.tgs) and video (.webm) stickers — not single-frame images.
            if sticker.is_animated or sticker.is_video:
                skipped_count += 1
                continue

            try:
                local_webp_path = os.path.join(downloads_dir, f"sticker_{idx}.webp")
                await client.download_media(sticker.file_id, file_name=local_webp_path)

                # Convert webp -> jpg (flatten transparency onto white background).
                with Image.open(local_webp_path) as img:
                    img = img.convert("RGBA")
                    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                    flattened = Image.alpha_composite(background, img).convert("RGB")

                    jpg_path = os.path.join(downloads_dir, f"sticker_{idx}.jpg")
                    flattened.save(jpg_path, "JPEG", quality=95)

                converted_count += 1
            except Exception as e:
                skipped_count += 1
                continue

        if converted_count == 0:
            await status_msg.edit_text(
                "No static stickers could be converted (pack may be all animated/video)."
            )
            return

        await status_msg.edit_text(f"Zipping {converted_count} images...")

        zip_path = os.path.join(temp_dir, f"{pack_name}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in sorted(os.listdir(downloads_dir)):
                if fname.endswith(".jpg"):
                    zf.write(os.path.join(downloads_dir, fname), arcname=fname)

        caption = f"{converted_count} stickers converted"
        if skipped_count:
            caption += f", {skipped_count} skipped (animated/video/failed)"

        await message.reply_document(document=zip_path, caption=caption)
        await status_msg.delete()

    finally:
        # Always clean up the temp folder, success or failure.
        shutil.rmtree(temp_dir, ignore_errors=True)

