import os
import re
import random
import string
import tempfile
import shutil
import zipfile

from pyrogram import Client, filters, raw
from pyrogram.types import Message
from PIL import Image

PACK_LINK_REGEX = re.compile(r"t\.me/(?:addstickers|addemoji)/([A-Za-z0-9_]+)")


def extract_pack_name(text: str) -> str | None:
    text = (text or "").strip()
    match = PACK_LINK_REGEX.search(text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_]+", text):
        return text
    return None


def random_suffix(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


async def get_sticker_set(client: Client, short_name: str):
    """Vanilla Pyrogram has no high-level get_stickers_set() — call the raw API directly."""
    return await client.invoke(
        raw.functions.messages.GetStickerSet(
            stickerset=raw.types.InputStickerSetShortName(short_name=short_name),
            hash=0,
        )
    )


async def download_raw_document(client: Client, document, dest_path: str):
    """Download a raw Document (e.g. a sticker) by pulling it chunk by chunk via upload.GetFile."""
    location = raw.types.InputDocumentFileLocation(
        id=document.id,
        access_hash=document.access_hash,
        file_reference=document.file_reference,
        thumb_size="",
    )
    limit = 1024 * 1024  # 1 MB per chunk
    offset = 0
    with open(dest_path, "wb") as f:
        while True:
            result = await client.invoke(
                raw.functions.upload.GetFile(location=location, offset=offset, limit=limit)
            )
            chunk = result.bytes
            if not chunk:
                break
            f.write(chunk)
            offset += len(chunk)
            if len(chunk) < limit:
                break


@Client.on_message(filters.text)
async def handle_message(client: Client, message: Message):
    pack_name = extract_pack_name(message.text)

    if not pack_name:
        return  # not a sticker pack link / short-name — ignore silently

    status_msg = await message.reply_text(f"Looking up pack '{pack_name}'...")

    try:
        result = await get_sticker_set(client, pack_name)
    except Exception as e:
        await status_msg.edit_text(
            f"Couldn't find that sticker pack. Double-check the link and try again.\n"
            f"(debug: {e})"
        )
        return

    documents = result.documents
    if not documents:
        await status_msg.edit_text("That pack has no stickers.")
        return

    await status_msg.edit_text(
        f"Found '{result.set.title}' ({len(documents)} stickers). Downloading and converting..."
    )

    # Use a temp directory for both downloads and the final zip; removed in `finally`.
    temp_dir = tempfile.mkdtemp(prefix="stickerpack_")
    downloads_dir = os.path.join(temp_dir, f"downloads_{random_suffix()}")
    os.makedirs(downloads_dir, exist_ok=True)

    converted_count = 0
    skipped_count = 0

    try:
        for idx, doc in enumerate(documents, start=1):
            # Skip animated (.tgs) and video (.webm) stickers — not single-frame images.
            if doc.mime_type in ("application/x-tgsticker", "video/webm"):
                skipped_count += 1
                continue

            try:
                local_webp_path = os.path.join(downloads_dir, f"sticker_{idx}.webp")
                await download_raw_document(client, doc, local_webp_path)

                # Convert webp -> jpg (flatten transparency onto white background).
                with Image.open(local_webp_path) as img:
                    img = img.convert("RGBA")
                    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                    flattened = Image.alpha_composite(background, img).convert("RGB")

                    jpg_path = os.path.join(downloads_dir, f"sticker_{idx}.jpg")
                    flattened.save(jpg_path, "JPEG", quality=95)

                converted_count += 1
            except Exception:
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
