# PyOCCI CLI

This is a draft of a OCCI client written in Python.

## Quick instructions:

    $ virtualenv VENV
    $ source VENV/bin/activate
    $ python setup.py install
    $ voms-proxy-init -voms fedcloud.egi.eu -rfc
    $ pyocci --debug --insecure --endpoint-url https://example.org:8787 --occi-group foobar capabilities

