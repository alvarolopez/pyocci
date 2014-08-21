import prettytable

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
                # FIXME(aloga): is this really true?
                if link["kind"]["term"] == "networkinterface":
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
