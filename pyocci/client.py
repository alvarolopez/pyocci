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

"""
OCCI Client interface. Handles the REST calls and responses.
"""

import logging

import requests

try:
    import json
except ImportError:
    import simplejson as json

from pyocci import exceptions
from pyocci import utils


class Manager(object):
    """Provide CRUD operations."""

    def __init__(self, api):
        self.api = api

    def _list(self, url, obj_class=None, body=None):
        if body:
            _resp, body = self.api.client.post(url, body=body)
        else:
            _resp, body = self.api.client.get(url)
        return body

    def _get(self, url):
        _resp, body = self.api.client.get(url)
        return body


class HTTPClient(object):

    USER_AGENT = 'pyocci'

    def __init__(self,
                 endpoint_url,
                 auth_type,
                 username=None,
                 password=None,
                 group=None,
                 x509_user_proxy=None,
                 timeout=None,
                 http_log_debug=False,
                 insecure=False,
                 cacert=None):

        # Connection options
        self.endpoint_url = endpoint_url

        # Auth options
        self.auth_type = auth_type
        self.username = username
        self.password = password
        self.group = group

        if x509_user_proxy and self.auth_type == "voms":
            self.cert = x509_user_proxy
        else:
            self.cert = None

        # FIXME(aloga): we should let the users pass this
        self.auth_token = None

        if insecure:
            self.verify_cert = False
        else:
            if cacert:
                self.verify_cert = cacert
            else:
                self.verify_cert = True

        self.http_log_debug = http_log_debug
        if timeout is not None:
            self.timeout = float(timeout)
        else:
            self.timeout = None

        self._logger = logging.getLogger(__name__)
        if self.http_log_debug:
            ch = logging.StreamHandler()
            self._logger.setLevel(logging.DEBUG)
            self._logger.addHandler(ch)
            if hasattr(requests, 'logging'):
                rql = requests.logging.getLogger(requests.__name__)
                rql.addHandler(ch)
                # Since we have already setup the root logger on debug, we
                # have to set it up here on WARNING (its original level)
                # otherwise we will get all the requests logging messanges
                rql.setLevel(logging.WARNING)
        # requests within the same session can reuse TCP connections from pool
        self.http = requests.Session()

    def http_log_req(self, method, url, kwargs):
        if not self.http_log_debug:
            return

        string_parts = ['curl -i']

        if not kwargs.get('verify', True):
            string_parts.append(' --insecure')

        string_parts.append(" '%s'" % url)
        string_parts.append(' -X %s' % method)

        for element in kwargs['headers']:
            header = ' -H "%s: %s"' % (element, kwargs['headers'][element])
            string_parts.append(header)

        if 'data' in kwargs:
            string_parts.append(" -d '%s'" % (kwargs['data']))
        self._logger.debug("\nREQ: %s\n" % "".join(string_parts))

    def http_log_resp(self, resp):
        if not self.http_log_debug:
            return
        self._logger.debug(
            "RESP: [%s] %s\nRESP BODY: %s\n",
            resp.status_code,
            resp.headers,
            resp.text)

    def request(self, url, method, exit_on_failure=True, **kwargs):
        kwargs.setdefault('headers', kwargs.get('headers', {}))
        kwargs['headers']['User-Agent'] = self.USER_AGENT

        # FIXME(aloga): we need to fix this
        kwargs['headers']['Accept'] = 'application/occi+json'
#        kwargs['headers']['Accept'] = 'application/json'
        if 'body' in kwargs:
            kwargs['headers']['Content-Type'] = 'application/json'
            kwargs['data'] = json.dumps(kwargs['body'])
            del kwargs['body']
        else:
            pass
#            kwargs['headers']['Content-Type'] = 'text/occi'
#            kwargs['headers']['Content-Type'] = 'text/plain'
#            kwargs['headers']['Content-Type'] = 'application/occi+json'
#            kwargs['headers']['Content-Type'] = 'application/json'
        if self.timeout is not None:
            kwargs.setdefault('timeout', self.timeout)
        kwargs['verify'] = self.verify_cert

        self.http_log_req(method, url, kwargs)
        resp = self.http.request(
            method,
            url,
            cert=self.cert,
            **kwargs)
        self.http_log_resp(resp)

        if resp.text:
            # NOTE(alaski): Because force_exceptions_to_status_code=True
            # httplib2 returns a connection refused event as a 400 response.
            # To determine if it is a bad request or refused connection we need
            # to check the body.  httplib2 tests check for 'Connection refused'
            # or 'actively refused' in the body, so that's what we'll do.
            if resp.status_code == 400:
                if ('Connection refused' in resp.text or
                        'actively refused' in resp.text):
                    raise exceptions.ConnectionRefused(resp.text)
            try:
                body = json.loads(resp.text)
            except ValueError:
                body = None
        else:
            body = None

        if exit_on_failure and resp.status_code >= 400:
            raise exceptions.from_response(resp, body, url, method)

        return resp, body

    def _cs_request(self, url, method, **kwargs):
        # Perform the request once. If we get a 401 back then it
        # might be because the auth token expired, so try to
        # re-authenticate and try again. If it still fails, bail.
        try:
            if self.auth_token:
                kwargs.setdefault('headers',
                                  {})['X-Auth-Token'] = self.auth_token
#            if self.projectid:
#                kwargs['headers']['X-Auth-Project-Id'] = self.projectid

            resp, body = self.request(self.endpoint_url + url, method,
                                      **kwargs)
            return resp, body
        except exceptions.Unauthorized, ex:
            try:
                self.authenticate()
                kwargs.setdefault('headers',
                                  {})['X-Auth-Token'] = self.auth_token
                resp, body = self.request(self.endpoint_url + url,
                                          method, **kwargs)
                return resp, body
            except exceptions.Unauthorized:
                raise ex

    def _authenticate_with_keystone(self, url, **kwargs):
        version = "v2.0"
        if not url.endswith("/"):
            url += "/"

        url += version

        if self.auth_token:
            body = {"auth": {
                    "token": {"id": self.auth_token}}}
        elif self.auth_type == "voms":
            body = {"auth": {"voms": True}}
        else:
            body = {"auth": {
                    "passwordCredentials": {"username": self.user,
                                            "password": self.password}}}

        if self.group:
            body["auth"]["tenantName"] = self.group

        method = "POST"
        token_url = url + "/tokens"
        # if we have a valid auth token, use it instead of generating a new one
        if self.auth_token:
            kwargs.setdefault('headers', {})['X-Auth-Token'] = self.auth_token
            token_url += "/" + self.auth_token
            method = "GET"
            body = None

        if self.auth_token and self.tenant_id and self.management_url:
            return None

        # Make sure we follow redirects when trying to reach Keystone
        resp, respbody = self.request(
            token_url,
            method,
            body=body,
            allow_redirects=True,
            **kwargs)

        if resp.status_code == 200:
            self.auth_token = respbody['access']['token']['id']

        return None

#        #print token_url
#
#        #print body
#        try:
#            resp, body = self.request(token_url, "POST", body=body)
#        finally:
#            self.follow_all_redirects = tmp_follow_all_redirects
#
#        if resp.status_code == 200:
#            self.auth_token = body['access']['token']['id']
#            #print self.auth_token
#            return None
#        elif resp.status_code == 305:
#            return resp['location']
#        else:
#            raise exceptions.from_response(resp, body, url, "POST")

    def _authenticate_voms(self):
        resp, body = self.request(self.endpoint_url, 'GET',
                                  exit_on_failure=False)
        if resp.status_code == 401 and 'www-authenticate' in resp.headers:
            auth_url = resp.headers.get('www-authenticate', None)
            if auth_url:
                # FIXME(aloga): extract the url in a nice way, please
                auth_method, auth_url = auth_url.split()
                auth_url = auth_url.split("=")[-1][1:-1]
                if auth_method == "Keystone":
                    return self._authenticate_with_keystone(auth_url)
        elif resp.status_code >= 400:
            raise exceptions.from_response(resp, body,
                                           self.endpoint_url, "GET")
        return resp, body

    auth_methods = {
        "voms": _authenticate_voms,
    }

    def authenticate(self):
        return self.auth_methods[self.auth_type](self)

    def get(self, url, **kwargs):
        return self._cs_request(url, 'GET', **kwargs)

    def post(self, url, **kwargs):
        return self._cs_request(url, 'POST', **kwargs)

    def put(self, url, **kwargs):
        return self._cs_request(url, 'PUT', **kwargs)

    def delete(self, url, **kwargs):
        return self._cs_request(url, 'DELETE', **kwargs)


def get_client_class(version):
    versions = {
        "1.1": "pyocci.v1_1.client.Client",
    }
    try:
        client_path = versions[str(version)]
    except (KeyError, ValueError):
        msg = "Invalid client version '%s'. must be one of: %s" % (
              (version, ', '.join(versions.keys())))
        raise exceptions.UnsupportedVersion(msg)
    return utils.import_class(client_path)


def Client(version, *args, **kwargs):
    client_class = get_client_class(version)
    return client_class(*args, **kwargs)
