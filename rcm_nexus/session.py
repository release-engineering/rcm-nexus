# Copyright (c) 2014 Red Hat, Inc..
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the GNU Public License v3.0
# which accompanies this distribution, and is available at
# http://www.gnu.org/licenses/gpl.html
#
# Utility methods for nexuslib, and Session class that provides infrastructure
# methods that are tuned to deal with Nexus REST requests.
#
# NOTE: Calling session.close() is an important cleanup step to remove 
# cache directory required by httplib2.
#
# Authors:
#    John Casey (jcasey@redhat.com)

from __future__ import print_function

import os
import sys
import requests
import shutil
import getpass
import base64

import six


class Enum(object):
    def __init__(self, **kwargs):
        self._all_values = []
        
        for key,val in kwargs.items():
            setattr(self, key, val)
            self._all_values.append(val)
            
            if not isinstance(val, six.string_types):
                strkey = key + '_str'
                strval = str(val)
                setattr(self, strkey, strval)
                self._all_values.append(strval)
            
        
        self._all_values = set(self._all_values)
#         self._all_values = kwargs.values()
    
    def values(self):
        return self._all_values


class FileNotFoundError(RuntimeError):
    pass


def python_boolean(value):
    return True if str(value) in ('True', 'true') else False

class Session(object):
#     USER_AGENT = 'curl/7.19.7 (x86_64-redhat-linux-gnu) libcurl/7.19.7 NSS/3.14.3.0 zlib/1.2.3 libidn/1.18 libssh2/1.4.2'
    
    def __init__(self, config, debug=False):
        """Initialize the session, containing the environment config and default HTTP headers.
           Set default headers to accept = application/xml and content-type = application/xml
        """
        self.config = config
        self.debug = debug

        if config.username is not None:
            self.auth = requests.auth.HTTPBasicAuth(config.username, config.get_password())
        else:
            self.auth = None

        self.headers = {
            'Accept': 'application/xml',
            'Content-Type': 'application/xml',
            # 'User-Agent': Session.USER_AGENT,
        }

    def close(self):
        """Currently a no-op"""
    
    def _combine_headers(self, headers=None, existing_headers=None):
        """In the event headers are supplied with a method call, merge those with the default
           headers maintained by the Session instance, giving preference to the headers passed
           in. The result can be used for a specific HTTP call.
           
           Otherwise, if the passed-in headers are empty, just return the headers maintained for this session.
        """
        if existing_headers is None:
            existing_headers = self.headers
            
        result = dict(existing_headers)
        if headers is not None:
            result.update(headers)
            
        return result

    def _handle_error(self, response, path, fail):
        print(
            "%s %s failed: %s"
            % (response.request.method.upper(), path, response.status_code),
            file=sys.stderr
        )
        if response.status_code == 401:
            print(
                "Incorrect credentials for user %s. Username can be changed by "
                "setting USER env var, or in ~/.config/rcm-nexus.conf."
                % self.auth.username,
                file=sys.stderr,
            )
        if response.status_code == 403:
            print(
                "You don't have permissions to perform this action. Contact "
                "maintainers of the Nexus instance you are trying to use.",
                file=sys.stderr,
            )
        if response.headers.get("Content-Type", "").startswith("application/json"):
            data = response.json()
            for error in data["errors"]:
                print(error["msg"], file=sys.stderr)
        if fail:
            response.raise_for_status()
        return (response, None)

    def get(self, path, headers=None, expect_status=200, ignore_404=False, fail=True):
        """Issue a GET request to the Nexus server, on the given path. Expect a response status of 200, 
           unless specified by expect_status. Fail if 404 response is given, unless ignore_404 is specified.
           Fail any unexpected, non-404 response, unless fail is specified differently.
           
           Return requests.Response
        """
        h = self._combine_headers(headers)
        
        uri = self.config.url + path
        if self.debug:
            print("GET %s\n%s" % (uri,h))
            
        response = requests.get(uri, headers=h, verify=self.config.ssl_verify, auth=self.auth)
        
        if self.debug:
            print("Response data:\n %s\n\nBody:\n%s" % (response, response.text))
            
        if response.status_code == expect_status:
            return (response,response.text)
        elif ignore_404 and response.status_code == 404:
            return (response,response.text)
        else:
            return self._handle_error(response, path, fail)
                
    def post(self, path, body, headers=None, expect_status=201, ignore_404=False, fail=True):
        """Issue a POST request to the Nexus server, on the given path. Expect a response status of 201 (Created), 
           unless specified by expect_status. Fail if 404 response is given, unless ignore_404 is specified.
           Fail any unexpected, non-404 response, unless fail is specified differently.
           
           Return response.
        """
        h = self._combine_headers(headers)
        
        uri = self.config.url + path
        if self.debug:
            print("POST %s\n%s" % (uri,h))
            print("Request body:\n", body)
            
        response = requests.post(uri, data=body, headers=h, verify=self.config.ssl_verify, auth=self.auth)
        
        if self.debug:
            print("Response data:\n %s\n\nBody:\n%s\n" % (response, response.text))
            
        if response.status_code == expect_status:
            return (response,response.text)
        elif ignore_404 and response.status_code == 404:
            return (response,response.text)
        else:
            return self._handle_error(response, path, fail)
                
    def put(self, path, body, headers=None, expect_status=200, ignore_404=False, fail=True):
        """Issue a PUT request to the Nexus server, on the given path. Expect a response status of 200, 
           unless specified by expect_status. Fail if 404 response is given, unless ignore_404 is specified.
           Fail any unexpected, non-404 response, unless fail is specified differently.
           
           Return response.
        """
        h = self._combine_headers(headers)
        
        uri = self.config.url + path
        if self.debug:
            print("PUT %s\n%s" % (uri,h))
            print("Request body:\n", body)
            
        response = requests.put(uri, data=body, headers=h, verify=self.config.ssl_verify, auth=self.auth)
        
        if self.debug:
            print("Response data:\n %s\n\nBody:\n%s\n" % (response, response.text))
            
        if response.status_code == expect_status:
            return (response,response.text)
        elif ignore_404 and response.status_code == 404:
            return (response,response.text)
        else:
            return self._handle_error(response, path, fail)

    def stream_remote(self, url):
        """Download content from URL and generate chunks from the response. The
        URL should be provided as absolute URL including domain name.
        """
        with requests.get(url, auth=self.auth, stream=True) as resp:
            if resp.status_code == 404:
                raise FileNotFoundError()
            if resp.status_code >= 400:
                self._handle_error(resp, url, fail=True)
            for chunk in resp.iter_content(None):
                yield chunk
