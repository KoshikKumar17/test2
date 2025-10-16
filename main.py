import os
import asyncio
import aiohttp
from aiohttp.web import Application, AppRunner, TCPSite, RouteTableDef, Request, json_response
from pyrogram import Client
from config import Config

routes = RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request: Request):
    """ Handles the root route ("/") of the web application. """
    return json_response("Bot Running...")

async def start_web():
    """ Initializes and starts the web server. """
    web_app = Application()
    web_app.add_routes(routes)
    runner = AppRunner(web_app)
    await runner.setup()
    await TCPSite(runner, Config.HOST, Config.PORT).start()
    print("Web server started!!")
    return runner

async def stop_web(runner: AppRunner):
    """Stops the web server and performs cleanup."""
    print("Stopping Web Server!!")
    await runner.cleanup()

async def keep_traffic():
    """Keep traffic on host every 10 minutes."""
    while True:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://bot1-eqpc.onrender.com/') as response:
                if response.status == 200:
                    print("Host traffic alive!")
                else:
                    print("Failed to maintain traffic")
        await asyncio.sleep(600)  # 10 minutes

class Bot(Client):
    def __init__(self):
        super().__init__( 
            name="bot",
            bot_token=Config.BOT_TOKEN,
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            #sleep_threshold=30,
            max_concurrent_transmissions=5,
            plugins={
                "root": "plugins"
            }
        )

    async def start(self):
        await super().start()
        self.web_runner = await start_web()
        # Start keeping traffic alive
        asyncio.create_task(keep_traffic())
        print("New session started for me.")

    async def stop(self):
        await super().stop()
        await stop_web(self.web_runner)
        print("Session stopped. Bye!!")

Bot().run()
