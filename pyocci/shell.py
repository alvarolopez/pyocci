"""
OCCI Command Line Client
"""

from __future__ import print_function
import argparse
import logging
import sys

import pyocci
from pyocci import client
from pyocci import exceptions
from pyocci import utils
from pyocci.v1_1 import shell as shell_v1_1

DEFAULT_OCCI_API_VERSION=1.1

logger = logging.getLogger(__name__)

class OcciArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super(OcciArgumentParser, self).__init__(*args, **kwargs)


class OcciShell(object):
    def get_parser(self):
        parser = OcciArgumentParser(
            prog="pyocci",
            description=__doc__.strip(),
            epilog=("Run 'pyocci help COMMAND' "
                    "for help on an specific command."),
            add_help=False,
        )

        # Global arguments
        parser.add_argument('-h', '--help',
            action='store_true',
            help=argparse.SUPPRESS,
        )

        parser.add_argument('--version',
            action='version',
            version=pyocci.__version__
        )

        parser.add_argument('--debug',
            default=False,
            action='store_true',
            help="Print debugging output"
        )

        # API versioning
        parser.add_argument('--occi-api-version',
            metavar='<occi-api-ver>',
            default=utils.env('OCCI_API_VERSION',
                default=DEFAULT_OCCI_API_VERSION),
            help='Accepts 1.1, defaults to env[OCCI_API_VERSION].'
        )

        # Connection arguments
        parser.add_argument('--endpoint_url',
            default=utils.env('OCCI_ENDPOINT_URL'),
            help='Defaults to env[OCCI_ENDPOINT_URL].'
        )

        parser.add_argument('--occi-cacert',
            metavar='<ca-certificate>',
            default=utils.env('OCCI_CACERT', default=None),
            help='Specify a CA bundle file to use in '
                 'verifying a TLS (https) server certificate. '
                 'Defaults to env[OCCI_CACERT]')

        parser.add_argument('--insecure',
            default=utils.env('OCCI_INSECURE', default=False),
            action='store_true',
            help="Explicitly allow pyocci to perform \"insecure\" "
                 "SSL (https) requests. The server's certificate will "
                 "not be verified against any certificate authorities. "
                 "This option should be used with caution.")

        # Authentication options
        parser.add_argument("--auth_type",
            default="voms",
            help=("One of %s, . Defaults to 'voms'" %
                client.HTTPClient.auth_methods.keys())
        )

        parser.add_argument("--occi_username",
            default=utils.env("OCCI_USERNAME"),
            help="Defaults to env[OCCI_USERNAME]"
        )

        parser.add_argument("--occi_password",
            default=utils.env("OCCI_PASSWORD"),
            help="Defaults to env[OCCI_PASSWORD]"
        )

        parser.add_argument("--occi_group",
            default=utils.env("OCCI_GROUP"),
            help="Defaults to env[OCCI_GROUP]"
        )

        parser.add_argument("--x509_user_proxy",
            default=utils.env("X509_USER_PROXY"),
            help="Defaults to env[X509_USER_PROXY]"
        )

        return parser

    def get_subcommand_parser(self, version):
        parser = self.get_parser()

        self.subcommands = {}
        subparsers = parser.add_subparsers(metavar='<subcommand>')

        try:
            actions_module = {
                '1.1': shell_v1_1,
            }[version]
        except KeyError:
            actions_module = shell_v1_1

        self._find_actions(subparsers, actions_module)
        self._find_actions(subparsers, self)

        return parser

    def _find_actions(self, subparsers, actions_module):
        for attr in (a for a in dir(actions_module) if a.startswith('do_')):
            # I prefer to be hypen-separated instead of underscores.
            command = attr[3:].replace('_', '-')
            callback = getattr(actions_module, attr)
            desc = callback.__doc__ or ''
            action_help = desc.strip().split('\n')[0]
            arguments = getattr(callback, 'arguments', [])

            subparser = subparsers.add_parser(command,
                help=action_help,
                description=desc,
                add_help=False,
            )
            subparser.add_argument('-h', '--help',
                action='help',
                help=argparse.SUPPRESS,
            )
            self.subcommands[command] = subparser
            for (args, kwargs) in arguments:
                subparser.add_argument(*args, **kwargs)
            subparser.set_defaults(func=callback)

    @utils.arg('command', metavar='<subcommand>', nargs='?',
                    help='Display help for <subcommand>')
    def do_help(self, args):
        """
        Display help about this program or one of its subcommands.
        """
        if args.command:
            if args.command in self.subcommands:
                self.subcommands[args.command].print_help()
            else:
                raise exceptions.CommandError("'%s' is not a valid subcommand" %
                                              args.command)
        else:
            self.parser.print_help()

    def setup_debugging(self, debug):
        if not debug:
            return

        streamhandler = logging.StreamHandler()
        streamformat = "%(levelname)s (%(module)s:%(lineno)d) %(message)s"
        streamhandler.setFormatter(logging.Formatter(streamformat))
        logger.setLevel(logging.DEBUG)
        logger.addHandler(streamhandler)

    def main(self, argv):
        parser = self.get_parser()
        (options, args) = parser.parse_known_args(argv)
        self.setup_debugging(options.debug)

        subcommand_parser = self.get_subcommand_parser(
                options.occi_api_version)
        self.parser = subcommand_parser

        if options.help or not argv:
            subcommand_parser.print_help()
            return 0

        args = subcommand_parser.parse_args(argv)

        if args.func == self.do_help:
            self.do_help(args)
            return 0

        (
            endpoint_url,
            auth_type,
            username,
            password,
            group,
            x509_user_proxy,
            insecure,
            ) = (
                    args.endpoint_url,
                    args.auth_type,
                    args.occi_username,
                    args.occi_password,
                    args.occi_group,
                    args.x509_user_proxy,
                    args.insecure,
                )


        if not endpoint_url:
            raise exceptions.CommandError("You must provide and endpoint url "
                                          "via either --endpoint_url or "
                                          "env[OCCI_ENDPOINT_URL]")

        if auth_type not in client.HTTPClient.auth_methods.keys():
            raise exceptions.CommandError("Specified 'auth_type' not "
                "supported, provided '%s', expected one of "
                "%s" % (auth_type, client.HTTPClient.auth_methods.keys()))

        if auth_type == "voms" and not x509_user_proxy:
            raise exceptions.CommandError("If you are using VOMS authentication "
                                          "you must provide a valid proxy file "
                                          "via either --x509_user_proxy or "
                                          "env[X509_USER_PROXY]")

        self.cs = client.Client(
                options.occi_api_version,
                endpoint_url,
                auth_type,
                username=username,
                password=password,
                group=group,
                x509_user_proxy=x509_user_proxy,
                http_log_debug=options.debug,
                insecure=insecure,
        )

        args.func(self.cs, args)


def main():
    try:
        OcciShell().main(sys.argv[1:])
    except Exception, e:
        logger.debug(e, exc_info=1)
        print("ERROR: %s" % unicode(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
