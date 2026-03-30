import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery, ChatMemberUpdated
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

class BroadcastStudio(StatesGroup):
    waiting_for_content = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()

# --- NEW: AUTOMATIC GROUP DETECTION ---
@dp.my_chat_member()
async def on_bot_added_to_chat(event: ChatMemberUpdated):
    # This triggers whenever the bot is added to a new group/channel
    if event.new_chat_member.status in ["member", "administrator"]:
        db.add_group(event.chat.id, event.chat.title)
        logging.info(f"Automatically registered: {event.chat.title}")
        # Send a "Hello" to the group so you know it worked
        try:
            await bot.send_message(event.chat.id, f"✅ Broadcaster Bot connected to '{event.chat.title}'")
        except:
            pass

# --- KEYBOARDS ---
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Broadcast Studio", callback_data="studio"))
    builder.row(InlineKeyboardButton(text="⚙️ Manage Groups", callback_data="manage_groups"))
    return builder.as_markup()

def studio_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 Add/Edit URL Button", callback_data="add_btn"))
    builder.row(InlineKeyboardButton(text="🚀 SEND TO ALL", callback_data="send_all"))
    builder.row(InlineKeyboardButton(text="🎯 SEND TO SELECTED", callback_data="send_selected"))
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"))
    return builder.as_markup()

# --- HANDLERS ---

@dp.message(Command("start"), F.from_user.id == ADMIN_ID)
async def start_cmd(message: Message):
    await message.answer("🛠 **Broadcast Control Center**", reply_markup=main_menu())

@dp.callback_query(F.data == "manage_groups")
async def manage_groups(callback: CallbackQuery):
    groups = db.get_all_groups()
    builder = InlineKeyboardBuilder()
    
    if not groups:
        await callback.message.edit_text(
            "❌ **No groups found.**\n\n1. Add the bot to a group.\n2. Make sure it is an Admin.\n3. Then check back here.",
            reply_markup=main_menu()
        )
        return

    for gid, title, active in groups:
        status = "✅" if active else "❌"
        builder.row(InlineKeyboardButton(text=f"{status} {title}", callback_data=f"toggle_{gid}"))
    
    builder.row(
        InlineKeyboardButton(text="Select All", callback_data="all_on"),
        InlineKeyboardButton(text="Deselect All", callback_data="all_off")
    )
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="cancel"))
    await callback.message.edit_text("🎯 **Select Target Groups**", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_group(callback: CallbackQuery):
    db.toggle_group(int(callback.data.split("_")[1]))
    await manage_groups(callback)

@dp.callback_query(F.data == "all_on")
async def all_on(callback: CallbackQuery):
    db.set_all_status(1)
    await manage_groups(callback)

@dp.callback_query(F.data == "all_off")
async def all_off(callback: CallbackQuery):
    db.set_all_status(0)
    await manage_groups(callback)

@dp.callback_query(F.data == "studio")
async def start_studio(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("📝 **Send your content** (text, image, video, etc.) to the bot.")
    await state.set_state(BroadcastStudio.waiting_for_content)

@dp.message(BroadcastStudio.waiting_for_content, F.from_user.id == ADMIN_ID)
async def catch_content(message: Message, state: FSMContext):
    await state.update_data(msg_id=message.message_id, btn_text=None, btn_url=None)
    await message.reply("✨ **Preview Created!**", reply_markup=studio_keyboard())

@dp.callback_query(F.data == "add_btn")
async def add_btn_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter button text (e.g. 'Visit Site'):")
    await state.set_state(BroadcastStudio.waiting_for_button_text)

@dp.message(BroadcastStudio.waiting_for_button_text)
async def catch_text(message: Message, state: FSMContext):
    await state.update_data(btn_text=message.text)
    await message.answer("Enter URL (starting with http):")
    await state.set_state(BroadcastStudio.waiting_for_button_url)

@dp.message(BroadcastStudio.waiting_for_button_url)
async def catch_url(message: Message, state: FSMContext):
    if not message.text.startswith("http"):
        await message.answer("❌ Invalid URL. Must start with http")
        return
    await state.update_data(btn_url=message.text)
    await message.answer("✅ Button added!", reply_markup=studio_keyboard())

@dp.callback_query(F.data.in_(["send_all", "send_selected"]))
async def process_send(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    only_active = (callback.data == "send_selected")
    groups = db.get_all_groups(only_active=only_active)

    if not groups:
        await callback.answer("❌ No groups to send to!", show_alert=True)
        return

    kb = None
    if data.get('btn_text'):
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text=data['btn_text'], url=data['btn_url']))
        kb = b.as_markup()

    status_msg = await callback.message.edit_text(f"🚀 Sending to {len(groups)} groups...")
    
    success = 0
    for gid, title, *extra in groups:
        try:
            await bot.copy_message(chat_id=gid, from_chat_id=callback.message.chat.id, 
                                   message_id=data['msg_id'], reply_markup=kb)
            success += 1
            await asyncio.sleep(0.1) # Safe speed
        except Exception as e:
            logging.error(f"Failed to send to {title}: {e}")

    await status_msg.edit_text(f"✅ **Broadcast Finished!**\n\nTotal Groups: {len(groups)}\nSuccess: {success}\nFailed: {len(groups)-success}", reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🛠 **Broadcast Control Center**", reply_markup=main_menu())

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())