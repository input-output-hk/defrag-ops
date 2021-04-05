from typing import cast, Dict, List, Optional, Tuple, Union
import lib.objects
import lib.utility
import numpy
import re
import sys
import time


def filter_inputs(ops: lib.objects.OpsState) -> None:
    """ Filters utxos against a provided input filter and sets ops state """

    logger = ops.g_logger

    timer = time.time()
    if not ops.g_filter_tx_in:
        return

    target: Union[int, str] = ""
    filtered_utxos = ops.g_runtime_utxos.copy()
    for utxo, amount, address in ops.g_runtime_utxos:
        if ops.g_filter_tx_in_target == "utxo":
            target = utxo
        elif ops.g_filter_tx_in_target == "address":
            target = address
        elif ops.g_filter_tx_in_target == "lovelace":
            target = amount

        if ops.g_filter_tx_in_method in ["eq", "ne", "gt", "gte", "lt", "lte"]:
            target_int = cast(int, target)
            g_filter_tx_in_expr_int = cast(int, ops.g_filter_tx_in_expr)
            if (
                ops.g_filter_tx_in_method == "eq"
                and target_int == g_filter_tx_in_expr_int
            ):
                filtered_utxos.remove((utxo, amount, address))
            elif (
                ops.g_filter_tx_in_method == "ne"
                and target_int != g_filter_tx_in_expr_int
            ):
                filtered_utxos.remove((utxo, amount, address))
            elif (
                ops.g_filter_tx_in_method == "gt"
                and target_int > g_filter_tx_in_expr_int
            ):
                filtered_utxos.remove((utxo, amount, address))
            elif (
                ops.g_filter_tx_in_method == "gte"
                and target_int >= g_filter_tx_in_expr_int
            ):
                filtered_utxos.remove((utxo, amount, address))
            elif (
                ops.g_filter_tx_in_method == "lt"
                and target_int < g_filter_tx_in_expr_int
            ):
                filtered_utxos.remove((utxo, amount, address))
            elif (
                ops.g_filter_tx_in_method == "lte"
                and target_int <= g_filter_tx_in_expr_int
            ):
                filtered_utxos.remove((utxo, amount, address))

        if ops.g_filter_tx_in_method == "re":
            if re.search(cast(str, ops.g_filter_tx_in_expr), cast(str, target)):
                filtered_utxos.remove((utxo, amount, address))

    setattr(ops, "g_runtime_utxos", filtered_utxos)

    if ops.g_timers:
        logger.info(
            f"Time to filter inputs: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )


def generate_lovelace_list(
    ops: lib.objects.OpsState,
    count: int,
    lovelace_total: int,
    method: Optional[str] = None,
) -> List[int]:
    """ Creates a list of lovelaces of count elements summing to lovelace_total """

    logger = ops.g_logger

    timer = time.time()
    if method is None:
        method = "even" if ops.g_tx_output_evenly else "rnd"

    if method == "even":
        amounts = [int(lovelace_total / count) for x in range(0, count)]
    elif method == "rnd":
        # Type is numpy.ndarray[numpy.float64]
        amounts = numpy.random.random(count)
        amounts /= amounts.sum()  # type: ignore
        amounts *= lovelace_total
        # Type is converted back to List[int]
        amounts = [int(x) for x in amounts]

    # Adjust the outputs for the min UTxO required
    if ops.g_tx_output_min_utxo > 0:
        amounts = [
            ops.g_tx_output_min_utxo if x < ops.g_tx_output_min_utxo else x
            for x in amounts
        ]

    if ops.g_timers:
        logger.info(
            f"Time to generate a tx_out lovelace list: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )

    return amounts


def generate_tx_inputs(
    ops: lib.objects.OpsState,
    utxos: List[Tuple[str, int, str]],
    min_total: int,
    max_count: Optional[int] = None,
    strategy: str = "min",
) -> Tuple[Dict[str, Union[int, str]], List[str], List[Tuple[str, int, str]], str]:
    """ Creates a tx input set from a list of utxos """

    logger = ops.g_logger
    if max_count is None:
        max_count = ops.g_tx_max_inputs

    algorithm = "simple"
    required_min = min_total + ops.TX_FEE_LOVELACE_TOLERANCE

    # "min" strategy is used to select the minimum number of UTxOs to fund an operation
    # by creating a utxo input list starting with the largest available.  This is the
    # default mode used by the fragmentation operation.
    #
    # "max" strategy is used to select the maximum number of UTxOs and is the default
    # mode used by the defragmentation operation.
    input_list = []
    addresses = []
    selected_utxos = []
    if strategy == "min":
        count = 0
        total = 0
        # The utxo list is already sorted for the appropriate strategy
        # This allows sorts on big lists to happen in sqlite3 or elsewhere in the code
        # For fragmentation operations, runtime utxos are populated from cardano-cli utxo
        # query and sorted by descending lovelace value in fn cardano_cli_query_utxo
        for utxo, amount, address in utxos:
            if total <= required_min:
                input_list.append(utxo)
                addresses.append(address)
                selected_utxos.append((utxo, amount, address))
                count += 1
                total += amount
            else:
                break
            if count > max_count:
                logger.error(
                    f"ERROR: More than max_count {max_count} input UTxOs would be required to meet the minimum lovelace total required:"
                )
                logger.error(
                    f"{min_total} base Tx output + {ops.TX_FEE_LOVELACE_TOLERANCE} fee padding = {min_total + ops.TX_FEE_LOVELACE_TOLERANCE} lovelace"
                )
                sys.exit(1)
        if total < required_min:
            logger.error(
                "ERROR: Not enough input UTxOs are available to meet the minimum lovelace total required:"
            )
            logger.error(
                f"Required: {min_total} base Tx output + {ops.TX_FEE_LOVELACE_TOLERANCE} fee padding = {min_total + ops.TX_FEE_LOVELACE_TOLERANCE} lovelace"
            )
            logger.error(f"Available: {total} lovelace at {count} inputs")
            sys.exit(1)
    elif strategy == "max":
        # For defragmentation using the max strategy, utxos are populated from the
        # cardano-wallet sql db and pre-sorted by ascending lovelace value in
        # fn wallet_db_query_utxo
        utxo_element_list = []
        max_allowed = max_count if len(utxos) >= max_count else len(utxos)
        utxo_amounts = [amount for utxo, amount, address in utxos]

        # Pre-process the utxo selection to ensure min utxo value for the network plus fee tolerance is met
        if sum(utxo_amounts[0:max_allowed]) > required_min:
            utxo_element_list = list(range(0, max_allowed))
        else:
            # If the smallest max_allowed utxo elements summed do not meet the required amount, start algorithm A selection
            # Algorithm A: Find a single utxo that added to (max_allowed - 1) smallest utxos summed will meet the required amount
            utxo_window_sum = sum(utxo_amounts[0 : max_allowed - 1])
            for utxo_position in range(max_allowed, len(utxo_amounts)):
                if utxo_window_sum + utxo_amounts[utxo_position] > required_min:
                    utxo_element_list = list(range(0, max_allowed - 1)) + [
                        utxo_position
                    ]
                    algorithm = "sliding utxo"
                    break
            # If algorithm A does not work, fallback to algorithm B
            # Algorithm B: Slide a utxo window range toward increasing utxo value until the sum of the window range meets the required amount
            # This algorithm is about 10 times slower than algorithm A
            if utxo_element_list == []:
                for offset in range(0, len(utxo_amounts) - (max_allowed - 1)):
                    if sum(utxo_amounts[offset : max_allowed + offset]) > required_min:
                        utxo_element_list = list(range(offset, max_allowed + offset))
                        algorithm = "sliding window"
                        break

        if len(utxo_element_list) == 0:
            logger.error(
                "ERROR: Not enough input UTxOs are available to meet the minimum lovelace total required:"
            )
            logger.error(
                f"Required: {min_total} base Tx output + {ops.TX_FEE_LOVELACE_TOLERANCE} fee padding = {min_total + ops.TX_FEE_LOVELACE_TOLERANCE} lovelace"
            )
            logger.error(
                f"Maximum available: {sum(utxo_amounts[-max_allowed:])} lovelace at {max_count} inputs"
            )
            sys.exit(1)
        elif len(utxo_element_list) != max_allowed:
            logger.error(
                f"ERROR: UTxO input element list length is not an expected value of {max_allowed}: {len(utxo_element_list)}"
            )
            sys.exit(1)

        # Apply pre-processed utxos element list to build the input list requirements
        count = 0
        total = 0
        for utxo, amount, address in [utxos[element] for element in utxo_element_list]:
            if count >= max_count:
                break
            else:
                input_list.append(utxo)
                addresses.append(address)
                selected_utxos.append((utxo, amount, address))
                count += 1
                total += amount
        if total < required_min:
            logger.error(
                "ERROR: Not enough input UTxOs are available to meet the minimum lovelace total required:"
            )
            logger.error(
                f"Required: {min_total} base Tx output + {ops.TX_FEE_LOVELACE_TOLERANCE} fee padding = {min_total + ops.TX_FEE_LOVELACE_TOLERANCE} lovelace"
            )
            logger.error(f"Available: {total} lovelace at {count} inputs")
            sys.exit(1)

    inputs = "--tx-in " + " --tx-in ".join(input_list)

    timer = time.time()
    # Ensuring the list of address used for witnessing is unique will minimize cost
    unique_addresses = list(set(addresses))
    base58_addresses = [lib.utility.base58_encode(x) for x in unique_addresses]

    if ops.g_timers:
        logger.info(
            f"Time to base58 encode the input address list: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )

    return (
        {"string": inputs, "count": len(input_list), "sum": total},
        base58_addresses,
        selected_utxos,
        algorithm,
    )


def generate_tx_outputs(
    addresses: List[str], amounts: List[int]
) -> Dict[str, Union[int, str]]:
    """ Creates a tx output dict(string, count, sum) from a list of addresses and amounts of equal length """

    output_list = [f"{address}+{amount}" for address, amount in zip(addresses, amounts)]
    outputs = "--tx-out " + " --tx-out ".join(output_list)
    total = sum(amounts)

    return {"string": outputs, "count": len(output_list), "sum": total}


def purge_missing_utxos(ops: lib.objects.OpsState) -> None:
    """ Purges runtime input UTxOs which have gone missing dynamically from ops state """

    logger = ops.g_logger

    # Use updated ops state to purge any remaining runtime utxos which have disappeared from the network
    # This may occur if the wallet is being used while a frag or defrag operation is occurring
    timer = time.time()
    if ops.g_frag:
        missing_utxos = set(ops.g_runtime_utxos) - set(ops.g_cardano_cli_utxo)
    else:
        missing_utxos = set(ops.g_runtime_utxos) - set(ops.g_wallet_utxo)
    for missing_utxo in missing_utxos:
        getattr(ops, "g_runtime_utxos").remove(missing_utxo)

    if ops.g_timers:
        logger.info(
            f"Time to purge missing input utxos: {lib.utility.time_delta_to_str(time.time() - timer)}"
        )
