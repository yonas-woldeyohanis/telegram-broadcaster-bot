import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
from dotenv import load_dotenv
from database import Database

# 1. SETUP & ENVIRONMENT
load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
db = Database("bot_database.db")

class BroadcastStudio(StatesGroup):
    waiting_for_content = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()

# 2. DUMMY WEB SERVER (FOR RENDER/UPTIMEROBOT)
async def handle(request):
    return web.Response(text="Bot is running and healthy!")

# 3. KEYBOARDS (UI)
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Broadcast Studio", callback_data="studio"))
    builder.row(InlineKeyboardButton(text="⚙️ Manage Groups", callback_data="manage_groups"))
    builder.row(InlineKeyboardButton(text="📊 Detailed Stats", callback_data="view_stats"))
    return builder.as_markup()

def studio_keyboard(has_btn=False):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 " + ("Edit Button" if has_btn else "Add URL Button"), callback_data="add_btn"))
    builder.row(InlineKeyboardButton(text="🚀 SEND TO ALL", callback_data="send_all"))
    builder.row(InlineKeyboardButton(text="🎯 SEND TO SELECTED", callback_data="send_selected"))
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"))
    return builder.as_markup()

# 4. SECURITY & AUTO-REGISTRATION
@dp.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated):
    # Only register if the ADMIN added the bot
    if event.from_user.id != ADMIN_ID:
        return
    if event.new_chat_member.status in ["member", "administrator"]:
        db.add_group(event.chat.id, event.chat.title)
        logging.info(f"Registered new group: {event.chat.title}")

@dp.message(Command("register"), F.from_user.id == ADMIN_ID)
async def manual_register(message: Message):
    if message.chat.type in ["group", "supergroup"]:
        db.add_group(message.chat.id, message.chat.title)
        await message.answer(f"✅ Group '{message.chat.title}' registered!")

# 5. COMMAND HANDLERS
@dp.message(Command("start"), F.from_user.id == ADMIN_ID)
async def start_cmd(message: Message):
    await message.answer("🛠 **Broadcast Control Center**", reply_markup=main_menu(), parse_mode="Markdown")

@dp.message(Command("stats"), F.from_user.id == ADMIN_ID)
async def stats_cmd(message: Message):
    groups = db.get_all_groups()
    b_stats = db.get_global_stats()
    text = (f"📈 **Stats**\n\nGroups: {len(groups)}\nBroadcasts: {b_stats[0]}\nDelivered: {b_stats[1]}")
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("clean"), F.from_user.id == ADMIN_ID)
async def clean_cmd(message: Message):
    msg = await message.answer("🔍 Cleaning database...")
    groups = db.get_all_groups()
    removed = 0
    for gid, title, *extra in groups:
        try: await bot.get_chat(gid)
        except:
            db.remove_group(gid)
            removed += 1
    await msg.edit_text(f"✅ Cleanup finished! Removed {removed} dead groups.")

# 6. BROADCAST STUDIO & BUTTON EDITOR
@dp.callback_query(F.data == "studio")
async def start_studio(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("📝 **Send your content** (text, photo, etc.) to the bot.")
    await state.set_state(BroadcastStudio.waiting_for_content)

@dp.message(BroadcastStudio.waiting_for_content, F.from_user.id == ADMIN_ID)
async def catch_content(message: Message, state: FSMContext):
    await state.update_data(msg_id=message.message_id, btn_text=None, btn_url=None)
    await message.reply("✨ **Preview Created!**", reply_markup=studio_keyboard())

@dp.callback_query(F.data == "add_btn")
async def add_btn_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter button text (e.g. 'Join Now'):")
    await state.set_state(BroadcastStudio.waiting_for_button_text)

@dp.message(BroadcastStudio.waiting_for_button_text)
async def catch_btn_text(message: Message, state: FSMContext):
    await state.update_data(btn_text=message.text)
    await message.answer("Now send the **URL** (must start with http):")
    await state.set_state(BroadcastStudio.waiting_for_button_url)

@dp.message(BroadcastStudio.waiting_for_button_url)
async def catch_url(message: Message, state: FSMContext):
    url_text = message.text.strip()
    if not url_text.lower().startswith("http"):
        await message.answer("❌ Invalid URL! Must start with http:// or https://")
        return
    await state.update_data(btn_url=url_text)
    await message.answer("✅ Button added to preview!", reply_markup=studio_keyboard(has_btn=True))

# 7. GROUP MANAGEMENT UI
@dp.callback_query(F.data == "manage_groups")
async def manage_groups(callback: CallbackQuery):
    groups = db.get_all_groups()
    builder = InlineKeyboardBuilder()
    if not groups:
        await callback.message.edit_text("❌ No groups found in database.", reply_markup=main_menu())
        return
    for gid, title, active in groups:
        status = "✅" if active else "❌"
        builder.row(InlineKeyboardButton(text=f"{status} {title}", callback_data=f"toggle_{gid}"))
    builder.row(InlineKeyboardButton(text="Select All", callback_data="all_on"), InlineKeyboardButton(text="Deselect All", callback_data="all_off"))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="cancel"))
    await callback.message.edit_text("🎯 **Target Selection**", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_group(callback: CallbackQuery):
    db.toggle_group(int(callback.data.split("_")[1]))
    await manage_groups(callback)

@dp.callback_query(F.data == "all_on")
async def all_on(callback: CallbackQuery):
    db.set_all_status(1); await manage_groups(callback)

@dp.callback_query(F.data == "all_off")
async def all_off(callback: CallbackQuery):
    db.set_all_status(0); await manage_groups(callback)

# 8. STATS CALLBACK
@dp.callback_query(F.data == "view_stats")
async def callback_stats(callback: CallbackQuery):
    groups = db.get_all_groups()
    active_count = len([g for g in groups if g[2] == 1])
    b_stats = db.get_global_stats()
    text = (f"📊 **Detailed Stats**\n\nTotal Groups: {len(groups)}\nActive: {active_count}\nBroadcasts: {b_stats[0]}\nMessages: {b_stats[1]}")
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="Markdown")
    await callback.answer()

# 9. EXECUTION LOGIC (SENDING)
@dp.callback_query(F.data.in_(["send_all", "send_selected"]))
async def process_send(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    only_active = (callback.data == "send_selected")
    groups = db.get_all_groups(only_active=only_active)

    if not groups:
        await callback.answer("⚠️ No groups selected!", show_alert=True); return

    kb = None
    if data.get('btn_text') and data.get('btn_url'):
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text=data['btn_text'], url=data['btn_url']))
        kb = b.as_markup()

    status_msg = await callback.message.edit_text(f"🚀 Sending to {len(groups)} groups...")
    success = 0
    for gid, title, *extra in groups:
        try:
            await bot.copy_message(chat_id=gid, from_chat_id=callback.message.chat.id, message_id=data['msg_id'], reply_markup=kb)
            success += 1
            await asyncio.sleep(0.1)
        except: continue

    db.update_broadcast_stats(success)
    await status_msg.edit_text(f"✅ **Done!**\nSent to {success} groups.", reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear(); await callback.message.edit_text("🛠 **Control Center**", reply_markup=main_menu())

# 10. CLOUD RUNTIME (DYNAMIC PORT)
async def main():
    PORT = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    asyncio.create_task(site.start())
    print(f"🚀 Bot live on port {PORT}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())