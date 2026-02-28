import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncio
import os
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

# --- НАСТРОЙКИ (ЗАМЕНИТЕ НА СВОИ ID) ---
WELCOME_CHANNEL_ID = 1477296089882427493  # Канал для приветствий
APPLY_CHANNEL_ID = 1477340577254211808    # Канал для заявок
NEWBIE_ROLE_ID = 1477340663342301326      # Роль "Новичок"
VERIFIED_ROLE_ID = 1477003764576817296    # Роль "Верифицирован"
VOICE_TEMPLATE_CHANNEL_ID = 1477361557792100363  # Канал "Создать"
VOICE_CATEGORY_ID = 1477361244729114646          # Категория для голосовых

# Словарь для хранения созданных голосовых каналов
user_channels = {}

# --- СОБЫТИЯ ---
@bot.event
async def on_ready():
    print(f'✅ Бот запущен как {bot.user}')
    print(f'📝 ID бота: {bot.user.id}')
    
    # Синхронизация slash команд
    try:
        synced = await tree.sync()
        print(f'✅ Синхронизировано {len(synced)} команд')
    except Exception as e:
        print(f'❌ Ошибка синхронизации: {e}')

@bot.event
async def on_member_join(member):
    """Авто-приветствие и выдача роли новичка"""
    guild = member.guild
    
    # Находим канал для приветствий
    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    
    # Находим роль новичка
    newbie_role = guild.get_role(NEWBIE_ROLE_ID)
    
    if welcome_channel and newbie_role:
        try:
            # Выдаем роль новичка
            await member.add_roles(newbie_role)
            
            # Отправляем приветствие
            embed = discord.Embed(
                title="🚗 Добро пожаловать в Транспортную Компанию!",
                description=f"Привет, {member.mention}!\n\nМы рады видеть тебя в нашем автопарке! 🎉",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(
                name="📋 Что делать дальше?",
                value="1. Пройди верификацию: `/verify`\n"
                      "2. Ознакомься с правилами\n"
                      "3. Подавай заявку: `/apply`\n"
                      "4. Создай голосовой канал для колонны",
                inline=False
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(text=f"ID: {member.id}")
            
            await welcome_channel.send(embed=embed)
            
        except Exception as e:
            print(f"Ошибка при приветствии: {e}")
    else:
        print("❌ Не найден канал приветствий или роль новичка")

# --- ВЕРИФИКАЦИЯ ---
class VerifyButton(Button):
    def __init__(self):
        super().__init__(
            label="✅ Подтвердить личность",
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
                    f"{user.mention}, вы успешно прошли верификацию! 🎉\nТеперь вам открыт доступ ко всем каналам.",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Роль верификации не найдена!", ephemeral=True)

@tree.command(name="verify", description="🔐 Пройти верификацию новичка")
async def verify(interaction: discord.Interaction):
    """Команда верификации"""
    view = View()
    view.add_item(VerifyButton())
    
    embed = discord.Embed(
        title="🔐 Система Верификации",
        description="Нажмите на кнопку ниже, чтобы подтвердить, что вы реальный человек и получить доступ ко всем каналам сервера.",
        color=discord.Color.green()
    )
    embed.add_field(
        name="📌 Правила",
        value="• Не создавайте альтернативные аккаунты\n"
              "• Используйте адекватный никнейм\n"
              "• После верификации ознакомьтесь с правилами",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- ЗАЯВКА ---
class ApplicationModal(Modal, title="📝 Заявка в компанию"):
    nickname = TextInput(
        label="Ваш никнейм в Discord",
        placeholder="Например: Driver_007",
        max_length=50
    )
    age = TextInput(
        label="Ваш возраст",
        placeholder="18+",
        max_length=10
    )
    experience = TextInput(
        label="Опыт работы / Стаж",
        style=discord.TextStyle.long,
        placeholder="Расскажите о своем опыте вождения (реальный или игровой)",
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        channel = guild.get_channel(APPLY_CHANNEL_ID)
        
        if channel:
            embed = discord.Embed(
                title="📥 Новая заявка на работу",
                description=f"Пользователь {interaction.user.mention} подал заявку!",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="👤 Пользователь", value=f"{interaction.user.mention} ({interaction.user})", inline=False)
            embed.add_field(name="🆔 Никнейм", value=self.nickname.value, inline=True)
            embed.add_field(name="🎂 Возраст", value=self.age.value, inline=True)
            embed.add_field(name="💼 Опыт работы", value=self.experience.value, inline=False)
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
            embed.set_footer(text=f"ID: {interaction.user.id}")
            
            try:
                await channel.send(embed=embed)
                await interaction.response.send_message(
                    "✅ Ваша заявка успешно отправлена руководству!\nОжидайте ответа в ЛС или на сервере.",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(f"❌ Ошибка отправки: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Канал для заявок не найден!", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message("❌ Произошла ошибка при отправке заявки.", ephemeral=True)

@tree.command(name="apply", description="📝 Подать заявку на работу водителем")
async def apply(interaction: discord.Interaction):
    """Подать заявку в компанию"""
    await interaction.response.send_modal(ApplicationModal())

# --- ГОЛОСОВЫЕ КАНАЛЫ ---
@bot.event
async def on_voice_state_update(member, before, after):
    """Авто-создание голосовых каналов"""
    guild = member.guild
    
    # Если пользователь зашёл в канал-шаблон
    if after.channel and after.channel.id == VOICE_TEMPLATE_CHANNEL_ID:
        category = guild.get_channel(VOICE_CATEGORY_ID) if VOICE_CATEGORY_ID else None
        
        try:
            # Создаём новый голосовой канал
            new_channel = await guild.create_voice_channel(
                name=f"🚛 {member.display_name}",
                category=category,
                reason="Авто-создание канала для колонны"
            )
            
            # Перемещаем пользователя
            await member.move_to(new_channel)
            
            # Сохраняем канал
            user_channels[member.id] = new_channel.id
            
            # Отправляем инструкции
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
            try:
                await member.send("❌ Не удалось создать канал. Обратитесь к администратору.")
            except:
                pass

    # Если пользователь покинул свой канал
    if before.channel and before.channel.id in user_channels.values():
        channel = before.channel
        
        # Проверяем, пуст ли канал
        if len(channel.members) == 0:
            try:
                await channel.delete(reason="Канал пуст")
                # Удаляем из словаря
                user_ids_to_delete = [uid for uid, cid in user_channels.items() if cid == channel.id]
                for uid in user_ids_to_delete:
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
    
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный канал!", delete_after=5)
        return
    
    owner_id = None
    for uid, cid in user_channels.items():
        if cid == channel.id:
            owner_id = uid
            break
    
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
    """Установить лимит в канале"""
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    
    channel = ctx.author.voice.channel
    
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный канал!", delete_after=5)
        return
    
    owner_id = None
    for uid, cid in user_channels.items():
        if cid == channel.id:
            owner_id = uid
            break
    
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
    """Закрыть канал"""
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    
    channel = ctx.author.voice.channel
    
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный канал!", delete_after=5)
        return
    
    owner_id = None
    for uid, cid in user_channels.items():
        if cid == channel.id:
            owner_id = uid
            break
    
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
    """Открыть канал"""
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    
    channel = ctx.author.voice.channel
    
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный канал!", delete_after=5)
        return
    
    owner_id = None
    for uid, cid in user_channels.items():
        if cid == channel.id:
            owner_id = uid
            break
    
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
    """Удалить канал"""
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны быть в голосовом канале!", delete_after=5)
        return
    
    channel = ctx.author.voice.channel
    
    if channel.id not in user_channels.values():
        await ctx.send("❌ Это не личный канал!", delete_after=5)
        return
    
    owner_id = None
    for uid, cid in user_channels.items():
        if cid == channel.id:
            owner_id = uid
            break
    
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

@bot.command(name="help")
async def help_command(ctx):
    """Справка по командам"""
    embed = discord.Embed(
        title="📚 Список команд",
        description="**Slash команды:**\n"
                    "`/verify` - Пройти верификацию\n"
                    "`/apply` - Подать заявку\n\n"
                    "**Команды префикса:**\n"
                    "`!rename <название>` - Переименовать канал\n"
                    "`!limit <число>` - Установить лимит\n"
                    "`!lock` - Закрыть канал\n"
                    "`!unlock` - Открыть канал\n"
                    "`!delete` - Удалить канал\n"
                    "`!help` - Эта справка",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, delete_after=30)

# --- ЗАПУСК ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Неверный токен! Проверьте токен в файле .env")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
