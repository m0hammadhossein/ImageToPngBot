from datetime import timedelta
from os import remove
from asyncio import sleep
import motor.motor_asyncio
from pyrogram import Client, filters, enums, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from uvloop import install
from utils.config import API_ID, API_HASH, TOKEN, DB_USER, DB_PASS, SUDO, DB_NAME
from utils.convert import convert_img
from utils.filters import step_filter

install()
client = Client('bot', api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN)
db = motor.motor_asyncio.AsyncIOMotorClient(f'mongodb://{DB_USER}:{DB_PASS}@127.0.0.1:27017/{DB_NAME}')[DB_NAME]


async def pagination(page_size, page_num=1):
    while True:
        skips = page_size * (page_num - 1)
        results = list(await db['users'].find().skip(skips).limit(page_size))
        if results:
            page_num += 1
            yield results
        else:
            break


@client.on_message()
async def check_spam(_, msg):
    user_info = await db['users'].find_one({'_id': msg.from_user.id})
    if msg.from_user.id == SUDO:
        if user_info:
            setattr(msg, 'step', user_info['step'])
            setattr(msg, 'is_converting', user_info['is_converting'])
        else:
            await db['users'].insert_one({
                '_id': msg.from_user.id,
                'is_converting': False,
                'step': 'empty'
            })
            setattr(msg, 'step', 'empty')
            setattr(msg, 'is_converting', False)
        msg.continue_propagation()
    if user_info:
        if user_info['block']:
            msg.stop_propagation()
        if msg.date < (user_info['date'] + timedelta(seconds=5)):
            if user_info['cn_spam'] >= 3:
                await db['users'].update_one({'_id': msg.from_user.id}, {'$set': {'cn_spam': 0, 'block': True}})
                await msg.reply_text('<b>You were blocked due to spam</b>', parse_mode=enums.ParseMode.HTML)
            else:
                await db['users'].update_one(
                    {'_id': msg.from_user.id},
                    {'$set': {'cn_spam': user_info['cn_spam'] + 1}}
                )
        else:
            await db['users'].update_one({'_id': msg.from_user.id}, {'$set': {'date': msg.date, 'cn_spam': 0}})
        setattr(msg, 'is_converting', user_info['is_converting'])
    else:
        await db['users'].insert_one({
            '_id': msg.from_user.id,
            'block': False,
            'cn_spam': 0,
            'date': msg.date,
            'is_converting': False})
        setattr(msg, 'is_converting', False)
    msg.continue_propagation()


@client.on_message(filters.user(SUDO) & step_filter('fwd'))
async def forward_msg(_, msg):
    await db['users'].update_one({'_id': SUDO}, {'$set': {'step': 'is_fwd'}})
    await msg.reply_text('The message sending operation has started')
    success_send = 0
    async for members in pagination(20):
        for mem in members:
            try:
                await msg.copy(mem['_id'])
                success_send += 1
            except errors.FloodWait as ex:
                await sleep(ex.value)
                await msg.copy(mem['_id'])
                success_send += 1
            except errors.UserBlocked:
                continue
        await sleep(5)
    await db['users'].update_one({'_id': SUDO}, {'$set': {'step': 'empty'}})
    await msg.reply_text(f'Your message was successfully sent to {success_send} users')


@client.on_message(filters.user(SUDO) & filters.regex(r'^/unblock (\d+)$'))
async def unblock_user(_, msg):
    await db['users'].update_one({'_id': int(msg.matches[0].group(1))}, {'$set': {'block': False}})
    await msg.reply_text('Done')


@client.on_message(filters.user(SUDO) & filters.regex(r'^/block (\d+)$'))
async def block_user(_, msg):
    await db['users'].update_one({'_id': int(msg.matches[0].group(1))}, {'$set': {'block': True}})
    await msg.reply_text('Done')


@client.on_message(filters.user(SUDO) & filters.command('panel'))
async def panel(_, msg):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton('👤statistics', callback_data='statistics'),
            InlineKeyboardButton('🚫Blocked users', callback_data='block'),
        ],
        [
            InlineKeyboardButton('🗣Public submission', callback_data='fwd')
        ]
    ])
    await msg.reply_text('<b>⚙️Admin panel⚙️</b>', parse_mode=enums.ParseMode.HTML, reply_markup=keyboard)


@client.on_message(filters.command('start'))
async def block_user(_, msg):
    await msg.reply_text('''Hi, welcome.
Please submit your photo for format conversion''')


@client.on_message(filters.photo)
async def convert(_, msg):
    if msg.is_converting:
        await msg.reply_text('Please wait until the previous photo is converted')
    else:
        if msg.photo.file_size <= 5242880:
            await db['users'].update_one({'_id': msg.from_user.id}, {'$set': {'is_converting': True}})
            await msg.reply_text('Please wait...')
            path = await msg.download()
            await convert_img(path, f'{msg.chat.id}-{msg.id}.png')
            await msg.reply_document(f'{msg.chat.id}-{msg.id}.png')
            remove(path)
            remove(f'{msg.chat.id}-{msg.id}.png')
            await db['users'].update_one({'_id': msg.from_user.id}, {'$set': {'is_converting': False}})
        else:
            await msg.reply_text('The maximum size of the photo should be 5 MB')


@client.on_callback_query(filters.user(SUDO))
async def check_data(_, cl: CallbackQuery):
    information = await db['users'].find_one({'_id': SUDO})
    if information['step'] in ('empty', 'is_fwd'):
        if cl.data == 'statistics':
            cn = await db['users'].count_documents({})
            await cl.answer(f'Number of users including yourself : {cn}', show_alert=True)
        elif cl.data == 'block':
            cn = await db['users'].count_documents({'block': True})
            await cl.answer(f'Number of blocked users : {cn}', show_alert=True)
        elif cl.data == 'fwd':
            if information['step'] == 'is_fwd':
                await cl.answer('Please wait until the end of the previous operation')
            else:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='cancel')]])
                await db['users'].update_one({'_id': SUDO}, {'$set': {'step': 'fwd'}})
                await cl.message.reply_text('Please send your message.', reply_markup=keyboard)
    else:
        if cl.data == 'cancel':
            db['users'].update_one({'_id': SUDO}, {'$set': {'step': 'empty'}})
            await cl.message.edit_text('The operation was canceled')
        else:
            await cl.answer('Please complete or cancel the previous operation first', show_alert=True)


client.run()
