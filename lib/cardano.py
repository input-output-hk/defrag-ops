from typing import Any, Callable, cast, Dict, List, Tuple, Union
import json
import lib.objects
import lib.utility
import lib.utxo
import lib.wallet
import semver
import subprocess
import sys
import time


def cardano_address_child_prv_and_skey_gen(
    ops: lib.objects.OpsState, prv: str, account_index: str, address_index: str
) -> str:
    """ Generate a child private cardano address key and cardano shelley skey """

    # logger = ops.g_logger

    # timer = time.time()
    result = lib.utility.shell_cmd(
        ops,
        f"bash -c 'cardano-address key child {account_index}/{address_index} <<< "
        + f'"{prv}" | cardano-cli key convert-cardano-address-key --byron-payment-key '
        + "--signing-key-file <(cat -) --out-file >(cat -)'",
        sensitive=True,
        self_check=True,
        shell=True,
    )
    skey = json.dumps(json.loads(result.stdout), separators=(",", ":"))

    # if ops.g_timers:
    #     logger.info(
    #         f"Time to generate a child private key and shelley skey: {lib.utility.time_delta_to_str(time.time() - timer)}"
    #     )

    return skey


def cardano_address_gen_bootstrap(
    ops: lib.objects.OpsState,
    pub: str,
    network_id: str,
    account_index: str,
    address_index: str,
    child_pub: str,
) -> str:
    """ Generate a bootstrap cardano address """

    # The staging network needs to use the mainnet flag, otherwise the address scheme is not correct
    if ops.g_network == "mainnet" or ops.g_network == "staging":
        network_tag = "mainnet"
    else:
        network_tag = network_id

    result = lib.utility.shell_cmd(
        ops,
        cmd=(
            f'cardano-address address bootstrap --root "{pub}"'
            + f' --network-tag {network_tag} {account_index}/{address_index} <<< "{child_pub}"'
        ),
        self_check=True,
        shell=True,
    )
    bootstrap_addr = result.stdout

    return bootstrap_addr


def cardano_address_gen_byron_prv_from_mnemonics(ops: lib.objects.OpsState) -> str:
    """ Generate a cardano byron private key from mnemonics """

    result = lib.utility.shell_cmd(
        ops,
        f'cardano-address key from-recovery-phrase Byron <<< "{ops.g_mnemonics}"',
        sensitive=True,
        self_check=True,
        shell=True,
    )
    root_prv = result.stdout

    return root_prv


def cardano_address_gen_child_prv(
    ops: lib.objects.OpsState, prv: str, account_index: str, address_index: str
) -> str:
    """ Generate a child private cardano address key """

    # logger = ops.g_logger

    # timer = time.time()
    result = lib.utility.shell_cmd(
        ops,
        f'cardano-address key child {account_index}/{address_index} <<< "{prv}"',
        sensitive=True,
        self_check=True,
        shell=True,
    )
    child_prv = result.stdout

    # if ops.g_timers:
    #     logger.info(
    #         f"Time to generate a child private key: {lib.utility.time_delta_to_str(time.time() - timer)}"
    #     )

    return child_prv


def cardano_address_gen_pub(ops: lib.objects.OpsState, prv: str) -> str:
    """ Generate a public cardano address key from a private key """

    result = lib.utility.shell_cmd(
        ops,
        f'cardano-address key public --with-chain-code <<< "{prv}"',
        sensitive=True,
        self_check=True,
        shell=True,
    )
    pub = result.stdout

    return pub


def cardano_address_inspect(
    ops: lib.objects.OpsState, root_pub: str, address: str
) -> Tuple[str, str]:
    """ Inspects a cardano address and returns the derivation path and sets ops state """

    logger = ops.g_logger

    g_lookup_hits_sql_drvs = ops.g_lookup_hits_sql_drvs

    # timer = time.time()

    if address in ops.g_wallet_db_address_drvs:
        account_index = f"{ops.g_wallet_db_address_drvs[address]['account_ix']}H"
        address_index = f"{ops.g_wallet_db_address_drvs[address]['address_ix']}H"
        g_lookup_hits_sql_drvs += 1
    else:
        cmd = f'cardano-address address inspect --root "{root_pub}" <<< "{address}"'
        result = lib.utility.shell_cmd(ops, cmd, self_check=True, shell=True)

        try:
            inspection = json.loads(result.stdout)
        except Exception:
            logger.error(
                "ERROR: invalid json returned when inspecting a cardano address."
            )
            logger.error(cmd)
            logger.exception("")
            sys.exit(1)

        account_index = inspection["derivation_path"]["account_index"]
        address_index = inspection["derivation_path"]["address_index"]

        # Add the new key to the lookup table to optimize future lookups:
        getattr(ops, "g_wallet_db_address_drvs")[address] = {}
        getattr(ops, "g_wallet_db_address_drvs")[address]["account_ix"] = int(
            account_index.strip("H")
        )
        getattr(ops, "g_wallet_db_address_drvs")[address]["address_ix"] = int(
            address_index.strip("H")
        )

    setattr(ops, "g_lookup_hits_sql_drvs", g_lookup_hits_sql_drvs)

    # ops.g_timers and logger.info(
    #     f"Time to inspect or lookup an address for derivation path: {lib.utility.time_delta_to_str(time.time() - timer)}"
    # )

    return account_index, address_index


def cardano_address_key_prep(ops: lib.objects.OpsState) -> None:
    """ Prepare the public and private keys required with cardano-address and set ops state """

    root_prv = cardano_address_gen_byron_prv_from_mnemonics(ops)
    root_pub = cardano_address_gen_pub(ops, root_prv)
    child_prv = cardano_address_gen_child_prv(
        ops, root_prv, ops.DEFAULT_ACCOUNT_INDEX, ops.DEFAULT_ADDRESS_INDEX
    )
    child_pub = cardano_address_gen_pub(ops, child_prv)
    bootstrap_addr = cardano_address_gen_bootstrap(
        ops,
        root_pub,
        ops.g_network_id,
        ops.DEFAULT_ACCOUNT_INDEX,
        ops.DEFAULT_ADDRESS_INDEX,
        child_pub,
    )

    setattr(ops, "g_shelley_root_prv", root_prv)
    setattr(ops, "g_shelley_root_pub", root_pub)
    setattr(ops, "g_shelley_prv", child_prv)
    setattr(ops, "g_shelley_address", bootstrap_addr)


def cardano_cli_gen_byron_skey(ops: lib.objects.OpsState, prv: str) -> str:
    """ Generate a Shelley skey from a Byron private key """

    logger = ops.g_logger

    timer = time.time()
    # fmt: off
    cmd = (
        "bash -c 'cardano-cli key convert-cardano-address-key --byron-payment-key "
        + (f"--signing-key-file <(echo -n {prv}) --out-file >(cat -)'")
    )
    # fmt: on
    result = lib.utility.shell_cmd(
        ops, cmd, sensitive=True, self_check=True, shell=True
    )
    skey = json.dumps(json.loads(result.stdout), separators=(",", ":"))

    if ops.g_timers:
        logger.info(
            f"Time to generate a Byron skey: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )

    return skey


def cardano_cli_gen_vkey(ops: lib.objects.OpsState, skey: str) -> str:
    """ Generate a Shelley vkey from an skey """

    # fmt: off
    cmd = (
        "bash -c 'cardano-cli key verification-key --signing-key-file <(echo -n "
        + '"'
        + skey.replace('"', r"\"")
        + '"'
        + ") --verification-key-file >(cat -)'"
    )
    # fmt: on
    result = lib.utility.shell_cmd(
        ops, cmd, sensitive=True, self_check=True, shell=True
    )
    vkey = json.dumps(json.loads(result.stdout), separators=(",", ":"))

    return vkey


def cardano_cli_key_prep(ops: lib.objects.OpsState) -> None:
    """ Prepare the public and private keys required with cardano-cli and set ops state """

    shelley_skey = cardano_cli_gen_byron_skey(ops, ops.g_shelley_prv)
    shelley_vkey = cardano_cli_gen_vkey(ops, shelley_skey)

    setattr(ops, "g_shelley_skey", shelley_skey)
    setattr(ops, "g_shelley_vkey", shelley_vkey)


def cardano_cli_protocol_params(ops: lib.objects.OpsState) -> None:
    """ Queries cardano cli for protocol parameters and sets ops state """

    logger = ops.g_logger

    timer = time.time()
    # fmt: off
    if ops.g_network == "testnet" or ops.g_network == "staging":
        network = ["--testnet-magic", f"{ops.g_network_id}"]
    else:
        network = ["--mainnet"]

    cmd = "cardano-cli"
    args = [
        "query",
        "protocol-parameters",
    ] + network

    if semver.compare(ops.g_cardano_cli_tag, "1.26.1") < 0:
        args.append("--mary-era")

    # fmt: on
    result = lib.utility.shell_cmd(ops, cmd, args, self_check=True, shell=False)
    network_protocol_params = json.dumps(
        json.loads(result.stdout), separators=(",", ":")
    )

    try:
        network_protocol_params_parsed = json.loads(network_protocol_params)
    except Exception:
        logger.error(
            "ERROR: invalid json returned when parsing cardano-cli protocol parameters."
        )
        logger.error(cmd)
        logger.exception("")
        sys.exit(1)

    setattr(ops, "g_network_protocol_params", network_protocol_params)
    setattr(
        ops,
        "g_network_protocol_params_min_utxo",
        network_protocol_params_parsed["minUTxOValue"],
    )

    if not ops.g_network_min_utxo_override:
        setattr(ops, "g_tx_output_min_utxo", ops.g_network_protocol_params_min_utxo)

    if ops.g_timers:
        logger.info(
            f"Time to query cardano-cli protocol parameters: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )


def cardano_cli_query_utxo(
    ops: lib.objects.OpsState, address: str, ascending: bool = True
) -> None:
    """ Queries a cardano cli address for utxos and yields a sorted tuple of utxos and sets ops state"""

    logger = ops.g_logger

    timer = time.time()
    # Query cardano-cli for the address UTxOs
    # fmt: off
    cmd = (
        ("bash -c 'cardano-cli query utxo ")
        + ("--mary-era " if semver.compare(ops.g_cardano_cli_tag, "1.26.1") < 0 else "")
        + (f"--testnet-magic {ops.g_network_id} " if ops.g_network == "testnet" or ops.g_network == "staging" else "--mainnet ")
        + (f"--address {address} --out-file >(cat -)'")
    )
    # fmt: on

    result = lib.utility.shell_cmd(ops, cmd, self_check=True, shell=True)

    try:
        utxos = json.loads(result.stdout)
    except Exception:
        logger.error("ERROR: invalid json returned when querying shelley address utxo.")
        logger.error(cmd)
        logger.exception("")
        sys.exit(1)

    unsorted_utxos = cardano_cli_utxo_dict_to_list(ops, utxos)

    # Sort the utxos list primarily by amount (descending), then utxo (tx_hash#tx_ix, descending)
    utxos = cardano_cli_utxo_list_sort(
        unsorted_utxos, sort_lambda=lambda x: (x[1], x[0]), ascending=False
    )

    setattr(ops, "g_cardano_cli_utxo", utxos)

    if ops.g_timers:
        logger.info(
            f"Time to query cardano-cli utxos: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )


def cardano_cli_tip_get(ops: lib.objects.OpsState) -> Dict[str, Union[int, str]]:
    """ Queries cardano cli for the tip information """

    logger = ops.g_logger

    timer = time.time()
    # fmt: off
    cmd = (
        "cardano-cli query tip "
        + (f"--testnet-magic {ops.g_network_id} " if ops.g_network == "testnet" or ops.g_network == "staging" else "--mainnet")
    )
    # fmt: on
    result = lib.utility.shell_cmd(ops, cmd, self_check=True, shell=True)

    try:
        tip = json.loads(result.stdout)
    except Exception:
        logger.error("ERROR: invalid json returned when querying cardano-cli tip.")
        logger.error(cmd)
        logger.exception("")
        sys.exit(1)

    if ops.g_timers:
        logger.info(
            f"Time to query cardano-cli tip information: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )
    return tip


def cardano_cli_tx_compose(
    ops: lib.objects.OpsState,
) -> Dict[str, Union[bool, int, str]]:
    """ Generates fragmentation transactions and sets ops state """

    logger = ops.g_logger

    # Fragmentation operation setup
    if ops.g_frag:
        if len(ops.g_runtime_utxos) < 1:
            logger.info("")
            logger.info("Fragmentation complete: no UTxO remain")
            logger.info("")
            return {
                "state": False,
                "fee": 0,
                "inputs": 0,
                "outputs": 0,
                "algorithm": "none",
            }

        timer = time.time()
        inputs, input_addresses, selected_utxo, algorithm = lib.utxo.generate_tx_inputs(
            ops,
            ops.g_runtime_utxos,
            min_total=ops.g_tx_output_lovelace,
            max_count=ops.g_tx_max_inputs,
            strategy="min",
        )
        output_addresses = lib.wallet.wallet_output_addresses(
            ops, ops.g_tx_output_count
        )
        output_amounts = lib.utxo.generate_lovelace_list(
            ops, ops.g_tx_output_count, ops.g_tx_output_lovelace
        )
        outputs = lib.utxo.generate_tx_outputs(output_addresses, output_amounts)

        if ops.g_timers:
            logger.info(
                f"Time to generate tx inputs and outputs: {lib.utility.time_delta_to_str(time.time() - timer)}"
            )

    # Defragmentation operation setup
    if not ops.g_frag:
        if len(ops.g_runtime_utxos) < 2:
            logger.info("")
            logger.info(
                "Defragmentation complete: less than 2 UTxO remain (excluding new defrag Tx change UTxOs)"
            )
            logger.info("")
            return {
                "state": False,
                "fee": 0,
                "inputs": 0,
                "outputs": 0,
                "algorithm": "none",
            }

        timer = time.time()
        inputs, input_addresses, selected_utxo, algorithm = lib.utxo.generate_tx_inputs(
            ops,
            ops.g_runtime_utxos,
            min_total=ops.g_tx_output_min_utxo,
            max_count=ops.g_tx_max_inputs,
            strategy="max",
        )
        outputs = {"string": "", "count": 0, "sum": 0}

        if ops.g_timers:
            logger.info(
                f"Time to generate tx inputs and outputs: {lib.utility.time_delta_to_str(time.time() - timer)}"
            )

    # Operation execution
    tx_fee = cardano_cli_tx_process(ops, inputs, outputs, input_addresses)
    status = {
        "state": True,
        "fee": tx_fee,
        "inputs": inputs["count"],
        "outputs": outputs["count"],
        "algorithm": algorithm,
    }

    # Remove runtime utxos that were consumed in this tx
    timer = time.time()
    for utxo in selected_utxo:
        try:
            getattr(ops, "g_runtime_utxos").remove(utxo)
        except ValueError:
            logger.exception(
                "ERROR: An expected runtime utxo was found not in the list during runtime cleanup."
            )
            sys.exit(1)

    if ops.g_timers:
        logger.info(
            f"Time to purge consumed utxos: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )

    return status


def cardano_cli_tx_draft(
    ops: lib.objects.OpsState,
    inputs: Dict[str, Union[int, str]],
    outputs: Dict[str, Union[int, str]],
    change_address: str,
    tx_fee: int = 0,
    tx_change: int = 0,
    ttl: int = 0,
) -> str:
    """ Creates a draft transaction for cardano-cli """

    # fmt: off
    cmd = (
        "bash -c 'cardano-cli transaction build-raw "
        + cast(str, inputs["string"])
        + " "
        + cast(str, outputs["string"])
        + (f" --tx-out {change_address}+{tx_change} ")
        + (f"--ttl {ttl} --fee {tx_fee} --out-file >(cat -)'")
    )
    # fmt: on
    result = lib.utility.shell_cmd(ops, cmd, shell=True)
    tx_draft = json.dumps(json.loads(result.stdout), separators=(",", ":"))

    return tx_draft


def cardano_cli_tx_fee_calc(
    ops: lib.objects.OpsState,
    tx_body: str,
    inputs: Dict[str, Union[int, str]],
    outputs: Dict[str, Union[int, str]],
) -> int:
    """ Queries cardano cli for a minimum fee calculation """

    logger = ops.g_logger

    # fmt: off
    cmd = (
        "bash -c 'cardano-cli transaction calculate-min-fee --tx-body-file <(echo -n "
        + '"'
        + tx_body.replace('"', r"\"")
        + '") '
        + (f"--testnet-magic {ops.g_network_id} " if ops.g_network == "testnet" or ops.g_network == "staging" else "--mainnet ")
        + '--protocol-params-file <(echo -n "'
        + ops.g_network_protocol_params.replace('"', r"\"")
        + '") '
        + f"--tx-in-count {cast(int, inputs['count'])} --tx-out-count {cast(int, outputs['count']) + 1} "
        + f"--witness-count {cast(int, inputs['count'])} --byron-witness-count 0'"
    )
    # fmt: on
    result = lib.utility.shell_cmd(ops, cmd, self_check=True, shell=True)
    fee = result.stdout
    if "Lovelace" not in fee:
        logger.error(
            f'ERROR: The fee calculation did not return an expected response containing the string "Lovelace": {fee}'
        )
        sys.exit(1)
    tx_fee = fee.split()[0]
    try:
        tx_fee_int = int(tx_fee, 10)
        if tx_fee_int < 1:
            logger.error(
                f"ERROR: The fee calculation is calculating a fee of less than 1 lovelace: {tx_fee_int}"
            )
            sys.exit(1)
    except Exception:
        logger.exception(
            f"ERROR: The fee calculation is returning a value that is not an integer: {tx_fee_int}"
        )
        sys.exit(1)

    return tx_fee_int


def cardano_cli_tx_id(ops: lib.objects.OpsState, tx_signed: str) -> str:
    """ Obtains a cardano transaction id """

    # fmt: off
    cmd = (
        "bash -c 'cardano-cli transaction txid --tx-file <(echo -n "
        + '"' + tx_signed.replace('"', r"\"")
        + "\")'"
    )
    # fmt: on
    result = lib.utility.shell_cmd(ops, cmd, self_check=True, shell=True)
    tx_id = result.stdout.strip()

    return tx_id


def cardano_cli_tx_process(
    ops: lib.objects.OpsState,
    inputs: Dict[str, Union[int, str]],
    outputs: Dict[str, Union[int, str]],
    input_addresses: List[str],
) -> int:
    """ Obtain a stable fee estimation and submit the transaction if `--live` """

    logger = ops.g_logger

    tip = cardano_cli_tip_get(ops)
    if "slot" in tip:
        # For node > 1.25.1
        ttl = cast(int, tip["slot"]) + ops.TX_TTL_TOLERANCE
    elif "slotNo" in tip:
        # For node <= 1.25.1
        ttl = cast(int, tip["slotNo"]) + ops.TX_TTL_TOLERANCE
    else:
        logger.error("ERROR: unable to obtain the current cardano node slot number.")
        sys.exit(1)

    # Time to obtain cardano-cli tip is reported separately, so not included here
    timer = time.time()
    tx_fee = -1
    tx_fee_last = 0
    count = 0
    while tx_fee != tx_fee_last and count <= ops.TX_FEE_CALC_ATTEMPTS:
        tx_fee = tx_fee_last
        tx_change = cast(int, inputs["sum"]) - cast(int, outputs["sum"]) - tx_fee
        tx_draft = cardano_cli_tx_draft(
            ops, inputs, outputs, ops.g_shelley_address, tx_fee, tx_change, ttl
        )

        tx_fee_last = cardano_cli_tx_fee_calc(ops, tx_draft, inputs, outputs)
        count += 1

    if tx_fee != tx_fee_last and count > ops.TX_FEE_CALC_ATTEMPTS:
        logger.error(
            f"ERROR: unable to obtain a stable fee calculation after {count} attempts."
        )
        sys.exit(1)

    logger.info(
        (
            "Tx ready: (inputs, outputs, inSum, outSum, change, fees) = ("
            + (f"{inputs['count']}, ")
            + (f"{outputs['count']} + change_addr, ")
            + (f"{inputs['sum']}, ")
            + (f"{outputs['sum']}, ")
            + (f"{tx_change}, ")
            + (f"{tx_fee})...")
        )
    )

    if ops.g_timers:
        logger.info(
            f"Time to generate a stable fee estimation: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )

    # Sign the raw transaction and obtain the transaction id
    timer = time.time()
    tx_signed = cardano_cli_tx_sign(ops, tx_draft, input_addresses)
    tx_id = cardano_cli_tx_id(ops, tx_signed)

    if ops.g_timers:
        logger.info(
            f"Time to sign the tx and obtain a tx_id: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )

    logger.debug("")
    logger.debug("DEBUG Tx INPUTS:")
    logger.debug(json.dumps(inputs, indent=2))
    logger.debug("")
    logger.debug("DEBUG Tx OUTPUTS (excluding change_addr):")
    logger.debug(json.dumps(outputs, indent=2))
    logger.debug("")

    # Submit the signed transaction
    timer = time.time()
    if ops.g_live:
        logger.info(
            f"    ...submitted to network {ops.g_network} ({ops.g_network_id}) as tx_id: {tx_id}"
        )
        cardano_cli_tx_submit(ops, tx_signed)
    else:
        logger.info(
            f"    ...dry run -- not submitting Tx to the network (txid: {tx_id})"
        )

    if ops.g_timers:
        logger.info(
            f"Time to submit the tx: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )

    return tx_fee


def cardano_cli_tx_sign(
    ops: lib.objects.OpsState, tx_body: str, addresses: List[str]
) -> str:
    """ Signs a cardano cli raw transaction and sets ops state """

    g_lookup_hits_cli_skey = ops.g_lookup_hits_cli_skey

    # Generate the witness skeys
    if addresses == [ops.g_shelley_address]:
        witness_keys = [ops.g_shelley_skey]
    else:
        witness_keys = []
        for address in addresses:
            # See if the skey already exists for this address in the lookup table
            if address in ops.g_cardano_cli_skeys:
                witness_keys.append(ops.g_cardano_cli_skeys[address])
                g_lookup_hits_cli_skey += 1
            else:
                account_index, address_index = cardano_address_inspect(
                    ops, ops.g_shelley_root_pub, address
                )

                # Use two commands piped through the same shell subprocess to minimize overhead
                address_skey = cardano_address_child_prv_and_skey_gen(
                    ops, ops.g_shelley_root_prv, account_index, address_index
                )

                # For debug, individual commands can be used instead at the cost of performance
                #
                # address_prv = cardano_address_gen_child_prv(
                #     ops,
                #     ops.g_shelley_root_prv, account_index, address_index
                # )
                # address_skey = cardano_cli_gen_byron_skey(ops, address_prv)
                witness_keys.append(address_skey)
                getattr(ops, "g_cardano_cli_skeys")[address] = address_skey
        setattr(ops, "g_lookup_hits_cli_skey", g_lookup_hits_cli_skey)

    # Assembly the witness cli arguments
    witness_text = [
        (
            '--signing-key-file <(echo -n "'
            + skey.replace('"', r"\"")
            + f'") --address {address} '
        )
        for skey, address in zip(witness_keys, addresses)
    ]
    witness_string = "".join(witness_text)
    # fmt: off
    # The staging network also uses the `--mainnet` flag for Tx signing
    cmd = (
        "bash -c 'cardano-cli transaction sign --tx-body-file <(echo -n "
        + '"' + tx_body.replace('"', r"\"") + '") '
        + witness_string
        + (f"--testnet-magic {ops.g_network_id}" if ops.g_network == "testnet" else "--mainnet")
        + " --out-file >(cat -)'"
    )
    # fmt: on
    result = lib.utility.shell_cmd(ops, cmd, self_check=True, shell=True)
    tx_signed = json.dumps(json.loads(result.stdout), separators=(",", ":"))

    return tx_signed


def cardano_cli_tx_submit(
    ops: lib.objects.OpsState, tx_signed: str
) -> subprocess.CompletedProcess:
    """ Submits a cardano cli raw transaction """

    # fmt: off
    cmd = (
        "bash -c 'cardano-cli transaction submit --tx-file <(echo -n "
        + '"' + tx_signed.replace('"', r"\"")
        + '") '
        + (f"--testnet-magic {ops.g_network_id}'" if ops.g_network == "testnet" or ops.g_network == "staging" else "--mainnet'")
    )
    # fmt: on
    result = lib.utility.shell_cmd(ops, cmd, self_check=True, shell=True)

    return result


def cardano_cli_utxo_dict_to_list(
    ops: lib.objects.OpsState, dict_utxos: Dict[str, Dict[str, Any]]
) -> List[Tuple[str, int, str]]:
    """ Converts a cardano cli utxo dict to a list of tuples and removes asset containing utxos """

    logger = ops.g_logger

    if len(dict_utxos) == 0 and ops.g_frag:
        logger.error(
            "ERROR: No UTxO found in the bootstrap address to fund frag operations."
        )
        sys.exit(1)
    elif len(dict_utxos) == 0 and not ops.g_frag:
        return []

    if "value" in dict_utxos[list(dict_utxos)[0]]:
        # For node > 1.25.1
        # Return a list of tuples of List[Tuple(utxo, lovelace, address)]
        return [
            (utxo, dict_utxos[utxo]["value"]["lovelace"], dict_utxos[utxo]["address"])
            for utxo in dict_utxos
            if len(dict_utxos[utxo]["value"]) == 1
            and "lovelace" in dict_utxos[utxo]["value"]
        ]
    elif "amount" in dict_utxos[list(dict_utxos)[0]]:
        # For node <= 1.25.1
        # Return a list of tuples of List[Tuple(utxo, amount[0], address)]
        return [
            (utxo, dict_utxos[utxo]["amount"][0], dict_utxos[utxo]["address"])
            for utxo in dict_utxos
            if len(dict_utxos[utxo]["amount"][1]) == 0
        ]
    else:
        logger.error("ERROR: unable to parse the cardano cli utxo dictionary.")
        sys.exit(1)


def cardano_cli_utxo_list_sort(
    utxos: List[Tuple[str, int, str]],
    sort_lambda: Callable[[Tuple[str, int, str]], Tuple[int, str]],
    ascending: bool = True,
) -> List[Tuple[str, int, str]]:
    """ Sorts a cardano cli utxo list of tuples """

    reverse = True if ascending is False else False
    return sorted(utxos, key=sort_lambda, reverse=reverse)
