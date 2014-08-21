# Copyright 2013 Spanish National Research Council (CSIC)
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import prettytable

from pyocci import exceptions
from pyocci import occi
from pyocci import utils


def do_capabilities(cs, args):
    """Print a list of the service capabilities."""
    caps = cs.capabilities.list()
    fields = ["scheme", "location", "term", "title"]

    schemes = {i["scheme"] for i in caps}

    print schemes
    for scheme in schemes:
        aux = [i for i in caps if scheme == i["scheme"]]
        utils.print_list(aux, fields)


@utils.arg('--detailed',
           dest='detailed',
           action='store_true',
           help='Get a detailed listing of the running instances')
def do_instance_list(cs, args):
    """Print a list of the running instances."""
    instances = cs.instances.list()

    fields = ["OCCI ID"]
    if args.detailed:
        fields.extend(["Name", "State", "Network"])
        occi_attrs = ("occi.compute.hostname",
                      "occi.compute.state")

    pt = prettytable.PrettyTable([f for f in fields], caching=False)
    pt.align = 'l'

    for instance in instances:
        row = []
        attrs = instance.get('attributes', {})
        instance_id = attrs.get('occi.core.id', None)
        row.append(instance_id)

        if args.detailed and instance_id:
            if not all([i in attrs for i in occi_attrs]):
                instance = cs.instances.detail(instance_id)
                attrs = instance.get('attributes', {})

            name = attrs.get("occi.core.title", None)
            if name is None:
                name = attrs.get("occi.compute.hostname", None)
            row.append(name)
            row.append(attrs.get("occi.compute.state", None))

            links = instance.get("links", [])
            network = []
            for link in links:
                if occi.CATEGORIES["network"] in link["kind"]["related"]:
                    # get IPv4
                    ip = link["attributes"].get(
                        "occi.networkinterface.address",
                        None
                    )
                    if not ip:
                        ip = link["attributes"].get(
                            "occi.networkinterface.ip6",
                            None
                        )
                    network.append(ip)
            row.append(network)

        pt.add_row(row)

    print(pt.get_string())


@utils.arg('instance',
           help='Instance OCCI ID')
def do_instance_show(cs, args):
    """Get details about an instance."""
    try:
        instance = cs.instances.detail(args.instance)
    except exceptions.NotFound as e:
        msg = "No server with an id of '%s' exists" % args.instance
        e.message = msg
        raise

    _print_server_details(instance)


def _print_server_details(instance):

    d = instance["attributes"].copy()

    for mixin in instance.get("mixins", []):
        mmap = {
            "image": occi.CATEGORIES["image"],
            "flavor": occi.CATEGORIES["flavor"],
        }
        for k, url in mmap.iteritems():
            if url in mixin.get("related", []):
                d["%s name" % k] = mixin.get("title", None)
                d["%s id" % k] = mixin.get("term", None)
                d["%s scheme" % k] = mixin.get("scheme", None)
                continue

    d["network"] = []
    for link in instance.get("links", []):
        if occi.CATEGORIES["network"] in link["kind"].get("related", []):
            mac = link["attributes"]["occi.networkinterface.mac"]
            address = link["attributes"].get("occi.networkinterface.address",
                                             None)
            if not address:
                address = link["attributes"].get("occi.networkinterface.ip6",
                                                 None)

            d["network"].append("%s (%s)" % (address, mac))

    utils.print_dict(d)
