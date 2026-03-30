import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from database import Database

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
db = Database("bot_database.db")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# States for our "Studio" logic
class BroadcastStudio(StatesGroup):
    waiting_for_content = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()

# --- KEYBOARDS ---
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Broadcast Studio", callback_data="studio"))
    builder.row(InlineKeyboardButton(text="⚙️ Manage Groups", callback_data="manage_groups"))
    return builder.as_markup()

def studio_keyboard(has_button=False):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 " + ("Edit Button" if has_button else "Add URL Button"), callback_data="add_btn"))
    builder.row(
        InlineKeyboardButton(text="🎯 Select Targets", callback_data="manage_groups"),
        InlineKeyboardButton(text="🚀 SEND NOW", callback_data="confirm_send")
    )
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"))
    return builder.as_markup()

# --- HANDLERS ---

@dp.message(Command("start"), F.from_user.id == ADMIN_ID)
async def start_cmd(message: Message):
    await message.answer("🛠 **Welcome to Broadcast Studio Pro**\nSelect an option below:", reply_markup=main_menu())

# 1. Manage Groups (Selection Feature)
@dp.callback_query(F.data == "manage_groups")
async def manage_groups(callback: CallbackQuery):
    groups = db.get_all_groups()
    builder = InlineKeyboardBuilder()
    for gid, title, active in groups:
        status = "✅" if active else "❌"
        builder.row(InlineKeyboardButton(text=f"{status} {title}", callback_data=f"toggle_{gid}"))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="studio"))
    await callback.message.edit_text("🎯 **Select Target Groups**\nClick a group to enable/disable it for the next broadcast:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_group(callback: CallbackQuery):
    group_id = int(callback.data.split("_")[1])
    db.toggle_group(group_id)
    await manage_groups(callback) # Refresh list

# 2. Broadcast Studio Logic
@dp.callback_query(F.data == "studio")
async def start_studio(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("📝 **Send me anything** (text, photo, video) that you want to broadcast.")
    await state.set_state(BroadcastStudio.waiting_for_content)

@dp.message(BroadcastStudio.waiting_for_content, F.from_user.id == ADMIN_ID)
async def catch_content(message: Message, state: FSMContext):
    # Store the message ID and type to replicate it later
    await state.update_data(msg_id=message.message_id, btn_text=None, btn_url=None)
    await message.reply("✨ **Post Preview Created!**\nYou can now add buttons or select specific groups.", reply_markup=studio_keyboard())

# 3. Adding a Custom Button
@dp.callback_query(F.data == "add_btn")
async def add_btn_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter the **Text** for the button (e.g., 'Join Channel'):")
    await state.set_state(BroadcastStudio.waiting_for_button_text)

@dp.message(BroadcastStudio.waiting_for_button_text)
async def catch_btn_text(message: Message, state: FSMContext):
    await state.update_data(btn_text=message.text)
    await message.answer("Now send the **URL** (e.g., 'https://t.me/...'):")
    await state.set_state(BroadcastStudio.waiting_for_button_url)

@dp.message(BroadcastStudio.waiting_for_button_url)
async def catch_btn_url(message: Message, state: FSMContext):
    if not message.text.startswith("http"):
        await message.answer("❌ Invalid URL. Please start with http:// or https://")
        return
    await state.update_data(btn_url=message.text)
    await message.answer("✅ Button attached to post!", reply_markup=studio_keyboard(has_button=True))

# 4. Final Execution
@dp.callback_query(F.data == "confirm_send")
async def finalize_broadcast(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    groups = db.get_all_groups(only_active=True)
    
    if not groups:
        await callback.answer("❌ No active groups selected!", show_alert=True)
        return

    # Create the custom keyboard if user added a button
    kb = None
    if data.get('btn_text'):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text=data['btn_text'], url=data['btn_url']))
        kb = builder.as_markup()

    await callback.message.edit_text(f"🚀 **Sending to {len(groups)} selected groups...**")
    
    count = 0
    for gid, title in groups:
        try:
            await bot.copy_message(chat_id=gid, from_chat_id=callback.message.chat.id, 
                                   message_id=data['msg_id'], reply_markup=kb)
            count += 1
            await asyncio.sleep(0.05)
        except Exception: continue

    await callback.message.edit_text(f"✅ **Done!**\nReached {count} groups.", reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Studio Closed.", reply_markup=main_menu())

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())