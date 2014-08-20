Quick instructions:

virtualenv VENV
source VENV/bin/activate
python setup.py install

voms-proxy-init -voms fedcloud.egi.eu -rfc

pyocci --debug --insecure --endpoint_url https://example.org:8787 --occi_group foobar capabilities

