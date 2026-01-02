import sys
import logging

from src.utils import config
import psycopg2
import requests

logging.basicConfig(level=logging.INFO)


def checkExistingOrders():
    PL_API_KEY = config.PL_API_KEY
    BASE_URL = "https://api.planet.com/compute/ops/orders/v2"
    BASIC_AUTH = (PL_API_KEY, "")
    response = requests.get(BASE_URL, auth=BASIC_AUTH)

    if response.status_code == 200:
        logging.info("Successfully accessed the stats/orders/v2 API")
    else:
        logging.error(f"Error accessing stats/orders/v2 API: {response.content}")

    myjson = response.json()
    print(f"Found {len(myjson['orders'])} new order(s)")
    for order in myjson["orders"]:
        for product in order["products"]:
            for item in product["item_ids"]:
                id = order["id"]
                name = order["name"]
                created_on = order["created_on"]
                last_message = order["last_message"]
                scene_id = item
                item_type = product["item_type"]
                product_bundle = product["product_bundle"]
                row = getScene(scene_id)
                if row is None:
                    id = putOrder(
                        id,
                        name,
                        created_on,
                        last_message,
                        scene_id,
                        item_type,
                        product_bundle,
                    )
                else:
                    logging.info(f"{scene_id} already on file")


def putOrder(id, name, created_on, last_message, scene_id, item_type, product_bundle):
    sql = """
        INSERT INTO public.planet_orders(
            id, order_name, created_on, last_message,
            scene_id, item_type, product_bundle
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s);
    """
    values = (id, name, created_on, last_message, scene_id, item_type, product_bundle)
    conn = psycopg2.connect(config.DB_CONNECTION_STRING)
    id = None
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql, values)
            conn.commit()
            logging.info(f"{scene_id} added to database")
        except Exception as e:
            logging.error(
                f"orderScene unexpected error: {e}",
                exc_info=True,
            )
            return "error"
    return id


def getScene(scene_id):
    sql = """
        SELECT * FROM public.planet_orders WHERE scene_id='%s'
    """ % (scene_id)
    conn = psycopg2.connect(config.DB_CONNECTION_STRING)
    row = None
    with conn.cursor() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
    return row


if __name__ == "__main__":
    checkExistingOrders()
