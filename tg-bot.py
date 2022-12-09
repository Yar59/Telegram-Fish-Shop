import logging
from textwrap import dedent
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
    create_customer
)

logger = logging.getLogger(__name__)

(
    START,
    HANDLE_MENU,
    HANDLE_DESCRIPTION,
    HANDLE_CART,
    WAITING_EMAIL,
) = range(5)
(
    MENU,
    DESCRIPTION,
    CART,
    ORDER,
) = range(4)


def get_state_after_reload(update: Update, context: CallbackContext, redis_db):
    query = update.callback_query
    if query:
        query.answer()
    user_id = update.effective_chat.id
    current_state = int(redis_db.get(user_id))
    return current_state


def start(update: Update, context: CallbackContext, base_url, api_key, redis_db):
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
    next_state = HANDLE_MENU
    redis_db.set(user_id, next_state)
    return next_state


def start_over(update: Update, context: CallbackContext, base_url, api_key, redis_db) -> int:
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
    query.message.reply_text(
        text='Показываем рыбов:',
        reply_markup=reply_markup
    )
    query.message.delete()
    next_state = HANDLE_MENU
    redis_db.set(user_id, next_state)
    return next_state


def cancel(update: Update, context: CallbackContext, redis_db) -> int:
    user_id = update.effective_chat.id
    update.message.reply_text(
        'Надеюсь тебе понравился наш магазин!'
    )
    next_state = ConversationHandler.END
    redis_db.set(user_id, next_state)
    return next_state


def handle_menu(update: Update, context: CallbackContext, base_url, api_key, redis_db) -> int:
    query = update.callback_query
    query.answer()
    user_id = update.effective_chat.id
    product_id = query['data']
    product = get_product(base_url, api_key, product_id)
    image_link = fetch_image(base_url, api_key, product['relationships']['main_image']['data']['id'])
    message = dedent(f'''
        {product["attributes"]["name"]}
        {product["attributes"]["description"]}
        Цена за кг: {product["meta"]["display_price"]["with_tax"]["formatted"]}
    ''')
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
    query.message.reply_photo(
        photo=image_link,
        caption=message,
        reply_markup=reply_markup,
    )
    query.message.delete()
    next_state = HANDLE_DESCRIPTION
    redis_db.set(user_id, next_state)
    return next_state


def handle_description(update: Update, context: CallbackContext, base_url, api_key, redis_db) -> int:
    query = update.callback_query
    query.answer()
    quantity, product_id = query['data'].split('|')
    user_id = update.effective_chat.id
    add_product_to_cart(base_url, api_key, product_id, quantity, user_id)
    next_state = HANDLE_DESCRIPTION
    redis_db.set(user_id, next_state)
    return next_state


def handle_cart(update: Update, context: CallbackContext, base_url, api_key, redis_db) -> int:
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
            dedent(f'''
                {item_name}
                {item_price_formatted} за кг
                {item_quantity} кг за {item_cost_formatted}
            ''')
        )
    message = f'{"".join(items_info)}\nСтоимость корзины {total_cost/100} $'
    keyboard = [
        [InlineKeyboardButton(f'Удалить {name} из корзины', callback_data=f'del|{product_id}')]
        for name, product_id in fish_names_ids.items()
    ]
    keyboard.append(
        [
            InlineKeyboardButton('Меню', callback_data=str(MENU)),
            InlineKeyboardButton('Оформить заказ', callback_data=str(ORDER)),
        ],
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.message.reply_text(
        text=message,
        reply_markup=reply_markup,
    )
    query.message.delete()
    next_state = HANDLE_CART
    redis_db.set(user_id, next_state)
    return next_state


def handle_order(update: Update, context: CallbackContext, base_url, api_key, redis_db) -> int:
    query = update.callback_query
    query.answer()
    user_id = update.effective_chat.id
    if query['data'] == str(ORDER):
        message = 'Пришлите, пожалуйста, вашу электронную почту.'

    keyboard = [
        InlineKeyboardButton('Меню', callback_data=str(MENU)),
        InlineKeyboardButton('Корзина', callback_data=str(CART)),
    ],
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.reply_text(
        text=message,
        reply_markup=reply_markup,
    )
    query.message.delete()
    next_state = WAITING_EMAIL
    redis_db.set(user_id, next_state)
    return next_state


def handle_email(update: Update, context: CallbackContext, base_url, api_key, redis_db) -> int:
    user_id = update.effective_chat.id
    if '@' in update.message.text:
        customer_email = update.message.text.strip()
        message = f'Записал Вашу почту {customer_email}'
        update.message.reply_text(
            text=message,
        )
        create_customer(base_url, api_key, user_id, message)
        next_state = ConversationHandler.END
        redis_db.set(user_id, next_state)
        return next_state
    else:
        message = 'Это не похоже на почту, попробуйте еще раз.'
        update.message.reply_text(
            text=message,
        )
        next_state = WAITING_EMAIL
        redis_db.set(user_id, next_state)
        return next_state


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
        entry_points=[
            CommandHandler(
                'start',
                partial(start, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db)
            ),
            CallbackQueryHandler(partial(get_state_after_reload, redis_db=redis_db)),
            MessageHandler(Filters.text, partial(get_state_after_reload, redis_db=redis_db)),
        ],
        states={
            HANDLE_MENU: [
                CallbackQueryHandler(
                    partial(handle_cart, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db),
                    pattern=f'^{CART}$'
                ),
                CallbackQueryHandler(
                    partial(handle_menu, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db)
                )
            ],
            HANDLE_DESCRIPTION: [
                CallbackQueryHandler(
                    partial(start_over, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db),
                    pattern=f'^{MENU}$'
                ),
                CallbackQueryHandler(
                    partial(handle_cart, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db),
                    pattern=f'^{CART}$'
                ),
                CallbackQueryHandler(
                    partial(handle_description, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db)
                )
            ],
            HANDLE_CART: [
                CallbackQueryHandler(
                    partial(start_over, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db),
                    pattern=f'^{MENU}$'
                ),
                CallbackQueryHandler(
                    partial(handle_order, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db),
                    pattern=f'^{ORDER}$'
                ),
                CallbackQueryHandler(
                    partial(handle_cart, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db)
                )
            ],
            WAITING_EMAIL: [
                CallbackQueryHandler(
                    partial(start_over, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db),
                    pattern=f'^{MENU}$'
                ),
                CallbackQueryHandler(
                    partial(handle_cart, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db),
                    pattern=f'^{CART}$'
                ),
                MessageHandler(Filters.text, partial(handle_email, base_url=moltin_base_url, api_key=api_key, redis_db=redis_db))
            ]
        },
        fallbacks=[
            CommandHandler('cancel', partial(cancel, redis_db=redis_db)),
            CommandHandler('start', partial(cancel, redis_db=redis_db)),
        ],
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()


if __name__ == '__main__':
    main()

