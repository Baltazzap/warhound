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

# Файл для хранения дней рождения
BIRTHDAYS_FILE = "birthdays.json"

# Словарь для голосовых каналов
user_channels = {}


# --- ФУНКЦИИ ДЛЯ ДНЕЙ РОЖДЕНИЯ (JSON) ---
def load_birthdays():
    """Загрузить дни рождения из JSON"""
    if os.path.exists(BIRTHDAYS_FILE):
        with open(BIRTHDAYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_birthdays(data):
    """Сохранить дни рождения в JSON"""
    with open(BIRTHDAYS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_age(birthdate: str) -> int:
    """Вычислить возраст по дате рождения"""
    try:
        birth = datetime.strptime(birthdate, "%d.%m.%Y")
        today = datetime.now()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        return age
    except:
        return 0


# --- БАЗА ДАННЫХ (для остального) ---
def init_db():
    conn = sqlite3.connect("warhound.db")
    cursor = conn.cursor()
    
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            channel_id TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT
        )
    """)
    
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photo_votes (
            contest_id INTEGER,
            user_id TEXT,
            photo_message_id TEXT,
            votes INTEGER DEFAULT 0,
            PRIMARY KEY (contest_id, user_id, photo_message_id)
        )
    """)
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect("warhound.db")
    conn.row_factory = sqlite3.Row
    return conn

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
    
    # Запуск проверки дней рождения (каждый день в 00:00)
    check_birthdays.start()
    check_server_status.start()


@bot.event
async def on_member_join(member):
    guild = member.guild
    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    newbie_role = guild.get_role(NEWBIE_ROLE_ID)
    
    if welcome_channel and newbie_role:
        try:
            await member.add_roles(newbie_role)
            
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
        super().__init__(label="✅ Я не робот", style=discord.ButtonStyle.green, custom_id="verify_button")

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
                    f"💡 Не забудьте установить дату рождения: `/birthday`",
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
                    "После верификации вам откроется доступ к каналам сервера.",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ============================================
# 🎂 ДНИ РОЖДЕНИЯ (БЕЗ БД)
# ============================================
@tree.command(name="birthday", description="🎂 Установить или посмотреть день рождения")
@app_commands.describe(
    day="День (1-31)",
    month="Месяц (1-12)",
    year="Год (например, 1995)"
)
async def birthday(interaction: discord.Interaction, day: int = None, month: int = None, year: int = None):
    """Установить или посмотреть день рождения"""
    
    # Если параметры не указаны — показываем дату пользователя
    if day is None or month is None:
        birthdays = load_birthdays()
        user_id = str(interaction.user.id)
        
        if user_id in birthdays:
            bday = birthdays[user_id]
            age = get_age(bday) if year else "скрыт"
            embed = discord.Embed(
                title="🎂 Ваш день рождения",
                description=f"📅 **{bday}**\n"
                           f"🎂 Возраст: **{age}** лет",
                color=discord.Color.pink()
            )
            embed.set_footer(text="Чтобы изменить, используйте /birthday с параметрами")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="🎂 День рождения не установлен",
                description="Укажите дату рождения командой:\n"
                           "`/birthday day:15 month:6 year:1995`\n\n"
                           "🎉 В день рождения бот поздравит вас в общем канале!",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Проверка валидности даты
    if day < 1 or day > 31:
        await interaction.response.send_message("❌ День должен быть от 1 до 31!", ephemeral=True)
        return
    if month < 1 or month > 12:
        await interaction.response.send_message("❌ Месяц должен быть от 1 до 12!", ephemeral=True)
        return
    if year and (year < 1900 or year > datetime.now().year):
        await interaction.response.send_message("❌ Неверный год!", ephemeral=True)
        return
    
    # Форматируем дату
    birthdate = f"{day:02d}.{month:02d}"
    if year:
        birthdate += f".{year}"
    
    # Сохраняем в JSON
    birthdays = load_birthdays()
    birthdays[str(interaction.user.id)] = birthdate
    save_birthdays(birthdays)
    
    embed = discord.Embed(
        title="🎂 День рождения установлен!",
        description=f"{interaction.user.mention}, ваш день рождения: **{birthdate}**\n\n"
                   f"🎉 В этот день бот поздравит вас в общем канале!",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="birthdays", description="📅 Показать все дни рождения участников")
async def birthdays_list(interaction: discord.Interaction):
    """Показать все дни рождения"""
    await interaction.response.defer()
    
    birthdays = load_birthdays()
    guild = interaction.guild
    
    if not birthdays:
        await interaction.followup.send("📭 Пока никто не установил день рождения!", ephemeral=True)
        return
    
    # Сортируем по дате
    sorted_bdays = sorted(
        birthdays.items(),
        key=lambda x: datetime.strptime(x[1][:5], "%d.%m") if len(x[1]) >= 5 else datetime.now()
    )
    
    # Группируем по месяцам
    months = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    
    embed = discord.Embed(
        title="📅 Дни рождения Warhound Logistics",
        description="🎉 Поздравляем наших водителей в их праздники!",
        color=discord.Color.pink(),
        timestamp=discord.utils.utcnow()
    )
    
    current_month = None
    bday_list = []
    
    for user_id, bdate in sorted_bdays[:20]:  # Показываем топ 20
        try:
            day, month = int(bdate[:2]), int(bdate[3:5])
            user = guild.get_member(int(user_id))
            name = user.display_name if user else f"Участник#{user_id[-4:]}"
            
            month_name = months.get(month, "Неизвестно")
            
            if current_month != month_name:
                if bday_list:
                    embed.add_field(name=f"📍 {current_month}", value="\n".join(bday_list), inline=False)
                    bday_list = []
                current_month = month_name
            
            age_text = f" ({get_age(bdate)} лет)" if len(bdate) > 5 else ""
            bday_list.append(f"• **{name}** — {day}.{month:02d}{age_text}")
        except:
            continue
    
    if bday_list:
        embed.add_field(name=f"📍 {current_month}", value="\n".join(bday_list), inline=False)
    
    embed.set_footer(text=f"Всего: {len(birthdays)} участников | Чтобы добавить свою дату: /birthday")
    
    await interaction.followup.send(embed=embed)


@tree.command(name="remove_birthday", description="❌ Удалить свой день рождения")
async def remove_birthday(interaction: discord.Interaction):
    """Удалить день рождения"""
    birthdays = load_birthdays()
    user_id = str(interaction.user.id)
    
    if user_id in birthdays:
        del birthdays[user_id]
        save_birthdays(birthdays)
        await interaction.response.send_message("✅ Ваш день рождения удалён!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ У вас не установлен день рождения!", ephemeral=True)


@tasks.loop(hours=24)
async def check_birthdays():
    """Ежедневная проверка дней рождения (в 00:00)"""
    now = datetime.now()
    today = f"{now.day:02d}.{now.month:02d}"
    
    birthdays = load_birthdays()
    
    # Находим тех, у кого сегодня ДР
    for user_id, bdate in birthdays.items():
        if bdate.startswith(today):
            user = bot.get_user(int(user_id))
            if user:
                channel = bot.get_channel(WELCOME_CHANNEL_ID)
                if channel:
                    age = get_age(bdate)
                    await channel.send(
                        f"🎂🎉 **С ДНЁМ РОЖДЕНИЯ, {user.mention}!** 🎉\n\n"
                        f"🎁 Желаю ровных дорог, полных прицепов и никаких ДТП!\n"
                        f"🎂 Возраст: **{age}** лет\n"
                        f"🐺 **Беги со стаей** и будь счастлив на дорогах! 🚛⚡"
                    )


@check_birthdays.before_loop
async def before_check_birthdays():
    """Ждём до полуночи перед первым запуском"""
    await bot.wait_until_ready()
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    await asyncio.sleep((midnight - now).total_seconds())


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
        
        for channel in interaction.guild.text_channels:
            if f"тикет-{interaction.user.name}" in channel.name and channel.category == category:
                await interaction.response.send_message(f"❌ У вас уже есть тикет: {channel.mention}", ephemeral=True)
                return
        
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
        
        conn = get_db()
        conn.execute("INSERT INTO tickets (user_id, channel_id, status) VALUES (?, ?, 'open')", (str(interaction.user.id), str(channel.id)))
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
    
    await interaction.response.defer()
    
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
    
    await interaction.followup.send(embed=embed)
    
    schedule_channel = interaction.guild.get_channel(SCHEDULE_CHANNEL_ID)
    if schedule_channel:
        await schedule_channel.send("🔔 **Новый рейс доступен для записи!**", embed=embed)


@tree.command(name="schedule", description="📅 Показать ближайшие рейсы")
async def show_schedule(interaction: discord.Interaction):
    await interaction.response.defer()
    
    conn = get_db()
    cursor = conn.execute("SELECT title, description, start_time, route, organizer_id FROM schedules ORDER BY start_time LIMIT 5")
    schedules = cursor.fetchall()
    conn.close()
    
    if not schedules:
        await interaction.followup.send("📭 Ближайших рейсов нет. Следите за анонсами!", ephemeral=True)
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
    
    await interaction.followup.send(embed=embed)


# ============================================
# 📸 ФОТОКОНКУРС (/photocontest)
# ============================================
@tree.command(name="create_contest", description="📸 Создать фотоконкурс (админ)")
@app_commands.describe(title="Название конкурса", duration_hours="Длительность в часах")
async def create_contest(interaction: discord.Interaction, title: str, duration_hours: int = 24):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Только для администрации!", ephemeral=True)
        return
    
    await interaction.response.defer()
    
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
                   f"🗳️ Голосуйте реакциями 👍 под фото\n\n"
                   f"🏆 Победитель получит звание и роль!",
        color=discord.Color.pink()
    )
    embed.set_footer(text=f"ID конкурса: {contest_id}")
    
    channel = interaction.guild.get_channel(PHOTO_CONTEST_CHANNEL_ID)
    if channel:
        msg = await channel.send(embed=embed)
        await msg.add_reaction("📷")
        await msg.add_reaction("👍")
        await interaction.followup.send(f"✅ Конкурс создан в {channel.mention}!", ephemeral=True)
    else:
        await interaction.followup.send("❌ Канал для фотоконкурсов не настроен!", ephemeral=True)


@tree.command(name="end_contest", description="🏆 Завершить фотоконкурс и выбрать победителя (админ)")
@app_commands.describe(message_id="ID сообщения с победным фото", winner="Победитель конкурса")
async def end_contest(interaction: discord.Interaction, message_id: str, winner: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Только для администрации!", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    embed = discord.Embed(
        title="🏆 Победитель фотоконкурса!",
        description=f"🎉 Поздравляем {winner.mention}!\n\n"
                   f"📸 [Победное фото](https://discord.com/channels/{interaction.guild.id}/{PHOTO_CONTEST_CHANNEL_ID}/{message_id})\n\n"
                   f"⭐ Вы получаете звание **Фотограф стаи** и специальную роль!",
        color=discord.Color.gold()
    )
    
    channel = interaction.guild.get_channel(PHOTO_CONTEST_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)
        await interaction.followup.send("✅ Конкурс завершён, победитель объявлен!", ephemeral=True)
    else:
        await interaction.followup.send("❌ Канал не найден!", ephemeral=True)


# ============================================
# 🖥️ СТАТУС СЕРВЕРА (/server)
# ============================================
@tasks.loop(minutes=5)
async def check_server_status():
    """Фоновая проверка статуса игрового сервера"""
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


@tree.command(name="server", description="🖥️ Статус игрового сервера")
async def server_status(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🖥️ Статус сервера Warhound Logistics",
        description="🎮 Euro Truck Simulator 2 / American Truck Simulator",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    
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
            
            embed = discord.Embed(
                title=self.title_input.value or "📢 Объявление",
                description=self.description.value,
                color=color_value,
                timestamp=discord.utils.utcnow()
            )
            if self.footer.value:
                embed.set_footer(text=self.footer.value)
            embed.set_author(
                name=f"Отправлено: {interaction.user.display_name}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            
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
# 🎤 ГОЛОСОВЫЕ КАНАЛЫ
# ============================================
@bot.event
async def on_voice_state_update(member, before, after):
    guild = member.guild
    
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
            
            embed = discord.Embed(
                title="🎤 Ваш канал создан!",
                description=f"Канал: {new_channel.mention}",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📋 Команды управления:",
                value="`!rename <название>` - переименовать\n"
                      "`!limit <число>` - лимит пользователей\n"
                      "`!lock` - закрыть канал\n"
                      "`!unlock` - открыть канал\n"
                      "`!delete` - удалить канал",
                inline=False
            )
            try:
                await member.send(embed=embed)
            except:
                pass
        except Exception as e:
            print(f"Ошибка создания канала: {e}")

    if before.channel and before.channel.id in user_channels.values():
        channel = before.channel
        if len(channel.members) == 0:
            try:
                await channel.delete(reason="Канал пуст")
                user_ids_to_delete = [uid for uid, cid in user_channels.items() if cid == channel.id]
                for uid in user_ids_to_delete:
                    del user_channels[uid]
            except Exception as e:
                print(f"Ошибка удаления канала: {e}")


@bot.command(name="rename")
async def rename_channel(ctx, *, name: str):
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    channel = ctx.author.voice.channel
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный канал!", delete_after=5)
        return
    owner_id = next((uid for uid, cid in user_channels.items() if cid == channel.id), None)
    if owner_id != ctx.author.id:
        await ctx.send("❌ Вы не владелец канала!", delete_after=5)
        return
    try:
        await channel.edit(name=name)
        await ctx.send(f"✅ Канал переименован в **{name}**", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}", delete_after=5)


@bot.command(name="limit")
async def limit_channel(ctx, limit: int):
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    channel = ctx.author.voice.channel
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный канал!", delete_after=5)
        return
    owner_id = next((uid for uid, cid in user_channels.items() if cid == channel.id), None)
    if owner_id != ctx.author.id:
        await ctx.send("❌ Вы не владелец канала!", delete_after=5)
        return
    if limit < 0 or limit > 99:
        await ctx.send("❌ Лимит должен быть от 0 до 99!", delete_after=5)
        return
    try:
        await channel.edit(user_limit=limit)
        await ctx.send(f"✅ Лимит установлен: **{limit}** чел.", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}", delete_after=5)


@bot.command(name="lock")
async def lock_channel(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    channel = ctx.author.voice.channel
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный канал!", delete_after=5)
        return
    owner_id = next((uid for uid, cid in user_channels.items() if cid == channel.id), None)
    if owner_id != ctx.author.id:
        await ctx.send("❌ Вы не владелец канала!", delete_after=5)
        return
    try:
        overwrite = discord.PermissionOverwrite(connect=False)
        await channel.set_permission(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send("🔒 Канал закрыт", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}", delete_after=5)


@bot.command(name="unlock")
async def unlock_channel(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    channel = ctx.author.voice.channel
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный канал!", delete_after=5)
        return
    owner_id = next((uid for uid, cid in user_channels.items() if cid == channel.id), None)
    if owner_id != ctx.author.id:
        await ctx.send("❌ Вы не владелец канала!", delete_after=5)
        return
    try:
        overwrite = discord.PermissionOverwrite(connect=None)
        await channel.set_permission(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send("🔓 Канал открыт", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}", delete_after=5)


@bot.command(name="delete")
async def delete_channel(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    channel = ctx.author.voice.channel
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный канал!", delete_after=5)
        return
    owner_id = next((uid for uid, cid in user_channels.items() if cid == channel.id), None)
    if owner_id != ctx.author.id:
        await ctx.send("❌ Вы не владелец канала!", delete_after=5)
        return
    try:
        await channel.delete(reason="Удалён владельцем")
        if ctx.author.id in user_channels:
            del user_channels[ctx.author.id]
        await ctx.send("✅ Канал удалён", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}", delete_after=5)


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
    embed.add_field(name="🎂 Дни рождения", value="`/birthday` - Установить дату\n`/birthdays` - Список всех ДР", inline=False)
    embed.add_field(name="🎫 Поддержка", value="`/ticket` - Создать обращение к админам", inline=False)
    embed.add_field(name="📅 Рейсы", value="`/schedule` - Ближайшие рейсы\n`/add_schedule` - Добавить рейс (админ)", inline=False)
    embed.add_field(name="📸 Конкурсы", value="`/create_contest` - Создать конкурс (админ)\n`/end_contest` - Завершить конкурс (админ)", inline=False)
    embed.add_field(name="🖥️ Сервер", value="`/server` - Статус игрового сервера", inline=False)
    embed.add_field(name="📢 Админ", value="`/say` - Отправить embed от бота", inline=False)
    embed.add_field(name="🎤 Голосовые", value="`!rename/limit/lock/unlock/delete` - Управление личным каналом", inline=False)
    
    await ctx.send(embed=embed, delete_after=60)


# --- ЗАПУСК ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Неверный токен! Проверьте токен в файле .env")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
