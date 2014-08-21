from pyocci import client


class InstancesManager(client.Manager):
    def list(self):
        """Get a list of running instances."""
        return self._list("/compute/")

    def detail(self, instance):
        """Get details of an instance."""
        return self._get("/compute/%s" % instance)
