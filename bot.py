import os
import aiohttp
import discord
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Загружаем переменные из локального файла .env (если он есть)
load_dotenv()

# Получаем токен и ключи исключительно из переменных окружения хостинга/системы
TOKEN = os.getenv("DISCORD_TOKEN")
keys_string = os.getenv("GEMINI_API_KEYS", "")
GEMINI_API_KEYS = [
    key.strip() for key in keys_string.split(",") if key.strip()
]

# Включаем все интенты
intents = discord.Intents.all()
intents.message_content = True

client = discord.Client(intents=intents, fetch_offline_members=False)


@client.event
async def on_ready():
  print(f"Кузя {client.user} готов к работе!")


async def download_image_from_attachment(attachment):
  """Функция для скачивания картинок из вложений"""
  try:
    async with aiohttp.ClientSession() as session:
      async with session.get(attachment.url) as resp:
        if resp.status == 200:
          image_bytes = await resp.read()
          return types.Part.from_bytes(
              data=image_bytes,
              mime_type=attachment.content_type,
          )
  except Exception as e:
    print(f"Ошибка при скачивании картинки: {e}")
  return None


@client.event
async def on_message(message):
  if message.author == client.user:
    return

  content_lower = message.content.lower()
  user_name = message.author.display_name

  # Проверяем, ответил ли пользователь реплаем на сообщение самого бота
  is_reply_to_bot = False
  if message.reference and message.reference.message_id:
    try:
      replied_msg = await message.channel.fetch_message(
          message.reference.message_id
      )
      if replied_msg.author == client.user:
        is_reply_to_bot = True
    except Exception:
      pass

  if content_lower.startswith("кузя") or is_reply_to_bot:
    query = message.content
    if query.lower().startswith("кузя"):
      query = query[4:].strip()

    contents = []

    # Подтягиваем контекст предыдущего сообщения (если это реплай)
    if message.reference and message.reference.message_id:
      try:
        replied_msg = await message.channel.fetch_message(
            message.reference.message_id
        )
        if replied_msg.content:
          contents.append(
              f"[Контекст — то, о чём спрашивали ранее]: {replied_msg.content}"
          )

        if replied_msg.attachments:
          for att in replied_msg.attachments:
            if att.content_type and att.content_type.startswith("image/"):
              img_part = await download_image_from_attachment(att)
              if img_part:
                contents.append(img_part)
      except Exception as ref_err:
        print(f"Не удалось загрузить исходное сообщение: {ref_err}")

    # Проверяем картинки во вложениях текущего сообщения
    if message.attachments:
      for att in message.attachments:
        if att.content_type and att.content_type.startswith("image/"):
          img_part = await download_image_from_attachment(att)
          if img_part:
            contents.append(img_part)

    if query:
      contents.append(query)

    if not contents:
      await message.channel.send(f"{user_name} мяу мяу мяу мяяу")
      return

    # Цикл поочередного перебора ключей
    response = None
    last_error = None

    for i, api_key in enumerate(GEMINI_API_KEYS):
      try:
        gemini_client = genai.Client(api_key=api_key)
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )
        break
      except Exception as e:
        last_error = e
        print(f"Ключ #{i + 1} не ответил, пробуем следующий... Ошибка: {e}")

    # Проверяем, удалось ли получить ответ от какого-либо ключа
    if response:
      try:
        gemini_answer = response.text.strip()
        await message.channel.send(f"{user_name} мяу {gemini_answer}")
      except Exception as e:
        await message.channel.send(f"{user_name} мяуу... (ошибка обработки текста)")
        print(f"Ошибка текста: {e}")
    else:
      await message.channel.send(f"{user_name} мяуу... (ошибка нейросети)")
      print(f"Все ключи не сработали. Последняя ошибка: {last_error}")


if __name__ == "__main__":
  client.run(TOKEN)
