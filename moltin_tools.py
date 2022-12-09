from datetime import datetime
from urllib.parse import urljoin

import requests

_api_key = None
_expires = None


def get_api_key(base_url, client_id, client_secret):
    global _api_key
    global _expires
    url = urljoin(base_url, '/oauth/access_token')
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials',
    }
    current_time = datetime.now()
    timestamp = int(datetime.timestamp(current_time))

    if timestamp > _expires:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        token_params = response.json()
        _api_key = token_params['access_token']
        _expires = token_params['expires']

    return _api_key


def get_products(base_url, api_key):
    url = urljoin(base_url, '/pcm/products')
    headers = {'Authorization': f'Bearer {api_key}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()['data']


def add_product_to_cart(base_url, api_key, product_id, quantity, user_id):
    url = urljoin(base_url, f'/v2/carts/{user_id}/items')
    headers = {'Authorization': f'Bearer {api_key}'}
    payload = {
        "data": {
            "type": "cart_item",
            "id": product_id,
            "quantity": int(quantity),
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def get_cart(base_url, api_key, user_id):
    headers = {'Authorization': f'Bearer {api_key}'}
    url = urljoin(base_url, f'/v2/carts/{user_id}/items')
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_product(base_url, api_key, product_id):
    headers = {'Authorization': f'Bearer {api_key}'}
    url = urljoin(base_url, f'/catalog/products/{product_id}')
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()['data']


def fetch_image(base_url, api_key, image_id):
    headers = {'Authorization': f'Bearer {api_key}'}
    url = urljoin(base_url, f'/v2/files/{image_id}')
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]["link"]["href"]


def remove_item_from_cart(base_url, api_key, user_id, product_id):
    headers = {'Authorization': f'Bearer {api_key}'}
    url = urljoin(base_url, f'/v2/carts/{user_id}/items/{product_id}')
    response = requests.delete(url, headers=headers)
    response.raise_for_status()


def create_customer(base_url, api_key, user_id, email):
    headers = {'Authorization': f'Bearer {api_key}'}
    url = urljoin(base_url, '/v2/customers')
    payload = {
        "data": {
            "type": "customer",
            "name": user_id,
            "email": email,
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()['data']['id']


def get_customer(base_url, api_key, customer_id):
    headers = {'Authorization': f'Bearer {api_key}'}
    url = urljoin(base_url, f'/v2/customers/{customer_id}')
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def update_customer(base_url, api_key, customer_id, email):
    headers = {'Authorization': f'Bearer {api_key}'}
    url = urljoin(base_url, f'/v2/customers/{customer_id}')
    payload = {
        "data": {
            "type": "customer",
            "email": email,
        }
    }
    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

