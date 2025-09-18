import json
import re
import requests
import time

from dotenv import load_dotenv
from shopify import Shopify
from timeit import timeit

load_dotenv()

def get_cards():
  return requests.get("https://api.fastsimon.com/categories_navigation", params={
    "page_num": 1,
    "products_per_page": 500,
    "uuid": "d3cae9c0-9d9b-4fe3-ad81-873270df14b5",
    "api_type": "json",
    "narrow": '[["Set","Set_OP-12 Booster Pack: Legacy of the Master"],["Category","One Piece Singles"]]',
    "sort_by": "a_to_z",
    "category_id": 287039979707
  })

def get_title(card):
  return card["l"]

def get_price(card):
  condition, price = None, None
  price_nm = None
  for variant in card["vra"]:
    attributes = variant[1]
    for attribute in attributes:
      if attribute[0] == "Condition":
        condition = attribute[1][0]
      if attribute[0] == "Price":
        price = attribute[1][0].split(":")[1]
    if condition is not None and price is not None:
      if condition == "NM":
        price_nm = price
  return price_nm

def find_card_metafiels(product):
  number, rarity = None, None
  for metafield in product["metafields"]["nodes"]:
    if metafield["key"] == "custom.number":
      number = metafield["value"]
    if metafield["key"] == "custom.rarity":
      rarity = metafield["value"]
  return {
    "number": number,
    "rarity": rarity
  }

def manage_exceptions(key):
  if key == "Kuzan (SP) - OP10-082 - Super Rare":
    return "Kuzan (OP12 SP) - OP10-082 - Super Rare"
  elif key == "Lim (SP) - OP09-037 - Super Rare":
    return "Lim (OP12 SP) - OP09-037 - Super Rare"
  elif key == "Marshall.D.Teach (SP) (Gold) - OP09-093 - Super Rare":
    return "Marshall.D.Teach (OP12 SP) (Gold) - OP09-093 - Super Rare"
  elif key == "Marshall.D.Teach (SP) (Silver) - OP09-093 - Super Rare":
    return "Marshall.D.Teach (OP12 SP) (Silver) - OP09-093 - Super Rare"
  elif key == "Portgas.D.Ace (SP) - ST13-011 - Super Rare":
    return "Portgas.D.Ace (OP12 SP) - ST13-011 - Super Rare"
  elif key == "Yasopp (SP) - OP09-013 - Rare":
    return "Yasopp (OP12 SP) - OP09-013 - Rare"
  elif key == "Zoro-Juurou (SP) - ST18-004 - Super Rare":
    return "Zoro-Juurou (OP12 SP) - ST18-004 - Super Rare"
  return key

def lambda_handler(event, context):
  shopify = Shopify()

  response = get_cards()
  cards = json.loads(response.text)["items"]

  cards_price_list = {}

  for card in cards:
    cards_price_list[get_title(card)] = get_price(card)

  with open("/tmp/price_updates.jsonl", 'w') as file:
    file_is_empty = True
    products = shopify.get_products(306379292725, None)
    while True:
      for product in products["nodes"]:
        for variant in product["variants"]["nodes"]:
          key = product["title"]
          card_metafields = find_card_metafiels(product)
          if card_metafields["number"] is not None and card_metafields["rarity"] is not None:
            key += " - " + card_metafields["number"] if "number" in card_metafields else ""
            key += " - " + card_metafields["rarity"] if "rarity" in card_metafields else ""
          if key not in cards_price_list:
            key = manage_exceptions(key)
            if key not in cards_price_list:
              print(key + ": Not Found!")
          if key in cards_price_list and variant["price"] != cards_price_list[key] and cards_price_list[key] is not None:
            print(key + " - " + "Current Price: " + variant["price"] + " - New Price: " + cards_price_list[key])
            json.dump(shopify.get_product_jsonl(product["id"], variant["id"], cards_price_list[key]), file)
            file_is_empty = False
            file.write("\n")
      if products["pageInfo"]["hasNextPage"]:
        products = shopify.get_products(306379292725, products["pageInfo"]["endCursor"])
      else:
        break
    file.close()

    if not file_is_empty:
      response = shopify.create_staged_upload()
      url = response["data"]["stagedUploadsCreate"]["stagedTargets"][0]["url"]
      parameters = response["data"]["stagedUploadsCreate"]["stagedTargets"][0]["parameters"]

      key = shopify.upload_jsonl(url, parameters)
      shopify.run_bulk_operation_mutation(key)

      while True:
        time.sleep(5)
        response = shopify.get_current_bulk_operation()
        if response["data"]["currentBulkOperation"]["status"] != "RUNNING":
          break
      
if __name__ == '__main__':
  execution_time = timeit(lambda: lambda_handler({}, {}), number=1)
  print(f"Temps d'exécution lambda_handler: {execution_time:.6f} secondes")