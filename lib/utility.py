from datetime import datetime
from typing import List, Union
import base58
import binascii
import docopt
import lib.objects
import lib.validate
import logging
import os
import pwd
import shutil
import subprocess
import sys
import time


def base58_decode(base58_string: str) -> str:
    """ Converts a base58 encoded string to a hexadecimal string """

    return binascii.hexlify(base58.b58decode(base58_string)).decode()


def base58_encode(hex_string: str) -> str:
    """ Converts a hexadecimal string to a base58 encoded string """

    return base58.b58encode(binascii.unhexlify(hex_string)).decode()


def cmd_exists(ops: lib.objects.OpsState, cmd: str) -> None:
    """ Validates a required executable dependency is found in the path and sets ops state """

    logger = ops.g_logger

    path = shutil.which(cmd)
    if path is None:
        logger.error(f"ERROR: A required dependency was not found in the path: {cmd}")
        sys.exit(1)

    if cmd == "bash":
        setattr(ops, "g_bash_path", path)


def date_time_str() -> str:
    """ Returns a date time string in UTC """

    return f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"


def log_debug_header(logger: logging.Logger, arguments: docopt.Dict) -> None:
    """ Logs debug header statements """

    try:
        user = subprocess.check_output(
            ["logname"], stderr=subprocess.PIPE, text=True
        ).strip()
    except Exception:
        user = pwd.getpwuid(os.getuid())[0]

    if not (arguments["print-bootstrap-address"] and arguments["--raw"]):
        logger.info("")

    logger.debug("User: {0}, Command: {1}".format(user, " ".join(sys.argv)))
    logger.debug("Arguments:")
    logger.debug(arguments)


def shell_cmd(
    ops: lib.objects.OpsState,
    cmd: str,
    args: List[str] = [],
    sensitive: bool = False,
    self_check: bool = False,
    check: bool = False,
    shell: bool = False,
) -> subprocess.CompletedProcess:
    """ Executes a shell command and returns stdout, stderr and return code """

    logger = ops.g_logger
    bash_path = ops.g_bash_path
    shell_cmd: Union[List[str], str] = ""

    try:
        if shell is True:
            shell_cmd = cmd + " " + " ".join(args)
            result = subprocess.run(
                shell_cmd,
                shell=True,
                check=check,
                universal_newlines=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                executable=bash_path,
            )
        else:
            shell_cmd = [cmd] + args
            result = subprocess.run(
                shell_cmd,
                shell=False,
                check=check,
                universal_newlines=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        if self_check is True and result.returncode != 0:
            if sensitive:
                logger.error("ERROR: shell command failed")
            else:
                logger.error(f"ERROR: shell command failed: {shell_cmd}")
            logger.error(f"command stdout: {result.stdout}")
            logger.error(f"command stderr: {result.stderr}")
            logger.error(f"command returncode: {result.returncode}")
            sys.exit(1)
    except Exception:
        if sensitive:
            logger.error("ERROR: shell command failed")
        else:
            logger.exception(f"ERROR: shell command failed: {shell_cmd}")
        sys.exit(1)

    return result


def time_delta_to_str(time_delta: float, ms: bool = True) -> str:
    """ Returns a user friendly hh:mm:ss[.SSS] string given a time().time delta """

    hours, rem = divmod(time_delta, 3600)
    minutes, seconds = divmod(rem, 60)

    if ms:
        time_string = f"{int(hours):02.0f}:{int(minutes):02.0f}:{seconds:06.3f}"
    else:
        time_string = f"{int(hours):02.0f}:{int(minutes):02.0f}:{int(seconds):02.0f}"

    return time_string


def sigint_handler(ops: lib.objects.OpsState, signal: int, frame) -> None:
    """ Adds signal interrupt handling  """

    logger = ops.g_logger

    logger.info("")
    logger.info("")
    logger.info("SIGINT or CTRL-C interruption detected.")
    logger.info("")
    logger.info("Status up to the time of interruption is:")
    summary_footer(ops)
    sys.exit(0)


def summary_footer(ops: lib.objects.OpsState) -> None:
    """ Logs a summary footer """

    logger = ops.g_logger

    logger.info("")
    logger.info(
        f'Summary of {"fragmentation" if ops.g_frag else "defragmentation"} '
        + f'{"*** LIVE-RUN ***" if ops.g_live else "dry-run"} '
        + f"on Cardano network {ops.g_network.upper()} ({ops.g_network_id}) finished at {date_time_str()}"
    )
    logger.info("")
    logger.info(
        f'Total transactions {"submitted" if ops.g_live else "prepared"}:'.ljust(36)
        + str(ops.g_sum_tx_count)
    )
    logger.info(
        f'Total fees {"submitted" if ops.g_live else "estimated"} (lovelace):'.ljust(36)
        + str(ops.g_sum_tx_fees)
    )
    logger.info(
        f'Total inputs {"submitted" if ops.g_live else "prepared"}:'.ljust(36)
        + str(ops.g_sum_tx_inputs)
    )
    logger.info(
        f'Total outputs {"submitted" if ops.g_live else "prepared"}:'.ljust(36)
        + str(ops.g_sum_tx_outputs).ljust(15)
        + " (not including change_addr)"
    )
    logger.info(
        "Elapsed runtime:".ljust(36)
        + f"{time_delta_to_str(time.time() - ops.g_start_time, ms=False)}".ljust(16)
        + "(hh:mm:ss)"
    )


def summary_header(ops: lib.objects.OpsState) -> None:
    """ Logs a summary header """

    logger = ops.g_logger

    # Warn if we are `--live` and prompt for confirmation
    if ops.g_live:
        logger.warning(
            f"WARNING: This script is about to submit transactions to the Cardano *** {ops.g_network.upper()} ({ops.g_network_id}) *** network."
        )
        if ops.g_network == "mainnet":
            if ops.g_network_id == "764824073":
                logger.warning(
                    "WARNING: This means that *REAL* funds will be transacted and *REAL* fees will be spent on the public mainnet."
                )
            else:
                logger.warning(
                    "WARNING: This means that funds will be transacted and fees will be spent on a mainnet like network, but not the real mainnet."
                    + f'WARNING: The real mainnet network magic id is "764824073", whereas this command has set the `--magic` option to "{ops.g_network_id}".'
                )
        logger.warning(
            "WARNING: To *estimate* transaction fees, run the same command again without the `--live` option for a dry run."
        )
        logger.warning(
            "WARNING: If a wallet sends or receives transactions between a dry run and a live run, fees incurred may also change."
        )
        logger.warning("WARNING:")
        logger.warning(
            f"WARNING: Do you wish to proceed with transacting real funds and real fees on Cardano {ops.g_network.upper()} ({ops.g_network_id}) network?"
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

    # Start the transaction header
    logger.info(
        f'Starting {"" if ops.g_frag else "de"}fragmentation ops '
        + f'({"*** LIVE-RUN ***" if ops.g_live else "dry-run"}):'
    )
    logger.info("")
