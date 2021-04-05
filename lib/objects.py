from typing import Dict, List, Tuple, Union
import logging
import time


class OpsState:
    # fmt: off
    # Class constants
    BINARY_DEPS = ["bash", "cardano-address", "cardano-cli", "cardano-wallet"]
    ACCEPT_CARDANO_ADDRESS_VER: Dict[str, str] = {
        "3.2.0": "115174cc451d3fc6b90ce61782f841e51f271c3d"
    }
    ACCEPT_CARDANO_CLI_VER: Dict[str, str] = {
        "1.26.1": "62f38470098fc65e7de5a4b91e21e36ac30799f3"
    }
    ACCEPT_CARDANO_WALLET_VER: Dict[str, str] = {
        "2021.3.4": "f4d697a2c8f1df3acba578d9554508896d331b8d"
    }
    MIN_BASH_VER: str = "4.4.0"                                           # Released in 2016
    WALLET_API_VER: str = "v2"
    WALLET_API_HEALTHCHECK: str = "network/information"
    WALLET_TO_CLI_HEIGHT_TOLERANCE: int = 5                               # Maximum tolerable blockHeight diff between wallet and cardano-cli for ops to proceed
    TX_FEE_CALC_ATTEMPTS: int = 10                                        # Attempt a maximum number of fee calculation attempts for a stable fee
    TX_FEE_LOVELACE_TOLERANCE: int = 3000000                              # Minimum lovelace amount to pad Tx inputs to cover fees
    TX_TTL_TOLERANCE: int = 300                                           # Set a Tx ttl for cardano-cli transactions
    DEFAULT_ACCOUNT_INDEX: str = "0H"                                     # Set the default byron wallet account index
    DEFAULT_ADDRESS_INDEX: str = "444138633H"                             # Set the default byron wallet address index
    # fmt: on

    def __init__(self, logger):
        # fmt: off
        # Instance variables
        self.g_api_timeout: int = 30                                      # Set a connection and read timeout value for wallet API calls
        self.g_bash_path: str = ""                                        # The path to bash on the current system
        self.g_cardano_address_tag: str = ""                              # The tag of cardano-address available in the script's shell path
        self.g_cardano_address_rev: str = ""                              # The rev of cardano-address available in the script's shell path
        self.g_cardano_cli_tag: str = ""                                  # The tag of cardano-cli available in the shell
        self.g_cardano_cli_rev: str = ""                                  # The rev of cardano-cli available in the shell
        self.g_cardano_wallet_tag: str = ""                               # The tag of cardano-wallet available in the script's shell path
        self.g_cardano_wallet_rev: str = ""                               # The rev of cardano-wallet available in the script's shell path
        self.g_cardano_cli_skeys: Dict[str, str] = {}                     # {base58_address: skey}
        self.g_cardano_cli_utxo: List[Tuple[str, int, str]] = []          # [(tx_hash#tx_ix, lovelace, address), ...] from cardano-cli
        self.g_confirm: bool = True                                       # Whether to confirmation prompt on `--live` operations
        self.g_dynamic: bool = False                                      # Whether to support a dynamic wallet where utxos may disappear during runtime
        self.g_filter_tx_in_expr: Union[int, str] = ""                    # tx_in filter expression, if enabled
        self.g_filter_tx_in: bool = False                                 # Whether to enable a tx_in filter
        self.g_filter_tx_in_method: str = ""                              # tx_in filter method, if enabled
        self.g_filter_tx_in_target: str = ""                              # tx_in filter target, if enabled
        self.g_frag: bool = True                                          # Whether in `frag` mode (True) or `defrag` mode (False)
        self.g_live: bool = False                                         # Submit generated Txs if true, otherwise dry-run
        self.g_logger: logging.Logger = logger                            # Set the logger
        self.g_lookup_hits_cli_skey: int = 0                              # Tracks the number of hash map hits for the skey lookup table
        self.g_lookup_hits_sql_drvs: int = 0                              # Tracks the number of hash map hits for the sql drv lookup table
        self.g_mnemonics: str = ""                                        # 12 space delimited mnemonics
        self.g_network_id: str = ""                                       # Network id for the selected network
        self.g_network_min_utxo_override: bool = False                    # Whether a min utxo override has been specified from the cli
        self.g_network: str = "NOT_YET_SET"                               # "mainnet" or "testnet"
        self.g_network_protocol_params_min_utxo: int = 0                  # Reference network protocol min utxo
        self.g_network_protocol_params: str = ""                          # Network protocol parameters for the selected network
        self.g_runtime_utxos: List[Tuple[str, int, str]] = []             # Tracks remaining unprocessed utxos for the `frag` or `defrag` operation
        self.g_shelley_address: str = ""                                  # Shelley era compatible cardano-address generated address
        self.g_shelley_prv: str = ""                                      # Shelley private key (byron type)
        self.g_shelley_root_prv: str = ""                                 # Shelley era compatible root private key
        self.g_shelley_root_pub: str = ""                                 # Shelley era compatible root public key
        self.g_shelley_skey: str = ""                                     # Shelley private key (shelley type)
        self.g_shelley_vkey: str = ""                                     # Shelley public key (shelley type)
        self.g_socket_path: str = ""                                      # Socket path
        self.g_start_time: float = time.time()                            # Operation start time in unix epoch timestamp format
        self.g_sum_tx_count: int = 0                                      # Sum of transactions processed or submitted
        self.g_sum_tx_fees: int = 0                                       # Sum of operation fees
        self.g_sum_tx_inputs: int = 0                                     # Sum of the number of inputs processed or submitted
        self.g_sum_tx_outputs: int = 0                                    # Sum of the number of outputs processed or submitted
        self.g_timers: bool = False                                       # Whether to debug log detailed operation timings
        self.g_tx_max_inputs: int = 0                                     # Maximum number of inputs allowed per Tx
        self.g_tx_output_count: int = 0                                   # Output count per Tx using new byron addresses
        self.g_tx_output_evenly: bool = False                             # For `frag` ops, distribute lovelace total evenly if true (default: random)
        self.g_tx_output_frag_address: str = ""                           # For `frag` ops, the tx_out address method (bootstrap, random, new)
        self.g_tx_output_lovelace: int = 0                                # Total lovelace output per Tx
        self.g_tx_output_min_utxo: int = 0                                # Minimum UTxO size, in Lovelace.  Gets set to network params or overriden by cli.
        self.g_tx_repeat: int = 1                                         # Defines the repeat count for the transaction operation
        self.g_wallet_db_address_drvs: Dict[str, Dict[str, int]] = {}     # {base58_address: {account_ix|address_ix: value}} from cardano-wallet
        self.g_wallet_db_addresses: List[Tuple[str, int, int, str]] = []  # [(address, account_ix, address_ix, status), ...] from cardano-wallet
        self.g_wallet_db_path: str = ""                                   # Wallet db path
        self.g_wallet_id: str = ""                                        # Wallet id
        self.g_wallet_id_passphrase: str = ""                             # Wallet id passphrase
        self.g_wallet_ip: str = ""                                        # Wallet ip (ipv4 or ipv6)
        self.g_wallet_port: str = ""                                      # Wallet port (validated as int)
        self.g_wallet_server_api: str = ""                                # Wallet api endpoint (assumes http)
        self.g_wallet_tls: bool = False                                   # Sets http or https for wallet server url
        self.g_wallet_utxo_address_count: int = 0                         # Total utxo unique address count
        self.g_wallet_utxo_count: int = 0                                 # Total utxo count (excluding asset utxos)
        self.g_wallet_utxo_count_asset: int = 0                           # Total asset utxo count
        self.g_wallet_utxo: List[Tuple[str, int, str]] = []               # [(tx_hash#tx_ix, lovelace, address), ...] from cardano-wallet
        self.g_wallet_utxo_lovelace_count: int = 0                        # Total utxo lovelace sum
        # fmt: on
