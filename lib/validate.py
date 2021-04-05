import docopt
import ipaddress
import lib.cardano
import lib.objects
import lib.utility
import lib.wallet
import logging
import os
import re
import semver
import stat
import sys
import time


def confirm(logger: logging.Logger, level: int, prompt: str) -> bool:
    """ Prompts a user for confirmation after a prompt question """

    logger.log(level, prompt)
    try:
        answer = input()
        if answer.lower()[0] == "y":
            return True
    except EOFError:
        return False

    return False


def validate_args(ops: lib.objects.OpsState, arguments: docopt.Dict) -> None:
    """ Validates passed arguments from CLI and sets ops state """

    logger = ops.g_logger

    timer = time.time()

    # Required validation for all sub-commands
    validate_mnemonics(ops, arguments["--mnemonics"])

    # Set the network specification
    if arguments["--mainnet"]:
        setattr(ops, "g_network", "mainnet")
        setattr(ops, "g_network_id", "764824073")
    elif arguments["--testnet"]:
        setattr(ops, "g_network", "testnet")
        setattr(ops, "g_network_id", "1097911063")
    elif arguments["--staging"]:
        setattr(ops, "g_network", "staging")
        setattr(ops, "g_network_id", "633343913")
    else:
        logger.error("ERROR: A recognized network was not specified.")
        logger.error(
            "Use either the `--mainnet` (mainnet), `--testnet` (testnet), or `--staging` (staging) option and try again."
        )
        sys.exit(1)

    # Override the network protocol magic with a custom value if provided
    if arguments["--magic"]:
        validate_magic(logger, arguments["--magic"])
        setattr(ops, "g_network_id", arguments["--magic"])

    if arguments["frag"]:
        validate_tx_output_count(ops, arguments["--outputs"])
        validate_tx_output_lovelace(ops, arguments["--total"])

        # Set the mode to `frag`
        setattr(ops, "g_frag", True)

        # Set the tx_out having the byron bootstrap address
        if arguments["--bootstrap"]:
            setattr(ops, "g_tx_output_frag_address", "bootstrap")
        elif arguments["--random"]:
            setattr(ops, "g_tx_output_frag_address", "random")
        elif arguments["--new"]:
            setattr(ops, "g_tx_output_frag_address", "new")
        else:
            logger.error(
                "ERROR: An output address type of `--bootstrap`, `--random`, or `--new` must be specified."
            )
            sys.exit(1)

        # Set the total lovelace distribution to even instead of random
        if arguments["--even"]:
            setattr(ops, "g_tx_output_evenly", True)

    if arguments["defrag"]:
        # Set the mode to `defrag`
        setattr(ops, "g_frag", False)

    if arguments["frag"] or arguments["defrag"]:
        validate_wallet_id(ops, arguments["--wid"])
        validate_wallet_id_passphrase(ops, arguments["--wpass"])
        validate_wallet_db(ops, arguments["--wdb"])
        validate_tx_max_inputs(ops, arguments["--max"])
        validate_tx_repeat_count(ops, arguments["--repeat"])
        validate_node_socket_path(
            ops, arguments["--socket"], "CARDANO_NODE_SOCKET_PATH"
        )
        validate_wallet_ip(ops, arguments["--ip"])
        validate_wallet_port(ops, arguments["--port"])
        validate_timeout(ops, arguments["--timeout"])

        # Set the no confirm flag
        if arguments["--no-confirm"]:
            setattr(ops, "g_confirm", False)

        # Set the min utxo parameter
        if arguments["--min"]:
            setattr(ops, "g_network_min_utxo_override", True)
            validate_tx_min_utxo(ops, arguments["--min"])

        # Validate an input filter if given
        if arguments["--filter"]:
            validate_filter(
                ops, arguments["--filter"], arguments["METHOD"], arguments["EXPR"]
            )

        # Set the timers flag
        if arguments["--timers"]:
            setattr(ops, "g_timers", True)

        # Set the live run flag
        if arguments["--live"]:
            setattr(ops, "g_live", True)

        # Set the no confirm flag
        if arguments["--no-confirm"]:
            setattr(ops, "g_confirm", False)

        # Set the dynamic flag
        if arguments["--dynamic"]:
            setattr(ops, "g_dynamic", True)

        # Set the http/s protocol
        if arguments["--tls"]:
            setattr(ops, "g_wallet_tls", True)

    if ops.g_timers:
        logger.info(
            f"Time to validate arguments: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )


def validate_bash_version(ops: lib.objects.OpsState) -> None:
    """ Validates bash shell is an acceptable version """

    logger = ops.g_logger

    result = lib.utility.shell_cmd(
        ops, 'echo "${BASH_VERSION}"', self_check=True, shell=True
    )
    bash_ver = re.split(r"[^0-9.]", result.stdout)[0]

    if semver.compare(bash_ver, ops.MIN_BASH_VER) < 0:
        logger.error(
            f"ERROR: bash version {bash_ver} is less than the version required: {ops.MIN_BASH_VER}"
        )
        sys.exit(1)

    logger.debug(f"bash ver: {bash_ver}")


def validate_cardano_address_version(ops: lib.objects.OpsState) -> None:
    """ Validates cardano-address is an acceptable version, warn if not, and set ops state """

    logger = ops.g_logger

    result = lib.utility.shell_cmd(ops, "cardano-address", ["version"], self_check=True)

    # Expected output format of the `cardano-address version` command is:
    # $MAJOR.$MINOR.$PATCH @ $REV

    cardano_address_ver_output = result.stdout
    cardano_address_regex = re.search(
        r"(\d+.\d+.\d+) @ ([a-f0-9]{40})", cardano_address_ver_output
    )

    if cardano_address_regex is not None and cardano_address_regex.group(1) is not None:
        cardano_address_tag = cardano_address_regex.group(1)
    else:
        logger.error(
            "ERROR: a recognized cardano-address version tag was not found in the output of: "
            + "`cardano-address version`\n"
            + f"STDOUT: {result.stdout.strip()}\n"
            + f"STDERR: {result.stderr.strip()}"
        )
        sys.exit(1)

    if cardano_address_regex is not None and cardano_address_regex.group(2) is not None:
        cardano_address_rev = cardano_address_regex.group(2)
    else:
        logger.error(
            "ERROR: a recognized cardano-address revision was not found in the output of: "
            + "`cardano-address version`\n"
            + f"STDOUT: {result.stdout.strip()}\n"
            + f"STDERR: {result.stderr.strip()}"
        )
        sys.exit(1)

    if cardano_address_tag not in ops.ACCEPT_CARDANO_ADDRESS_VER.keys() or (
        cardano_address_tag in ops.ACCEPT_CARDANO_ADDRESS_VER
        and cardano_address_rev != ops.ACCEPT_CARDANO_ADDRESS_VER[cardano_address_tag]
    ):
        logger.warning(
            f"WARNING: The cardano-address version of tag {cardano_address_tag} and revision {cardano_address_rev} is not a supported cardano-address version."
        )
        logger.warning(
            "WARNING: See the README.md for supported versions.  Unless you know what you are doing, you should stop and install a supported version."
        )
        logger.warning("WARNING:")
        logger.warning(
            "WARNING: Do you wish to proceed with an unsupported version of cardano-address, which may have unexpected results?"
        )
        logger.warning("WARNING:")
        if ops.g_confirm:
            if not lib.validate.confirm(
                logger, logging.WARNING, "WARNING: Do you wish to proceed? (y/n): "
            ):
                logger.info("")
                logger.info("Aborting.")
                sys.exit(0)
        else:
            logger.warning(
                'WARNING: Skipping confirmation as the "no confirm" (`--no-confirm`) option was given.'
            )
        logger.info("")

    setattr(ops, "g_cardano_address_tag", cardano_address_tag)
    setattr(ops, "g_cardano_address_rev", cardano_address_rev)

    logger.debug(f"cardano-address tag: {cardano_address_tag}")
    logger.debug(f"cardano-address rev: {cardano_address_rev}")


def validate_cardano_cli_version(ops: lib.objects.OpsState) -> None:
    """ Validates cardano-cli is an acceptable version, warn if not, and set ops state """

    logger = ops.g_logger

    result = lib.utility.shell_cmd(ops, "cardano-cli", ["--version"], self_check=True)

    # Expected output format of the `cardano-cli --version` command is:
    # cardano-cli $MAJOR.$MINOR.$PATCH - $SYSTEM - $GHCVER
    # git rev $REV

    cardano_cli_ver_output = result.stdout
    cardano_cli_regex = re.search(
        r"cardano-cli (\d+.\d+.\d+) .*\ngit rev ([a-f0-9]{40})", cardano_cli_ver_output
    )

    if cardano_cli_regex is not None and cardano_cli_regex.group(1) is not None:
        cardano_cli_tag = cardano_cli_regex.group(1)
    else:
        logger.error(
            "ERROR: a recognized cardano-cli version tag was not found in the output of: "
            + "`cardano-cli --version`\n"
            + f"STDOUT: {result.stdout.strip()}\n"
            + f"STDERR: {result.stderr.strip()}"
        )
        sys.exit(1)

    if cardano_cli_regex is not None and cardano_cli_regex.group(2) is not None:
        cardano_cli_rev = cardano_cli_regex.group(2)
    else:
        logger.error(
            "ERROR: a recognized cardano-cli revision was not found in the output of: "
            + "`cardano-cli --version`\n"
            + f"STDOUT: {result.stdout.strip()}\n"
            + f"STDERR: {result.stderr.strip()}"
        )
        sys.exit(1)

    if cardano_cli_tag not in ops.ACCEPT_CARDANO_CLI_VER.keys() or (
        cardano_cli_tag in ops.ACCEPT_CARDANO_CLI_VER
        and cardano_cli_rev != ops.ACCEPT_CARDANO_CLI_VER[cardano_cli_tag]
    ):
        logger.warning(
            f"WARNING: The cardano-cli version of tag {cardano_cli_tag} and revision {cardano_cli_rev} is not a supported cardano-cli version."
        )
        logger.warning(
            "WARNING: See the README.md for supported versions.  Unless you know what you are doing, you should stop and install a supported version."
        )
        logger.warning("WARNING:")
        logger.warning(
            "WARNING: Do you wish to proceed with an unsupported version of cardano-cli, which may have unexpected results?"
        )
        logger.warning("WARNING:")
        if ops.g_confirm:
            if not lib.validate.confirm(
                logger, logging.WARNING, "WARNING: Do you wish to proceed? (y/n): "
            ):
                logger.info("")
                logger.info("Aborting.")
                sys.exit(0)
        else:
            logger.warning(
                'WARNING: Skipping confirmation as the "no confirm" (`--no-confirm`) option was given.'
            )
        logger.info("")

    setattr(ops, "g_cardano_cli_tag", cardano_cli_tag)
    setattr(ops, "g_cardano_cli_rev", cardano_cli_rev)

    logger.debug(f"cardano-cli tag: {cardano_cli_tag}")
    logger.debug(f"cardano-cli rev: {cardano_cli_rev}")


def validate_cardano_wallet_version(ops: lib.objects.OpsState) -> None:
    """ Validates cardano-wallet is an acceptable version, warn if not, and set ops state """

    logger = ops.g_logger

    result = lib.utility.shell_cmd(ops, "cardano-wallet", ["version"], self_check=True)

    # Expected output format of the `cardano-wallet version` command is:
    # $YEAR.$MONTH.$DAY (git revision: $REV)

    cardano_wallet_ver_output = result.stdout
    cardano_wallet_regex = re.search(
        r"(\d+.\d+.\d+) \(git revision: ([a-f0-9]{40})\)", cardano_wallet_ver_output
    )

    if cardano_wallet_regex is not None and cardano_wallet_regex.group(1) is not None:
        cardano_wallet_tag = cardano_wallet_regex.group(1)
    else:
        logger.error(
            "ERROR: a recognized cardano-wallet version tag was not found in the output of: "
            + "`cardano-wallet version`\n"
            + f"STDOUT: {result.stdout.strip()}\n"
            + f"STDERR: {result.stderr.strip()}"
        )
        sys.exit(1)

    if cardano_wallet_regex is not None and cardano_wallet_regex.group(2) is not None:
        cardano_wallet_rev = cardano_wallet_regex.group(2)
    else:
        logger.error(
            "ERROR: a recognized cardano-wallet revision was not found in the output of: "
            + "`cardano-wallet version`\n"
            + f"STDOUT: {result.stdout.strip()}\n"
            + f"STDERR: {result.stderr.strip()}"
        )
        sys.exit(1)

    if cardano_wallet_tag not in ops.ACCEPT_CARDANO_WALLET_VER.keys() or (
        cardano_wallet_tag in ops.ACCEPT_CARDANO_WALLET_VER
        and cardano_wallet_rev != ops.ACCEPT_CARDANO_WALLET_VER[cardano_wallet_tag]
    ):
        logger.warning(
            f"WARNING: The cardano-wallet version of tag {cardano_wallet_tag} and revision {cardano_wallet_rev} is not a supported cardano-wallet version."
        )
        logger.warning(
            "WARNING: See the README.md for supported versions.  Unless you know what you are doing, you should stop and install a supported version."
        )
        logger.warning("WARNING:")
        logger.warning(
            "WARNING: Do you wish to proceed with an unsupported version of cardano-wallet, which may have unexpected results?"
        )
        logger.warning("WARNING:")
        if ops.g_confirm:
            if not lib.validate.confirm(
                logger, logging.WARNING, "WARNING: Do you wish to proceed? (y/n): "
            ):
                logger.info("")
                logger.info("Aborting.")
                sys.exit(0)
        else:
            logger.warning(
                'WARNING: Skipping confirmation as the "no confirm" (`--no-confirm`) option was given.'
            )
        logger.info("")

    setattr(ops, "g_cardano_wallet_tag", cardano_wallet_tag)
    setattr(ops, "g_cardano_wallet_rev", cardano_wallet_rev)

    logger.debug(f"cardano-wallet tag: {cardano_wallet_tag}")
    logger.debug(f"cardano-wallet rev: {cardano_wallet_rev}")


def validate_deps(ops: lib.objects.OpsState, arguments: docopt.Dict) -> None:
    """ Validates the required dependencies are available """

    logger = ops.g_logger

    timer = time.time()

    for dep in ops.BINARY_DEPS:
        lib.utility.cmd_exists(ops, dep)

    validate_bash_version(ops)
    validate_cardano_address_version(ops)
    validate_cardano_cli_version(ops)
    validate_cardano_wallet_version(ops)

    if arguments["frag"] or arguments["defrag"]:
        validate_wallet_server(ops)
        validate_wallet_id_health(ops)

    if ops.g_timers:
        logger.info(
            f"Time to validate dependencies: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )


def validate_file(logger: logging.Logger, path: str, read: bool = False) -> str:
    """ Validates a file exists and is readable """

    contents = None
    try:
        file = open(path, "r")
        if read:
            contents = file.read()
    except Exception:
        logger.exception(f"ERROR: Unable to read the file: {path}")
        sys.exit(1)
    else:
        file.close()

    if contents is None:
        return ""
    else:
        return contents


def validate_filter(
    ops: lib.objects.OpsState, target: str, method: str, expression: str
) -> None:
    """ Validates an input filter has the proper structure and sets ops state """

    logger = ops.g_logger

    if target not in ["utxo", "address", "lovelace"]:
        logger.error(
            f'ERROR: Input filter TARGET must be one of "utxo", "address", "lovelace": {target}'
        )
        sys.exit(1)

    if method not in ["re", "eq", "ne", "gt", "gte", "lt", "lte"]:
        logger.error(
            f'ERROR: Input filter METHOD must be one of "re", "eq", "ne", "gt", "gte", "lt", "lte": {method}'
        )
        sys.exit(1)

    if target in ["utxo", "address"] and method != "re":
        logger.error(
            f'ERROR: Input filter TARGET "{target}" must use a METHOD of "re": {method}'
        )
        sys.exit(1)

    if target == "lovelace" and method in ["eq", "ne", "gt", "gte", "lt", "lte"]:
        try:
            lovelace_int = int(expression, 10)
            if lovelace_int < 1:
                logger.error(
                    f'ERROR: Input filter TARGET "{target}" with METHOD "{method}" must have an expression value greater than 1: {expression}'
                )
                sys.exit(1)
        except Exception:
            logger.exception(
                f'ERROR: Input filter TARGET "{target}" with METHOD "{method}" has an expression that is not an integer: {expression}'
            )
            sys.exit(1)

    if method == "re":
        try:
            re.compile(expression)
        except re.error:
            logger.exception(
                f'ERROR: Input filter METHOD "{method}" must be a valid python regular expression: {expression}'
            )
            sys.exit(1)

    setattr(ops, "g_filter_tx_in", True)
    setattr(ops, "g_filter_tx_in_target", target)
    setattr(ops, "g_filter_tx_in_method", method)
    if method in ["eq", "ne", "gt", "gte", "lt", "lte"]:
        setattr(ops, "g_filter_tx_in_expr", lovelace_int)
    else:
        setattr(ops, "g_filter_tx_in_expr", expression)


def validate_ip(logger: logging.Logger, ip: str) -> str:
    """ Validates an IP is valid IPv4 or IPv6 """

    try:
        ipaddress.ip_address(ip)
    except Exception:
        logger.exception(
            f"ERROR: IP address given not recognized as IPv4 or IPv6: {ip}"
        )
        sys.exit(1)
    return ip


def validate_port(logger: logging.Logger, port: str) -> str:
    """ Validates a port is valid """

    try:
        port_int = int(port, 10)
        if not (1 <= port_int <= 65535):
            logger.error(f"ERROR: Port not between 1 and 65535: {port}")
            sys.exit(1)
    except Exception:
        logger.exception(f"ERROR: Port not an integer: {port}")
        sys.exit(1)
    return port


def validate_magic(logger: logging.Logger, magic: str) -> None:
    """ Validates a non-default network magic number is a positive integer or zero """

    try:
        magic_int = int(magic, 10)
        if magic_int < 0:
            logger.error(
                f"ERROR: The network protocol magic number must a positive integer or zero: {magic}"
            )
            sys.exit(1)
    except Exception:
        logger.exception(
            f"ERROR: Network protocol magic given is not an integer: {magic}"
        )
        sys.exit(1)


def validate_mnemonics(ops: lib.objects.OpsState, path: str) -> None:
    """ Validates a mnemonics file contains expected mnemonics and sets ops state """

    logger = ops.g_logger

    mnemonics = validate_file(logger, path, read=True)
    if len(mnemonics.strip().split()) != 12:
        logger.error(
            f"ERROR: There are not 12 mnemonics for a Byron random address in the mnemonics file: {path}"
        )
        sys.exit(1)

    setattr(ops, "g_mnemonics", mnemonics.strip())


def validate_node_socket_path(
    ops: lib.objects.OpsState, path: str, env_var: str
) -> None:
    """ Validates a socket file exists from a path or env var and sets ops state """

    logger = ops.g_logger

    cardano_node_socket_path = os.getenv(env_var)
    if path is None and cardano_node_socket_path is None:
        logger.error("ERROR: Unable to parse the socket path.")
        logger.error(
            f"Set the socket path with the `-s` option or by setting ${env_var} env var."
        )
        sys.exit(1)
    else:
        if path is not None:
            validate_socket_file(logger, path)
            setattr(ops, "g_socket_path", path)
        else:
            validate_socket_file(logger, cardano_node_socket_path)
            setattr(ops, "g_socket_path", cardano_node_socket_path)


def validate_socket_file(logger: logging.Logger, path: str) -> None:
    """ Validates a socket file exists """

    try:
        mode = os.stat(path).st_mode
        isSocket = stat.S_ISSOCK(mode)
        if not isSocket:
            logger.error(
                f"ERROR: The socket path given does not point to a socket file: {path}"
            )
            sys.exit(1)
    except Exception:
        logger.exception(f"ERROR: Unable to check the socket file: {path}")
        sys.exit(1)


def validate_timeout(ops: lib.objects.OpsState, seconds: str) -> None:
    """ Validates a timeout for conn and read wallet API calls and sets ops state """

    logger = ops.g_logger

    try:
        seconds_int = int(seconds, 10)
        if seconds_int < 1:
            logger.error(f"ERROR: Timeout given must be greater than 0: {seconds}")
            sys.exit(1)
    except Exception:
        logger.exception(f"ERROR: Timeout given is not an integer: {seconds}")
        sys.exit(1)

    setattr(ops, "g_api_timeout", seconds_int)


def validate_tx_max_inputs(ops: lib.objects.OpsState, count: str) -> None:
    """ Validates a maximum number of tx inputs as a constraint argument and sets ops state """

    logger = ops.g_logger

    try:
        count_int = int(count, 10)
        if count_int > 70:
            logger.warning(
                f"WARNING: Maximum transaction inputs may not be accepted on the network above 70: {count}"
            )
            logger.warning(
                "WARNING: Live fragmentation or defragmentation operations may fail."
            )
        elif ops.g_frag and count_int < 1:
            logger.error(
                f"ERROR: Maximum transaction inputs for fragmentation operations must be 1 or greater: {count}"
            )
            sys.exit(1)
        elif not ops.g_frag and count_int < 2:
            logger.error(
                f"ERROR: Maximum transaction inputs for defragmentation operations must be 2 or greater: {count}"
            )
            sys.exit(1)
    except Exception:
        logger.exception(
            f"ERROR: Maximum transaction inputs is not an integer: {count}"
        )
        sys.exit(1)

    setattr(ops, "g_tx_max_inputs", count_int)


def validate_tx_min_utxo(ops: lib.objects.OpsState, lovelace: str) -> None:
    """ Validates a minimum UTxO argument constraint and sets ops state """

    logger = ops.g_logger

    try:
        lovelace_int = int(lovelace, 10)
        if lovelace_int < 0:
            logger.error(
                f"ERROR: Minimum lovelace per UTxO must be zero or greater: {lovelace}"
            )
            sys.exit(1)
    except Exception:
        logger.exception(
            f"ERROR: Minimum lovelace per UTxO given is not an integer: {lovelace}"
        )
        sys.exit(1)

    lib.cardano.cardano_cli_protocol_params(ops)

    if lovelace_int != ops.g_network_protocol_params_min_utxo:
        logger.warning(
            f"WARNING: Minimum lovelace per UTxO on this network set by network protocol is {ops.g_network_protocol_params_min_utxo}."
        )
        logger.warning(
            f"WARNING: Minimum lovelace per UTxO specified on the command line is: {lovelace}"
        )
        logger.warning(
            "WARNING: Generally, unless you know what you are doing and why, you should leave the `--min` parameter at its default network protocol value."
        )
        logger.warning("WARNING:")
        if ops.g_confirm:
            if not confirm(
                logger, logging.WARNING, "WARNING: Do you wish to proceed? (y/n): "
            ):
                logger.info("")
                logger.info("Aborting.")
                sys.exit(0)
        else:
            logger.warning(
                'WARNING: Skipping confirmation as the "no confirm" (`--no-confirm`) option was given.'
            )
        logger.info("")

    setattr(ops, "g_tx_output_min_utxo", lovelace_int)


def validate_tx_output_count(ops: lib.objects.OpsState, count: str) -> None:
    """ Validates a transaction output count set point is valid and sets ops state """

    logger = ops.g_logger

    try:
        count_int = int(count, 10)
        if not (1 <= count_int <= 150):
            if count_int < 1:
                logger.error(
                    f"ERROR: Transaction output count is not greater than 1: {count}"
                )
                sys.exit(1)
            else:
                logger.warning(
                    f"WARNING: Transaction outputs per Tx may not be accepted on the network around 150 or above: {count}"
                )
    except Exception:
        logger.exception(
            f"ERROR: Transaction output count given is not an integer: {count}"
        )
        sys.exit(1)

    setattr(ops, "g_tx_output_count", count_int)


def validate_tx_output_lovelace(ops: lib.objects.OpsState, lovelace: str) -> None:
    """ Validates a transaction output total lovelace count and sets ops state """

    logger = ops.g_logger

    try:
        lovelace_int = int(lovelace, 10)
        if lovelace_int < 1:
            logger.error(
                f"ERROR: Lovelace total per transaction given is not greater than 1: {lovelace}"
            )
            sys.exit(1)
    except Exception:
        logger.exception(
            f"ERROR: Lovelace total per transaction given is not an integer: {lovelace}"
        )
        sys.exit(1)

    setattr(ops, "g_tx_output_lovelace", lovelace_int)


def validate_tx_repeat_count(ops: lib.objects.OpsState, count: str) -> None:
    """ Validates a transaction operation repeat count and sets ops state """

    logger = ops.g_logger

    try:
        count_int = int(count, 10)
        if count_int < 1:
            logger.error(
                f"ERROR: Transaction operation repeat count given is not greater than or equal to 1: {count}"
            )
            sys.exit(1)
    except Exception:
        logger.exception(
            f"ERROR: Transaction operation repeat count given is not an integer: {count}"
        )
        sys.exit(1)

    setattr(ops, "g_tx_repeat", count_int)


def validate_wallet_db(ops: lib.objects.OpsState, path: str) -> None:
    """ Validates a wallet database file and sets ops state """

    logger = ops.g_logger

    validate_file(logger, path)
    setattr(ops, "g_wallet_db_path", path)


def validate_wallet_id(ops: lib.objects.OpsState, wid: str) -> None:
    """ Validates a wallet id and sets ops state """

    logger = ops.g_logger

    if len(wid) != 40:
        logger.error(
            f"ERROR: Wallet id {wid} is not 40 characters in length: {len(wid)}"
        )
        sys.exit(1)
    try:
        int(wid, 16)
    except Exception:
        logger.exception(f"ERROR: Wallet id {wid} is not hexadecimal")
        sys.exit(1)

    setattr(ops, "g_wallet_id", wid)


def validate_wallet_id_health(ops: lib.objects.OpsState) -> None:
    """ Validates cardano-wallet server is in a ready state for the wallet id """

    logger = ops.g_logger

    timer = time.time()
    wallet_healthcheck_url = (
        f"{ops.g_wallet_server_api}/byron-wallets/{ops.g_wallet_id}"
    )

    request = lib.wallet.wallet_api(ops, wallet_healthcheck_url)
    try:
        wallet_sync_status = request.json()["state"]["status"]
        if wallet_sync_status != "ready":
            logger.error(
                f"ERROR: Wallet id {ops.g_wallet_id} sync status is not ready: {wallet_sync_status}"
            )
            logger.error("Wait until the wallet id sync status is ready and try again.")
            sys.exit(1)
    except ValueError as e:
        logger.error(
            f"ERROR: Unexpected wallet id json return value from: {wallet_healthcheck_url}"
        )
        logger.error(e)
        sys.exit(1)

    if ops.g_timers:
        logger.info(
            f"Time to validate wallet id health: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )


def validate_wallet_id_passphrase(ops: lib.objects.OpsState, path: str) -> None:
    """ Validates a wallet id passphrase file contains readable text and sets ops state """

    logger = ops.g_logger

    wallet_id_passphrase = validate_file(logger, path, read=True)
    if wallet_id_passphrase == "":
        logger.error(
            f"ERROR: A wallet id passphrase is not in the wallet id passphrase file: {path}"
        )
        sys.exit(1)

    setattr(ops, "g_wallet_id_passphrase", wallet_id_passphrase.strip())


def validate_wallet_ip(ops: lib.objects.OpsState, ip: str) -> None:
    """ Validates a valid IP for the wallet server endpoint and sets ops state """

    logger = ops.g_logger

    setattr(ops, "g_wallet_ip", validate_ip(logger, ip))


def validate_wallet_port(ops: lib.objects.OpsState, port: str) -> None:
    """ Validates a port for the wallet server endpoint and sets ops state """

    logger = ops.g_logger

    setattr(ops, "g_wallet_port", validate_port(logger, port))


def validate_wallet_server(ops: lib.objects.OpsState) -> None:
    """ Validates cardano-wallet server is responsive at the expected endpoint and sets ops state """

    logger = ops.g_logger

    timer = time.time()
    protocol = "https" if ops.g_wallet_tls else "http"
    wallet_server_url = f"{protocol}://{ops.g_wallet_ip}:{ops.g_wallet_port}"
    healthcheck_url = (
        f"{wallet_server_url}/{ops.WALLET_API_VER}/{ops.WALLET_API_HEALTHCHECK}"
    )

    request = lib.wallet.wallet_api(ops, healthcheck_url)
    try:
        wallet_sync_status = request.json()["sync_progress"]["status"]
        if wallet_sync_status != "ready":
            logger.error(
                f"ERROR: cardano-wallet server sync status is not ready: {wallet_sync_status}"
            )
            logger.error("Wait until the server sync status is ready and try again.")
            sys.exit(1)
        wallet_node_block_height = request.json()["node_tip"]["height"]["quantity"]

        tip = lib.cardano.cardano_cli_tip_get(ops)
        if "block" in tip:
            # For node > 1.25.1
            cardano_cli_block_height = tip["block"]
        elif "blockNo" in tip:
            # For node <= 1.25.1
            cardano_cli_block_height = tip["blockNo"]
        else:
            logger.error(
                "ERROR: unable to obtain the current cardano node block number."
            )
            sys.exit(1)

        if (
            abs(wallet_node_block_height - cardano_cli_block_height)
            > ops.WALLET_TO_CLI_HEIGHT_TOLERANCE
        ):
            logger.error(
                f"ERROR: cardano-wallet block height ({wallet_node_block_height}) "
                + f"and cardano-cli block height ({cardano_cli_block_height}) are out of sync "
                + f"with each other by more than {ops.WALLET_TO_CLI_HEIGHT_TOLERANCE} blocks."
            )
            logger.error(
                "Wait until both cardano-wallet and cardano-cli are synchronized to the blockchain "
                + f"and within {ops.WALLET_TO_CLI_HEIGHT_TOLERANCE} blocks of each other and try again."
            )
            sys.exit(1)
    except ValueError as e:
        logger.error(
            f"ERROR: Unexpected cardano-wallet json return value from: {healthcheck_url}"
        )
        logger.error(e)
        sys.exit(1)

    setattr(ops, "g_wallet_server_api", f"{wallet_server_url}/{ops.WALLET_API_VER}")

    if ops.g_timers:
        logger.info(
            f"Time to validate wallet server health: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )
