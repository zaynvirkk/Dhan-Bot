"""Validate existing dashboard firewall scope before an idempotent deployment."""
from __future__ import annotations

import json
import sys


def validate_firewall(rules, network):
    if not isinstance(rules, list) or len(rules) > 1:
        raise ValueError('Expected at most one named dashboard firewall rule')
    if not rules:
        return
    rule = rules[0]
    expected = (rule.get('network', '').rsplit('/', 1)[-1] == network
                and rule.get('direction') == 'INGRESS'
                and rule.get('disabled') is False
                and rule.get('targetTags') == ['dhan-private-dashboard']
                and rule.get('sourceRanges') == ['0.0.0.0/0']
                and not any(rule.get(k) for k in ('sourceTags', 'sourceServiceAccounts',
                                                  'targetServiceAccounts', 'denied')))
    if not expected:
        raise ValueError('Existing firewall rule scope differs; not replacing it')
    permissions = set()
    allowed = rule.get('allowed')
    if not isinstance(allowed, list):
        raise ValueError('Missing explicit TCP port permissions')
    for item in allowed:
        if not isinstance(item, dict) or item.get('IPProtocol') != 'tcp':
            raise ValueError('Only TCP 80 and 443 are permitted')
        ports = item.get('ports')
        if not isinstance(ports, list) or not ports or any(p not in ('80', '443') for p in ports):
            raise ValueError('Only explicit TCP ports 80 and 443 are permitted')
        permissions.update(ports)
    # GCP can return the two ports as one entry or two equivalent entries.
    if permissions != {'80', '443'}:
        raise ValueError('Both HTTP challenge and HTTPS ports are required')


if __name__ == '__main__':
    with open(sys.argv[1]) as stream:
        validate_firewall(json.load(stream), sys.argv[2])
