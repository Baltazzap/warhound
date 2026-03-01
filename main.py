import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput, Select
import asyncio
import os
import json
import aiohttp
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Загрузка токена из .env файла
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    print("❌ Ошибка: Токен не найден! Создайте файл .env с переменной DISCORD_TOKEN")
    exit()

# Настройка интентов
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
tree = bot.tree

# --- НАСТРОЙКИ (ВАШИ ID) ---
WELCOME_CHANNEL_ID = 1477296089882427493
NEWBIE_ROLE_ID = 1477340663342301326
VERIFIED_ROLE_ID = 1477003764576817296
VOICE_TEMPLATE_CHANNEL_ID = 1477361557792100363
VOICE_CATEGORY_ID = 1477361244729114646
TICKET_CATEGORY_ID = 1477004522617311242
SCHEDULE_CHANNEL_ID = 1477003982919700553
PHOTO_CONTEST_CHANNEL_ID = 1477003982919700553
ETS2_SERVER_IP = "127.0.0.1"
ETS2_SERVER_PORT = 27015

# --- JSON ФАЙЛЫ ---
BIRTHDAYS_FILE = "birthdays.json"
SCHEDULES_FILE = "schedules.json"
TICKETS_FILE = "tickets.json"
CONTESTS_FILE = "contests.json"
LEVELS_FILE = "levels.json"
VOICE_ACTIVITY_FILE = "voice_activity.json"

# --- НАСТРОЙКИ УРОВНЕЙ ---
MAX_LEVEL = 150
XP_PER_MESSAGE = 15
XP_PER_10MIN_VOICE = 100
MESSAGE_COOLDOWN = 60

# Словари для отслеживания
user_channels = {}
message_cooldowns = {}
voice_activity = {}


# ============================================
# 📁 ФУНКЦИИ ДЛЯ РАБОТЫ С JSON
# ============================================
def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_levels():
    return load_json(LEVELS_FILE)

def save_levels(data):
    save_json(LEVELS_FILE, data)

def load_voice_activity():
    return load_json(VOICE_ACTIVITY_FILE)

def save_voice_activity(data):
    save_json(VOICE_ACTIVITY_FILE, data)

def get_xp_for_level(level):
    return int(level ** 2 * 100)

def get_total_xp_for_level(level):
    total = 0
    for i in range(1, level + 1):
        total += get_xp_for_level(i)
    return total

def get_level_from_xp(total_xp):
    level = 1
    while get_total_xp_for_level(level) <= total_xp and level < MAX_LEVEL:
        level += 1
    return level

def get_xp_progress(total_xp):
    level = get_level_from_xp(total_xp)
    
    if level >= MAX_LEVEL:
        return MAX_LEVEL, get_total_xp_for_level(MAX_LEVEL), get_total_xp_for_level(MAX_LEVEL), 100
    
    current_level_xp = get_total_xp_for_level(level - 1) if level > 1 else 0
    next_level_xp = get_total_xp_for_level(level)
    progress = total_xp - current_level_xp
    required = next_level_xp - current_level_xp
    percentage = int((progress / required) * 100) if required > 0 else 0
    
    return level, progress, required, percentage

def add_xp(user_id, amount):
    levels = load_levels()
    user_id = str(user_id)
    
    if user_id not in levels:
        levels[user_id] = {"xp": 0, "messages": 0, "voice_minutes": 0, "level": 1}
    
    levels[user_id]["xp"] += amount
    levels[user_id]["level"] = get_level_from_xp(levels[user_id]["xp"])
    
    save_levels(levels)
    return levels[user_id]["level"]


# ============================================
# 🎖️ КОМАНДЫ УРОВНЕЙ (EMBED)
# ============================================
@tree.command(name="level", description="🎖️ Показать свой уровень")
@app_commands.describe(member="Участник для просмотра (по умолчанию - вы)")
async def level(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    
    target = member or interaction.user
    levels = load_levels()
    user_id = str(target.id)
    
    level_data = levels.get(user_id, {"xp": 0, "messages": 0, "voice_minutes": 0, "level": 1})
    
    level = level_data.get("level", 1)
    messages = level_data.get("messages", 0)
    voice_mins = level_data.get("voice_minutes", 0)
    total_xp = level_data.get("xp", 0)
    
    hours = voice_mins // 60
    mins = voice_mins % 60
    
    lvl, progress, required, percentage = get_xp_progress(total_xp)
    
    # Цвет embed по уровню
    if level >= 100:
        color = discord.Color.gold()
        level_emoji = "👑"
    elif level >= 50:
        color = discord.Color.purple()
        level_emoji = "⭐"
    else:
        color = discord.Color.blue()
        level_emoji = "🔹"
    
    embed = discord.Embed(
        title=f"🎖️ Профиль: {target.display_name}",
        description=f"**{level_emoji} Уровень {level} —** {'| МАКСИМАЛЬНЫЙ УРОВЕНЬ!' if level >= MAX_LEVEL else ''}",
        color=color,
        timestamp=discord.utils.utcnow()
    )
    
    # Аватарка
    embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
    
    # Статистика
    embed.add_field(
        name="📊 Статистика",
        value=f"```Сообщений — {messages:,}\n```"
              f"```В голосе — {hours}ч {mins}м\n```"
              f"```Всего XP — {total_xp:,}```",
        inline=False
    )
    
    # Прогресс бар
    if level < MAX_LEVEL:
        bar_length = 10
        filled = int(bar_length * (progress / required))
        empty = bar_length - filled
        progress_bar = "▓" * filled + "░" * empty
        
        embed.add_field(
            name="📈 Прогресс",
            value=f"```[{progress_bar}] {percentage}%```\n"
                  f"**{progress:,}** / **{required:,} XP**",
            inline=False
        )
    else:
        embed.add_field(
            name="📈 Прогресс",
            value=f"```[{'▓' * 10}] 100%```\n"
                  f"**🏆 МАКСИМАЛЬНЫЙ УРОВЕНЬ**",
            inline=False
        )
    
    # Ранг
    all_levels = load_levels()
    sorted_levels = sorted(all_levels.items(), key=lambda x: x[1].get("level", 1), reverse=True)
    user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_levels) if uid == user_id), len(sorted_levels) + 1)
    
    embed.add_field(
        name="🏆 Место в топе",
        value=f"**#{user_rank}** из {len(sorted_levels)} участников",
        inline=False
    )
    
    embed.set_footer(text=f"ID: {target.id} | Warhound Logistics", icon_url=target.avatar.url if target.avatar else None)
    
    await interaction.followup.send(embed=embed)


@tree.command(name="leaderboard", description="🏆 Топ участников по уровням")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    
    levels = load_levels()
    guild = interaction.guild
    
    if not levels:
        await interaction.followup.send("📭 Пока нет данных!", ephemeral=True)
        return
    
    sorted_levels = sorted(levels.items(), key=lambda x: x[1].get("level", 1), reverse=True)[:15]
    
    embed = discord.Embed(
        title="🏆 Топ участников Warhound Logistics",
        description="🎖️ Рейтинг по уровню активности",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    
    for i, (user_id, data) in enumerate(sorted_levels, 1):
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"**{i}.**"
        user = guild.get_member(int(user_id))
        name = user.display_name if user else f"Участник#{user_id[-4:]}"
        
        lvl = data.get("level", 1)
        msgs = data.get("messages", 0)
        voice = data.get("voice_minutes", 0)
        
        level_emoji = "👑" if lvl >= MAX_LEVEL else "⭐" if lvl >= 50 else "🔹"
        
        embed.add_field(
            name=f"{medal} {name}",
            value=f"{level_emoji} **Уровень {lvl}**\n"
                  f"💬 {msgs:,} сообщений\n"
                  f"🎤 {voice} мин в голосе",
            inline=True
        )
    
    embed.set_footer(text="Активность = сообщения + голосовое время")
    
    await interaction.followup.send(embed=embed)


@tree.command(name="progress", description="📊 Быстрый просмотр прогресса")
async def progress(interaction: discord.Interaction):
    await interaction.response.defer()
    
    user_id = str(interaction.user.id)
    levels = load_levels()
    level_data = levels.get(user_id, {"xp": 0, "messages": 0, "voice_minutes": 0, "level": 1})
    
    level = level_data.get("level", 1)
    total_xp = level_data.get("xp", 0)
    messages = level_data.get("messages", 0)
    
    lvl, prog, required, percentage = get_xp_progress(total_xp)
    
    bar_length = 20
    filled = int(bar_length * (percentage / 100))
    empty = bar_length - filled
    progress_bar = "▓" * filled + "░" * empty
    
    embed = discord.Embed(
        title=f"📊 Прогресс: {interaction.user.display_name}",
        description=f"```[{progress_bar}] {percentage}%```",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="Текущий уровень", value=f"**{level}**", inline=True)
    embed.add_field(name="До следующего", value=f"**{required - prog:,} XP**", inline=True)
    embed.add_field(name="Сообщений", value=f"**{messages:,}**", inline=True)
    
    embed.set_footer(text="Продолжайте общаться и будьте в голосе!")
    
    await interaction.followup.send(embed=embed)


@tree.command(name="reset_level", description="🔄 Сбросить уровень участника (админ)")
@app_commands.describe(member="Участник для сброса")
async def reset_level(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Только для администрации!", ephemeral=True)
        return
    
    levels = load_levels()
    user_id = str(member.id)
    
    if user_id in levels:
        del levels[user_id]
        save_levels(levels)
        await interaction.response.send_message(f"✅ Уровень {member.mention} сброшен!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ У пользователя нет данных!", ephemeral=True)


# ============================================
# 📊 ОТСЛЕЖИВАНИЕ АКТИВНОСТИ
# ============================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    user_id = str(message.author.id)
    now = datetime.now().timestamp()
    
    # Проверка кулдауна
    if user_id in message_cooldowns:
        if now - message_cooldowns[user_id] < MESSAGE_COOLDOWN:
            await bot.process_commands(message)
            return
    
    # Начисление XP
    levels = load_levels()
    if user_id not in levels:
        levels[user_id] = {"xp": 0, "messages": 0, "voice_minutes": 0, "level": 1}
    
    levels[user_id]["messages"] += 1
    levels[user_id]["xp"] += XP_PER_MESSAGE
    levels[user_id]["level"] = get_level_from_xp(levels[user_id]["xp"])
    save_levels(levels)
    
    message_cooldowns[user_id] = now
    
    # Проверка повышения уровня
    old_level = levels[user_id]["level"] - 1
    new_level = levels[user_id]["level"]
    
    if new_level > old_level and new_level <= MAX_LEVEL:
        channel = message.channel
        await channel.send(
            f"🎉 **{message.author.mention}** повысил уровень до **{new_level}**! "
            f"{'🏆 МАКСИМАЛЬНЫЙ УРОВЕНЬ!' if new_level == MAX_LEVEL else ''}"
        )
    
    await bot.process_commands(message)


@bot.event
async def on_voice_state_update(member, before, after):
    user_id = str(member.id)
    now = datetime.now()
    guild = member.guild
    
    # Авто-создание голосовых каналов
    if after.channel and after.channel.id == VOICE_TEMPLATE_CHANNEL_ID:
        category = guild.get_channel(VOICE_CATEGORY_ID) if VOICE_CATEGORY_ID else None
        
        try:
            new_channel = await guild.create_voice_channel(
                name=f"🚛 {member.display_name}",
                category=category,
                reason="Авто-создание канала для колонны"
            )
            await member.move_to(new_channel)
            user_channels[member.id] = new_channel.id
        except Exception as e:
            print(f"Ошибка создания канала: {e}")

    # Удаление пустых каналов
    if before.channel and before.channel.id in user_channels.values():
        if len(before.channel.members) == 0:
            try:
                await before.channel.delete(reason="Канал пуст")
                user_ids = [uid for uid, cid in user_channels.items() if cid == before.channel.id]
                for uid in user_ids:
                    del user_channels[uid]
            except Exception as e:
                print(f"Ошибка удаления канала: {e}")
    
    # Отслеживание голосовой активности для XP
    if after.channel and not before.channel:
        voice_activity[user_id] = {
            "start_time": now.timestamp(),
            "last_activity": now.timestamp(),
            "is_speaking": not after.self_mute and not after.self_deaf
        }
    elif not after.channel and before.channel:
        if user_id in voice_activity:
            activity = voice_activity[user_id]
            minutes = int((now.timestamp() - activity["start_time"]) / 60)
            
            if minutes >= 10:
                xp_earned = (minutes // 10) * XP_PER_10MIN_VOICE
                add_xp(user_id, xp_earned)
                
                levels = load_levels()
                if user_id not in levels:
                    levels[user_id] = {"xp": 0, "messages": 0, "voice_minutes": 0, "level": 1}
                levels[user_id]["voice_minutes"] += minutes
                save_levels(levels)
            
            del voice_activity[user_id]
    
    if after.channel and user_id in voice_activity:
        voice_activity[user_id]["last_activity"] = now.timestamp()
        voice_activity[user_id]["is_speaking"] = not after.self_mute and not after.self_deaf


@tasks.loop(minutes=5)
async def check_voice_afk():
    now = datetime.now().timestamp()
    for user_id, activity in list(voice_activity.items()):
        if now - activity["last_activity"] > 300:
            activity["is_speaking"] = False


@check_voice_afk.before_loop
async def before_check_voice_afk():
    await bot.wait_until_ready()


# ============================================
# 🎂 ДНИ РОЖДЕНИЯ
# ============================================
def load_birthdays():
    return load_json(BIRTHDAYS_FILE)

def save_birthdays(data):
    save_json(BIRTHDAYS_FILE, data)

def get_age(birthdate: str) -> int:
    try:
        birth = datetime.strptime(birthdate, "%d.%m.%Y")
        today = datetime.now()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        return age
    except:
        return 0


@tree.command(name="birthday", description="🎂 Установить или посмотреть день рождения")
@app_commands.describe(day="День (1-31)", month="Месяц (1-12)", year="Год (например, 1995)")
async def birthday(interaction: discord.Interaction, day: int = None, month: int = None, year: int = None):
    if day is None or month is None:
        birthdays = load_birthdays()
        user_id = str(interaction.user.id)
        
        if user_id in birthdays:
            bday = birthdays[user_id]
            age = get_age(bday) if len(bday) > 5 else "скрыт"
            embed = discord.Embed(
                title="🎂 Ваш день рождения",
                description=f"📅 **{bday}**\n🎂 Возраст: **{age}** лет",
                color=discord.Color.pink()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="🎂 День рождения не установлен",
                description="Укажите дату: `/birthday day:15 month:6 year:1995`",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if day < 1 or day > 31 or month < 1 or month > 12:
        await interaction.response.send_message("❌ Неверная дата!", ephemeral=True)
        return
    
    birthdate = f"{day:02d}.{month:02d}"
    if year:
        birthdate += f".{year}"
    
    birthdays = load_birthdays()
    birthdays[str(interaction.user.id)] = birthdate
    save_birthdays(birthdays)
    
    await interaction.response.send_message(f"✅ День рождения установлен: **{birthdate}**", ephemeral=True)


@tree.command(name="birthdays", description="📅 Показать все дни рождения")
async def birthdays_list(interaction: discord.Interaction):
    await interaction.response.defer()
    
    birthdays = load_birthdays()
    guild = interaction.guild
    
    if not birthdays:
        await interaction.followup.send("📭 Пока никто не установил день рождения!", ephemeral=True)
        return
    
    sorted_bdays = sorted(birthdays.items(), key=lambda x: x[1][:5])[:20]
    
    embed = discord.Embed(
        title="📅 Дни рождения Warhound Logistics",
        color=discord.Color.pink(),
        timestamp=discord.utils.utcnow()
    )
    
    bday_list = []
    for user_id, bdate in sorted_bdays:
        user = guild.get_member(int(user_id))
        name = user.display_name if user else f"Участник#{user_id[-4:]}"
        bday_list.append(f"• **{name}** — {bdate}")
    
    embed.description = "\n".join(bday_list)
    embed.set_footer(text=f"Всего: {len(birthdays)} участников")
    
    await interaction.followup.send(embed=embed)


@tasks.loop(hours=24)
async def check_birthdays():
    now = datetime.now()
    today = f"{now.day:02d}.{now.month:02d}"
    birthdays = load_birthdays()
    
    for user_id, bdate in birthdays.items():
        if bdate.startswith(today):
            user = bot.get_user(int(user_id))
            if user:
                channel = bot.get_channel(WELCOME_CHANNEL_ID)
                if channel:
                    age = get_age(bdate)
                    await channel.send(
                        f"🎂🎉 **С ДНЁМ РОЖДЕНИЯ, {user.mention}!** 🎉\n\n"
                        f"🎁 Желаю ровных дорог и полных прицепов!\n"
                        f"🎂 Возраст: **{age}** лет\n"
                        f"🐺 **Беги со стаей**! 🚛⚡"
                    )


@check_birthdays.before_loop
async def before_check_birthdays():
    await bot.wait_until_ready()
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    await asyncio.sleep((midnight - now).total_seconds())


# ============================================
# 🎫 ТИКЕТЫ
# ============================================
def load_tickets():
    return load_json(TICKETS_FILE)

def save_tickets(data):
    save_json(TICKETS_FILE, data)


class TicketSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Выберите тип обращения...",
            options=[
                discord.SelectOption(label="🎮 Игровой вопрос", value="game", emoji="🎮"),
                discord.SelectOption(label="💬 Организационный", value="org", emoji="💬"),
                discord.SelectOption(label="⚠️ Жалоба", value="complaint", emoji="⚠️"),
                discord.SelectOption(label="💡 Предложение", value="suggestion", emoji="💡"),
                discord.SelectOption(label="🤝 Другое", value="other", emoji="🤝"),
            ]
        )
    
    async def callback(self, interaction: discord.Interaction):
        category = interaction.guild.get_channel(TICKET_CATEGORY_ID)
        if not category:
            await interaction.response.send_message("❌ Категория не настроена!", ephemeral=True)
            return
        
        for channel in interaction.guild.text_channels:
            if f"тикет-{interaction.user.name}" in channel.name and channel.category == category:
                await interaction.response.send_message(f"❌ У вас уже есть тикет: {channel.mention}", ephemeral=True)
                return
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        
        channel = await interaction.guild.create_text_channel(
            name=f"тикет-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        
        tickets = load_tickets()
        tickets[str(channel.id)] = {"user_id": str(interaction.user.id), "status": "open"}
        save_tickets(tickets)
        
        embed = discord.Embed(
            title="🎫 Обращение к администрации",
            description=f"Привет, {interaction.user.mention}!\n\n📝 Опишите ваш вопрос.\n\n`!close` - закрыть тикет",
            color=discord.Color.orange()
        )
        
        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Тикет создан: {channel.mention}", ephemeral=True)


@tree.command(name="ticket", description="🎫 Создать обращение")
async def ticket(interaction: discord.Interaction):
    view = View()
    view.add_item(TicketSelect())
    
    embed = discord.Embed(
        title="🎫 Система обращений",
        description="Выберите тип обращения ниже.",
        color=discord.Color.blue()
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.command(name="close")
async def close_ticket(ctx):
    if "тикет-" not in ctx.channel.name:
        await ctx.send("❌ Только для тикетов!", delete_after=5)
        return
    
    tickets = load_tickets()
    if str(ctx.channel.id) in tickets:
        del tickets[str(ctx.channel.id)]
        save_tickets(tickets)
    
    await ctx.send("🔒 Закрывается через 5 сек...")
    await asyncio.sleep(5)
    await ctx.channel.delete()


@bot.command(name="add")
async def add_to_ticket(ctx, member: discord.Member):
    if "тикет-" not in ctx.channel.name:
        await ctx.send("❌ Только для тикетов!", delete_after=5)
        return
    
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
    await ctx.send(f"✅ {member.mention} добавлен в тикет!", delete_after=5)


# ============================================
# 📅 РАСПИСАНИЕ
# ============================================
def load_schedules():
    return load_json(SCHEDULES_FILE)

def save_schedules(data):
    save_json(SCHEDULES_FILE, data)


@tree.command(name="add_schedule", description="📅 Добавить рейс (админ)")
@app_commands.describe(title="Название", start_time="Время (ДД.ММ ЧЧ:ММ)", route="Маршрут", description="Описание")
async def add_schedule(interaction: discord.Interaction, title: str, start_time: str, route: str, description: str = ""):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Только админам!", ephemeral=True)
        return
    
    schedules = load_schedules()
    schedule_id = len(schedules) + 1
    schedules[str(schedule_id)] = {
        "title": title,
        "start_time": start_time,
        "route": route,
        "description": description,
        "organizer_id": str(interaction.user.id)
    }
    save_schedules(schedules)
    
    embed = discord.Embed(
        title="📅 Новый рейс",
        description=f"**{title}**\n{description}\n\n🗓️ {start_time}\n🛣️ {route}",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)
    
    channel = interaction.guild.get_channel(SCHEDULE_CHANNEL_ID)
    if channel:
        await channel.send("🔔 **Новый рейс!**", embed=embed)


@tree.command(name="schedule", description="📅 Показать рейсы")
async def show_schedule(interaction: discord.Interaction):
    await interaction.response.defer()
    
    schedules = load_schedules()
    
    if not schedules:
        await interaction.followup.send("📭 Рейсов нет!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📅 Ближайшие рейсы",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    for sid, data in list(schedules.items())[:5]:
        embed.add_field(
            name=f"🚛 {data['title']}",
            value=f"🗓️ {data['start_time']}\n🛣️ {data['route']}",
            inline=False
        )
    
    await interaction.followup.send(embed=embed)


# ============================================
# 📸 ФОТОКОНКУРСЫ
# ============================================
def load_contests():
    return load_json(CONTESTS_FILE)

def save_contests(data):
    save_json(CONTESTS_FILE, data)


@tree.command(name="create_contest", description="📸 Создать конкурс (админ)")
@app_commands.describe(title="Название", duration_hours="Часов")
async def create_contest(interaction: discord.Interaction, title: str, duration_hours: int = 24):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Только админам!", ephemeral=True)
        return
    
    contests = load_contests()
    contest_id = len(contests) + 1
    contests[str(contest_id)] = {
        "title": title,
        "duration": duration_hours,
        "status": "active"
    }
    save_contests(contests)
    
    embed = discord.Embed(
        title="📸 Новый фотоконкурс!",
        description=f"**{title}**\n\n📷 Присылайте скриншоты!\n⏰ {duration_hours} часов",
        color=discord.Color.pink()
    )
    
    channel = interaction.guild.get_channel(PHOTO_CONTEST_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Конкурс создан!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Канал не найден!", ephemeral=True)


@tree.command(name="end_contest", description="🏆 Завершить конкурс (админ)")
@app_commands.describe(winner="Победитель")
async def end_contest(interaction: discord.Interaction, winner: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Только админам!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🏆 Победитель конкурса!",
        description=f"🎉 {winner.mention} получает звание **Фотограф стаи**!",
        color=discord.Color.gold()
    )
    
    channel = interaction.guild.get_channel(PHOTO_CONTEST_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)
    
    await interaction.response.send_message("✅ Конкурс завершён!", ephemeral=True)


# ============================================
# 🖥️ СТАТУС СЕРВЕРА
# ============================================
@tasks.loop(minutes=5)
async def check_server_status():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.truckyapp.com/v1/servers?vtc=warhound-logistics", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    servers = data.get("data", [])
                    online = sum(1 for s in servers if s.get("players", 0) > 0)
                    
                    if online > 0:
                        await bot.change_presence(activity=discord.Game(name=f"🚛 Сервер онлайн | {online} игроков"))
                    else:
                        await bot.change_presence(activity=discord.Game(name="🌙 Сервер оффлайн"))
    except:
        await bot.change_presence(activity=discord.Game(name="🌙 Статус неизвестен"))


@tree.command(name="server", description="🖥️ Статус сервера")
async def server_status(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🖥️ Статус сервера",
        description="🎮 ETS2 / ATS",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="🌐 IP", value=f"||{ETS2_SERVER_IP}:{ETS2_SERVER_PORT}||", inline=False)
    embed.add_field(name="👥 Статус", value="🟢 Онлайн", inline=True)
    embed.set_footer(text="Проверка каждые 5 минут")
    
    await interaction.response.send_message(embed=embed)


# ============================================
# 📢 SAY COMMAND
# ============================================
class EmbedModal(Modal, title="📝 Создать Embed"):
    title_input = TextInput(label="Заголовок", max_length=256, required=False, default="📢 Объявление")
    description = TextInput(label="Описание", style=discord.TextStyle.long, max_length=4000, required=True)
    color = TextInput(label="Цвет (HEX)", max_length=7, required=False, default="#3498db")

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Только админам!", ephemeral=True)
            return
        
        try:
            color_value = int(self.color.value.replace('#', ''), 16)
        except:
            color_value = discord.Color.random()
        
        embed = discord.Embed(
            title=self.title_input.value,
            description=self.description.value,
            color=color_value,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"От: {interaction.user.display_name}")
        
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Отправлено!", ephemeral=True)


@tree.command(name="say", description="📢 Отправить от бота (админ)")
async def say(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Только админам!", ephemeral=True)
        return
    await interaction.response.send_modal(EmbedModal())


# ============================================
# 🔐 ВЕРИФИКАЦИЯ
# ============================================
class VerifyButton(Button):
    def __init__(self):
        super().__init__(label="✅ Я не робот", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(VERIFIED_ROLE_ID)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                f"{interaction.user.mention}, верификация пройдена! 🐺⚡\n"
                f"📊 Проверьте свой уровень: `/level`",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Роль не найдена!", ephemeral=True)


@tree.command(name="verify", description="🔐 Пройти верификацию")
async def verify(interaction: discord.Interaction):
    view = View()
    view.add_item(VerifyButton())
    
    embed = discord.Embed(
        title="🔐 Верификация",
        description="Нажмите кнопку, чтобы подтвердить, что вы не бот.",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ============================================
# 🎤 ГОЛОСОВЫЕ КАНАЛЫ
# ============================================
@bot.command(name="rename")
async def rename_channel(ctx, *, name: str):
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в ГК!", delete_after=5)
        return
    channel = ctx.author.voice.channel
    if channel.id not in user_channels.values():
        await ctx.send("❌ Не личный канал!", delete_after=5)
        return
    owner = next((uid for uid, cid in user_channels.items() if cid == channel.id), None)
    if owner != ctx.author.id:
        await ctx.send("❌ Вы не владелец!", delete_after=5)
        return
    await channel.edit(name=name)
    await ctx.send(f"✅ Переименован в **{name}**", delete_after=5)


@bot.command(name="limit")
async def limit_channel(ctx, limit: int):
    if not ctx.author.voice or ctx.author.voice.channel.id not in user_channels.values():
        await ctx.send("❌ Вы должны быть в своём канале!", delete_after=5)
        return
    await ctx.author.voice.channel.edit(user_limit=limit)
    await ctx.send(f"✅ Лимит: {limit}", delete_after=5)


@bot.command(name="lock")
async def lock_channel(ctx):
    if not ctx.author.voice or ctx.author.voice.channel.id not in user_channels.values():
        await ctx.send("❌ Вы должны быть в своём канале!", delete_after=5)
        return
    await ctx.author.voice.channel.set_permission(ctx.guild.default_role, connect=False)
    await ctx.send("🔒 Закрыт", delete_after=5)


@bot.command(name="unlock")
async def unlock_channel(ctx):
    if not ctx.author.voice or ctx.author.voice.channel.id not in user_channels.values():
        await ctx.send("❌ Вы должны быть в своём канале!", delete_after=5)
        return
    await ctx.author.voice.channel.set_permission(ctx.guild.default_role, connect=None)
    await ctx.send("🔓 Открыт", delete_after=5)


@bot.command(name="delete")
async def delete_channel(ctx):
    if not ctx.author.voice or ctx.author.voice.channel.id not in user_channels.values():
        await ctx.send("❌ Вы должны быть в своём канале!", delete_after=5)
        return
    await ctx.author.voice.channel.delete()
    await ctx.send("✅ Удалён", delete_after=5)


# ============================================
# 🎲 ДОП. КОМАНДЫ
# ============================================
@tree.command(name="ping", description="🏓 Проверка")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms", ephemeral=True)


@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="📚 Команды Warhound Logistics", color=discord.Color.blue())
    embed.add_field(name="🎖️ Уровни", value="`/level` - Моя карточка\n`/leaderboard` - Топ\n`/progress` - Прогресс", inline=False)
    embed.add_field(name="🔐 Верификация", value="`/verify` - Подтвердить аккаунт", inline=False)
    embed.add_field(name="🎂 Дни рождения", value="`/birthday` - Установить дату\n`/birthdays` - Список ДР", inline=False)
    embed.add_field(name="🎫 Поддержка", value="`/ticket` - Создать тикет", inline=False)
    embed.add_field(name="📅 Рейсы", value="`/schedule` - Рейсы\n`/add_schedule` - Добавить (админ)", inline=False)
    embed.add_field(name="📸 Конкурсы", value="`/create_contest` - Конкурс (админ)\n`/end_contest` - Завершить (админ)", inline=False)
    embed.add_field(name="🖥️ Сервер", value="`/server` - Статус сервера", inline=False)
    embed.add_field(name="📢 Админ", value="`/say` - Отправить embed\n`/reset_level` - Сброс уровня", inline=False)
    embed.add_field(name="🎤 Голосовые", value="`!rename/limit/lock/unlock/delete`", inline=False)
    
    await ctx.send(embed=embed, delete_after=60)


@bot.event
async def on_ready():
    print(f'✅ Бот запущен как {bot.user}')
    print(f'📝 ID: {bot.user.id}')
    
    try:
        synced = await tree.sync()
        print(f'✅ Синхронизировано {len(synced)} команд')
    except Exception as e:
        print(f'❌ Ошибка синхронизации: {e}')
    
    check_birthdays.start()
    check_server_status.start()
    check_voice_afk.start()


@bot.event
async def on_member_join(member):
    guild = member.guild
    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    newbie_role = guild.get_role(NEWBIE_ROLE_ID)
    
    if welcome_channel and newbie_role:
        await member.add_roles(newbie_role)
        
        embed = discord.Embed(
            title="🐺 Добро пожаловать в Warhound Logistics!",
            description=f"Привет, {member.mention}! ⚡\n\nТы вступаешь в компанию дальнобойщиков, где скорость, дисциплина и мощь — закон.",
            color=discord.Color.dark_gray(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="✅ Первые шаги:",
            value="1. `/verify` - верификация\n"
                  "2. Заявка: https://hub.truckyapp.com/vtc/warhound-logistics/apply\n"
                  "3. `/level` - проверить уровень\n"
                  "4. `/birthday` - установить ДР",
            inline=False
        )
        embed.set_footer(text="🔥 «Беги со стаей»")
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        
        await welcome_channel.send(embed=embed)


# --- ЗАПУСК ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Неверный токен!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


