from pyocci import client

class CapabilitiesManager(client.Manager):
    def list(self):
        """
        Get a list of capabilities
        """
        return self._list("/-/")
