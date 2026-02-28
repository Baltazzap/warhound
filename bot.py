import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from discord.ext import commands

# --- НАСТРОЙКИ (ЗАПОЛНИ СВОИМИ ДАННЫМИ) ---
TOKEN = ''.strip()  # Убирает пробелы

# ID Каналов (Правый клик по каналу -> Копировать ID)
WELCOME_CHANNEL_ID = 1477296089882427493  # Канал для приветствий
APPLY_CHANNEL_ID = 1477340577254211808    # Канал, куда приходят заявки
VOICE_TEMPLATE_CHANNEL_ID = 123456789012345678  # ID канала "➕ Создать канал"
VOICE_CATEGORY_ID = 1477361244729114646           # ID категории для новых каналов

# ID Ролей (Правый клик по роли -> Копировать ID)
NEWBIE_ROLE_ID = 1477340663342301326      # Роль "Новичок" (выдается при входе)
VERIFIED_ROLE_ID = 1477003764576817296    # Роль "Верифицирован" (выдается после проверки)

# Включаем все необходимые намерения (Intents)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Словарь для хранения созданных каналов: {user_id: channel_id}
user_channels = {}

# --- 1 и 2. АВТО-ПРИВЕТСТВИЕ И АВТО-РОЛЬ ---
@bot.event
async def on_member_join(member):
    # Находим канал приветствий
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    
    # Находим роль новичка
    newbie_role = member.guild.get_role(NEWBIE_ROLE_ID)

    if channel and newbie_role:
        # Выдаем роль
        await member.add_roles(newbie_role)
        
        # Отправляем приветствие
        embed = discord.Embed(
            title="🐺 **Добро пожаловать в **Warhound Logistics**!",
            description=f"Привет, {member.mention}! Держи курс со стаей, соблюдай правила и держи технику в порядке. 🚛🔥",
            color=discord.Color.blue()
        )
        embed.add_field(name="Что делать дальше?", value="1. Пройди верификацию командой `/verify`\n2. Ознакомься с правилами.")
        await channel.send(embed=embed)
    else:
        print("Ошибка: Не найден канал или роль новичка. Проверь ID в настройках.")

# --- 4. СИСТЕМА ВЕРИФИКАЦИИ ---
class VerifyButton(Button):
    def __init__(self):
        super().__init__(label="✅ Подтвердить личность", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        role = interaction.guild.get_role(VERIFIED_ROLE_ID)
        
        if role:
            await user.add_roles(role)
            await interaction.response.send_message(f"{user.mention}, вы успешно прошли верификацию! Доступ открыт.", ephemeral=True)
        else:
            await interaction.response.send_message("Ошибка: Роль верифицированного не найдена.", ephemeral=True)

@tree.command(name="verify", description="🔐 Пройти верификацию новичка")
async def verify(interaction: discord.Interaction):
    view = View()
    view.add_item(VerifyButton())
    
    embed = discord.Embed(
        title="Система Верификации",
        description="Нажмите на кнопку ниже, чтобы подтвердить, что вы реальный человек и получить доступ к чатам.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- 3. ФОРМА ЗАЯВКИ В КОМПАНИЮ ---
class ApplicationModal(Modal, title="Заявка в компанию"):
    # Поля формы
    nickname = TextInput(label="Ваш никнейм в Discord", placeholder="Например: Driver_007")
    age = TextInput(label="Ваш возраст", placeholder="16+")
    experience = TextInput(label="Опыт работы / Стаж", style=discord.TextStyle.long, placeholder="Расскажите о своем опыте вождения...")

    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(APPLY_CHANNEL_ID)
        
        # Создаем красивое сообщение с заявкой
        embed = discord.Embed(title="📥 Новая заявка в компанию", color=discord.Color.gold())
        embed.add_field(name="👤 Сотрудник", value=interaction.user.mention)
        embed.add_field(name="🆔 Никнейм", value=self.nickname.value, inline=False)
        embed.add_field(name="🎂 Возраст", value=self.age.value, inline=True)
        embed.add_field(name="💼 Опыт", value=self.experience.value, inline=False)
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")

        if channel:
            await channel.send(embed=embed)
            await interaction.response.send_message("✅ Ваша заявка успешно отправлена руководству!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ошибка: Канал для заявок не найден.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message("Произошла ошибка при отправке заявки.", ephemeral=True)

@tree.command(name="apply", description="📝 Подать заявку на работу водителем")
async def apply(interaction: discord.Interaction):
    await interaction.response.send_modal(ApplicationModal())

# --- АВТО-СОЗДАНИЕ ГОЛОСОВЫХ КАНАЛОВ ---
@bot.event
async def on_voice_state_update(member, before, after):
    """Создание личного канала при входе в канал 'Создать'"""
    
    # Если пользователь зашёл в канал-шаблон
    if after.channel and after.channel.id == VOICE_TEMPLATE_CHANNEL_ID:
        guild = member.guild
        
        # Получаем категорию (если указана)
        category = guild.get_channel(VOICE_CATEGORY_ID) if VOICE_CATEGORY_ID else None
        
        # Создаём новый голосовой канал
        try:
            new_channel = await guild.create_voice_channel(
                name=f" {member.display_name}",
                category=category,
                reason="Авто-создание канала для колонны"
            )
            
            # Перемещаем пользователя в новый канал
            await member.move_to(new_channel)
            
            # Сохраняем информацию о канале
            user_channels[member.id] = new_channel.id
            
            # Отправляем сообщение с инструкциями (если есть текстовый канал)
            embed = discord.Embed(
                title="🎤 Ваш голосовой канал создан!",
                description=f"Канал: {new_channel.mention}\n\n**Доступные команды:**\n"
                           f"`!rename <название>` - переименовать канал\n"
                           f"`!limit <число>` - установить лимит\n"
                           f"`!lock` - закрыть канал\n"
                           f"`!unlock` - открыть канал\n"
                           f"`!delete` - удалить канал",
                color=discord.Color.green()
            )
            await member.send(embed=embed)
            
        except Exception as e:
            print(f"Ошибка создания канала: {e}")
            await member.send("❌ Не удалось создать канал. Обратитесь к администратору.")

    # Если пользователь покинул свой личный канал
    if before.channel and before.channel.id in user_channels.values():
        channel_id = before.channel.id
        
        # Проверяем, остался ли кто-то в канале
        if len(before.channel.members) == 0:
            # Удаляем пустой канал
            try:
                await before.channel.delete(reason="Канал пуст")
                # Удаляем из словаря
                user_channels_to_delete = [uid for uid, cid in user_channels.items() if cid == channel_id]
                for uid in user_channels_to_delete:
                    del user_channels[uid]
            except Exception as e:
                print(f"Ошибка удаления канала: {e}")

# --- КОМАНДЫ УПРАВЛЕНИЯ КАНАЛОМ ---
@bot.command(name="rename")
async def rename_channel(ctx, *, name: str):
    """Переименовать свой голосовой канал"""
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    
    channel = ctx.author.voice.channel
    
    # Проверяем, является ли канал личным
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный авто-созданный канал!", delete_after=5)
        return
    
    # Проверяем, владелец ли это канала
    owner_id = None
    for uid, cid in user_channels.items():
        if cid == channel.id:
            owner_id = uid
            break
    
    if owner_id != ctx.author.id:
        await ctx.send("❌ У вас нет прав на управление этим каналом!", delete_after=5)
        return
    
    try:
        await channel.edit(name=name)
        await ctx.send(f"✅ Канал переименован в **{name}**", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}", delete_after=5)

@bot.command(name="limit")
async def limit_channel(ctx, limit: int):
    """Установить лимит пользователей в канале"""
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    
    channel = ctx.author.voice.channel
    
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный авто-созданный канал!", delete_after=5)
        return
    
    owner_id = None
    for uid, cid in user_channels.items():
        if cid == channel.id:
            owner_id = uid
            break
    
    if owner_id != ctx.author.id:
        await ctx.send("❌ У вас нет прав на управление этим каналом!", delete_after=5)
        return
    
    if limit < 0 or limit > 99:
        await ctx.send("❌ Лимит должен быть от 0 до 99!", delete_after=5)
        return
    
    try:
        await channel.edit(user_limit=limit)
        await ctx.send(f"✅ Установлен лимит: **{limit}** чел.", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}", delete_after=5)

@bot.command(name="lock")
async def lock_channel(ctx):
    """Закрыть канал (только по приглашению)"""
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    
    channel = ctx.author.voice.channel
    
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный авто-созданный канал!", delete_after=5)
        return
    
    owner_id = None
    for uid, cid in user_channels.items():
        if cid == channel.id:
            owner_id = uid
            break
    
    if owner_id != ctx.author.id:
        await ctx.send("❌ У вас нет прав на управление этим каналом!", delete_after=5)
        return
    
    try:
        # Запрещаем @everyone подключаться
        overwrite = discord.PermissionOverwrite(connect=False)
        await channel.set_permission(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send("🔒 Канал закрыт", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}", delete_after=5)

@bot.command(name="unlock")
async def unlock_channel(ctx):
    """Открыть канал"""
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    
    channel = ctx.author.voice.channel
    
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный авто-созданный канал!", delete_after=5)
        return
    
    owner_id = None
    for uid, cid in user_channels.items():
        if cid == channel.id:
            owner_id = uid
            break
    
    if owner_id != ctx.author.id:
        await ctx.send("❌ У вас нет прав на управление этим каналом!", delete_after=5)
        return
    
    try:
        # Разрешаем @everyone подключаться
        overwrite = discord.PermissionOverwrite(connect=None)
        await channel.set_permission(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send("🔓 Канал открыт", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}", delete_after=5)

@bot.command(name="delete")
async def delete_channel(ctx):
    """Удалить свой канал"""
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    
    channel = ctx.author.voice.channel
    
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный авто-созданный канал!", delete_after=5)
        return
    
    owner_id = None
    for uid, cid in user_channels.items():
        if cid == channel.id:
            owner_id = uid
            break
    
    if owner_id != ctx.author.id:
        await ctx.send("❌ У вас нет прав на управление этим каналом!", delete_after=5)
        return
    
    try:
        await channel.delete(reason="Удалён владельцем")
        del user_channels[ctx.author.id]
        await ctx.send("✅ Канал удалён", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}", delete_after=5)

@bot.command(name="channelinfo")
async def channel_info(ctx):
    """Показать информацию о вашем канале"""
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    
    channel = ctx.author.voice.channel
    
    embed = discord.Embed(title="📊 Информация о канале", color=discord.Color.blue())
    embed.add_field(name="Название", value=channel.name)
    embed.add_field(name="Пользователей", value=f"{len(channel.members)}/{channel.user_limit or '∞'}")
    embed.add_field(name="ID канала", value=channel.id)
    
    await ctx.send(embed=embed, delete_after=10)

    # Вместо фиксированного имени, можно использовать ник или префикс
new_channel = await guild.create_voice_channel(
    name=f"🚛 Колонна {member.display_name}",
    # или
    name=f"🚚 {member.name}#{member.discriminator}",
    category=category
)

# Запуск бота
@bot.event
async def on_ready():
    print(f'Бот запущен как {bot.user}')
    try:
        synced = await tree.sync()
        print(f"Синхронизировано {len(synced)} команд.")
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

bot.run(TOKEN)
# В конце файла bot.py
import aiohttp

async def main():
    connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with bot:
            bot._http._Session = session
            await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

    import asyncio

async def main():
    async with bot:
        try:
            await bot.start(TOKEN)
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            print("Проверьте:")
            print("1. Интернет-соединение")
            print("2. Корректность токена")
            print("3. Не блокирует ли антивирус")

if __name__ == "__main__":
    asyncio.run(main())