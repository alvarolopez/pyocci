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
