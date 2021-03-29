#!/usr/bin/env python 
"""
Lists, creates, updates and deletes agents (workers) in the TaskRouter workspace for Agent Pay.
"""

import os
import sys
import configparser
import argparse
import logging
import json
from twilio.rest import Client
from twilio.base.exceptions import TwilioException, TwilioRestException


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
        description="list, add, update or delete an agent")

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

    subparsers = parser.add_subparsers(dest='action')

    list_parser = subparsers.add_parser('list', help='list agents or a specific agent')
    list_parser.add_argument(
        'name', nargs='?', default=None,
        help="agent name (default: all)")

    add_parser = subparsers.add_parser('add', help='add an agent')
    add_parser.add_argument('name', help='agent name')
    add_parser.add_argument('contact', help='contact phone number')
    add_parser.add_argument('mobile', help='mobile phone number')

    update_parser = subparsers.add_parser('update', help='update an agent')
    update_parser.add_argument('name', help='agent name')
    update_parser.add_argument('contact', help='contact phone number')
    update_parser.add_argument('mobile', help='mobile phone number')

    delete_parser = subparsers.add_parser('delete', help='delete an agent')
    delete_parser.add_argument('name', help='agent name')

    return parser.parse_args()


def main(args):
    config = configparser.ConfigParser()
    config.read('pay.ini')
    level = args.log.upper() if args.log else config['items']['log_level'].upper()
    configure_logging(level=getattr(logging, level))
    workspace_sid = config['items']['workspace_sid']
    workers = []
    client = Client(args.key, args.pw, args.account)

    # Get worker by name.
    def get_worker(name):
        for worker in workers:
            if worker.friendly_name == name:
                return worker
        else:
            sys.exit(f"There is no configured agent '{name}'")

    # List named agent or all agents.  
    def list_agents(name):
        if not workers:
            sys.exit('There are no agents configured')

        _workers = [get_worker(name)] if name else workers

        print('Name                Contact Number      Mobile Number')
        print('------------------------------------------------------------')

        # Note that we have to do individual API fetches, as the list operation 
        # does not return worker attributes.
        for worker in _workers:
            worker = client.taskrouter.workspaces(workspace_sid).workers(worker.sid).fetch()
            attributes = json.loads(worker.attributes)
            print(
                f"{worker.friendly_name:20}"
                f"{attributes['contact_uri']:20}"
                f"{attributes['mobile_number']:20}")

    # Create an agent with the specified name, contact URI and mobile phone number.
    # TODO: validate phone numbers.
    def add_agent(name, contact_uri, mobile_number):
        attributes_json = json.dumps({'contact_uri': contact_uri, 'mobile_number': mobile_number})
        worker = client.taskrouter.workspaces(workspace_sid).workers.create(
            friendly_name=name, 
            attributes=attributes_json)
        logger.debug('Created agent, SID=%s', worker.sid)

    # Update an agent's contact URI and mobile phone number. 
    # Any other attributes will be preserved.
    # TODO: validate phone numbers.
    def update_agent(name, contact_uri, mobile_number):
        worker = get_worker(name)
        worker = client.taskrouter.workspaces(workspace_sid).workers(worker.sid).fetch()
        attributes = json.loads(worker.attributes)
        attributes['contact_uri'] = contact_uri
        attributes['mobile_number'] = mobile_number
        attributes_json = json.dumps(attributes)
        client.taskrouter.workspaces(workspace_sid).workers(worker.sid).update(attributes=attributes_json)
        logger.debug('Updated agent, SID=%s', worker.sid)

    # Delete an agent.
    def delete_agent(name):
        worker = get_worker(name)
        client.taskrouter.workspaces(workspace_sid).workers(worker.sid).delete()
        logger.debug('Deleted agent, SID=%s', worker.sid)

    try:
        workers = client.taskrouter.workspaces(workspace_sid).workers.list()
        logger.debug('Got list of %s agents', len(workers))

        if args.action == 'list':       list_agents(args.name)
        elif args.action == 'add':      add_agent(args.name, args.contact, args.mobile)
        elif args.action == 'update':   update_agent(args.name, args.contact, args.mobile)
        elif args.action == 'delete':   delete_agent(args.name)

    except TwilioRestException as ex:
        sys.exit(f"{ex.msg}")

    except TwilioException as ex:
        sys.exit(f"Unable to access API: check credentials. Full message:\n{ex}")    


if __name__ == "__main__":
    main(get_args())