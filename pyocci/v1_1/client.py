from pyocci import client
from pyocci.v1_1 import capabilities

class Client(object):
    def __init__(self, *args, **kwargs):
        self.capabilities = capabilities.CapabilitiesManager(self)

        # NOTE(aloga):  we need to pop used arguments
        self.client = client.HTTPClient(*args, **kwargs)
