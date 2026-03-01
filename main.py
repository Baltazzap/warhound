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

# --- НАСТРОЙКИ (ВАШИ ID) ---
WELCOME_CHANNEL_ID = 1477296089882427493
NEWBIE_ROLE_ID = 1477340663342301326
VERIFIED_ROLE_ID = 1477340898625847338
VOICE_TEMPLATE_CHANNEL_ID = 1477361557792100363
VOICE_CATEGORY_ID = 1477361244729114646

# Словарь для хранения созданных голосовых каналов
user_channels = {}


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
                    f"Теперь подавайте заявку в VTC: https://hub.truckyapp.com/vtc/warhound-logistics/apply",
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
    embed.add_field(
        name="🐺 Почему это важно?",
        value="• Защита сервера от спама и рейдов\n"
              "• Подтверждение серьёзности ваших намерений\n"
              "• Доступ к закрытым каналам компании",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# --- ГОЛОСОВЫЕ КАНАЛЫ ---
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


# --- SAY COMMAND (ОТПРАВКА EMBED ОТ БОТА) ---
class EmbedModal(Modal, title="📝 Создать Embed сообщение"):
    title_input = TextInput(
        label="Заголовок",
        placeholder="Введите заголовок сообщения",
        max_length=256,
        required=False,
        default="📢 Объявление"
    )
    description = TextInput(
        label="Описание",
        style=discord.TextStyle.long,
        placeholder="Основной текст сообщения",
        max_length=4000,
        required=True
    )
    color = TextInput(
        label="Цвет (HEX)",
        placeholder="#3498db",
        max_length=7,
        required=False,
        default="#3498db"
    )
    footer = TextInput(
        label="Подвал (footer)",
        placeholder="Текст в подвале сообщения",
        max_length=2048,
        required=False
    )

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


# --- ПИНГ КОМАНДА ---
@tree.command(name="ping", description="🏓 Проверка бота")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms", ephemeral=True)


# --- СПРАВКА ---
@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="📚 Список команд",
        description="**Slash команды:**\n"
                    "`/verify` - Пройти верификацию (подтвердить, что не робот)\n"
                    "`/say` - Отправить embed (админ)\n"
                    "`/ping` - Проверка бота\n\n"
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

