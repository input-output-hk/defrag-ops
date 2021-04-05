# Cardano Defragmentation Ops Tool (defrag-ops.py)


## Introduction

* The defrag-ops.py script provides the capability to defragment UTxO in individual Cardano wallets.
* At the moment only Byron legacy (random) wallets are supported.
* As a wallet becomes fragmented with more UTxO, wallet performance can decrease.
* Defragmenting UTxO with this tool can help regain wallet performance.

* This tool is designed to work on Mary era or later Cardano networks; it is not expected to not work properly on earlier Cardano eras (Byron, Shelley, Allegra)
* This tool will only work with UTxOs that do *NOT* contain a native asset; UTxOs containing a native asset or asset(s) will be *ignored*


## Software Requirements

* defrag-ops.py requires the following software to be installed and available from the system path at the versions indicated:
  * python3 and python3 library dependencies (tested at python 3.8)
  * bash (>= 4.4.0)
  * [cardano-cli](https://github.com/input-output-hk/cardano-node/tree/master/cardano-cli) (part of cardano-node, tags: 1.26.1)
  * [cardano-addresses](https://github.com/input-output-hk/cardano-addresses) (tags: 3.2.0)
  * [cardano-wallet](https://github.com/input-output-hk/cardano-wallet) server (tags: v2021-03-04)
  * [cardano-node](https://github.com/input-output-hk/cardano-node) (tags: 1.26.1)
* If the Cardano software is installed and available from the system path, but not at the above indicated versioning, defrag-ops will display a `WARNING`.

* Cardano-node and cardano-wallet must be run as servers and connected to the network that the wallet to fragment or defragment is part of.
  * When running cardano-node, the socket file created by cardano-node server must be available to defrag-ops.py.
  * When running cardano-wallet, the ip and port to the API server, as well as the path to the sqlite3 database for the wallet of interest must be available to defrag-ops.py.
* Since fragmentation and defragmentation operations on a big wallet can be slow, it is recommended to run a cardano-node and cardano-wallet server on a dedicated machine which are not serving additional load.


### Nix

* Nix can help set up these dependencies quickly.
* If you don't have Nix and would like to try, Nix can be installed by following directions [here](https://nixos.org/manual/nix/stable/#chap-installation) where a multi-user installation is recommended.
* Example commands for nix building a cardano-node server for testnet from a git cloned repo and then starting it are:
```
$ nix-build default.nix -A scripts.testnet.node -o launch-testnet-node
$ ./launch-testnet-node
```

* The cardano-node socket file for the example above would then be found in the state-node-testnet directory (`state-node-testnet/node.socket`).
* Example commands for nix building a cardano-wallet server from a git cloned repo and then starting it for testnet are:
```
$ mkdir testnet-db
$ curl -OL https://raw.githubusercontent.com/input-output-hk/iohk-nix/master/cardano-lib/testnet-byron-genesis.json
$ nix-build default.nix -A cardano-wallet -o cardano-wallet
$ ./cardano-wallet/bin/cardano-wallet serve --listen-address 127.0.0.1 --port 8090 --testnet ./testnet-byron-genesis.json --node-socket $CARDANO_NODE_SOCKET_PATH --database ./testnet-db
```

* A `shell.nix` file is provided which provides all necessary command line and python dependencies.
* It can be utilized by entering a nix-shell with the command:
```
$ nix-shell
```

* If a file named `cardano-node-socket-path.txt` containing the path to the cardano-node socket file is created in the same directory as the `shell.nix` file, nix-shell will automatically export the path to enable `cardano-cli` to work out of the box.
* See the respective repositories for more details on building these products and running them.


### Python Virtual Environment

* Python dependenices for defrag-ops.py can also be installed with through virtual env and make instead of Nix:
```
# Create and activate virtual env
$ python3 -m venv .env
$ . .env/bin/activate

# Install this script's library requirements
$ make install

# When finished working in the virtual environment
$ deactivate
```


## System Requirements

* The defrag-ops.py script has been observed to utilize up to about 512 MB RSS RAM peak during operation.
* Faster CPU will result in better performance, but there is no hard requirement.
* If run on the same system, enough compute and RAM will need to be available to run defrag-ops, cardano-node and cardano-wallet concurrently.


## Performance

* On a modern PC with 4 physical cores, each with 2 threads (8 logical cores or vCPU) running at about 3.5 GHz clock speed:
  * Defragmentation performance can be about 40k UTxO per hour.


## General Concepts

### The Bootstrap Address

* The defrag-ops.py script requires, at the very minimum, a set of mnemonics for a Byron legacy (random) wallet, specified with `--mnemonics M_PATH` where `M_PATH` is the path to a file containing the mnemonics, and a network, either `--testnet`, `--staging` or `--mainnet`.
* From this, the simplest command available to run is the `print-bootstrap-address` command, where `./mnemonics.txt` is used as an example for `M_PATH`:
```
$ ./defrag-ops.py print-bootstrap-address --mnemonics ./mnemonics.txt --testnet

Shelley era compatible *** testnet (1097911063) *** bootstrap address:
  This address will be used to fund operations for the `frag` sub-command
  This address will be used to return change to for the `defrag` sub-command

  37btjrVyb4KDdVL9vqtU4P9caQKp3pv...EXAMPLE...BOOTSTRAP...ADDRESS...a14uCrL1n7qPwsXhWUT8ziGdhkDaByPNx5DGaY6fVioDfhyc
```

* This will generate a Byron legacy bootstrap address (an example of which is shown above) which belongs to the wallet and is used by the defrag-ops.py script for fund return of defragmentation operations as the change address.
* Cardano wallet successfully recognizes this bootstrap address as its own and this address can be funded like a regular wallet address, or spent from like a regular wallet address using the cardano-wallet API or other methods.


### Dry Run

* By default, defragmentation commands will be executed as "dry" or non-live which means transactions will be prepared, but not submitted to the network.
* This allows for the operator to compose a `defrag` command, execute the command as a "dry run" by default and observe the summary information output.
* If the output is not expected or otherwise needs to be changed, the command can be updated and dry run again until the operator is satisfied.
* The same command can then be sent to the network by appending the `--live` flag.


### Fees

* Dry runs provide fee estimations as part of the individual transaction summary and overall command summary information.
* Fee information is determined the same way for both dry runs and live runs: using `cardano-cli transaction calculate-min-fee`.
* Since the fee calculation method is the same for both dry and live runs, as long as transactions details for a dry run will be the same as for a live run, the estimated dry fees should match the live fees.
* If a wallet transacts (sends or receives transactions) after a dry run but before a live run is performed and correct fees need to be re-assessed, simply re-execute the dry run to obtain a new updated fee estimation.


### Logging

* By default, defrag-ops.py will log to `stdout` and `/dev/log` at log levels of `INFO`, `WARNING` and `ERROR`.
* If the `-d` option is appended to any defrag-ops.py command, additional `DEBUG` level logging will be logged to `stdout` and `/dev/log`.
* A `--timers` option for `defrag` operations will print additional internal script timing information at `INFO` log level that can be useful for debugging purposes.
* In general, in the case of an error or failure, a detailed message will be logged and in many cases a python stack trace will also be provided for additional debugging information.
* The exception to this will be errors which involve secrets which should not be logged and subsequently the failure message may be more limited by design.


### Secrets Handling

* defrag-ops.py does not create temporary files during operation.
* Apart from reading secrets from the provided secret file paths, secrets handling is done in memory and through shell process substitution and piping.


### UTxO State

* defrag-ops.py reads wallet and bootstrap address state once during script start up and does not, by default, further try to read wallet state.
* If new UTxOs become available in the wallet during defrag-ops.py operation, they won't be available to be acted on until the next time the script is run and state is read again.
* This also implies that if UTxOs disappear during script operation because another software spends UTxOs from the same wallet concurrently, defrag-ops.py won't realize this and will likely end up throwning an error due to trying to spend missing UTxOs.
* While a `--dynamic` option can be specified at a heavy performance cost to reduce the risk of spending missing UTxOs, it is advised to simply not perform other spend transactions on the wallet while defrag-ops.py is running.


## Useful Diagnostic Commands:

* The following commands are useful for following progress of fragmentation and defragmentation operations by monitoring wallet UTxO distribution, UTxO sum and wallet total addresses:
```
# This command only needs to be executed once
$ export WALLET=<YOUR_WALLET_ID_HERE>

# This command can be executed for updated status (adjust as needed for your specific wallet endpoint):
$ curl -s http://localhost:8090/v2/byron-wallets/$WALLET/statistics/utxos | jq --sort-keys . \
  && echo "Total UTxO: $(curl -s http://localhost:8090/v2/byron-wallets/$WALLET/statistics/utxos | jq ".distribution | add")" \
  && echo "Total addresses: $(curl -s http://localhost:8090/v2/byron-wallets/$WALLET/addresses | jq ". | length")"
```

* The following command is useful to query UTxO status on the bootstrap address (the `--testnet-magic` option should be removed or adjusted for networks other than public testnet):
```
cardano-cli query utxo --mary-era --testnet-magic 1097911063 --address $BOOTSTRAP_ADDRESS
```

## Options Common to Defrag Ops

* All available command options are shown in defrag-ops.py help:
```
$ ./defrag-ops.py --help
```

* Options and arguments enclosed in no brackets are required.
* Options and arguments enclosed in round brackets () are required to have one of the option elements included.
* Options and arguments enclosed in square brackets [] are not required.

* The following options are required by the `defrag` command, as they have no bracket (square or round):
```
--mnemonics M_PATH                                 # Where M_PATH is a path to the file holding the mnemonics secret words for the wallet
--wid W_ID                                         # Where W_ID is the wallet ID from cardano-wallet
--wpass W_PATH                                     # Where W_PATH is a path to the file holding the wallet secret passphrase
--wdb DB_PATH                                      # Where DB_PATH is a path to the cardano-wallet sqlite3 file for the wallet
```

* The following option requires at least one option element, the network to connect to, to be provided from within the rounded brackets.
* A non-default network protocol magic override can be optionally provided if a network other than the public mainnet, staging or testnet are to be connected to:
```
(--testnet | --staging | --mainnet) [--magic NUM]  # Network selection (required) and network protocol magic (optional)
```

* The following options are not required but are available to the defrag command:
```
[--socket S_PATH]                                  # To provide the cardano-node socket path if not exported to env var CARDANO_NODE_SOCKET_PATH
[--ip IP]                                          # To provide the ip to cardano-wallet server (defaults to 127.0.0.1)
[--port PORT]                                      # To provide the port to cardano-wallet server (defaults to 8090)
[--tls]                                            # To set API calls to use HTTPS with cardano-wallet server
[--live]                                           # To run an operation live rather than dry
[--no-confirm]                                     # To skip a live run confirmation safety prompt
[--timeout SECS]                                   # To specify the connection and read timeout for API calls to cardano-wallet server
[--dynamic]                                        # To specify wallet UTxO state should be re-obtained after each transaction to check for missing UTxOs
[-d]                                               # To log DEBUG level information
[--min UTXO]                                       # To override the network protocol specified default for minimum lovelace per UTxO
[--max INPUTS]                                     # To set the maximum number of inputs per transaction (defaults to 70)
[--repeat COUNT]                                   # To repeat the specified frag or defrag transaction COUNT times (defaults to 1)
[--timers]                                         # To log timer information
[--filter TARGET METHOD EXPR]                      # To filter input utxos against either a numerical or python regex comparison
```

* The `--dynamic` option has a large performance cost and can slow down operations drastically.  Generally it is not needed unless defragmentation will be performed on a wallet which will be concurrently sending out ADA.  This option will help mitigate, but not eliminate, the risk of defrag failure due to the script trying to spend a UTxO it thinks is available but which has actually disappeared due to a concurrent send from another software.  It is therefore recommended to perform defrag operations when no other wallet operations are on-going.
* See the output from the defrag-ops.py help for more details on these options:
```
$ ./defrag-ops.py --help
```


### Defragmentation Usage Examples

* To defragment UTxO from a wallet to the bootstrap address, a dry run example command on testnet is:
```
$ ./defrag-ops.py defrag --mnemonics ./mnemonics.txt \
                     --wid d30d35ff48e7266c139430158b6df9e0a9729904 \
                     --wpass ./passphrase.txt \
                     --wdb /var/lib/my_wallet_db_storage/testnet/rnd.d30d35ff48e7266c139430158b6df9e0a9729904.sqlite \
                     --testnet
```

* This is quite verbose -- let's wrap up these common options into an environment variable so we don't need to keep repeating them.
* The output will be the initial bootstrap address followed by a transaction  and operations summary, similar to the following:
```
$ export COMMON="--mnemonics $PATH_TO_MNEMONICS_FILE --wid $WALLETID --wpass $PATH_TO_PASS_FILE --wdb $PATH_TO_WALLET_DB --testnet"

$ ./defrag-ops.py defrag $COMMON

<...snip bootstrap address info...>

Starting defragmentation ops (dry-run):

Defragment operation 1 of 1 started at 2021-03-03 18:37:34 UTC with 1642 non-asset utxo inputs to be processed:
Tx ready: (inputs, outputs, inSum, outSum, change, fees) = (70, 0 + change_addr, 470031904, 0, 469186163, 845741)...
    ...dry run -- not submitting Tx to the network (txid: bbabca2f54269e3e147f1d87677f269b2b5bc48ed849ab79fd39fd0075f963c2)
Cache (drvHits, skeyHits, drvLen, skeyLen): (70, 0, 100506, 70), Dust algorithm: simple
Operation time: 00:00:05.808, Elapsed time: 00:00:05



Summary of defragmentation dry-run on Cardano network TESTNET (1097911063) finished at 2021-03-03 18:37:40 UTC

Total transactions prepared:        1
Total fees estimated (lovelace):    845741
Total inputs prepared:              70
Total outputs prepared:             0               (not including change_addr)
Elapsed runtime:                    00:00:05        (hh:mm:ss)
```

* In the output above, we can see relevant information including:
  * The network is `TESTNET (1097911063)`.
  * This is a `dry run`.
  * The script found 1642 non-asset UTxO input available to utilize for the operation: `...with 1642 non-asset utxo inputs to be processed`.
  * The transaction summarizes: 70 inputs, 0 outputs plus a change address output.
  * The transaction summarizes: the input sum value (inSum: at about 470 ADA), output sum value (outSum: at 0 ADA).
  * The transaction summarizes: the change amount (change: at about 469 ADA), the fee (fees: at about 0.8 ADA).
  * The transaction id, which can be checked on the network's blockchain explorer for `live` submissions.

* If the same command as above is re-run with the additional `-d` option for debug logging, details of the tx-ins and tx-outs are shown:
```
<...snip...>
# Debug Output:
--tx-in 45f57a4d41ee0fbd9dfffda950d617c537ef0b35d4283abe39c8d37a972105cb#1
--tx-in 45f57a4d41ee0fbd9dfffda950d617c537ef0b35d4283abe39c8d37a972105cb#4
--tx-in 45f57a4d41ee0fbd9dfffda950d617c537ef0b35d4283abe39c8d37a972105cb#5
<...snip...>
```


## Defragmentation Operations:

* By default, the defragmentation command `defrag` will collect up to the `--max` number of UTxOs, sorted by smallest first and send them all as a single UTxO output transaction to the bootstrap address.
* The maximum number of UTxOs per single transaction is about 70.  Going higher will likely result in the network rejecting the transaction and defrag-ops.py will warn about this if `--max` is set higher than 70.
* Defragmentation requires no funding in the bootstrap address as the `defrag` operation will collect funds from other addresses in the wallet and return them as a larger UTxO into the bootstrap address, less the transaction fee.
* Basic defragmentation example commands are:
```
# Defrag 70 UTxO into the bootstrap address
$ ./defrag-ops.py defrag $COMMON

# Defrag 70 UTxO into the bootstrap address, repeating 10 times
# (700 UTxO reduction in total from non-bootstrap addresses)
$ ./defrag-ops.py defrag $COMMON --repeat 10
```

* In the case of `defrag` operation, since each transaction collects new UTxOs that are available and these input UTxOs fund the defragmentation transaction, there are no concerns about waiting for UTxOs to settle before repeating the next defragmentation transaction.
* `defrag` operations require each input UTxO to have a secret key calculated and provided as a transaction witness.  This means that typically 70 secrets keys need to be generated per `defrag` transaction.  To improve performance, two dictionary lookup tables in memory are used to avoid repeating key calculations for UTxOs which already had shared address calculations performed during preparation of a previous transaction.  Cache hit and size information is provided with each transaction summary, an example of which is:
```
Cache (drvHits, skeyHits, drvLen, skeyLen): (54, 6, 103695, 1638), Dust algorithm: simple
```

### Dust Collection

* On networks where there is a minimum UTxO, a wallet with a lot of small dust from the Byron era may not have its smallest `--max` number of UTxO sum to the `--min` UTxO value of the network.
* In this case, a dust algorithm is employed.
* The general order of attempts to meet the UTxO minimum value plus fee threshold is to select `--max` input UTxOs using the following algorithms: simple, sliding UTxO, sliding window:
  * Simple: select the smallest `--max` number of UTxO (70 by default) and sum them.
  * Sliding UTxO: select the smallest `--max` number of UTxO - 1 (69 by default) and try to find a single last UTxO so the sum as a group will be large enough.
  * Sliding Window: select the smallest `--max` number of UTxO (70 by default) from the full UTxO value sorted list.  Increment the position of the full group in the sorted list of UTxO elements by 1 and re-sum, repeating until the group sums to meet the requirement.
* Whichever algorithm is utilized in composing the `defrag` transaction will be shown in the transaction summary as: `Dust algorithm: $TYPE`, like in the example above.
* When defragmenting a dusty wallet, depending on the UTxO distribution several passes may need to be made to finish a full `defrag`.  See the "Testing Dust Algorithms" section below for ideas on how to enhance a dusty wallet `defrag`.


### Full Wallet Defragmentation

* To fully `defrag` a wallet down to a single UTxO, multiple passes are needed.
* This is because defrag-ops.py only checks global wallet state for new UTxOs to `defrag` during startup, and also because during operation 1 new change UTxO output to the bootstrap address is created for every transaction.  The change address UTxOs generated during defrag operation cannot themselves be defragmented in the same command.

* Let's take a medium sized fragmented wallet to illustrate.
* If this wallet has 6366 UTxO, all NOT in the bootstrap address, and we can defragment 70 UTxO per transaction, we can run a defrag with a `--repeat` option set to at least 6366 / 70 = 91 transactions (rounding up):
```
# Defrag up to 70 UTxO into the bootstrap address per Tx, repeating 91 times
$ ./defrag-ops.py defrag $COMMON --repeat 91
```

* This works, but since we had 91 `defrag` transactions, we now have 91 new UTxO that exist in the bootstrap address as change.  The wallet before the defragmentation had 6366 UTxO and now has 91 UTxO.  Double check this with the "Useful Diagnostic Commands" from above to convince yourself.
* Now we can repeat the defrag command again, but this time with a `--repeat` of 2 which is sufficient to `defrag` 91 UTxOs:
```
# Defrag up to 70 UTxO into the bootstrap address per Tx, repeating 2 times
$ ./defrag-ops.py defrag $COMMON --repeat 2
```

* And now we have 2 UTxO in the bootstrap address which are change UTxO from the above 2 `defrag` transactions.  Running the `defrag` command once more without the `--repeat` option (since it defaults to 1) will reduce the remaining 2 UTxO to a single large value UTxO in the bootstrap address.
* Since the wallet recognizes the bootstrap address and the UTxO in it, this large value single UTxO can be spent like any other UTxO of the wallet.


## Advanced Defrag Ops


### Defragging the Bootstrap Address Only

* If a substantial amount of dust develops in the bootstrap address, the UTxOs in the bootstrap address alone can be defragmented without modifying the rest of the wallet.
* This can be done by using an input filter option: `--filter`, which takes arguments of `TARGET`, `METHOD` and `EXPR` (expression) and removes any inputs for which `EXPR` evaluates `True`.
* The `TARGET` of a `--filter` can be a UTxO (TX_HASH#TX_IX), an address or a lovelace amount.
* The `METHOD` can be one of "re", "eq", "ne", "gt", "gte", "lt", "lte", which stand for python regex, or the common mathematic operators.
* The `EXPR` will be either a python regular expression for the case of `METHOD` "re", or an integer.
* Only a `TARGET` of lovelace can be used with the mathematic comparison operator `METHOD`s.
* For an address as the `TARGET`, the address must be provided in hexidecimal format rather than base58.
* To convert between base58 and hexidecimal address format, the base58, xxd and tr binaries can be used (also provided in nix-shell).
* Conversion examples are:
```
# Base58 to Hex conversion:
# Base58 example address:
# 37btjrVyb4KDdVL9vqtU4P9caQKp3pvnCRtT22pGnGmAGJTafKb9UEjE4Uo8Mgr9Nba14uCrL1n7qPwsXhWUT8ziGdhkDaByPNx5DGaY6fVioDfhyc

$ echo -n $BASE58_ADDR | base58 -d | xxd -p | tr -d '\n'
82d818584983581c8397944db375bd2482cc3e552cec44d7a4e7063b7bf5e08c5c7535e2a201581e581c3c6f3168cf6399afdc692da940bbd49d4dbfa772b78e3a819f985d2d02451a4170cb17001a5c99fe23


# Hex to Base58 conversion:
# Hex example address:
# 82d818584983581c8397944db375bd2482cc3e552cec44d7a4e7063b7bf5e08c5c7535e2a201581e581c3c6f3168cf6399afdc692da940bbd49d4dbfa772b78e3a819f985d2d02451a4170cb17001a5c99fe23
$ echo -n $HEX_ADDR | xxd -p -r | base58
37btjrVyb4KDdVL9vqtU4P9caQKp3pvnCRtT22pGnGmAGJTafKb9UEjE4Uo8Mgr9Nba14uCrL1n7qPwsXhWUT8ziGdhkDaByPNx5DGaY6fVioDfhyc
```

* The filter will remove any input UTxOs which returns `True` for the given `TARGET`, `METHOD` and `EXPR` evaluation.
* To now `defrag` only the bootstrap address, we can filter the wallet's input UTxO to exclude all UTxO from consideration except the bootstrap addresses UTxOs, using a negative regex lookahead and substituting the hex format of the bootstrap address into the `<HEX_ADDRESS>` parameter of the following command:
```
# Use the `--repeat X` option if needed
$ ./defrag-ops.py defrag $COMMON --filter address re '^(?!<HEX_ADDRESS>).*$'
```

* The filter feature can be used creatively for other advanced `defrag` operations.
