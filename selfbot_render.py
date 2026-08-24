#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   DISCORD SELF-BOT — RENDER EDITION v4.0                    ║
║   DM / GROUP DM / SERVER — All channels supported           ║
║   For authorized security testing only                      ║
╚══════════════════════════════════════════════════════════════╝
"""
"""SELF-HEALING IMPORT — ensures discord.py-self is loaded"""
import subprocess, sys
try:
    import discord
    # Verify we have Intents (discord.py-self specific)
    _ = discord.Intents.all
except AttributeError:
    print("⚠️ Wrong discord library detected. Auto-fixing...")
    subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "discord", "discord.py", "-y"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--force-reinstall",
                           "git+https://github.com/dolfies/discord.py-self.git"])
    print("✅ Fixed! Restarting...")
    subprocess.check_call([sys.executable] + sys.argv)
    sys.exit(0)
    
import discord
from discord.ext import commands, tasks
from discord.ext.commands import UserConverter
import aiohttp
import asyncio
import os
import sys
import json
import random
import datetime
import platform
import logging
import re
from typing import Optional, Union

# ─── RENDER CONFIG ───────────────────────────────────────────────────────────

RENDER_PORT = int(os.getenv("PORT", 8080))
RENDER_URL = os.getenv("RENDER_URL", None)
PING_INTERVAL = 240

# ─── BOT CONFIG ──────────────────────────────────────────────────────────────

TOKEN = os.getenv("DISCORD_TOKEN") or input("Enter your Discord user token: ").strip()
PREFIX = "-"

# ─── LOGGING ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("selfbot")

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def is_dm(ctx) -> bool:
    """Check if the command was invoked in a DM or Group DM."""
    return isinstance(ctx.channel, (discord.DMChannel, discord.GroupChannel))

def is_guild(ctx) -> bool:
    """Check if the command was invoked in a guild/server."""
    return ctx.guild is not None


async def resolve_user(ctx, argument: str) -> Optional[discord.User]:
    """
    Resolve a user from a string in ANY context (DM, Group DM, Server).
    Accepts: mention (<@ID>), raw ID, username#discrim, or just username.
    """
    if argument is None:
        return None

    # 1. Try the built-in UserConverter first (handles mentions, IDs, names)
    try:
        converter = UserConverter()
        return await converter.convert(ctx, argument)
    except (commands.UserNotFound, commands.BadArgument):
        pass

    # 2. Try resolving as a raw integer ID
    try:
        uid = int(argument.strip())
        return await bot.fetch_user(uid)
    except (ValueError, discord.NotFound, discord.HTTPException):
        pass

    # 3. Try looking up by name in DMs / Group DMs
    if is_dm(ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            recipient = ctx.channel.recipient
            if recipient and (argument.lower() in recipient.name.lower() or
                              argument.lower() in str(recipient).lower()):
                return recipient
        elif isinstance(ctx.channel, discord.GroupChannel):
            for recipient in ctx.channel.recipients:
                if argument.lower() in recipient.name.lower() or \
                   argument.lower() in str(recipient).lower():
                    return recipient

    return None


def channel_type_str(ctx) -> str:
    """Return a human-readable channel type string."""
    if isinstance(ctx.channel, discord.DMChannel):
        return "DM"
    elif isinstance(ctx.channel, discord.GroupChannel):
        return "Group DM"
    elif ctx.guild:
        return f"Server: {ctx.guild.name}"
    return "Unknown"


# ─── SPICY TEXT DATABASE ─────────────────────────────────────────────────────

SPICY_TEXTS = [
    "Imagine what I'd do to you if we were alone 🔥",
    "You're making this very difficult for me... in more ways than one 😈",
    "I'm not saying I'm obsessed, but I think about you a lot... 🫦",
    "Stop looking at me like that unless you're ready for what happens next 💋",
    "You have no idea what you do to me 🥵",
    "I'd cancel my plans for you. And I never cancel plans. 😏",
    "If you keep being cute, I might have to do something about it 🔞",
    "You're dangerous. You should come with a warning label. 🚨",
    "I'm not blushing. It's just... warm in here. 🫣",
    "Tell me to stop, and I won't. Tell me to keep going, and I won't either. 🤫",
    "I want to feel your skin against mine. Right now. 🥵",
    "Forget dinner. Come here and let me show you what I really want 🍑",
    "The things I'd do to you... Discord would ban me for typing them. 🔞",
    "You'd look better in my bed than in that outfit 😈",
    "I don't share. That includes you. You're mine now. 🖤",
    "Pin me against the wall and show me who I belong to. 🔥",
    "I've been thinking about your lips all day. Let me stop thinking. 💋",
    "Just one night. That's all I'm asking. You won't regret it. 😈",
    "Bite me. Leave a mark. I want everyone to know. 🦷",
    "I'm not usually like this... but for you? I'll make an exception. 🫦",
    "I want you so bad I can barely breathe. Take me. Now. 💦",
    "Spread me open and make me forget my own name. 🍑🔥",
    "Your hands belong on my body. Not anywhere else. Fucking use them. 🔞",
    "Put it in my mouth and watch me take it all. No gag reflex. 😈",
    "I'm wet just thinking about you. Come fix that. 💦",
    "Rough. Hard. Feral. That's how I want you to take me. 🥵",
    "I want to feel you deep inside me until I can't walk straight. 🍆💦",
    "Choke me. Spank me. Own me. I'm yours to break. 🖤🔥",
    "My thighs are already trembling. Don't keep me waiting. 😈💕",
    "Fuck me like you hate me, then hold me like you love me. 🔥🫂",
    "I want your cum dripping down my throat. 👅💦",
    "My bed is empty. My legs are open. You know what to do. 🍑🔥",
    "I'm not wearing anything under this. Come find out. 😏",
    "Eat me out until I scream your name. 👅🌮💦",
    "💣 **BOOM.** Server got fucking obliterated. Cry about it. 🔥",
    "🍑 **This server just got fucked raw. No lube. No mercy.** 😈",
    "🔥 **Razed to the ground. Better luck next time, losers.** 💀",
    "💦 **Nuked so hard even the channels came.** ...and then they died. 🥵",
    "🔞 **Your server? Gone. Your tears? Delicious.** 🧂",
    "🖤 **I don't play fair. I play to win. And I just won.** 💯",
    "💀 **This server got Thanos-snapped. Perfectly balanced.** ✨",
    "🥵 **Admin? I don't need admin. I need a cigarette after that.** 🚬",
    "🎯 **Target acquired. Target eliminated. Moving on.** 💥",
]

SPICY_EMOJIS = [
    "🔥", "💦", "🥵", "😈", "🍑", "🍆", "👅", "🫦", "💋", "🖤",
    "🔞", "💕", "💯", "🎯", "💀", "🚨", "🥴", "🫣", "😏", "💥",
    "✨", "🌮", "🍑", "🦷", "🐉", "🌊", "💜", "❤️‍🔥", "🔥", "💦"
]

def spicy_line():
    return f"{random.choice(SPICY_TEXTS)} {' '.join(random.choices(SPICY_EMOJIS, k=random.randint(1, 3)))}"

def spicy_header():
    return random.choice([
        "**🔥 NUKED BY AUTHORIZED SECURITY TEST 🔥**",
        "**💦 COMPROMISED — NO MERCY 💦**",
        "**😈 PWNED — GET FUCKED 😈**",
        "**🔞 EXPLOITED — CRY MORE 🔞**",
        "**💀 OWNED — SIT DOWN 💀**",
        "**🥵 BREACHED — TOO EASY 🥵**",
    ])

# ─── GIF DATABASE ────────────────────────────────────────────────────────────

FALLBACK_GIFS = {
    "hug":    ["https://i.imgur.com/5qBsLXT.gif", "https://i.imgur.com/r9aU2xv.gif"],
    "kiss":   ["https://i.imgur.com/KLVzr3q.gif", "https://i.imgur.com/fszBfDk.gif"],
    "cuddle": ["https://i.imgur.com/4oBK98N.gif", "https://i.imgur.com/0ttby7k.gif"],
    "pat":    ["https://i.imgur.com/5Ct9Tud.gif", "https://i.imgur.com/6QQVqWZ.gif"],
    "slap":   ["https://i.imgur.com/mJ5e8eP.gif", "https://i.imgur.com/8JF4iRR.gif"],
    "spicy":  ["https://i.imgur.com/kfQ6H15.gif", "https://i.imgur.com/sGVgr74.gif"],
}

API_ENDPOINTS = {
    "hug":    "https://nekos.life/api/v2/img/hug",
    "kiss":   "https://nekos.life/api/v2/img/kiss",
    "cuddle": "https://nekos.life/api/v2/img/cuddle",
    "pat":    "https://nekos.life/api/v2/img/pat",
    "slap":   "https://nekos.life/api/v2/img/slap",
}

async def fetch_gif(action: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_ENDPOINTS.get(action, ""), timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "url" in data:
                        return data["url"]
    except Exception:
        pass
    return random.choice(FALLBACK_GIFS.get(action, FALLBACK_GIFS["hug"]))

# ─── QUESTS API ──────────────────────────────────────────────────────────────

QUEST_API_BASE = "https://discord.com/api/v9"
QUEST_HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

async def _api_request(method: str, path: str, body: dict = None):
    url = f"{QUEST_API_BASE}{path}"
    try:
        async with aiohttp.ClientSession(headers=QUEST_HEADERS) as session:
            async with session.request(method, url, json=body) as resp:
                data = await resp.json() if resp.content_type == "application/json" else {}
                return resp.status, data
    except Exception as e:
        return 0, {"error": str(e)}

# ─── BOT CLIENT ──────────────────────────────────────────────────────────────

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=PREFIX,
    self_bot=True,
    intents=intents,
    help_command=None,
    case_insensitive=True
)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: RENDER HEALTH SERVER
# ═══════════════════════════════════════════════════════════════════════════════

class HealthServer:
    def __init__(self, port: int):
        self.port = port
        self._site = None
        self._runner = None

    async def start(self):
        from aiohttp import web
        app = web.Application()

        async def health(request):
            ch_type = "unknown"
            return web.json_response({
                "status": "alive",
                "user": str(bot.user),
                "servers": len(bot.guilds),
                "commands": len(bot.commands),
                "uptime": datetime.datetime.now().isoformat()
            })

        async def root(request):
            return web.Response(
                text=f"🛠️ Self-Bot: {bot.user} | {len(bot.commands)} cmds | DM+Groups+Servers\n",
                content_type="text/plain"
            )

        app.router.add_get("/", root)
        app.router.add_get("/health", health)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await self._site.start()
        log.info(f"🌐 Health server on 0.0.0.0:{self.port}")

    async def stop(self):
        if self._site: await self._site.stop()
        if self._runner: await self._runner.cleanup()


async def self_ping():
    if not RENDER_URL:
        log.info("📡 No RENDER_URL — use UptimeRobot to keep alive")
        return
    log.info(f"📡 Self-ping → {RENDER_URL}/health every {PING_INTERVAL}s")
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{RENDER_URL}/health", timeout=10) as resp:
                    log.debug(f"📡 Self-ping: HTTP {resp.status}")
        except Exception as e:
            log.debug(f"📡 Self-ping failed: {e}")
        await asyncio.sleep(PING_INTERVAL)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    log.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    log.info(f"📡 {len(bot.guilds)} servers | 👥 {sum(g.member_count for g in bot.guilds)} users")
    log.info(f"⚡ Prefix: {PREFIX}  |  Commands: {len(bot.commands)} loaded")
    log.info(f"🌐 DM/Group DM/Server: ALL CHANNELS SUPPORTED")
    log.info(f"🌐 Render health port: {RENDER_PORT}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{PREFIX}help | DM & groups OK"
        )
    )

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: GIF / INTERACTION COMMANDS — WORKS IN DM, GROUP DM, SERVERS
# ═══════════════════════════════════════════════════════════════════════════════

INTERACTION_COLORS = {
    "hug": 0xFF69B4, "kiss": 0xFF1493, "cuddle": 0x9370DB,
    "pat": 0x98FB98, "slap": 0xFF4500,
}
INTERACTION_VERBS = {
    "hug": ("hugs", "🤗"), "kiss": ("kisses", "💋"),
    "cuddle": ("cuddles", "🥰"), "pat": ("pats", "🐱"),
    "slap": ("slaps", "👋"),
}

async def _interaction_cmd(ctx, action: str, target: Optional[discord.User] = None):
    """Generic GIF interaction — works in DM, Group DM, and Servers."""
    target = target or ctx.author
    verb, emoji = INTERACTION_VERBS[action]
    gif_url = await fetch_gif(action)
    embed = discord.Embed(
        description=f"**{ctx.author.display_name}** {verb} **{target.display_name}** {emoji}",
        color=INTERACTION_COLORS.get(action, 0x5865F2)
    )
    embed.set_image(url=gif_url)
    await ctx.send(embed=embed)


@bot.command(name="hug")
async def hug(ctx, *, target: str = None):
    """Hug someone — works in DM, Group DM, and Servers. Usage: -hug @user"""
    user = await resolve_user(ctx, target) if target else None
    await _interaction_cmd(ctx, "hug", user)

@bot.command(name="kiss")
async def kiss(ctx, *, target: str = None):
    """Kiss someone — works anywhere. Usage: -kiss @user"""
    user = await resolve_user(ctx, target) if target else None
    await _interaction_cmd(ctx, "kiss", user)

@bot.command(name="cuddle")
async def cuddle(ctx, *, target: str = None):
    """Cuddle someone — works anywhere. Usage: -cuddle @user"""
    user = await resolve_user(ctx, target) if target else None
    await _interaction_cmd(ctx, "cuddle", user)

@bot.command(name="pat")
async def pat(ctx, *, target: str = None):
    """Pat someone — works anywhere. Usage: -pat @user"""
    user = await resolve_user(ctx, target) if target else None
    await _interaction_cmd(ctx, "pat", user)

@bot.command(name="slap")
async def slap(ctx, *, target: str = None):
    """Slap someone — works anywhere. Usage: -slap @user"""
    user = await resolve_user(ctx, target) if target else None
    await _interaction_cmd(ctx, "slap", user)

@bot.command(name="spicy")
async def spicy_gif(ctx, *, target: str = None):
    """Send a spicy GIF — works anywhere. Usage: -spicy @user"""
    user = await resolve_user(ctx, target) if target else ctx.author
    gif_url = await fetch_gif("spicy")
    embed = discord.Embed(
        description=f"**{ctx.author.display_name}** sends spicy energy to **{user.display_name}** 🔥💦",
        color=0xFF0044
    )
    embed.set_image(url=gif_url)
    await ctx.send(embed=embed)
    await ctx.send(f"*{random.choice(SPICY_TEXTS)}* {' '.join(random.choices(SPICY_EMOJIS, k=2))}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: NUKE / SPAM / VOLATILE — Some guild-only, some DM-compatible
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="nuke")
@commands.cooldown(1, 60, commands.BucketType.guild)
async def nuke(ctx, *, reason: str = None):
    """💣 SERVER ONLY: Delete ALL channels. Type -confirm_nuke_yes to confirm."""
    if not is_guild(ctx):
        return await ctx.send("❌ `-nuke` only works in servers, not DMs.")

    await ctx.send(
        f"⚠️ **WARNING:** This will delete ALL channels in **{ctx.guild.name}**!\n"
        f"Type `{PREFIX}confirm_nuke_yes` within 15s to confirm."
    )

    def check(m):
        return m.author == ctx.author and m.content == f"{PREFIX}confirm_nuke_yes"

    try:
        await bot.wait_for("message", timeout=15.0, check=check)
    except asyncio.TimeoutError:
        return await ctx.send("❌ Nuke cancelled (timeout).")

    await ctx.send(f"{spicy_header()}\n{spicy_line()}")

    deleted, failed = 0, 0
    for channel in list(ctx.guild.channels):
        try:
            await channel.delete()
            deleted += 1
            await asyncio.sleep(1.0)
        except discord.Forbidden:
            failed += 1
        except discord.HTTPException:
            failed += 1
            await asyncio.sleep(3)

    try:
        report = await ctx.guild.create_text_channel("nuked-by-selfbot")
        await report.send(
            f"{spicy_header()}\n"
            f"💣 **Nuke Complete**\n"
            f"❌ Deleted: `{deleted}` channels\n"
            f"⚠️ Failed: `{failed}`\n"
            f"{spicy_line()}"
        )
    except Exception:
        pass
    log.info(f"Nuked {ctx.guild.name}: {deleted} deleted, {failed} failed")

@bot.command(name="confirm_nuke_yes")
async def confirm_nuke_noop(ctx):
    pass

@bot.command(name="spam")
@commands.cooldown(1, 30, commands.BucketType.channel)
async def spam(ctx, count: int = 5, *, message: str = None):
    """
    💬 Spam a message — WORKS IN DM, GROUP DM, AND SERVERS.
    Usage: -spam 10 Hello there (max 50, cooldown 30s)
    """
    count = min(count, 50)
    if count < 1:
        return await ctx.send("❌ Count must be >= 1", delete_after=5)
    if not message:
        message = f"{spicy_header()}\n{spicy_line()}"

    await ctx.send(f"💬 Spamming `{count}` messages...", delete_after=3)
    sent = 0
    for i in range(count):
        try:
            msg = message if i % 5 != 0 else f"{message}\n{spicy_line()}"
            await ctx.send(msg)
            sent += 1
            await asyncio.sleep(1.0)
        except discord.HTTPException:
            await asyncio.sleep(5)
    await ctx.send(f"✅ Sent `{sent}/{count}` messages", delete_after=5)

@bot.command(name="spicyspam")
@commands.cooldown(1, 60, commands.BucketType.channel)
async def spicy_spam(ctx, count: int = 5):
    """
    🌶️ Spicy text spam — WORKS IN DM, GROUP DM, AND SERVERS.
    Usage: -spicyspam 10 (max 30)
    """
    count = min(count, 30)
    await ctx.send(f"🌶️ Spamming `{count}` spicy messages...", delete_after=3)

    sent = 0
    for i in range(count):
        try:
            await ctx.send(
                f"{spicy_header()}\n{spicy_line()}\n"
                f"{' '.join(random.choices(SPICY_EMOJIS, k=3))}"
            )
            sent += 1
            await asyncio.sleep(1.5)
        except discord.HTTPException:
            await asyncio.sleep(5)
    await ctx.send(f"✅ Sent `{sent}` spicy messages 🔥", delete_after=5)

@bot.command(name="purge")
@commands.cooldown(1, 10, commands.BucketType.channel)
async def purge(ctx, amount: int = 20):
    """
    🗑️ Bulk delete messages — WORKS IN DM, GROUP DM, AND SERVERS.
    Usage: -purge 50 (max 100)
    """
    amount = min(amount, 100)
    try:
        deleted = await ctx.purge(limit=amount + 1)
        actual = len(deleted) - 1
        await ctx.send(f"🗑️ Purged `{actual}` messages ✅", delete_after=5)
    except discord.Forbidden:
        await ctx.send("❌ Can't delete messages here (no permissions).")
    except Exception as e:
        await ctx.send(f"❌ Purge failed: {e}")

@bot.command(name="massdm")
@commands.cooldown(1, 300, commands.BucketType.guild)
async def massdm(ctx, *, message: str = None):
    """📨 SERVER ONLY: DM all members in the current server."""
    if not is_guild(ctx):
        return await ctx.send("❌ `-massdm` only works in servers, not DMs.")

    msg = message or f"📢 Security test from {ctx.author}.\n{spicy_line()}"
    members = [m for m in ctx.guild.members if not m.bot and m != bot.user]
    await ctx.send(f"📨 DMing **{len(members)}** members...", delete_after=5)

    sent, failed = 0, 0
    for member in members:
        try:
            await member.send(msg)
            sent += 1
            await asyncio.sleep(2)
        except (discord.Forbidden, discord.HTTPException):
            failed += 1
    log.info(f"MassDM: {sent} sent, {failed} failed in {ctx.guild.name}")

@bot.command(name="strip")
@commands.cooldown(1, 120, commands.BucketType.guild)
async def strip(ctx):
    """🔻 SERVER ONLY: Delete all removable roles."""
    if not is_guild(ctx):
        return await ctx.send("❌ `-strip` only works in servers, not DMs.")

    await ctx.send("⚠️ Deleting all removable roles...", delete_after=5)
    deleted = 0
    for role in reversed(ctx.guild.roles):
        if role.is_default() or role.is_premium_subscriber():
            continue
        try:
            await role.delete()
            deleted += 1
            await asyncio.sleep(1.5)
        except (discord.Forbidden, discord.HTTPException):
            pass
    await ctx.send(f"✅ Deleted `{deleted}` roles", delete_after=5)

@bot.command(name="renameall")
@commands.cooldown(1, 120, commands.BucketType.guild)
async def rename_all(ctx, *, new_name: str = "Nuked-by-SelfBot"):
    """🔄 SERVER ONLY: Rename all channels."""
    if not is_guild(ctx):
        return await ctx.send("❌ `-renameall` only works in servers, not DMs.")

    await ctx.send(f"🔄 Renaming channels to `{new_name}`...", delete_after=5)
    renamed = 0
    for channel in ctx.guild.channels:
        try:
            await channel.edit(name=new_name[:100].lower().replace(" ", "-"))
            renamed += 1
            await asyncio.sleep(1)
        except (discord.Forbidden, discord.HTTPException):
            pass
    await ctx.send(f"✅ Renamed `{renamed}` channels", delete_after=5)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: RICH PRESENCE — Works everywhere
# ═══════════════════════════════════════════════════════════════════════════════

_presence_cycle_active = True

ROTATING_PRESENCES = [
    {"type": discord.ActivityType.playing,     "name": "Security Assessment"},
    {"type": discord.ActivityType.watching,    "name": "over network traffic"},
    {"type": discord.ActivityType.listening,   "name": "to packet captures"},
    {"type": discord.ActivityType.competing,   "name": "in a CTF"},
    {"type": discord.ActivityType.streaming,   "name": "Penetration Testing"},
]

PRESENCE_TYPE_MAP = {
    "playing": discord.ActivityType.playing,
    "watching": discord.ActivityType.watching,
    "listening": discord.ActivityType.listening,
    "streaming": discord.ActivityType.streaming,
    "competing": discord.ActivityType.competing,
}

STATUS_MAP = {
    "online": discord.Status.online, "idle": discord.Status.idle,
    "dnd": discord.Status.dnd, "donotdisturb": discord.Status.dnd,
    "invisible": discord.Status.invisible, "offline": discord.Status.invisible,
}

@tasks.loop(seconds=30)
async def presence_cycle():
    if not _presence_cycle_active: return
    status = random.choice(ROTATING_PRESENCES)
    activity = discord.Activity(type=status["type"], name=status["name"])
    await bot.change_presence(activity=activity)

@presence_cycle.before_loop
async def before_presence_cycle():
    await bot.wait_until_ready()

@bot.command(name="setrpc")
async def set_rpc(ctx, status_type: str = None, *, status_name: str = None):
    """
    🎮 Set custom Rich Presence — WORKS ANYWHERE.
    Types: playing, watching, listening, streaming, competing
    Usage: -setrpc playing "Minecraft"
           -setrpc reset   (back to rotating)
    """
    global _presence_cycle_active

    if status_type is None or status_type.lower() == "reset":
        _presence_cycle_active = True
        presence_cycle.start()
        return await ctx.send("🔄 RPC reset to rotating cycle", delete_after=5)

    act_type = PRESENCE_TYPE_MAP.get(status_type.lower())
    if not act_type:
        return await ctx.send(
            f"❌ Invalid type. Options: {', '.join(PRESENCE_TYPE_MAP.keys())}", delete_after=5)
    if not status_name:
        return await ctx.send("❌ Provide a name. Usage: `-setrpc playing \"Minecraft\"`", delete_after=5)

    _presence_cycle_active = False
    presence_cycle.stop()
    activity = discord.Activity(type=act_type, name=status_name)
    await bot.change_presence(activity=activity)
    await ctx.send(f"✅ RPC set to **{status_type}**: `{status_name}`", delete_after=5)

@bot.command(name="setstatus")
async def set_status(ctx, status: str = "online"):
    """📡 Change status — WORKS ANYWHERE. Options: online, idle, dnd, invisible"""
    new_status = STATUS_MAP.get(status.lower())
    if not new_status:
        return await ctx.send("❌ Options: online, idle, dnd, invisible", delete_after=5)
    await bot.change_presence(status=new_status)
    await ctx.send(f"✅ Status changed to **{status.lower()}**", delete_after=5)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: QUEST AUTO-COMPLETE — Works anywhere
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="quests")
async def list_quests(ctx):
    """📋 List your Discord quests — WORKS ANYWHERE."""
    status, data = await _api_request("GET", "/users/@me/quests")
    if status != 200:
        return await ctx.send(f"❌ Failed to fetch quests (HTTP {status})")
    quests = data.get("quests", [])
    if not quests:
        return await ctx.send("📋 No active quests found.")
    embed = discord.Embed(
        title="📋 Your Discord Quests",
        color=0x5865F2,
        description=f"Found **{len(quests)}** quest(s)"
    )
    for q in quests:
        name = q.get("questName", q.get("id", "Unknown"))
        s = "✅ Completed" if q.get("completedAt") else "⏳ In Progress"
        embed.add_field(name=name, value=s, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="autoquest")
@commands.cooldown(1, 300, commands.BucketType.user)
async def auto_quest(ctx):
    """🎮 Auto-complete pending Discord quests — WORKS ANYWHERE. Cooldown: 300s."""
    await ctx.send("🎮 **Quest Auto-Completer** — Fetching quests...", delete_after=5)

    status, data = await _api_request("GET", "/users/@me/quests")
    if status != 200:
        return await ctx.send(f"❌ API error: HTTP {status}")

    quests = data.get("quests", [])
    active = [q for q in quests if not q.get("completedAt")]
    if not active:
        return await ctx.send("📋 No pending quests. Accept some in Discord's Quests tab!")

    await ctx.send(f"🎯 Working on **{len(active)}** quest(s)...", delete_after=5)

    completed, failed = 0, 0
    for quest in active:
        qid = quest["id"]
        qname = quest.get("questName", qid[:10])
        log.info(f"Processing quest: {qname}")

        await _api_request("POST", f"/quests/{qid}/enroll")
        await asyncio.sleep(1)

        for i in range(3):
            ts = int(datetime.datetime.now().timestamp() * 1000)
            await _api_request("POST", f"/quests/{qid}/video-progress", {"timestamp": ts})
            await asyncio.sleep(1.5)

        for i in range(3):
            await _api_request("POST", f"/quests/{qid}/heartbeat", {"stream_key": None, "terminal": False})
            await asyncio.sleep(1.5)

        s, _ = await _api_request("POST", f"/quests/{qid}/claim")
        if s in (200, 201):
            completed += 1
            await ctx.send(f"✅ **{qname}** — Completed!", delete_after=5)
        else:
            s2, _ = await _api_request("POST", f"/quests/{qid}/claim")
            if s2 in (200, 201):
                completed += 1
                await ctx.send(f"✅ **{qname}** — Completed!", delete_after=5)
            else:
                failed += 1
                await ctx.send(f"⚠️ **{qname}** — Claim failed (HTTP {s})", delete_after=5)
        await asyncio.sleep(2)

    embed = discord.Embed(
        title="🎮 Quest Results",
        color=0x00FF00 if failed == 0 else 0xFFA500,
        description=f"✅ {completed} completed\n❌ {failed} failed\n📋 {len(active)} total"
    )
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: UTILITY COMMANDS — All work everywhere
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="help")
async def help_command(ctx, *, category: str = None):
    """📚 Show help — WORKS ANYWHERE. Categories: gif, nuke, rpc, quest, utility, all"""
    embed = discord.Embed(
        title=f"🛠️ Self-Bot — `{PREFIX}` prefix",
        color=0x5865F2,
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(text=f"{len(bot.commands)} commands | DM ✓ Groups ✓ Servers ✓")

    cat = (category or "all").lower()

    if cat in ("gif", "gifs", "interaction", "all"):
        embed.add_field(
            name="🤗 **Interaction / GIF**  ✅ DM ✓ Group ✓ Server",
            value=(
                f"`{PREFIX}hug @user` — Hug someone\n"
                f"`{PREFIX}kiss @user` — Kiss someone\n"
                f"`{PREFIX}cuddle @user` — Cuddle someone\n"
                f"`{PREFIX}pat @user` — Pat someone\n"
                f"`{PREFIX}slap @user` — Slap someone\n"
                f"`{PREFIX}spicy @user` — Spicy GIF 🔥\n"
            ),
            inline=False
        )

    if cat in ("nuke", "volatile", "spam", "destructive", "all"):
        embed.add_field(
            name="💣 **Volatile / Nuke**",
            value=(
                f"`{PREFIX}nuke` — 🔒 SERVER ONLY — Delete all channels\n"
                f"`{PREFIX}spam <n> <msg>` — ✅ DM/Group/Server (max 50)\n"
                f"`{PREFIX}spicyspam <n>` — ✅ DM/Group/Server (max 30)\n"
                f"`{PREFIX}purge <n>` — ✅ DM/Group/Server (max 100)\n"
                f"`{PREFIX}massdm <msg>` — 🔒 SERVER ONLY\n"
                f"`{PREFIX}strip` — 🔒 SERVER ONLY — Delete roles\n"
                f"`{PREFIX}renameall <n>` — 🔒 SERVER ONLY\n"
            ),
            inline=False
        )

    if cat in ("rpc", "presence", "status", "all"):
        embed.add_field(
            name="🎮 **Rich Presence**  ✅ DM ✓ Group ✓ Server",
            value=(
                f"`{PREFIX}setrpc <type> \"<name>\"` — Custom RPC\n"
                f"  Types: {', '.join(PRESENCE_TYPE_MAP.keys())}\n"
                f"`{PREFIX}setrpc reset` — Resume rotating cycle\n"
                f"`{PREFIX}setstatus <mode>` — online, idle, dnd, invisible\n"
            ),
            inline=False
        )

    if cat in ("quest", "quests", "all"):
        embed.add_field(
            name="🎯 **Quests**  ✅ DM ✓ Group ✓ Server",
            value=(
                f"`{PREFIX}quests` — List your active quests\n"
                f"`{PREFIX}autoquest` — Auto-complete all pending quests\n"
            ),
            inline=False
        )

    if cat in ("utility", "info", "misc", "all"):
        embed.add_field(
            name="🔧 **Utility / Info**  ✅ DM ✓ Group ✓ Server",
            value=(
                f"`{PREFIX}help [category]` — This menu\n"
                f"`{PREFIX}ping` — Latency\n"
                f"`{PREFIX}info` — Account & system info\n"
                f"`{PREFIX}servers` — List all servers\n"
                f"`{PREFIX}whois @user/ID/name` — User info\n"
                f"`{PREFIX}avatar @user/ID/name` — Get avatar\n"
                f"`{PREFIX}typing <sec>` — Typing indicator\n"
                f"`{PREFIX}say <msg>` — Say something\n"
                f"`{PREFIX}edit <new>` — Edit your last message\n"
                f"`{PREFIX}stats` — Session stats\n"
                f"`{PREFIX}spicytxt [n]` — Generate spicy text\n"
                f"`{PREFIX}chtype` — Show current channel type\n"
            ),
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    """🏓 Check latency — WORKS ANYWHERE."""
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command(name="info")
async def info(ctx):
    """ℹ️ Account info — WORKS ANYWHERE."""
    embed = discord.Embed(title="ℹ️ Self-Bot Info", color=0x5865F2)
    embed.add_field(name="👤 Account", value=f"{bot.user} (`{bot.user.id}`)", inline=False)
    embed.add_field(name="📡 Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="⚡ Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="🐍 Python", value=sys.version.split()[0], inline=True)
    embed.add_field(name="💻 Platform", value=platform.system(), inline=True)
    embed.add_field(name="📚 Library", value="discord.py-self", inline=True)
    embed.add_field(name="📋 Commands", value=len(bot.commands), inline=True)
    embed.add_field(name="📍 Channel", value=channel_type_str(ctx), inline=True)
    embed.add_field(name="☁️ Host", value="Render", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="servers")
async def servers_list(ctx):
    """📋 List servers — WORKS ANYWHERE."""
    guilds = sorted(bot.guilds, key=lambda g: g.member_count, reverse=True)
    lines = [f"**{i+1}.** {g.name} — `{g.id}` — `{g.member_count}` mem" for i, g in enumerate(guilds)]
    for i in range(0, len(lines), 10):
        embed = discord.Embed(
            title=f"📋 Servers ({len(guilds)})",
            description="\n".join(lines[i:i+10]),
            color=0x5865F2
        )
        await ctx.send(embed=embed)

@bot.command(name="whois")
async def whois(ctx, *, target: str = None):
    """
    🔍 User info — WORKS ANYWHERE.
    Accepts: @mention, user ID, username, or nothing (shows you)
    """
    user = await resolve_user(ctx, target) if target else ctx.author
    if not user:
        return await ctx.send("❌ Couldn't find that user.", delete_after=10)

    created = discord.utils.format_dt(user.created_at, style="R")
    embed = discord.Embed(title=str(user), color=user.accent_color or 0x5865F2)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="🆔 ID", value=user.id, inline=True)
    embed.add_field(name="🤖 Bot", value="✅ Yes" if user.bot else "❌ No", inline=True)
    embed.add_field(name="📅 Created", value=created, inline=True)
    if user.banner:
        embed.set_image(url=user.banner.url)
    await ctx.send(embed=embed)

@bot.command(name="avatar")
async def avatar(ctx, *, target: str = None):
    """🖼️ Get avatar — WORKS ANYWHERE. Accepts @mention, ID, or username."""
    user = await resolve_user(ctx, target) if target else ctx.author
    if not user:
        return await ctx.send("❌ Couldn't find that user.", delete_after=5)
    embed = discord.Embed(title=f"{user}'s Avatar", color=user.accent_color or 0x5865F2)
    embed.set_image(url=user.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="typing")
async def typing_indicator(ctx, seconds: int = 5):
    """⌨️ Show typing — WORKS ANYWHERE. Usage: -typing 10 (max 30s)"""
    seconds = min(seconds, 30)
    async with ctx.typing():
        await asyncio.sleep(seconds)
    await ctx.send(f"⌨️ Typed for {seconds}s", delete_after=3)

@bot.command(name="say")
async def say(ctx, *, message: str):
    """💬 Say something — WORKS ANYWHERE."""
    await ctx.send(message)

@bot.command(name="edit")
async def edit_message(ctx, *, new_content: str):
    """✏️ Edit your last message — WORKS ANYWHERE."""
    async for msg in ctx.channel.history(limit=5):
        if msg.author == bot.user and msg.id != ctx.message.id:
            try:
                await msg.edit(content=new_content)
                return await ctx.send("✅ Edited", delete_after=3)
            except discord.HTTPException as e:
                return await ctx.send(f"❌ {e}", delete_after=5)

@bot.command(name="stats")
async def stats(ctx):
    """📊 Session stats — WORKS ANYWHERE."""
    embed = discord.Embed(title="📊 Self-Bot Statistics", color=0x5865F2)
    embed.add_field(name="📡 Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="👥 Total Users", value=f"{sum(g.member_count for g in bot.guilds):,}", inline=True)
    embed.add_field(name="📊 Total Channels", value=sum(len(g.channels) for g in bot.guilds), inline=True)
    embed.add_field(name="⚡ Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="📋 Commands", value=len(bot.commands), inline=True)
    embed.add_field(name="📍 Here", value=channel_type_str(ctx), inline=True)
    embed.add_field(name="💾 Python", value=sys.version.split()[0], inline=True)
    await ctx.send(embed=embed)

@bot.command(name="spicytxt")
async def spicy_text(ctx, count: int = 1):
    """🌶️ Generate spicy text — WORKS ANYWHERE. Usage: -spicytxt 5"""
    count = min(count, 10)
    lines = [spicy_line() for _ in range(count)]
    await ctx.send("\n\n".join(lines))

@bot.command(name="chtype")
async def channel_type(ctx):
    """📍 Show current channel type — WORKS ANYWHERE."""
    await ctx.send(
        f"📍 **Channel Type:** {channel_type_str(ctx)}\n"
        f"👤 **Author:** {ctx.author}\n"
        f"🆔 **Channel ID:** `{ctx.channel.id}`"
    )

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"⏳ **Cooldown** — Try again in `{error.retry_after:.0f}s`",
            delete_after=10
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❌ **Missing argument.**\nUsage: `{PREFIX}{ctx.command.name} {ctx.command.signature}`",
            delete_after=10
        )
    elif isinstance(error, commands.BadArgument):
        await ctx.send(
            f"❌ **Invalid argument.**\nCheck `{PREFIX}help {ctx.command.name}` for usage.",
            delete_after=10
        )
    elif isinstance(error, commands.CommandNotFound):
        pass  # silent
    else:
        log.error(f"Error in {ctx.command}: {error}")
        await ctx.send(f"❌ **Error:** `{error}`", delete_after=10)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9: MAIN
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    print(r"""
╔══════════════════════════════════════════════════════╗
║     ███████╗███████╗██╗     ██████╗  ██████╗ ████████╗
║     ██╔════╝██╔════╝██║     ██╔══██╗██╔═══██╗╚══██╔══╝
║     ███████╗█████╗  ██║     ██████╔╝██║   ██║   ██║
║     ╚════██║██╔══╝  ██║     ██╔══██╗██║   ██║   ██║
║     ███████║███████╗███████╗██████╔╝╚██████╔╝   ██║
║     ╚══════╝╚══════╝╚══════╝╚═════╝  ╚═════╝    ╚═╝
║        v4.0 — DM / Groups / Servers — All Channels
╚══════════════════════════════════════════════════════╝
    """)
    print(f"  🌐 Prefix     : {PREFIX}")
    print(f"  📋 Commands   : {len(bot.commands)} total")
    print(f"  🔥 Spicy      : {len(SPICY_TEXTS)} texts")
    print(f"  🎯 Quests     : Auto-complete enabled")
    print(f"  ✅ DM/Group   : All applicable commands work in DMs & groups")
    print(f"  🏠 Render Port: {RENDER_PORT}")
    print(f"  📡 Self-ping  : {'Enabled → ' + RENDER_URL if RENDER_URL else 'Disabled (use UptimeRobot)'}")
    print()

    health = HealthServer(RENDER_PORT)
    await health.start()

    asyncio.create_task(self_ping())
    presence_cycle.start()

    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        await health.stop()
        await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Exiting.")
