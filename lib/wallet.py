import collections
import json
import lib.utility
import random
import requests
import sys
import time


def wallet_api(
    ops, url, method="get", data={}, headers={"Content-type": "application/json"}
):
    """ Execute a wallet request operation and handle or return the result """

    logger = ops.g_logger
    timeout = (ops.g_api_timeout, ops.g_api_timeout)

    try:
        if method == "get":
            request = requests.get(url, timeout=timeout)
        elif method == "post":
            request = requests.post(url, data=data, headers=headers, timeout=timeout)
        else:
            logger.error(f"ERROR: Unknown api method {method}")
            sys.exit(1)
        request.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(f"ERROR: The endpoint returned an unhealthy status: {url}")
        logger.error("Fix the server health and try again.")
        logger.error(e)
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        logger.error(f"ERROR: Could not connect to endpoint: {url}")
        logger.error("Fix the server health and try again.")
        logger.error(e)
        sys.exit(1)
    except requests.exceptions.Timeout as e:
        logger.error(f"ERROR: Timed out trying to connect to: {url}")
        logger.error("Fix the server health and try again.")
        logger.error(e)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error: Exception on GET at endpoint: {url}")
        logger.error("Fix the server health and try again.")
        logger.error(e)
        sys.exit(1)
    return request


def wallet_byron_address_create(ops):
    """ Creates a new cardano wallet byron address """

    logger = ops.g_logger

    wallet_byron_address_create_url = (
        f"{ops.g_wallet_server_api}/byron-wallets/{ops.g_wallet_id}/addresses"
    )

    data = json.dumps({"passphrase": f"{ops.g_wallet_id_passphrase}"})
    request = wallet_api(ops, wallet_byron_address_create_url, method="post", data=data)
    try:
        byron_address_new = request.json()
        if byron_address_new["state"] != "unused":
            logger.error(
                f"ERROR: The new byron address returned is not in state unused: {byron_address_new['state']}"
            )
            sys.exit(1)
    except ValueError as e:
        logger.error(
            f"ERROR: Unexpected new byron address json return value from: {wallet_byron_address_create_url}"
        )
        logger.error(e)
        sys.exit(1)
    return byron_address_new["id"]


def wallet_output_addresses(ops, count):
    """ Creates a list of cardano byron addresses """

    logger = ops.g_logger

    timer = time.time()
    if ops.g_tx_output_frag_address == "bootstrap":
        addresses = [ops.g_shelley_address for x in range(0, count)]
    elif ops.g_tx_output_frag_address == "random":
        if count < len(ops.g_wallet_db_addresses):
            addresses = [
                lib.utility.base58_encode(address)
                for address, account_index, address_index, status in random.sample(
                    ops.g_wallet_db_addresses, count
                )
            ]
        else:
            addresses = [
                lib.utility.base58_encode(address)
                for address, account_index, address_index, status in random.choices(
                    ops.g_wallet_db_addresses, k=count
                )
            ]
    elif ops.g_tx_output_frag_address == "new":
        addresses = [wallet_byron_address_create(ops) for x in range(0, count)]
    else:
        logger.error(
            f"ERROR: Unknown cardano wallet address mode: {ops.g_tx_output_frag_address}"
        )
        sys.exit(1)
    ops.g_timers and logger.info(
        "Time to generate a tx_out address list using the "
        + f"{ops.g_tx_output_frag_address} method: {lib.utility.time_delta_to_str(time.time() - timer)}"
    )

    return addresses


def wallet_stats(ops):
    """ Determine wallet total UTxO, address and lovelace count and sets ops state """

    logger = ops.g_logger

    timer = time.time()
    utxos = len(ops.g_wallet_utxo)
    addresses = [utxo[2] for utxo in ops.g_wallet_utxo]
    unique_addresses = len(collections.Counter(addresses).keys())
    lovelaces = sum([utxo[1] for utxo in ops.g_wallet_utxo])

    setattr(ops, "g_wallet_utxo_count", utxos)
    setattr(ops, "g_wallet_utxo_address_count", unique_addresses)
    setattr(ops, "g_wallet_utxo_lovelace_count", lovelaces)
    ops.g_timers and logger.info(
        f"Time to generate wallet statistics: {lib.utility.time_delta_to_str(time.time() - timer)}"
    )
