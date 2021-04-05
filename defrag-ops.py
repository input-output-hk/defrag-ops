#! /usr/bin/env python
"""Cardano Defragmentation Ops Tool

Usage:
  defrag-ops.py print-bootstrap-address --mnemonics M_PATH (--testnet | --staging | --mainnet) [--magic NUM] [--raw] [-d]
  defrag-ops.py frag   --mnemonics M_PATH --wid W_ID --wpass W_PATH --wdb DB_PATH --outputs O_COUNT --total LOVELACE (--testnet | --staging | --mainnet) [--magic NUM]
                     (--bootstrap | --random | --new) [--even] [--min UTXO] [--max INPUTS] [--repeat COUNT] [--timers] [--filter TARGET METHOD EXPR]
                     [--socket S_PATH] [--ip IP] [--port PORT] [--tls] [--live] [--no-confirm] [--timeout SECS] [--dynamic] [-d]
  defrag-ops.py defrag --mnemonics M_PATH --wid W_ID --wpass W_PATH --wdb DB_PATH (--testnet | --staging | --mainnet) [--magic NUM]
                     [--min UTXO] [--max INPUTS] [--repeat COUNT] [--timers] [--filter TARGET METHOD EXPR]
                     [--socket S_PATH] [--ip IP] [--port PORT] [--tls] [--live] [--no-confirm] [--timeout SECS] [--dynamic] [-d]
  defrag-ops.py (-h | --help)
  defrag-ops.py --version

Sub-commands:
  print-bootstrap-address  Prints the shelley era compatible (bootstrap) address from byron legacy mnemonics
  frag                     Increase wallet fragmentation
  defrag                   Decrease wallet fragmentation

Sub-command Options Requirements:
  Options and arguments enclosed in no brackets are required.
    * Example: `--mnemonics M_PATH` must be specified.
  Options and arguments enclosed in round brackets () are required to have one of the option elements included.
    * Example: either --testnet, --staging or --mainnet from `(--testnet | --staging | --mainnet)` must be specified.
  Options and arguments enclosed in square brackets [] are not required.
    * Example: --live from [--live] is optional and can be specified when ready to do a live run.

Options:
  --mnemonics M_PATH           Sets the path to the mnemonic file containing a 12 word,
                               space delimited Byron legacy (random wallet) set of mnemonics.
  --wid W_ID                   Sets the wallet ID name.
  --wpass W_PATH               Sets the path to the wallet id file containing only the wallet id passphrase.
  --wdb DB_PATH                Sets the path to the wallet sqlite3 database file for wallet W_ID.
  --outputs O_COUNT            Sets the number of outputs per Tx for `frag` ops, each using a new Byron address.
                               Minimum is 1.  Maximum value may be approximately 150 before Txs are rejected.
  --total LOVELACE             Sets the total Lovelace to be sent per Tx, excluding fees, for `frag` ops.
                               Be sure to reserve enough Lovelace in the bootstrap address to cover fees.
  --mainnet                    Sets the network to cardano mainnet.
  --testnet                    Sets the network to cardano testnet.
  --staging                    Sets the network to cardano staging.
  --magic NUM                  Sets the network protocol magic to a non-default value.
                               The default value for `--mainnet` is 764824073.
                               The default value for `--testnet` is 1097911063.
                               The default value for `--staging` is 633343913.
                               By setting this option to a different value, other networks can accesssed.
  --even                       Sets the total Lovelace distribution (`--total`) to be evenly divided for `frag` ops
                               among the outputs.  Without this option, the default is to assign the
                               total Lovelace distribution randomly to the outputs.
  --bootstrap                  Sets all tx_out addresses as the bootstrap address for `frag` ops.
  --random                     Sets all tx_out addresses as randomly selected from preexisting Byron legacy
                               addresses for `frag` ops.  If there are more tx_outs than preexisting addresses,
                               the address list will be non-unique.
  --new                        Sets all tx_out addresses to newly created Byron legacy addresses for `frag` ops.
                               Note that even with dry run operation, new addresses will still be created.
  --min UTXO                   Overrides the network default minimum allowed UTxO amount, in Lovelace, for an output.
                               This option is provided for advanced frag operations testing.  For basic `frag` or
                               `defrag` ops, it is best to leave this option undeclared which will then
                               default to the value specified by the network protocol parameters.  If this option
                               is set to a different value than the network declares, you will be prompted to
                               confirm this is really what you want.
  --max INPUTS                 Sets the maximum number of inputs allowed in a Tx.  [default: 70]
                               Minimum is 1 for `frag` or 2 for `defrag` operations.
  --repeat COUNT               Sets the `frag` or `defrag` operations to repeat COUNT times.  [default: 1]
  --timers                     Enable info level logging of various operation times for optimization purposes.
  --filter TARGET METHOD EXPR  Apply a filter against tx_inputs, removing them if EXPR is true.
                               Where TARGET can be one of "utxo", "address", or "lovelace".
                               Where METHOD can be one of "re", "eq", "ne", "gt", "gte", "lt", "lte".
                               Where EXPR is either a python regular expression used with METHOD "re" or a
                               positive integer used with the other integer comparison methods, equal,
                               not equal, greater than, greater than or equal, less than, less than or equal.
                               Note that when using the "address" TARGET, it must be given in hex format not base58.
  --socket S_PATH              Sets the path to the cardano-node socket file.
                               If not set, reads the path from env var $CARDANO_NODE_SOCKET_PATH.
  --ip IP                      Sets the wallet server ip to an ipv4 or ipv6 address. [default: 127.0.0.1]
  --port PORT                  Sets the wallet server port. [default: 8090]
  --tls                        Sets the wallet server URL to HTTPS protocol.
  --live                       Submit generated Txs to the network.  Default mode is "dry" (no Txs submitted).
                               Generally, it is advisable to do a dry run first and this will also give a
                               fee estimate for the operation.
  --no-confirm                 Disables the confirmation prompt when running a frag or defrag live (`--live`).
  --timeout SECS               Sets the default connection and read timeout for wallet API calls.  [default: 30]
  --dynamic                    Enables fresh wallet state checks with each transaction to purge utxos which have
                               gone missing.  This may be needed to avoid runtime errors on a wallet which is
                               actively sending or receiving transactions while defrag-ops is being used.  This
                               option WILL slow down operations significantly when used with a large wallet.
  --raw                        Applicable to only the `print-bootstrap-address` sub-command, this option will
                               print only the bootstrap address with no additional context information.  Useful
                               for scripting.

  -d                           Enable debug output.

  -h --help                    Show this screen.
  --version                    Show version.

Requirements:
  * python3 (tested at python 3.8)
  * bash shell must be available for process substitution
  * cardano-cli must be in the path
  * cardano-address must be in the path
  * cardano-wallet server must be running and accessible (except for `print-bootstrap-address`)
  * cardano-node must be running on the same network as specified in this command's (--testnet | --staging | --mainnet) [--magic NUM]
    parameter options and be accessible via socket file (except for `print-bootstrap-address`)
"""

from docopt import docopt
from functools import partial
from logging import Formatter
from logging import handlers
from signal import signal, SIGINT
from typing import cast
import lib.cardano
import lib.db
import lib.objects
import lib.utility
import lib.utxo
import lib.validate
import lib.wallet
import logging
import os
import sys
import time


# Set up logging
logger = logging.getLogger(__name__)
ch = logging.StreamHandler(sys.stdout)
logger.addHandler(ch)
lh = handlers.SysLogHandler(address="/dev/log")
lf = Formatter("defragment[{0}]: %(message)s".format(os.getpid()))
lh.setFormatter(lf)
logger.addHandler(lh)
if "-d" in sys.argv[1:]:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

# Create the operations state object
ops = lib.objects.OpsState(logger)

# Main
if __name__ == "__main__":

    signal(SIGINT, partial(lib.utility.sigint_handler, ops))

    arguments = docopt(__doc__, version="defrag-ops 1.0.0")

    # Preparatory validation
    lib.utility.log_debug_header(logger, arguments)
    lib.validate.validate_args(ops, arguments)
    lib.validate.validate_deps(ops, arguments)

    # Start key generation
    lib.cardano.cardano_address_key_prep(ops)
    lib.cardano.cardano_cli_key_prep(ops)

    if arguments["print-bootstrap-address"] and arguments["--raw"]:
        print(ops.g_shelley_address)
        sys.exit(0)

    logger.info(
        f"Shelley era compatible *** {ops.g_network} ({ops.g_network_id}) *** bootstrap address:"
    )
    logger.info(
        "  This address will be used to fund operations for the `frag` sub-command"
    )
    logger.info(
        "  This address will be used to return change to for the `defrag` sub-command"
    )
    logger.info("")
    logger.info(f"  {ops.g_shelley_address}")
    logger.info("")

    if arguments["print-bootstrap-address"]:
        sys.exit(0)

    logger.debug(f"Global wallet ID = {ops.g_wallet_id}")
    logger.debug(f"Global wallet DB path = {ops.g_wallet_db_path}")
    logger.debug(f"Global socket path = {ops.g_socket_path}")
    logger.debug(f"Global wallet server ip = {ops.g_wallet_ip}")
    logger.debug(f"Global wallet server port = {ops.g_wallet_port}")
    logger.debug(f"Global wallet server api = {ops.g_wallet_server_api}")

    # Start wallet processing
    lib.cardano.cardano_cli_query_utxo(ops, ops.g_shelley_address, ascending=False)
    lib.db.wallet_db_read(ops)
    lib.wallet.wallet_stats(ops)
    setattr(
        ops,
        "g_runtime_utxos",
        ops.g_cardano_cli_utxo.copy() if ops.g_frag else ops.g_wallet_utxo.copy(),
    )
    lib.utxo.filter_inputs(ops)

    logger.debug(
        f"Global cardano-cli starting bootstrap address utxo count (excluding asset utxos): {len(ops.g_cardano_cli_utxo)}"
    )
    logger.debug(
        f"Global wallet starting utxo count (excluding asset utxos): {ops.g_wallet_utxo_count}"
    )
    logger.debug(
        f"Global wallet starting utxo asset count (excluding lovelace only utxos): {ops.g_wallet_utxo_count_asset}"
    )
    logger.debug(
        f"Global wallet starting utxo address count: {ops.g_wallet_utxo_address_count}"
    )
    logger.debug(
        f"Global wallet starting utxo lovelace count (excluding asset utxos): {ops.g_wallet_utxo_lovelace_count}"
    )
    logger.debug(
        f"Global wallet starting db address count: {len(ops.g_wallet_db_addresses)}"
    )
    logger.debug(
        f"Global filtered runtime utxos (excluding asset utxos): {len(ops.g_runtime_utxos)}"
    )

    lib.utility.summary_header(ops)

    # Repeat the transaction operation g_tx_repeat times
    setattr(ops, "g_start_time", time.time())
    setattr(ops, "g_sum_tx_fees", 0)
    setattr(ops, "g_sum_tx_count", 0)
    setattr(ops, "g_sum_tx_inputs", 0)
    setattr(ops, "g_sum_tx_outputs", 0)
    g_sum_tx_fees = 0
    g_sum_tx_count = 0
    g_sum_tx_inputs = 0
    g_sum_tx_outputs = 0
    last_lookup_hits_sql_drvs = 0
    last_lookup_hits_cli_skey = 0
    for i in range(0, ops.g_tx_repeat):
        # Provide a status update for each operation repeat iteration
        iter_start_time = time.time()

        # Poll for updated chain state information at the start of each tx
        lib.cardano.cardano_cli_protocol_params(ops)

        # Perform a fresh state check with each Tx if the wallet is specified as dynamic
        # This has a significant performance cost on large wallets!
        if ops.g_dynamic:
            lib.cardano.cardano_cli_query_utxo(
                ops, ops.g_shelley_address, ascending=False
            )
            lib.db.wallet_db_read(ops)
            lib.wallet.wallet_stats(ops)
            lib.utxo.purge_missing_utxos(ops)

        logger.info(
            f'{"Fragment" if ops.g_frag else "Defragment"} operation {i + 1} of {ops.g_tx_repeat}'
            f" started at {lib.utility.date_time_str()} with "
            f"{len(ops.g_runtime_utxos)} non-asset utxo inputs {'available' if ops.g_frag else 'to be processed'}:"
        )

        status = lib.cardano.cardano_cli_tx_compose(ops)

        iter_end_time = time.time()
        logger.info(
            "Cache (drvHits, skeyHits, drvLen, skeyLen): "
            + f"({ops.g_lookup_hits_sql_drvs - last_lookup_hits_sql_drvs}, "
            + f"{ops.g_lookup_hits_cli_skey - last_lookup_hits_cli_skey}, "
            + f"{len(ops.g_wallet_db_address_drvs)}, {len(ops.g_cardano_cli_skeys)})"
            + f'{"" if ops.g_frag else ", Dust algorithm: " + cast(str, status["algorithm"])}'
        )
        logger.info(
            f"Operation time: {lib.utility.time_delta_to_str(iter_end_time - iter_start_time)}, "
            + f"Elapsed time: {lib.utility.time_delta_to_str(iter_end_time - ops.g_start_time, ms=False)}"
        )
        logger.info("")
        logger.info("")

        last_lookup_hits_sql_drvs = ops.g_lookup_hits_sql_drvs
        last_lookup_hits_cli_skey = ops.g_lookup_hits_cli_skey

        if status["state"] is True:
            g_sum_tx_count += 1
            g_sum_tx_fees += cast(int, status["fee"])
            g_sum_tx_inputs += cast(int, status["inputs"])
            g_sum_tx_outputs += cast(int, status["outputs"])
            setattr(ops, "g_sum_tx_count", g_sum_tx_count)
            setattr(ops, "g_sum_tx_fees", g_sum_tx_fees)
            setattr(ops, "g_sum_tx_inputs", g_sum_tx_inputs)
            setattr(ops, "g_sum_tx_outputs", g_sum_tx_outputs)
        else:
            break

    lib.utility.summary_footer(ops)
