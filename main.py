import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from discord.ext import commands

# --- НАСТРОЙКИ (ЗАПОЛНИ СВОИМИ ДАННЫМИ) ---
TOKEN = 'MTQ3NzMzMzUwNzg0Mjc3MzEyNA.GPPrjI.Mc4VgQwk7-Dwi98MfYJnOzfW2yaZIK4gMnyUcY'

# ID Каналов (Правый клик по каналу -> Копировать ID)
WELCOME_CHANNEL_ID = 1477296089882427493  # Канал для приветствий
APPLY_CHANNEL_ID = 1477340577254211808    # Канал, куда приходят заявки

# ID Ролей (Правый клик по роли -> Копировать ID)
NEWBIE_ROLE_ID = 1477340663342301326      # Роль "Новичок" (выдается при входе)
VERIFIED_ROLE_ID = 1477003764576817296    # Роль "Верифицирован" (выдается после проверки)

# Включаем все необходимые намерения (Intents)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

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
            title="🚗 Добро пожаловать в Транспортную Компанию!",
            description=f"Привет, {member.mention}! Мы рады видеть тебя в нашем автопарке.",
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
    age = TextInput(label="Ваш возраст", placeholder="18+")
    experience = TextInput(label="Опыт работы / Стаж", style=discord.TextStyle.long, placeholder="Расскажите о своем опыте вождения...")

    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(APPLY_CHANNEL_ID)
        
        # Создаем красивое сообщение с заявкой
        embed = discord.Embed(title="📥 Новая заявка на работу", color=discord.Color.gold())
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