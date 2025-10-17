from pyrogram import Client, filters
from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from requests.utils import requote_uri
import requests
import html

@Client.on_inline_query()
def inline_query_handler(client, inline_query):
    query = inline_query.query.strip()
    qry = requote_uri(query)
    if not query:
        inline_query.answer(
            results=[],
            switch_pm_text="Type a song name to search!",
            switch_pm_parameter="start",
        )
        return

    # Fetch data from JioSaavn API
    api_url = f"https://jiosaavnsearch.vercel.app/search/songs?query={qry}&limit=15"
    try:
        response = requests.get(api_url)
        if response.status_code != 200:
            raise Exception("Invalid API response")
        ress = response.json()
    except Exception as e:
        inline_query.answer(
            results=[],
            switch_pm_text="Error fetching data. Try again later.",
            switch_pm_parameter="error",
        )
        return

    # Check if the JSON contains results
    if "data" not in ress or "results" not in ress["data"]:
        inline_query.answer(
            results=[],
            switch_pm_text="No results found.",
            switch_pm_parameter="no_results",
        )
        return

    results = ress["data"]["results"]
    if not results:
        inline_query.answer(
            results=[],
            switch_pm_text="No results found.",
            switch_pm_parameter="no_results",
        )
        return

    answers = []
    for result in results[:15]:  # Limit to 50 results to avoid flooding
        title = html.unescape(result.get("name", "Unknown Title"))
        url = result.get("url", "#")
        artist = html.unescape(result.get("primaryArtists", "Unknown Artist"))
        album = html.unescape(result.get("album", {}).get("name", "Unknown Album"))
        img_url = result.get("image", [{}])[1].get("link", "")

        # Add inline keyboard with a "Search Again" button
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Search Again", switch_inline_query_current_chat="")]]
        )

        answers.append(
            InlineQueryResultArticle(
                title=title,
                description=f"Artist: {artist} \nAlbum: {album}",
                thumb_url=img_url,
                input_message_content=InputTextMessageContent(f"{url}"),
                reply_markup=keyboard,
            )
        )

    # Send the results to the inline query
    inline_query.answer(answers, cache_time=30)

# If you want to remove &quot (as I saw in some songs)
# import html
# html.unescape()
# Ex: html.unescape(result.get("album", {}).get("name", "Unknown Album"))
