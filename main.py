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

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
db = Database("bot_database.db")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

class BroadcastStudio(StatesGroup):
    waiting_for_content = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()

# --- DUMMY WEB SERVER FOR RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

# --- KEYBOARDS ---
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Broadcast Studio", callback_data="studio"))
    builder.row(InlineKeyboardButton(text="⚙️ Manage Groups", callback_data="manage_groups"))
    builder.row(InlineKeyboardButton(text="📊 Detailed Stats", callback_data="view_stats"))
    # We add a small return button if we are already in a sub-menu
    return builder.as_markup()

# --- COMMAND HANDLERS ---

@dp.message(Command("start"), F.from_user.id == ADMIN_ID)
async def start_cmd(message: Message):
    await message.answer(f"👋 **Welcome Back, Commander!**\nUse the menu below to manage your empire.", reply_markup=main_menu(), parse_mode="Markdown")

@dp.message(Command("stats"), F.from_user.id == ADMIN_ID)
async def stats_cmd(message: Message):
    groups = db.get_all_groups()
    active_count = len([g for g in groups if g[2] == 1])
    b_stats = db.get_global_stats()
    
    text = (
        "📈 **Global Statistics**\n\n"
        f"👥 Total Groups: {len(groups)}\n"
        f"🎯 Active Targets: {active_count}\n"
        f"🚀 Total Broadcasts: {b_stats[0]}\n"
        f"📩 Total Messages Delivered: {b_stats[1]}"
    )
    await message.answer(text, parse_mode="Markdown")



# --- CALLBACK HANDLER FOR THE STATS BUTTON ---
@dp.callback_query(F.data == "view_stats")
async def callback_stats(callback: CallbackQuery):
    groups = db.get_all_groups()
    active_count = len([g for g in groups if g[2] == 1])
    b_stats = db.get_global_stats()
    
    stats_text = (
        "📊 **Detailed Statistics**\n\n"
        f"👥 **Total Groups:** {len(groups)}\n"
        f"🎯 **Active Targets:** {active_count}\n"
        f"🚀 **Total Broadcasts:** {b_stats[0]}\n"
        f"📩 **Messages Delivered:** {b_stats[1]}\n\n"
        "*(Note: 'Active' groups are those with a ✅ in Manage Groups)*"
    )
    
    # We use edit_text to keep the chat clean
    await callback.message.edit_text(
        stats_text, 
        reply_markup=main_menu(), 
        parse_mode="Markdown"
    )
    # This removes the "loading" spinner on the button
    await callback.answer()

@dp.message(Command("help"), F.from_user.id == ADMIN_ID)
async def help_cmd(message: Message):
    help_text = (
        "📖 **Broadcaster Bot Guide**\n\n"
        "1. Add the bot to your groups as Admin.\n"
        "2. Use **Manage Groups** to select which ones should receive messages.\n"
        "3. Use **Broadcast Studio** to create your post.\n"
        "4. You can add a URL button to any post.\n\n"
        "**Commands:**\n"
        "/start - Main Menu\n"
        "/stats - Quick Stats\n"
        "/clean - Remove groups where bot was kicked"
    )
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("clean"), F.from_user.id == ADMIN_ID)
async def clean_cmd(message: Message):
    msg = await message.answer("🔍 Checking all groups... this may take a moment.")
    groups = db.get_all_groups()
    removed = 0
    for gid, title, *extra in groups:
        try:
            await bot.get_chat(gid)
        except:
            db.remove_group(gid)
            removed += 1
    await msg.edit_text(f"✅ Cleanup finished!\nRemoved {removed} dead groups from database.")

# --- BROADCAST LOGIC ---

@dp.callback_query(F.data == "studio")
async def start_studio(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("📝 **Send your content** (text, photo, etc.) to the bot.")
    await state.set_state(BroadcastStudio.waiting_for_content)

@dp.message(BroadcastStudio.waiting_for_content, F.from_user.id == ADMIN_ID)
async def catch_content(message: Message, state: FSMContext):
    await state.update_data(msg_id=message.message_id)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 Add URL Button", callback_data="add_btn"))
    builder.row(InlineKeyboardButton(text="🚀 SEND TO ALL", callback_data="send_all"))
    builder.row(InlineKeyboardButton(text="🎯 SEND TO SELECTED", callback_data="send_selected"))
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"))
    await message.reply("✨ **Preview Created!**", reply_markup=builder.as_markup())

# --- FIXED URL CATCHER ---
@dp.message(BroadcastStudio.waiting_for_button_url)
async def catch_url(message: Message, state: FSMContext):
    url_text = message.text.strip() # REMOVES SPACES
    if not url_text.lower().startswith("http"): # CASE INSENSITIVE CHECK
        await message.answer("❌ Invalid URL. It must start with `http://` or `https://`", parse_mode="Markdown")
        return
    
    await state.update_data(btn_url=url_text)
    data = await state.get_data()
    
    # Re-show the preview options
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"✅ Button Attached: {data['btn_text']}", callback_data="add_btn"))
    builder.row(InlineKeyboardButton(text="🚀 SEND TO ALL", callback_data="send_all"))
    builder.row(InlineKeyboardButton(text="🎯 SEND TO SELECTED", callback_data="send_selected"))
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"))
    await message.answer("✨ **Button successfully added to preview!**", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "add_btn")
async def add_btn_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter button text (e.g. 'Join Channel'):")
    await state.set_state(BroadcastStudio.waiting_for_button_text)

@dp.message(BroadcastStudio.waiting_for_button_text)
async def catch_btn_text(message: Message, state: FSMContext):
    await state.update_data(btn_text=message.text)
    await message.answer("Now send the **URL** (starting with http):")
    await state.set_state(BroadcastStudio.waiting_for_button_url)

# --- SENDING LOGIC ---
@dp.callback_query(F.data.in_(["send_all", "send_selected"]))
async def process_send(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    only_active = (callback.data == "send_selected")
    groups = db.get_all_groups(only_active=only_active)

    if not groups:
        await callback.answer("⚠️ No groups selected! Go to 'Manage Groups' first.", show_alert=True)
        return

    kb = None
    if data.get('btn_text') and data.get('btn_url'):
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
            await asyncio.sleep(0.1) 
        except: continue

    db.update_broadcast_stats(success)
    await status_msg.edit_text(f"✅ **Broadcast Done!**\nSuccess: {success}", reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data == "manage_groups")
async def manage_groups(callback: CallbackQuery):
    groups = db.get_all_groups()
    builder = InlineKeyboardBuilder()
    if not groups:
        await callback.message.edit_text("❌ No groups found.", reply_markup=main_menu())
        return

    for gid, title, active in groups:
        status = "✅" if active else "❌"
        builder.row(InlineKeyboardButton(text=f"{status} {title}", callback_data=f"toggle_{gid}"))
    builder.row(InlineKeyboardButton(text="Select All", callback_data="all_on"), InlineKeyboardButton(text="Deselect All", callback_data="all_off"))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="cancel"))
    await callback.message.edit_text("🎯 **Manage Targets**", reply_markup=builder.as_markup())

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

@dp.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear(); await callback.message.edit_text("🛠 **Control Center**", reply_markup=main_menu())

@dp.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated):
    if event.new_chat_member.status in ["member", "administrator"]:
        db.add_group(event.chat.id, event.chat.title)

async def main():
    # Setup dummy server for Render
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    asyncio.create_task(site.start())

    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())