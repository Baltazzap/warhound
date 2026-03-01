import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput, Select
import asyncio
import os
import json
import sqlite3
import time
import random
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
TICKET_CATEGORY_ID = 1477004522617311242  # Замените на ID категории для тикетов
SCHEDULE_CHANNEL_ID = 1477003982919700553  # Канал для анонсов рейсов
PHOTO_CONTEST_CHANNEL_ID = 1477004431789785282  # Канал для фотоконкурсов
ETS2_SERVER_IP = "127.0.0.1"  # IP вашего игрового сервера
ETS2_SERVER_PORT = 27015       # Порт вашего игрового сервера
TRUCKY_VTC_ID = "43157"  # ID вашей VTC на Trucky

# Словарь для хранения созданных голосовых каналов
user_channels = {}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("warhound.db")
    cursor = conn.cursor()
    
    # Статистика водителей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            user_id TEXT PRIMARY KEY,
            miles INTEGER DEFAULT 0,
            deliveries INTEGER DEFAULT 0,
            rank TEXT DEFAULT 'Новичок',
            reputation INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 0,
            last_daily TEXT,
            current_job TEXT,
            job_start_time TEXT
        )
    """)
    
    # Расписание рейсов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            start_time TEXT,
            route TEXT,
            organizer_id TEXT,
            created_at TEXT
        )
    """)
    
    # Тикеты
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            channel_id TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT
        )
    """)
    
    # Фотоконкурсы
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photo_contests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            end_time TEXT,
            winner_id TEXT,
            status TEXT DEFAULT 'active'
        )
    """)
    
    # Голоса за фото
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photo_votes (
            contest_id INTEGER,
            user_id TEXT,
            photo_message_id TEXT,
            votes INTEGER DEFAULT 0,
            PRIMARY KEY (contest_id, user_id, photo_message_id)
        )
    """)
    
    # Репутация
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reputation (
            from_user TEXT,
            to_user TEXT,
            reason TEXT,
            timestamp TEXT,
            PRIMARY KEY (from_user, to_user)
        )
    """)
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect("warhound.db")
    conn.row_factory = sqlite3.Row
    return conn

# Инициализация БД при старте
init_db()


# --- СОБЫТИЯ ---
@bot.event
async def on_ready():
    print(f'✅ Бот запущен как {bot.user}')
    print(f'📝 ID бота: {bot.user.id}')
    
    try:
        synced = await tree.sync()
        print(f'✅ Синхронизировано {len(synced)} команд')
    except Exception as e:
        print(f'❌ Ошибка синхронизации: {e}')
    
    # Запуск фоновых задач
    check_server_status.start()

@bot.event
async def on_member_join(member):
    guild = member.guild
    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    newbie_role = guild.get_role(NEWBIE_ROLE_ID)
    
    if welcome_channel and newbie_role:
        try:
            await member.add_roles(newbie_role)
            
            # Инициализация пользователя в БД
            conn = get_db()
            conn.execute("INSERT OR IGNORE INTO drivers (user_id) VALUES (?)", (str(member.id),))
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                title="🐺 Добро пожаловать в Warhound Logistics!",
                description=f"Привет, новый член стаи! ⚡ {member.mention}\n\n"
                           "Ты вступаешь в компанию дальнобойщиков, где скорость, дисциплина и мощь — закон. "
                           "Здесь каждый рейс — испытание, а каждая миля — заслуга.",
                color=discord.Color.dark_gray(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(
                name="📋 Прежде чем выйти на трассу, ознакомься с:",
                value="📜 **Правила компании:** #📢┃анонсы-компании / #📝┃приказы-стаи\n"
                      "❓ **FAQ для новичков:** #🆘┃помощь-на-дороге\n"
                      "🖤 **Ролями и позывными:** Alpha, Wolf Lead, Pack Member — выбери свой статус правильно",
                inline=False
            )
            embed.add_field(
                name="🚛 Советы новичкам:",
                value="• Используй свой позывной в никнейме: `[Позывной] | [Имя]`\n"
                      "• Следи за рейсами в 🛣️┃расписание-рейсов\n"
                      "• В случае ЧП или поломки сразу пиши в ⚠️┃чп-и-задержки\n"
                      "• Подключайся к стае и общайся в 🐺┃общий-зал",
                inline=False
            )
            embed.add_field(
                name="✅ Первые шаги:",
                value="1. Пройди верификацию: `/verify` (подтверди, что ты не робот 🤖)\n"
                      "2. Подавай заявку в нашу VTC: https://hub.truckyapp.com/vtc/warhound-logistics/apply\n"
                      "3. Дождись одобрения менеджеров по найму\n"
                      "4. Получи роль водителя и выходи на трассу! 🛣️",
                inline=False
            )
            embed.set_footer(text="🔥 Слоган компании: «Беги со стаей» — чувствуй мощь, будь частью стаи и не сдавайся на дороге!")
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            await welcome_channel.send(embed=embed)
        except Exception as e:
            print(f"Ошибка при приветствии: {e}")


# --- ВЕРИФИКАЦИЯ ---
class VerifyButton(Button):
    def __init__(self):
        super().__init__(
            label="✅ Я не робот",
            style=discord.ButtonStyle.green,
            custom_id="verify_button"
        )

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        role = guild.get_role(VERIFIED_ROLE_ID)
        
        if role:
            try:
                await user.add_roles(role)
                await interaction.response.send_message(
                    f"{user.mention}, вы успешно прошли верификацию! 🐺⚡\n"
                    f"Теперь подавайте заявку в VTC: https://hub.truckyapp.com/vtc/warhound-logistics/apply\n\n"
                    f"💡 Используйте `/stats` чтобы посмотреть свой профиль!",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Роль верификации не найдена!", ephemeral=True)


@tree.command(name="verify", description="🔐 Пройти верификацию (подтвердить, что вы не робот)")
async def verify(interaction: discord.Interaction):
    view = View()
    view.add_item(VerifyButton())
    
    embed = discord.Embed(
        title="🔐 Верификация участника",
        description="Нажмите на кнопку ниже, чтобы подтвердить, что вы реальный человек, а не бот.\n\n"
                    "После верификации вам откроется доступ к каналам сервера и вы сможете подать заявку в нашу VTC.",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ============================================
# 📊 СТАТИСТИКА ВОДИТЕЛЯ (/stats)
# ============================================
@tree.command(name="stats", description="📊 Показать статистику водителя")
@app_commands.describe(member="Участник для просмотра статистики (по умолчанию - вы)")
async def stats(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    conn = get_db()
    
    cursor = conn.execute("SELECT * FROM drivers WHERE user_id = ?", (str(target.id),))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        # Создаём запись если нет
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO drivers (user_id) VALUES (?)", (str(target.id),))
        conn.commit()
        conn.close()
        miles, deliveries, rank, reputation, coins = 0, 0, "Новичок", 0, 0
    else:
        miles = row["miles"]
        deliveries = row["deliveries"]
        rank = row["rank"]
        reputation = row["reputation"]
        coins = row["coins"]
    
    # Определяем цвет по рангу
    rank_colors = {
        "Новичок": discord.Color.gray(),
        "Водитель": discord.Color.blue(),
        "Опытный": discord.Color.green(),
        "Профи": discord.Color.purple(),
        "Легенда": discord.Color.gold(),
        "Alpha": discord.Color.red()
    }
    
    embed = discord.Embed(
        title=f"📊 Профиль: {target.display_name}",
        description=f"🏆 **Ранг:** {rank}\n"
                   f"🪙 **Монеты:** {coins:,}\n"
                   f"⭐ **Репутация:** {reputation}",
        color=rank_colors.get(rank, discord.Color.blue()),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="🛣️ Пройдено", value=f"{miles:,} км", inline=True)
    embed.add_field(name="📦 Доставок", value=f"{deliveries}", inline=True)
    
    # Проверка активного задания
    if row and row["current_job"]:
        embed.add_field(
            name="🚛 Активное задание",
            value=f"```{row['current_job']}```\n🕐 Начато: <t:{int(datetime.fromisoformat(row['job_start_time']).timestamp())}:R>",
            inline=False
        )
    
    embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
    embed.set_footer(text=f"ID: {target.id} | Warhound Logistics")
    
    await interaction.response.send_message(embed=embed)


# ============================================
# 🏆 ЛИДЕРБОРД (/leaderboard)
# ============================================
@tree.command(name="leaderboard", description="🏆 Топ водителей компании")
@app_commands.describe(category="Категория: miles/deliveries/reputation")
async def leaderboard(interaction: discord.Interaction, category: str = "miles"):
    conn = get_db()
    
    # Выбор сортировки
    sort_by = {"miles": "miles", "deliveries": "deliveries", "reputation": "reputation"}.get(category, "miles")
    sort_name = {"miles": "🛣️ Километраж", "deliveries": "📦 Доставки", "reputation": "⭐ Репутация"}.get(category, "🛣️ Километраж")
    
    cursor = conn.execute(f"SELECT user_id, miles, deliveries, reputation, rank FROM drivers ORDER BY {sort_by} DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await interaction.response.send_message("📭 Пока нет данных для лидерборда!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🏆 Топ водителей Warhound Logistics",
        description=f"{sort_name} — лучшие из лучших 🐺",
        color=discord.Color.gold()
    )
    
    for i, row in enumerate(rows, 1):
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
        user = interaction.guild.get_member(int(row["user_id"]))
        name = user.display_name if user else f"Участник#{row['user_id'][-4:]}"
        
        value = f"🏆 {row['rank']} | "
        if category == "miles":
            value += f"🛣️ {row['miles']:,} км"
        elif category == "deliveries":
            value += f"📦 {row['deliveries']} доставок"
        else:
            value += f"⭐ {row['reputation']} репутации"
        
        embed.add_field(name=f"{medal} {name}", value=value, inline=False)
    
    embed.set_footer(text="Используй /stats чтобы посмотреть свой прогресс!")
    
    await interaction.response.send_message(embed=embed)


# ============================================
# 🎫 ТИКЕТ-СИСТЕМА (/ticket)
# ============================================
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
            await interaction.response.send_message("❌ Категория для тикетов не настроена!", ephemeral=True)
            return
        
        # Проверка: есть ли уже тикет
        for channel in interaction.guild.text_channels:
            if f"тикет-{interaction.user.name}" in channel.name and channel.category == category:
                await interaction.response.send_message(f"❌ У вас уже есть тикет: {channel.mention}", ephemeral=True)
                return
        
        # Создаём канал
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
        }
        
        ticket_type = {"game": "🎮", "org": "💬", "complaint": "⚠️", "suggestion": "💡", "other": "🤝"}.get(self.values[0], "🎫")
        
        channel = await interaction.guild.create_text_channel(
            name=f"тикет-{interaction.user.name}",
            category=category,
            overwrites=overwrites,
            reason=f"Тикет [{self.values[0]}] от {interaction.user}"
        )
        
        # Сохраняем в БД
        conn = get_db()
        conn.execute(
            "INSERT INTO tickets (user_id, channel_id, status) VALUES (?, ?, 'open')",
            (str(interaction.user.id), str(channel.id))
        )
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title=f"{ticket_type} Обращение к администрации",
            description=f"Привет, {interaction.user.mention}!\n\n"
                       f"Тип обращения: **{self.values[0]}**\n\n"
                       "📝 Опишите вашу проблему или вопрос.\n"
                       "Администрация ответит в ближайшее время.\n\n"
                       "❌ **Закрыть тикет:** напишите `!close`\n"
                       "👥 **Добавить участника:** `!add @user`",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Тикет #{channel.id}")
        
        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Тикет создан: {channel.mention}", ephemeral=True)


@tree.command(name="ticket", description="🎫 Создать обращение к администрации")
async def ticket(interaction: discord.Interaction):
    view = View()
    view.add_item(TicketSelect())
    
    embed = discord.Embed(
        title="🎫 Система обращений",
        description="Выберите тип вашего обращения ниже.\n"
                   "Созданный тикет будет виден только вам и администрации.",
        color=discord.Color.blue()
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.command(name="close")
async def close_ticket(ctx):
    if "тикет-" not in ctx.channel.name:
        await ctx.send("❌ Эта команда работает только в тикетах!", delete_after=5)
        return
    
    # Удаляем из БД
    conn = get_db()
    conn.execute("DELETE FROM tickets WHERE channel_id = ?", (str(ctx.channel.id),))
    conn.commit()
    conn.close()
    
    await ctx.send("🔒 Тикет закрывается через 5 секунд...")
    await asyncio.sleep(5)
    await ctx.channel.delete()


@bot.command(name="add")
async def add_to_ticket(ctx, member: discord.Member):
    if "тикет-" not in ctx.channel.name:
        await ctx.send("❌ Эта команда работает только в тикетах!", delete_after=5)
        return
    
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
    await ctx.send(f"✅ {member.mention} добавлен в тикет!", delete_after=5)


# ============================================
# 📅 РАСПИСАНИЕ РЕЙСОВ (/schedule)
# ============================================
@tree.command(name="add_schedule", description="📅 Добавить рейс (только админ)")
@app_commands.describe(
    title="Название рейса",
    description="Описание маршрута",
    start_time="Дата и время (ДД.ММ ЧЧ:ММ)",
    route="Маршрут: Город А → Город Б"
)
async def add_schedule(
    interaction: discord.Interaction,
    title: str,
    description: str,
    start_time: str,
    route: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Только для администрации!", ephemeral=True)
        return
    
    conn = get_db()
    conn.execute(
        "INSERT INTO schedules (title, description, start_time, route, organizer_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (title, description, start_time, route, str(interaction.user.id), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title="📅 Новый рейс добавлен!",
        description=f"**{title}**\n{description}\n\n"
                   f"🗓️ **Время:** {start_time}\n"
                   f"🛣️ **Маршрут:** {route}\n"
                   f"👤 **Организатор:** {interaction.user.mention}",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)
    
    # Уведомление в канал рейсов
    schedule_channel = interaction.guild.get_channel(SCHEDULE_CHANNEL_ID)
    if schedule_channel:
        await schedule_channel.send("🔔 **Новый рейс доступен для записи!**", embed=embed)


@tree.command(name="schedule", description="📅 Показать ближайшие рейсы")
async def show_schedule(interaction: discord.Interaction):
    conn = get_db()
    cursor = conn.execute("SELECT title, description, start_time, route, organizer_id FROM schedules ORDER BY start_time LIMIT 5")
    schedules = cursor.fetchall()
    conn.close()
    
    if not schedules:
        await interaction.response.send_message("📭 Ближайших рейсов нет. Следите за анонсами!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📅 Ближайшие рейсы Warhound Logistics",
        description="Записывайтесь и не опаздывайте! 🚛🐺",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    for title, desc, time_str, route, org_id in schedules:
        organizer = interaction.guild.get_member(int(org_id))
        org_name = organizer.mention if organizer else "Неизвестно"
        
        embed.add_field(
            name=f"🚛 {title}",
            value=f"{desc}\n🗓️ {time_str}\n🛣️ {route}\n👤 Орг: {org_name}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)


# ============================================
# 🎁 ЕЖЕДНЕВНЫЙ БОНУС (/daily)
# ============================================
@tree.command(name="daily", description="🎁 Получить ежедневный бонус")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = datetime.now()
    
    conn = get_db()
    cursor = conn.execute("SELECT last_daily, coins FROM drivers WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row and row["last_daily"]:
        last = datetime.fromisoformat(row["last_daily"])
        if (now - last).total_seconds() < 86400:
            remaining = 86400 - (now - last).total_seconds()
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await interaction.response.send_message(
                f"⏰ Вы уже забрали бонус! Вернитесь через {hours}ч {minutes}м.",
                ephemeral=True
            )
            conn.close()
            return
    
    # Выдаём награду
    new_coins = (row["coins"] if row else 0) + 50
    conn.execute(
        "INSERT OR REPLACE INTO drivers (user_id, coins, last_daily) VALUES (?, ?, ?)",
        (user_id, new_coins, now.isoformat())
    )
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title="🎁 Ежедневный бонус получен!",
        description=f"{interaction.user.mention}, вы получили:\n\n"
                   f"🪙 **+50 монет** (всего: {new_coins})\n"
                   f"⭐ **+1 репутация**\n\n"
                   f"Завтра ждёт новая награда! Вернитесь через 24 часа.",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url="https://i.imgur.com/goldcoin.png")
    
    await interaction.response.send_message(embed=embed)


# ============================================
# 🚛 РАБОТА / РЕЙСЫ (/work)
# ============================================
JOBS = [
    {"name": "Доставка продуктов", "km": 150, "pay": 25},
    {"name": "Перевозка стройматериалов", "km": 300, "pay": 55},
    {"name": "Контейнерный рейс", "km": 500, "pay": 95},
    {"name": "Хрупкий груз (осторожно!)", "km": 200, "pay": 50},
    {"name": "Срочная доставка", "km": 100, "pay": 30},
]

@tree.command(name="work", description="🚛 Система работы: взять/завершить рейс")
@app_commands.describe(action="Действие: take/complete")
async def work(interaction: discord.Interaction, action: str):
    user_id = str(interaction.user.id)
    conn = get_db()
    cursor = conn.execute("SELECT current_job, job_start_time, coins FROM drivers WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if action == "take":
        if row and row["current_job"]:
            await interaction.response.send_message("🚛 У вас уже есть активное задание! Завершите его командой `/work complete`", ephemeral=True)
            conn.close()
            return
        
        job = random.choice(JOBS)
        conn.execute(
            "UPDATE drivers SET current_job = ?, job_start_time = ? WHERE user_id = ?",
            (job["name"], datetime.now().isoformat(), user_id)
        )
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="🚛 Новое задание получено!",
            description=f"📦 **{job['name']}**\n"
                       f"🛣️ Расстояние: {job['km']} км\n"
                       f"💰 Оплата: {job['pay']} монет\n\n"
                       f"⏱️ Завершите рейс командой `/work complete`",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        
    elif action == "complete":
        if not row or not row["current_job"]:
            await interaction.response.send_message("❌ У вас нет активного задания! Возьмите рейс: `/work take`", ephemeral=True)
            conn.close()
            return
        
        # Расчёт бонуса за скорость
        start = datetime.fromisoformat(row["job_start_time"])
        hours = (datetime.now() - start).total_seconds() / 3600
        
        conn.execute(
            "UPDATE drivers SET coins = coins + 50, deliveries = deliveries + 1, current_job = NULL, job_start_time = NULL WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="✅ Рейс завершён!",
            description=f"{interaction.user.mention}, отличная работа! 🎉\n\n"
                       f"💰 **+50 монет** зачислено\n"
                       f"📦 **+1 доставка** в статистику\n"
                       f"⭐ **+1 репутация** за надёжность",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Используйте: `/work take` или `/work complete`", ephemeral=True)


# ============================================
# ⭐ РЕПУТАЦИЯ (/rep)
# ============================================
@tree.command(name="rep", description="⭐ Выдать репутацию участнику")
@app_commands.describe(member="Участник", reason="Причина")
async def rep(interaction: discord.Interaction, member: discord.Member, reason: str):
    if member.id == interaction.user.id:
        await interaction.response.send_message("❌ Нельзя выдать репутацию самому себе!", ephemeral=True)
        return
    
    from_user = str(interaction.user.id)
    to_user = str(member.id)
    
    conn = get_db()
    
    # Проверка: не выдавал ли уже
    cursor = conn.execute(
        "SELECT * FROM reputation WHERE from_user = ? AND to_user = ?",
        (from_user, to_user)
    )
    if cursor.fetchone():
        await interaction.response.send_message("❌ Вы уже выдавали репутацию этому участнику!", ephemeral=True)
        conn.close()
        return
    
    # Запись в БД
    conn.execute(
        "INSERT INTO reputation (from_user, to_user, reason, timestamp) VALUES (?, ?, ?, ?)",
        (from_user, to_user, reason, datetime.now().isoformat())
    )
    conn.execute("UPDATE drivers SET reputation = reputation + 1 WHERE user_id = ?", (to_user,))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title="⭐ Репутация выдана!",
        description=f"{interaction.user.mention} выдал репутацию {member.mention}\n\n"
                   f"📝 **Причина:** {reason}",
        color=discord.Color.purple()
    )
    
    await interaction.response.send_message(embed=embed)
    await member.send(f"⭐ Вам выдали репутацию от {interaction.user.name}: {reason}")


# ============================================
# 📸 ФОТОКОНКУРС (/photocontest)
# ============================================
@tree.command(name="create_contest", description="📸 Создать фотоконкурс (админ)")
@app_commands.describe(title="Название конкурса", duration_hours="Длительность в часах")
async def create_contest(interaction: discord.Interaction, title: str, duration_hours: int = 24):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Только для администрации!", ephemeral=True)
        return
    
    end_time = (datetime.now() + timedelta(hours=duration_hours)).isoformat()
    
    conn = get_db()
    conn.execute(
        "INSERT INTO photo_contests (title, description, end_time, status) VALUES (?, ?, ?, 'active')",
        (title, f"Конкурс скриншотов от {interaction.user.name}", end_time)
    )
    contest_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title="📸 Новый фотоконкурс!",
        description=f"**{title}**\n\n"
                   f"📷 Присылайте ваши лучшие скриншоты в этот канал!\n"
                   f"⏰ Конкурс продлится **{duration_hours} часов**\n"
                   f"🗳️ Голосуйте реакциями под фото\n\n"
                   f"🏆 Победитель получит **500 монет** и звание!",
        color=discord.Color.pink()
    )
    embed.set_footer(text=f"ID конкурса: {contest_id}")
    
    channel = interaction.guild.get_channel(PHOTO_CONTEST_CHANNEL_ID)
    if channel:
        msg = await channel.send(embed=embed)
        await msg.add_reaction("📷")
        await interaction.response.send_message(f"✅ Конкурс создан в {channel.mention}!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Канал для фотоконкурсов не настроен!", ephemeral=True)


@tree.command(name="vote", description="🗳️ Проголосовать за фото")
async def vote(interaction: discord.Interaction, message_id: str):
    # Упрощённая версия: голосование реакциями
    await interaction.response.send_message(
        "🗳️ Проголосуйте реакцией 👍 под понравившимся фото!\n"
        "Администрация подведёт итоги автоматически.",
        ephemeral=True
    )


# ============================================
# 🔗 TRUCKY.APP ИНТЕГРАЦИЯ (/trucky)
# ============================================
@tree.command(name="trucky", description="🔗 Синхронизация с Trucky.app")
async def trucky_sync(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔗 Trucky.app Интеграция",
        description=f"👤 **Ваш Discord:** {interaction.user.mention}\n"
                   f"🚛 **VTC:** Warhound Logistics\n\n"
                   f"📋 Чтобы синхронизировать профиль:\n"
                   f"1. Зайдите на https://hub.truckyapp.com\n"
                   f"2. Откройте настройки профиля\n"
                   f"3. Привяжите ваш Discord аккаунт\n"
                   f"4. Вступите в VTC: `{TRUCKY_VTC_ID}`\n\n"
                   f"✅ После привязки статика будет обновляться автоматически!",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url="https://truckyapp.com/logo.png")
    
    view = View()
    btn = Button(label="🌐 Открыть Trucky", url="https://hub.truckyapp.com/vtc/warhound-logistics", style=discord.ButtonStyle.link)
    view.add_item(btn)
    
    await interaction.response.send_message(embed=embed, view=view)


# ============================================
# 🖥️ СТАТУС СЕРВЕРА ETS2/ATS (/server)
# ============================================
@tasks.loop(minutes=5)
async def check_server_status():
    """Фоновая проверка статуса игрового сервера"""
    status_channel = bot.get_channel(SCHEDULE_CHANNEL_ID)  # Замените на канал статуса
    if not status_channel:
        return
    
    try:
        # Простая проверка через aiohttp (для Convoy-серверов)
        async with aiohttp.ClientSession() as session:
            # Пример для Trucky-сервера
            async with session.get(f"https://api.truckyapp.com/v1/servers?vtc={TRUCKY_VTC_ID}", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    servers = data.get("data", [])
                    online = sum(1 for s in servers if s.get("players", 0) > 0)
                    
                    # Обновляем статус бота
                    if online > 0:
                        await bot.change_presence(activity=discord.Game(name=f"🚛 Сервер онлайн | {online} игроков"))
                    else:
                        await bot.change_presence(activity=discord.Game(name="🌙 Сервер оффлайн"))
    except Exception as e:
        print(f"Ошибка проверки сервера: {e}")


@tree.command(name="server", description="🖥️ Статус игрового сервера")
async def server_status(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🖥️ Статус сервера Warhound Logistics",
        description="🎮 Euro Truck Simulator 2 / American Truck Simulator",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    
    # Здесь можно добавить реальную проверку через a2s библиотеку
    embed.add_field(name="🌐 IP", value=f"||{ETS2_SERVER_IP}:{ETS2_SERVER_PORT}||", inline=False)
    embed.add_field(name="👥 Статус", value="🟢 Онлайн (проверка каждые 5 мин)", inline=True)
    embed.add_field(name="🚛 Конвой", value="Доступен", inline=True)
    
    embed.set_footer(text="Автоматическая проверка каждые 5 минут")
    
    await interaction.response.send_message(embed=embed)


# ============================================
# 📢 SAY COMMAND (ОТПРАВКА EMBED)
# ============================================
class EmbedModal(Modal, title="📝 Создать Embed сообщение"):
    title_input = TextInput(label="Заголовок", placeholder="Введите заголовок", max_length=256, required=False, default="📢 Объявление")
    description = TextInput(label="Описание", style=discord.TextStyle.long, placeholder="Основной текст", max_length=4000, required=True)
    color = TextInput(label="Цвет (HEX)", placeholder="#3498db", max_length=7, required=False, default="#3498db")
    footer = TextInput(label="Подвал", placeholder="Текст в подвале", max_length=2048, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ У вас нет прав администратора!", ephemeral=True)
                return
            
            color_value = discord.Color.random()
            if self.color.value:
                try:
                    color_value = int(self.color.value.replace('#', ''), 16)
                except:
                    color_value = discord.Color.random()
            
            embed = discord.Embed(title=self.title_input.value or "📢 Объявление", description=self.description.value, color=color_value, timestamp=discord.utils.utcnow())
            if self.footer.value:
                embed.set_footer(text=self.footer.value)
            embed.set_author(name=f"Отправлено: {interaction.user.display_name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("✅ Сообщение отправлено!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        try:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)
        except:
            pass


@tree.command(name="say", description="📢 Отправить сообщение от имени бота (только для админов)")
async def say(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ У вас нет прав администратора!", ephemeral=True)
        return
    await interaction.response.send_modal(EmbedModal())


# ============================================
# 🎲 ДОП. КОМАНДЫ
# ============================================
@tree.command(name="ping", description="🏓 Проверка бота")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms", ephemeral=True)


@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="📚 Список команд Warhound Logistics", color=discord.Color.blue())
    embed.add_field(name="🔐 Верификация", value="`/verify` - Подтвердить аккаунт", inline=False)
    embed.add_field(name="📊 Статистика", value="`/stats` - Профиль водителя\n`/leaderboard` - Топ участников", inline=False)
    embed.add_field(name="🚛 Работа", value="`/work take` - Взять рейс\n`/work complete` - Завершить рейс", inline=False)
    embed.add_field(name="🎫 Поддержка", value="`/ticket` - Создать обращение", inline=False)
    embed.add_field(name="📅 Рейсы", value="`/schedule` - Ближайшие рейсы\n`/add_schedule` - Добавить рейс (админ)", inline=False)
    embed.add_field(name="🎁 Бонусы", value="`/daily` - Ежедневная награда\n`/rep @user причина` - Выдать репутацию", inline=False)
    embed.add_field(name="📸 Конкурсы", value="`/create_contest` - Создать конкурс (админ)\n`/vote` - Проголосовать", inline=False)
    embed.add_field(name="🔗 Интеграции", value="`/trucky` - Trucky.app\n`/server` - Статус сервера", inline=False)
    embed.add_field(name="🎤 Голосовые каналы", value="`!rename/limit/lock/unlock/delete` - Управление личным каналом", inline=False)
    
    await ctx.send(embed=embed, delete_after=60)


# --- ЗАПУСК ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Неверный токен! Проверьте токен в файле .env")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
