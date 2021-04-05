import lib.utility
import logging
import sqlite3
import sys
import time


def sqlite3_db_conn(logger: logging.Logger, path: str) -> sqlite3.Connection:
    """ Create a database connection to an sqlite3 database """

    try:
        db = sqlite3.connect(path)
    except sqlite3.Error:
        logger.exception(
            "ERROR: An sqlite3 database exception occurred while attempting to connect."
        )
    return db


def wallet_db_query_address_count(
    ops: lib.objects.OpsState, db: sqlite3.Connection
) -> None:
    """ Obtains wallet address information from the database and sets ops state """

    logger = ops.g_logger

    timer = time.time()
    try:
        cur = db.cursor()
        cur.execute(
            "SELECT address, account_ix, address_ix, status FROM rnd_state_address WHERE rnd_state_address.slot = "
            + "(SELECT max(slot) FROM rnd_state_address) "
            + 'UNION SELECT address, account_ix, address_ix, "unused" as status FROM rnd_state_pending_address'
        )
        rows = cur.fetchall()
    except sqlite3.Error:
        logger.exception(
            "ERROR: An sqlite3 database exception occurred while attempting to fetch wallet address count."
        )

    if len(rows) == 0:
        logger.error(f"ERROR: No addresses found at {ops.g_wallet_db_path}")
        sys.exit(1)

    setattr(ops, "g_wallet_db_addresses", rows)
    g_wallet_db_address_drvs = {}
    for address, account_ix, address_ix, status in ops.g_wallet_db_addresses:
        g_wallet_db_address_drvs[lib.utility.base58_encode(address)] = {
            "account_ix": account_ix if account_ix < 2 ** 31 else account_ix - 2 ** 31,
            "address_ix": address_ix if address_ix < 2 ** 31 else address_ix - 2 ** 31,
        }
    setattr(ops, "g_wallet_db_address_drvs", g_wallet_db_address_drvs)

    if ops.g_timers:
        logger.info(
            f"Time to query wallet address state and generate an address lookup dictionary: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )


def wallet_db_query_utxo(ops: lib.objects.OpsState, db: sqlite3.Connection) -> None:
    """ Obtains all UTxO state for the given sqlite3 database and sets ops state """

    logger = ops.g_logger

    timer = time.time()
    try:
        cur = db.cursor()
        cur.execute(
            "WITH utxo_table AS (SELECT input_tx_id || '#' || input_index as utxo, output_coin, output_address FROM utxo WHERE slot = (SELECT max(slot) FROM utxo)), "
            + "utxo_asset_table AS (SELECT tx_id || '#' || tx_index as utxo_asset FROM utxo_token WHERE slot = (SELECT max(slot) FROM utxo_token)) "
            + "SELECT * FROM utxo_table where utxo NOT IN (SELECT DISTINCT utxo_asset FROM utxo_asset_table) ORDER BY output_coin ASC"
        )
        rows = cur.fetchall()
    except sqlite3.Error:
        logger.exception(
            "ERROR: An sqlite3 database exception occurred while attempting to fetch tables rows."
        )
        sys.exit(1)

    if len(rows) == 0:
        logger.error(f"ERROR: No UTxO found at {ops.g_wallet_db_path}")
        sys.exit(1)

    setattr(ops, "g_wallet_utxo", rows)

    if ops.g_timers:
        logger.info(
            f"Time to query wallet utxo state: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )


def wallet_db_query_utxo_asset(
    ops: lib.objects.OpsState, db: sqlite3.Connection
) -> None:
    """ Obtains a count of asset containing UTxOs and sets ops state """

    logger = ops.g_logger

    timer = time.time()
    try:
        cur = db.cursor()
        cur.execute(
            "WITH utxo_asset_table AS (SELECT tx_id || '#' || tx_index as utxo_asset FROM utxo_token WHERE slot = (SELECT max(slot) FROM utxo_token)) "
            + "SELECT COUNT(DISTINCT utxo_asset) FROM utxo_asset_table WHERE utxo_asset NOT NULL"
        )
        row = cur.fetchone()
    except sqlite3.Error:
        logger.exception(
            "ERROR: An sqlite3 database exception occurred while attempting to fetch tables rows."
        )
        sys.exit(1)

    if len(row) == 0:
        logger.error(f"ERROR: No asset UTxO count found at {ops.g_wallet_db_path}")
        sys.exit(1)

    try:
        utxo_count_asset = row[0]
        if not (0 <= utxo_count_asset):
            logger.error(
                f"ERROR: Asset UTxO count is not greater than or equal to 0: {utxo_count_asset}"
            )
            sys.exit(1)
    except Exception:
        logger.exception(
            f"ERROR: Asset UTxO count result is not an integer: {utxo_count_asset}"
        )
        sys.exit(1)

    setattr(ops, "g_wallet_utxo_count_asset", utxo_count_asset)

    if ops.g_timers:
        logger.info(
            f"Time to query wallet asset utxo count: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )


def wallet_db_read(ops: lib.objects.OpsState) -> None:
    """ Reads the required state from the cardano-wallet sqlite3 database and sets ops state """

    logger = ops.g_logger

    db = sqlite3_db_conn(logger, ops.g_wallet_db_path)
    with db:
        wallet_db_query_utxo(ops, db)
        wallet_db_query_utxo_asset(ops, db)
        wallet_db_query_address_count(ops, db)
