from aiogram import Bot, Dispatcher, types, executor
from aiogram.types.message import ContentType
from PIL import Image
from config import api_token, sponsor_channel_link, sponsor_channel_id
import shutil
import os
import logging

dir_path = os.path.dirname(os.path.realpath(__file__))

# Set up logging configuration to save logs to 'pdfbot.log'
log_file_path = dir_path + '/pdfbot.log'

logging.basicConfig(
    filename=log_file_path,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Initialize Telegram bot and Dispatcher
bot = Bot(token=api_token)
dp = Dispatcher(bot)

# Dictionaries to store photo IDs and PDF names for each user
photos_id = {}
pdf_names = {}


async def is_channel_member(user_id):
    member = await bot.get_chat_member(sponsor_channel_id, user_id)
    if member.status == 'member' or member.status == 'administrator' or member.status == 'creator':
        return True
    return False


@dp.message_handler(commands='start')
async def show_main_list(message: types.Message):
    keyboard_markup = types.InlineKeyboardMarkup(row_width=2)
    keyboard_markup.add(types.InlineKeyboardButton('Join!', sponsor_channel_link))

    await message.reply('Hi, now send me the images that you want convert to PDF. '
                        '\n\nyou will be notified about added images,'
                        '\n\nif you need high quality PDF send images as file!'
                        '\n\nthis bot is totally free with NO watermarks! but you need to join the below channel to use it.',
                        reply_markup=keyboard_markup)


# Function to create and return a keyboard markup for converting images or removing added images
def get_convert_and_delete_keyboard():
    images_keyboard_markup = types.InlineKeyboardMarkup(row_width=1)
    text_and_data = (
        ('Convert to pdf', 'Convert to pdf'),
        ('Remove added images', 'Remove added images'))
    row_btns = (types.InlineKeyboardButton(text, callback_data=data) for text, data in text_and_data)
    images_keyboard_markup.add(*row_btns)
    return images_keyboard_markup


def get_rename_pdf_keyboard():
    images_keyboard_markup = types.InlineKeyboardMarkup(row_width=2)
    text_and_data = (
        ('Yes!', 'yes'),
        ('No!', 'no'))
    row_btns = (types.InlineKeyboardButton(text, callback_data=data) for text, data in text_and_data)
    images_keyboard_markup.add(*row_btns)
    return images_keyboard_markup

# Handler for incoming document messages (for high-quality images)
@dp.message_handler(content_types=ContentType.DOCUMENT)
async def get_user_images_hq(message: types.Message):
    if message.document.mime_type.split('/')[0] == 'image':
        user_id = str(message.chat.id)

        if not await is_channel_member(user_id):
            keyboard_markup = types.InlineKeyboardMarkup(row_width=2)
            keyboard_markup.add(types.InlineKeyboardButton('Join!', sponsor_channel_link))

            return await message.reply(text='please join below channel first.', reply_markup=keyboard_markup)

        else:
            count = 1

            for key, val in photos_id.items():
                if list(val.keys())[0] == user_id:
                    count += 1
            try:
                photos_id[message.document.file_id] = {user_id: count}
            except Exception as e:
                print(e)
                pass

            await message.reply(text=f'Your image added! \nnumber of added images: {count}',
                                reply_markup=get_convert_and_delete_keyboard())


@dp.message_handler(content_types=ContentType.PHOTO)
async def get_user_images(message: types.Message):
    user_id = str(message.chat.id)
    count = 1
    # Count the number of added images for the user
    if not await is_channel_member(user_id):
        keyboard_markup = types.InlineKeyboardMarkup(row_width=2)
        keyboard_markup.add(types.InlineKeyboardButton('Join!', sponsor_channel_link))

        return await message.reply(text='please join below channel first.', reply_markup=keyboard_markup)
    else:
        for key, val in photos_id.items():
            if list(val.keys())[0] == user_id:
                count += 1
        try:
            photos_id[message.photo[2].file_id] = {user_id: count}
        except IndexError:
            try:
                photos_id[message.photo[1].file_id] = {user_id: count}
            except IndexError:
                photos_id[message.photo[0].file_id] = {user_id: count}

        await message.reply(text=f'Your image added! \nnumber of added images: {count}',
                            reply_markup=get_convert_and_delete_keyboard())


def delete_user_data(user_id):
    user_photos_to_remove = []

    # Find user's photos and store them for removal
    for key, val in photos_id.items():
        if list(val.keys())[0] == user_id:
            user_photos_to_remove.append(key)

        # Delete photos from photos_id dictionary
    for el in user_photos_to_remove:
        del photos_id[el]

    try:
        shutil.rmtree(dir_path + '/UserData/' + user_id)
    except (FileExistsError, FileNotFoundError):
        pass

    try:
        pdf_names.pop(user_id)
    except KeyError:
        pass


@dp.callback_query_handler(text='Convert to pdf')
async def convert_to_pdf(query: types.CallbackQuery):
    await query.answer('')
    await bot.send_message(query.message.chat.id, 'Do you want to set pdf name?',
                           reply_markup=get_rename_pdf_keyboard())


@dp.callback_query_handler(text='yes')
async def send_pdf_name(query: types.CallbackQuery):
    await bot.edit_message_text(chat_id=query.message.chat.id, text='Send you\'r prefer name as english words:',
                                message_id=query.message.message_id)
    await query.answer('')


@dp.message_handler()
async def set_pdf_name(message: types.Message):
    user_id = str(message.chat.id)
    pdf_names[user_id] = message.text

    try:
        pdf_path = f'{dir_path}/UserData/{user_id}/{pdf_names[user_id]}.pdf'
        await image_to_pdf(user_id, pdf_path)

    except KeyError:
        print(KeyError)
        pdf_path = f'{dir_path}/UserData/{user_id}/converted.pdf'
        await image_to_pdf(user_id, pdf_path)

    except IndexError:
        await bot.send_message(message.chat.id, 'Please send you\'r images...')
        return

    pdf = types.InputFile(pdf_path)
    await bot.send_document(user_id, pdf)

    delete_user_data(user_id)

# Callback handler for 'no' response to convert without setting a PDF name
@dp.callback_query_handler(text='no')
async def convert_to_pdf(query: types.CallbackQuery):
    await query.answer('Processing...')
    await bot.edit_message_text(chat_id=query.message.chat.id, text='Processing...',
                                message_id=query.message.message_id)
    user_id = str(query.message.chat.id)

    try:
        pdf_path = f'{dir_path}/UserData/{user_id}/{pdf_names[user_id]}.pdf'
        await image_to_pdf(user_id, pdf_path)

    except KeyError:
        try:
            pdf_path = f'{dir_path}/UserData/{user_id}/converted.pdf'
            await image_to_pdf(user_id, pdf_path)

        except IndexError:
            await bot.send_message(query.message.chat.id, 'Please send you\'r images first...')
            return

    except IndexError:
        await bot.send_message(query.message.chat.id, 'Please send you\'r images first...')
        return

    pdf = types.InputFile(pdf_path)
    await bot.send_document(user_id, pdf)

    delete_user_data(user_id)

# Function to convert user's images to a PDF
async def image_to_pdf(user_id, pdf_path):
    try:
        os.makedirs(dir_path + '/UserData/' + user_id)
    except FileExistsError:
        pass
    temp_photos_id = photos_id.copy()

    temp_photos_id.keys()
    for key, val in temp_photos_id.items():

        if list(val.keys())[0] == user_id:
            await bot.download_file_by_id(key, dir_path + '/UserData/' + user_id + '/' + str(val[user_id]) + '.jpg')

    images = []
    try:
        images_name = sorted([int(el[:-4]) for el in os.listdir(dir_path + '/UserData/' + user_id)])

        # Open and convert images to RGB format
        for im in images_name:
            images.append(Image.open(dir_path + '/UserData/' + user_id + '/' + str(im) + '.jpg'))
        images = [im.convert('RGB') for im in images]
    except Exception as e:
        print(e)
        pass

    images[0].save(pdf_path,
                   save_all=True, append_images=images[1:])
    return True

# Callback handler for 'Remove added images' button
@dp.callback_query_handler(text='Remove added images')
async def delete_images(query: types.CallbackQuery):
    user_id = str(query.message.chat.id)

    await query.answer('Added images removed.')

    delete_user_data(user_id)

    await bot.send_message(query.message.chat.id, 'Your added images have been deleted!'
                                                  ' \n\nnow you can send images again.')


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
