import logging
from functools import partial

import redis
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler
)
from environs import Env

from moltin_tools import (
    get_api_key,
    get_products,
    get_cart,
    add_product_to_cart,
    get_product,
    fetch_image,
    remove_item_from_cart,
)

logger = logging.getLogger(__name__)

(
    START,
    HANDLE_MENU,
    HANDLE_DESCRIPTION,
    HANDLE_CART
) = range(4)
(
    MENU,
    DESCRIPTION,
    CART,
) = range(3)


def start(update: Update, context: CallbackContext, base_url, api_key):
    products = get_products(base_url, api_key)
    user_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton(product['attributes']['name'], callback_data=product['id'])]
        for product in products
    ]
    keyboard.append(
        [
            InlineKeyboardButton('Корзина', callback_data=str(CART)),
        ],
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        text='Показываем рыбов:',
        reply_markup=reply_markup
    )
    return HANDLE_MENU


def start_over(update: Update, context: CallbackContext, base_url, api_key) -> int:
    query = update.callback_query
    query.answer()
    products = get_products(base_url, api_key)
    user_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton(product['attributes']['name'], callback_data=product['id'])]
        for product in products
    ]
    keyboard.append(
        [
            InlineKeyboardButton('Корзина', callback_data=str(CART)),
        ],
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.delete()
    query.message.reply_text(
        text='Показываем рыбов:',
        reply_markup=reply_markup
    )
    return HANDLE_MENU


def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        'Надеюсь тебе понравился наш магазин!'
    )
    return ConversationHandler.END


def handle_menu(update: Update, context: CallbackContext, base_url, api_key) -> int:
    query = update.callback_query
    query.answer()
    product_id = query['data']
    product = get_product(base_url, api_key, product_id)
    image_link = fetch_image(base_url, api_key, product['relationships']['main_image']['data']['id'])
    message = f'{product["attributes"]["name"]}\n{product["attributes"]["description"]}\n' \
              f'Цена за кг: {product["meta"]["display_price"]["with_tax"]["formatted"]}'
    keyboard = [
        [
            InlineKeyboardButton('1 кг', callback_data=f'1|{product_id}'),
            InlineKeyboardButton('5 кг', callback_data=f'5|{product_id}'),
            InlineKeyboardButton('10 кг', callback_data=f'10|{product_id}'),
        ],
        [
            InlineKeyboardButton('Корзина', callback_data=str(CART)),
            InlineKeyboardButton('Назад', callback_data=str(MENU)),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.delete()
    query.message.reply_photo(
        photo=image_link,
        caption=message,
        reply_markup=reply_markup,
    )
    return HANDLE_DESCRIPTION


def handle_description(update: Update, context: CallbackContext, base_url, api_key) -> int:
    query = update.callback_query
    query.answer()
    quantity, product_id = query['data'].split('|')
    user_id = update.effective_chat.id
    add_product_to_cart(base_url, api_key, product_id, quantity, user_id)
    return HANDLE_DESCRIPTION


def handle_cart(update: Update, context: CallbackContext, base_url, api_key) -> int:
    query = update.callback_query
    query.answer()
    user_id = update.effective_chat.id
    if '|' in query['data']:
        action, product_id = query['data'].split('|')
        remove_item_from_cart(base_url, api_key, user_id, product_id)
    cart = get_cart(base_url, api_key, user_id)
    fish_names_ids = {}
    total_cost = 0
    items_info = []
    for item in cart['data']:
        item_name = item['name']
        item_id = item['id']
        fish_names_ids[item_name] = item_id
        item_price = item['value']['amount']
        item_price_formatted = f'{item_price / 100} $'
        item_quantity = item['quantity']
        item_cost = item_price * item_quantity
        total_cost += item_cost
        item_cost_formatted = f'{item_cost / 100} $'
        items_info.append(
            f'{item_name}\n{item_price_formatted} за кг\n{item_quantity} кг за {item_cost_formatted}\n\n'
        )
    message = f'{"".join(items_info)}\nСтоимость корзины {total_cost/100} $'
    keyboard = [
        [InlineKeyboardButton(f'Удалить {name} из корзины', callback_data=f'del|{product_id}')]
        for name, product_id in fish_names_ids.items()
    ]
    keyboard.append(
        [
            InlineKeyboardButton('Меню', callback_data=str(MENU)),
        ],
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.message.delete()
    query.message.reply_text(
        text=message,
        reply_markup=reply_markup,
    )
    return HANDLE_CART


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    env = Env()
    env.read_env()
    tg_token = env('TG_TOKEN')
    redis_host = env('REDIS_HOST')
    redis_port = env('REDIS_PORT')
    redis_db = env('REDIS_DB', 0)
    redis_username = env('REDIS_USERNAME')
    redis_password = env('REDIS_PASSWORD')
    moltin_client_id = env('MOLTIN_CLIENT_ID')
    moltin_client_secret = env('MOLTIN_CLIENT_SECRET')
    moltin_base_url = env('MOLTIN_BASE_URL')
    api_key = get_api_key(moltin_base_url, moltin_client_id, moltin_client_secret)

    redis_db = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        username=redis_username,
        password=redis_password,
        decode_responses=True
    )

    updater = Updater(token=tg_token)

    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', partial(start, base_url=moltin_base_url, api_key=api_key))],
        states={
            HANDLE_MENU: [
                CallbackQueryHandler(
                    partial(handle_cart, base_url=moltin_base_url, api_key=api_key),
                    pattern='^' + str(CART) + '$'
                ),
                CallbackQueryHandler(partial(handle_menu, base_url=moltin_base_url, api_key=api_key))
            ],
            HANDLE_DESCRIPTION: [
                CallbackQueryHandler(
                    partial(start_over, base_url=moltin_base_url, api_key=api_key),
                    pattern='^' + str(MENU) + '$'
                ),
                CallbackQueryHandler(
                    partial(handle_cart, base_url=moltin_base_url, api_key=api_key),
                    pattern='^' + str(CART) + '$'
                ),
                CallbackQueryHandler(partial(handle_description, base_url=moltin_base_url, api_key=api_key))
            ],
            HANDLE_CART: [
                CallbackQueryHandler(
                    partial(start_over, base_url=moltin_base_url, api_key=api_key),
                    pattern='^' + str(MENU) + '$'
                ),
                CallbackQueryHandler(partial(handle_cart, base_url=moltin_base_url, api_key=api_key))
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('start', cancel),
        ],
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()


if __name__ == '__main__':
    main()

