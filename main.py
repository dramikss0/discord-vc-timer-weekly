import discord
from discord.ext import commands
import json
import time
from datetime import datetime

import os
TOKEN = os.getenv("TOKEN")
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


# --- отслеживание голоса ---
@bot.event
async def on_voice_state_update(member, old_state, new_state):
    user_id = str(member.id)

    if user_id not in data:
        data[user_id] = {"weekly": {}, "join_time": None}

    # ЗАШЁЛ в голос
    if old_state.channel is None and new_state.channel is not None:
        data[user_id]["join_time"] = time.time()

    # ВЫШЕЛ из голоса
    elif old_state.channel is not None and new_state.channel is None:
        join_time = data[user_id]["join_time"]

        if join_time:
            duration = int(time.time() - join_time)
            week = get_week_key()

            if week not in data[user_id]["weekly"]:
                data[user_id]["weekly"][week] = 0

            data[user_id]["weekly"][week] += duration
            data[user_id]["join_time"] = None

            save_data()


# --- команда ---
@bot.command()
async def voicetime(ctx):
    week = get_week_key()

    results = []

    for user_id, user_data in data.items():
        seconds = user_data.get("weekly", {}).get(week, 0)

        # если сейчас в голосе — добавляем текущее время
        if user_data.get("join_time"):
            seconds += int(time.time() - user_data["join_time"])

        if seconds > 0:
            results.append((user_id, seconds))

    if not results:
        await ctx.send("Нет данных")
        return

    # сортировка по убыванию
    results.sort(key=lambda x: x[1], reverse=True)

    lines = []

    for i, (user_id, seconds) in enumerate(results, start=1):
        member = ctx.guild.get_member(int(user_id))

        if member:
            name = member.display_name
        else:
            user = await bot.fetch_user(int(user_id))
            name = user.name if user else f"User {user_id}"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60

        lines.append(f"{i}. {name} — {hours}ч {minutes}м")

    # Discord ограничение ~2000 символов
    message = "\n".join(lines[:20])

    await ctx.send(message)


# --- запуск ---
bot.run(TOKEN)
