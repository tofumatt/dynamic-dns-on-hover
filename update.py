#!/usr/bin/env python
"""
Dynamic DNS for Hover

Most code from https://gist.github.com/dankrause/5585907

usage:
    update.py --username=USERNAME --password=PASSWORD <domain> [--ip=IP]
    update.py --config=CONFIG <domain> [--ip=IP]

options:

    --username=USERNAME  Your username on hover.com
    --password=PASSWORD  Your password on hover.com
    <domain>             Domain to update
    --ip=IP              IP to set, if empty get external IP from ifconfig.me

    --config=CONFIG      Read usernameand password from a INI like file
"""

import ConfigParser
import docopt
import requests
import sys
import logging

VERSION = 0.1

class HoverException(Exception):
    pass

class HoverAPI(object):
    def __init__(self, username, password):
        params = {"username": username, "password": password}
        r = requests.post("https://www.hover.com/api/login", params=params)
        logging.debug(r)
        if not r.ok or "hoverauth" not in r.cookies:
            raise HoverException(r)
        self.cookies = {"hoverauth": r.cookies["hoverauth"]}
    def call(self, method, resource, data=None):
        url = "https://www.hover.com/api/{0}".format(resource)
        r = requests.request(method, url, data=data, cookies=self.cookies)
        if not r.ok:
            raise HoverException(r)
        if r.content:
            body = r.json()
            if "succeeded" not in body or body["succeeded"] is not True:
                raise HoverException(body)
            return body


def get_public_ip():
    return requests.get("http://ifconfig.me/ip").content


def update_dns(username, password, fqdn, ip):
    try:
        client = HoverAPI(username, password)
    except HoverException as e:
        raise HoverException("Authentication failed")
    dns = client.call("get", "dns")

    dns_id = None
    for domain in dns["domains"]:
        if fqdn == domain["domain_name"]:
            fqdn = "@.{domain_name}".format(**domain)
        for entry in domain["entries"]:
            logging.info(entry)
            if entry["type"].upper() != "A": continue
            logging.info(entry["name"])
            logging.info(domain["domain_name"])
            logging.info(fqdn)
            if "{0}.{1}".format(entry["name"], domain["domain_name"]) == fqdn:
                dns_id = entry["id"]
                break
    if dns_id is None:
        raise HoverException("No DNS record found for {0}".format(fqdn))

    response = client.call("put", "dns/{0}".format(dns_id), {"content": ip})

    if "succeeded" not in response or response["succeeded"] is not True:
        raise HoverException(response)

    print "Updated record for {0} to: {1}".format(fqdn, ip)


def main(args):
    if args["--username"]:
        username, password = args["--username"], args["--password"]
    else:
        config = ConfigParser.ConfigParser()
        config.read(args["--config"])
        items = dict(config.items("hover"))
        username, password = items["username"], items["password"]

    domain = args["<domain>"]
    ip = args.get("--ip", get_public_ip())

    try:
        logging.info(username, password, domain, ip)
        update_dns(username, password, domain, ip)
    except HoverException as e:
        print "Unable to update DNS: {0}".format(e)
        return 1

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    args = docopt.docopt(__doc__, version=VERSION)
    logging.debug(args)
    status = main(args)
    sys.exit(status)
