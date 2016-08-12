#!/usr/bin/env python
# -*- coding: utf-8 -*-

import xmlrpclib
import urllib2
import cookielib
import os
import getpass
import sys
from urlparse import urlparse


# replace this with bugzilla.eng.vmware.com after you're done testing -jon

BUGZILLA_URL = 'https://bugzilla-beta.eng.vmware.com/xmlrpc.cgi'
BUGZILLA_URL = 'https://bz3-mwonderfuldev-www1.eng.vmware.com/xmlrpc.cgi'
DEBUG = 1

PYVERSION = None

if sys.version_info < (2, 5):
    raise AssertionError("must use python 2.5 or greater")

if sys.version_info > (2, 8):
    raise AssertionError("python 3 is not supported")

if sys.version_info < (2, 7):
    PYVERSION = "py26"
else:
    PYVERSION = "py27"
    import httplib

class CookieTransport(xmlrpclib.Transport):

    '''A subclass of xmlrpclib.Transport that supports cookies.'''

    cookiejar = None
    scheme = 'https'

    def cookiefile(self):
        if 'USERPROFILE' in os.environ:
            homepath = os.path.join(os.environ['USERPROFILE'],
                                    'Local Settings', 'Application Data'
                                    )
        elif 'HOME' in os.environ:
            homepath = os.environ['HOME']
        else:
            homepath = ''

        cookiefile = os.path.join(homepath, '.bugzilla-cookies.txt')
        return cookiefile

    # Cribbed from xmlrpclib.Transport.send_user_agent

    def send_cookies(self, connection, cookie_request):
        if self.cookiejar is None:
            self.cookiejar = \
                cookielib.MozillaCookieJar(self.cookiefile())

            if os.path.exists(self.cookiefile()):
                self.cookiejar.load(self.cookiefile())
            else:
                self.cookiejar.save(self.cookiefile())

        # Let the cookiejar figure out what cookies are appropriate

        self.cookiejar.add_cookie_header(cookie_request)

        # Pull the cookie headers out of the request object...

        cookielist = list()
        for (h, v) in cookie_request.header_items():
            if h.startswith('Cookie'):
                cookielist.append([h, v])

        # ...and put them over the connection

        for (h, v) in cookielist:
            connection.putheader(h, v)

    def make_connection_py26(self, host):
        """xmlrpclib make_connection Python 2.6"""
        return self.make_connection(host)

    def make_connection_py27(self, host):
        """xmlrpclib make_connection Python 2.7"""
        # create a HTTPS connection object from a host descriptor
        # host may be a string, or a (host, x509-dict) tuple
        host, self._extra_headers, x509 = self.get_host_info(host)
        try:
            HTTPS = httplib.HTTPS
        except AttributeError:
            raise NotImplementedError(
                "your version of httplib doesn't support HTTPS"
                )
        else:
            return HTTPS(host, None, **(x509 or {}))

    def _parse_response_py26(self, responsefile, sock=None):
        return self._parse_response(responsefile, sock)

    def _parse_response_py27(self, responsefile, sock=None):
        """Code copied from pythong 2.6 lib."""
        # read response from input file/socket, and parse it
        p, u = self.getparser()

        while 1:
            if sock:
                response = sock.recv(1024)
            else:
                response = responsefile.read(1024)
            if not response:
                break
            if self.verbose:
                print "body:", repr(response)
            p.feed(response)

        responsefile.close()
        p.close()

        return u.close()

    # This is the same request() method from xmlrpclib.Transport,
    # with a couple additions noted below

    def request(
        self,
        host,
        handler,
        request_body,
        verbose=0,
        ):

        h = getattr(self, "make_connection_" + PYVERSION)(host)

        if verbose:
            h.set_debuglevel(1)

        # ADDED: construct the URL and Request object for proper cookie handling

        request_url = '%s://%s/' % (self.scheme, host)
        cookie_request = urllib2.Request(request_url)

        self.send_request(h, handler, request_body)
        self.send_host(h, host)
        self.send_cookies(h, cookie_request)  # ADDED. creates cookiejar if None.
        self.send_user_agent(h)
        self.send_content(h, request_body)

        (errcode, errmsg, headers) = h.getreply()

        # ADDED: parse headers and get cookies here
        # fake a response object that we can fill with the headers above

        class CookieResponse:

            def __init__(self, headers):
                self.headers = headers

            def info(self):
                return self.headers

        cookie_response = CookieResponse(headers)

        # Okay, extract the cookies from the headers

        self.cookiejar.extract_cookies(cookie_response, cookie_request)

        # And write back any changes

        if hasattr(self.cookiejar, 'save'):
            self.cookiejar.save(self.cookiejar.filename)

        if errcode != 200:
            raise xmlrpclib.ProtocolError(host + handler, errcode,
                    errmsg, headers)

        self.verbose = verbose

        try:
            sock = h._conn.sock
        except AttributeError:
            sock = None

        return getattr(self, "_parse_response_" + PYVERSION)(h.getfile(), sock)

class SafeCookieTransport(xmlrpclib.SafeTransport, CookieTransport):

    '''SafeTransport subclass that supports cookies.'''

    scheme = 'https'
    request = CookieTransport.request


class BugzillaServer(object):

    def __init__(self, url, cookie_file):
        self.url = url
        self.cookie_file = cookie_file

        self.cookie_jar = cookielib.MozillaCookieJar(self.cookie_file)
        self.server = xmlrpclib.ServerProxy(url, SafeCookieTransport())
        self.columns = None

    def login(self):

        if self.has_valid_cookie():
            return

        print '==> Bugzilla Login Required'
        print 'Enter username and password for Bugzilla at %s' \
            % self.url
        username = raw_input('Username: ')
        password = getpass.getpass('Password: ')

        debug('Logging in with username "%s"' % username)
        try:
            self.server.User.login({'login': username, 'password': password})
        except xmlrpclib.Fault, err:
            print 'A fault occurred:'
            print 'Fault code: %d' % err.faultCode
            print 'Fault string: %s' % err.faultString
        debug('logged in')
        self.cookie_jar.save

    def has_valid_cookie(self):
        try:
            parsed_url = urlparse(self.url)
            host = parsed_url[1]
            _path = parsed_url[2] or '/'

            # Cookie files don't store port numbers, unfortunately, so
            # get rid of the port number if it's present.

            host = host.split(':')[0]

            debug("Looking for '%s' cookie in %s" % (host,
                  self.cookie_file))
            self.cookie_jar.load(self.cookie_file, ignore_expires=True)

            try:
                cookie = self.cookie_jar._cookies[host]['/'
                        ]['Bugzilla_logincookie']

                if not cookie.is_expired():
                    debug('Loaded valid cookie -- no login required')
                    return True

                debug('Cookie file loaded, but cookie has expired')
            except KeyError:
                debug('Cookie file loaded, but no cookie for this server'
                      )
        except IOError, error:
            debug("Couldn't load cookie file: %s" % error)

        return False


def debug(s):
    """
    Prints debugging information if run with --debug
    """

    if DEBUG:
        print '>>> %s' % s


def main(args):
    if 'USERPROFILE' in os.environ:
        homepath = os.path.join(os.environ['USERPROFILE'],
                                'Local Settings', 'Application Data')
    elif 'HOME' in os.environ:
        homepath = os.environ['HOME']
    else:
        homepath = ''

    cookie_file = os.path.join(homepath, '.bugzilla-cookies.txt')

    server = BugzillaServer(BUGZILLA_URL, cookie_file)
    server.login()


if __name__ == '__main__':
    main(sys.argv[1:])