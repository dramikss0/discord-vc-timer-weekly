import discord
from discord.ext import commands
import json
import time
from datetime import datetime
import os

TOKEN = os.getenv("DISCORD_TOKEN")

DATA_FILE = "voice_data.json"

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# --- загрузка / сохранение ---
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_week_key():
    now = datetime.utcnow()
    y, w, _ = now.isocalendar()
    return f"{y}-W{w}"


data = load_data()

# время последнего сброса
RESET_TIME = time.time()


# --- отслеживание голосовых каналов ---
@bot.event
async def on_voice_state_update(member, old_state, new_state):
    now = time.time()

    def process_channel(channel):
        if channel is None:
            return

        members = [m for m in channel.members if not m.bot]

        # 2+ человека → начинаем считать
        if len(members) >= 2:
            for m in members:
                user_id = str(m.id)

                if user_id not in data:
                    data[user_id] = {"weekly": {}, "join_time": None}

                if data[user_id]["join_time"] is None:
                    data[user_id]["join_time"] = now

        # меньше 2 → останавливаем и фиксируем
        else:
            for m in members:
                user_id = str(m.id)

                if user_id in data and data[user_id].get("join_time"):
                    duration = int(now - data[user_id]["join_time"])
                    week = get_week_key()

                    if week not in data[user_id]["weekly"]:
                        data[user_id]["weekly"][week] = 0

                    data[user_id]["weekly"][week] += duration
                    data[user_id]["join_time"] = None

                    save_data()

    process_channel(old_state.channel)
    process_channel(new_state.channel)


# --- команда статистики ---
@bot.command()
async def voicetime(ctx):
    week = get_week_key()
    now = time.time()

    results = []

    for user_id, user_data in data.items():
        seconds = user_data.get("weekly", {}).get(week, 0)

        # 🔥 учитываем текущее время ТОЛЬКО если человек реально в голосе
        if user_data.get("join_time"):
            member = ctx.guild.get_member(int(user_id))

            if member and member.voice and member.voice.channel:
                channel = member.voice.channel
                members = [m for m in channel.members if not m.bot]

                if len(members) >= 2:
                    start = max(user_data["join_time"], RESET_TIME)
                    seconds += int(now - start)

        # ❌ убираем нули
        if seconds <= 0:
            continue

        results.append((user_id, seconds))

    if not results:
        await ctx.send("Нет данных")
        return

    # сортировка
    results.sort(key=lambda x: x[1], reverse=True)

    lines = []

    for i, (user_id, seconds) in enumerate(results, start=1):
        member = ctx.guild.get_member(int(user_id))

        if member:
            name = member.display_name
        else:
            try:
                user = await bot.fetch_user(int(user_id))
                name = user.name
            except:
                name = f"User {user_id}"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60

        lines.append(f"{i}. {name} — {hours}ч {minutes}м")

    await ctx.send("\n".join(lines[:20]))


# --- сброс статистики ---
@bot.command()
@commands.has_permissions(administrator=True)
async def resetvoice(ctx):
    global RESET_TIME

    RESET_TIME = time.time()

    week = get_week_key()

    for user_id in data:
        data[user_id]["weekly"][week] = 0

    save_data()

    await ctx.send("Статистика за текущую неделю сброшена")


# --- запуск ---
bot.run(TOKEN)
