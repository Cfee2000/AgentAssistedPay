#!/usr/bin/env python 
"""
Script that creates the Agent Pay TaskRouter workspace and the corresponding Verify service
for authenticating workers, and writes them to the config file.
"""

import os
import sys
import configparser
import argparse
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioException


__version__ = "0.1"

logger = logging.getLogger(__name__)


# Set up logging for the module.
def configure_logging(level=logging.INFO):
    logger.setLevel(level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s.%(msecs)03d: %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# Return parsed command line arguments.
def get_args():
    parser = argparse.ArgumentParser(
        description="Create the TaskRouter workspace and Verify service for Agent Pay")
    parser.add_argument(
        '-a', '--account', default=os.environ.get('TWILIO_ACCOUNT_SID'),
        help="account SID (default: TWILIO_ACCOUNT_SID env var)")
    parser.add_argument(
        '-k', '--key', default=os.environ.get('TWILIO_API_KEY'),
        help="API key (default: TWILIO_API_KEY env var)")
    parser.add_argument(
        '-p', '--pw', default=os.environ.get('TWILIO_API_SECRET'),
        help="API secret (default: TWILIO_API_SECRET env var)")
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument(
        '--log', choices=['debug', 'info', 'warning'], 
        help="set logging level")
    return parser.parse_args()


def main(args):
    config = configparser.ConfigParser()
    config.read('pay.ini')
    level = args.log.upper() if args.log else config['items']['log_level'].upper()
    configure_logging(level=getattr(logging, level))
    client = Client(args.key, args.pw, args.account)
    name = config['items']['service_name']
    workspace = None
    verifyService = None

    try:
        workspaces = client.taskrouter.workspaces.list(friendly_name=name)
        if workspaces:
            logger.debug(f"Workspace '{name}' already exists")
            workspace = workspaces[0]
        else:
            logger.debug(f"Creating workspace '{name}'")
            workspace = client.taskrouter.workspaces.create(friendly_name=name)

        verifyServices = client.verify.services.list()
        for verifyService in verifyServices:
            if verifyService.friendly_name == name:
                logger.debug(f"Verify service '{name}' already exists")
                break
        else:
            logger.debug(f"Creating Verify service '{name}'")
            verifyService = client.verify.services.create(friendly_name=name)

    except TwilioException as ex:
        sys.exit(f"Unable to access API: check credentials. Full message:\n{ex}")

    logger.info(f'Workspace SID: {workspace.sid}')
    logger.info(f'Verify service SID: {verifyService.sid}')
    logger.debug("Updating config file 'pay.ini'")
    config['items']['workspace_sid'] = workspace.sid
    config['items']['verify_service_sid'] = verifyService.sid
    with open('pay.ini', 'w') as file:
        config.write(file)


if __name__ == "__main__":
    main(get_args())