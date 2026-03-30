import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from database import Database

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Setup
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
db = Database("bot_database.db")

# 1. Track when the bot is added to a new group
@dp.my_chat_member()
async def on_my_chat_member(update: types.ChatMemberUpdated):
    if update.new_chat_member.status in ["member", "administrator"]:
        db.add_group(update.chat.id, update.chat.title)
        print(f"Added to group: {update.chat.title}")
    elif update.new_chat_member.status in ["left", "kicked"]:
        db.remove_group(update.chat.id)
        print(f"Removed from group: {update.chat.title}")

# 2. Command to check how many groups the bot is in
@dp.message(Command("stats"), F.from_user.id == ADMIN_ID)
async def cmd_stats(message: Message):
    groups = db.get_all_groups()
    await message.answer(f"I am currently in {len(groups)} groups.")

# 3. THE BROADCAST FEATURE
# Use: Reply to any message (text, photo, etc.) with /broadcast
@dp.message(Command("broadcast"), F.from_user.id == ADMIN_ID)
async def cmd_broadcast(message: Message):
    if not message.reply_to_message:
        await message.answer("Please reply to a message you want to broadcast with /broadcast")
        return

    groups = db.get_all_groups()
    count = 0
    
    msg = await message.answer(f"Broadcasting to {len(groups)} groups... 0%")

    for i, group in enumerate(groups):
        try:
            # Copy the replied message to the group
            await message.reply_to_message.copy_to(chat_id=group[0])
            count += 1
            # Prevent spam limits (Wait 0.1s between groups)
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Failed to send to {group[0]}: {e}")

    await msg.edit_text(f"✅ Broadcast complete!\nSent to {count} groups.")

async def main():
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())