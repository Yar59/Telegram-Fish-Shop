import os
from pprint import pprint
from urllib.parse import urljoin
import requests
from environs import Env


def get_api_key(base_url, client_id, client_secret):
    url = urljoin(base_url, '/oauth/access_token')
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials',
    }
    response = requests.post(url, data=payload)
    response.raise_for_status()
    return response.json()['access_token']


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
            "quantity": quantity,
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


def main():
    env = Env()
    env.read_env()
    moltin_client_id = env('MOLTIN_CLIENT_ID')
    moltin_client_secret = env('MOLTIN_CLIENT_SECRET')
    moltin_base_url = env('MOLTIN_BASE_URL')
    api_key = get_api_key(moltin_base_url, moltin_client_id, moltin_client_secret)
    pprint(get_product(moltin_base_url, api_key, '1a836540-bed8-419a-95bb-bc31e76dfd49'))


if __name__ == '__main__':
    main()


