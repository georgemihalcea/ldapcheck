# ldapcheck
ldap check service

## Overview
A service check for ldap, that can be used by haproxy to check the availability of the backend ldap servers.
It checks ldaps and ldap with starttls.

## Why
I wanted to set a better load balancer service check than a simple TCP connection to port 389 and 636 for a ldap cluster. I was thinking about a check similar to a mysql-check (bash script started by xinetd), like the one described here: https://www.howtoforge.com/tutorial/how-to-setup-haproxy-as-load-balancer-for-mariadb-on-centos-7/. I searched, but I did not find anything similar for ldap, so I decided to write one in python.

## How it works
The ldapcheck.py script starts 2 server sockets, one for ldap check and one for ldaps check. The 2 ports must be configured in the config.yml file. The host is optional, the default value is "0.0.0.0". An user must be created into the ldap and configured in the config.yml file. The check request must be a standard GET or HEAD http request ("GET /" or "HEAD /" is enough). When a check request is made on one of the 2 ports, the script connects to the ldap, using the url, username and password configured in the config.yml file. If the connection is successfull, it returns a standard "200 OK" http response. If not, it returns "503 Service Unavailable", and the error message (as json) in the body. If the request is invalid, it returns "400 Invalid Request".

## How to run it
The script can be run from command line (for debugging), but the best option is to be started during system boot.
For operating systems using systemd, the file etc/ldapcheck.service should be copied to `/etc/systemd/system/ldapcheck.service`, edited if the desired location of ldapcheck.py is other than "/usr/local/bin/ldapcheck.py", and the service should be activated with:
<pre>
systemctl daemon-reload
systemctl enable ldapcheck.service
systemctl start ldapcheck.service
</pre>

# How to use it with haproxy
This is an example configuration for a haproxy with one ldap and one ldaps frontends (VIPs) and one ldap and one ldaps backends (server pools). In my example, the ldapcheck service is running on the same servers as the ldap service, so it must use different ports. I configured 1389 for ldap and 1636 for ldaps (the same values configured in the config_sample.yml file).
<pre>
frontend ldap_front
    bind                  :389
    mode                  tcp
    description           LDAP Service
    option                tcplog
    option                socket-stats
    option                tcpka
    timeout client        5s
    default_backend       ldap_back

frontend ldaps_front
    bind                  :636
    mode                  tcp
    description           LDAPS Service
    option                tcplog
    option                socket-stats
    option                tcpka
    timeout client        5s
    default_backend       ldaps_back

backend ldap_back
    default-server        port 389 fall 3 rise 2 inter 2s downinter 3s slowstart 30s maxconn 512 maxqueue 512 weight 100
    server                ldap1 172.16.0.21 check port 1389
    server                ldap2 172.16.0.22 check port 1389
    mode                  tcp
    balance               first
    option                httpchk GET / HTTP/1.0
    http-check            expect status 200
    timeout server        2s
    timeout connect       1s

backend ldaps_back
    default-server        port 636 fall 3 rise 2 inter 2s downinter 3s slowstart 30s maxconn 512 maxqueue 512 weight 100
    server                ldap1 172.16.0.21 check port 1636
    server                ldap2 172.16.0.22 check port 1636
    mode                  tcp
    balance               first
    option                tcpka
    option                httpchk GET / HTTP/1.0
    http-check            expect status 200
    timeout server        2s
    timeout connect       1s
</pre>

