import json
import pandas as pd
import awswrangler as wr

from binance.client import Client, BinanceAPIException

import boto3
from botocore.exceptions import ClientError


def get_secret(key):

    secret_name = "binance-sectrets"
    region_name = "eu-central-1"

    # Create a Secrets Manager client
    session = boto3.session.Session(region_name=region_name)
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e

    secret = json.loads(get_secret_value_response['SecretString'])
    return secret[key]
    

def lambda_handler(event, context):
    binance_api_key = get_secret('BINANCE_API_KEY')
    binance_api_secret = get_secret('BINANACE_API_SECRET')
    binance_client = Client(binance_api_key, binance_api_secret)
    
    try:
        # get binance server time
        time_res = binance_client.get_server_time()

        # get all prices
        prices = binance_client.get_symbol_ticker()

        # get price eur to busd
        eur_busd = binance_client.get_symbol_ticker(symbol="EURBUSD")

        # get account data
        info = binance_client.get_account()
        assets = info['balances']
        
        wallet = []
        for asset in assets:
            quantity = float(asset["free"]) + float(asset["locked"])
            if quantity > 0:
                if asset["asset"] == "BUSD":
                    price_in_busd = 1
                else:
                    for price in prices:
                        if price["symbol"] == asset["asset"] + "BUSD":
                            price_in_busd = float(price["price"])

                amount_in_busd = (float(asset["free"]) + float(asset["locked"])) * price_in_busd
                amount_in_eur = amount_in_busd / float(eur_busd["price"])

                wallet_asset = {
                    "ts": time_res["serverTime"],
                    "asset": asset["asset"],
                    "quantity": float(asset["free"]) + float(asset["locked"]),
                    "amount_busd": amount_in_busd,
                    "amount_eur": amount_in_eur
                }
                
                wallet.append(wallet_asset)
        
        data = pd.DataFrame.from_dict(wallet)
        
        # Storing data on Data Lake
        try:
            print(data)
            wr.s3.to_parquet(
                df=data,
                path="s3://raw-binance-data/daily-wallet-export/",
                dataset=True
            )
            print("Data was load successfully.")
            return "success"
        except:
            print("An error occured.")
            return "error"
            

    except BinanceAPIException as e:
        print(e.status_code)
        print(e.message)