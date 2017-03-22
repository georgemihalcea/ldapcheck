#!/usr/bin/env python


"""
ldap check service
Author: George Mihalcea
Created: 22.03.2017
"""

import yaml
import ldap
import socket
import sys
import os
import signal
import multiprocessing
from threading import Thread
from time import sleep


CONFIG_FILE = '../config/config.yml'


def sig_term(mysignal, frame):
    """Handling termination signals
    """
    print("Signal %s frame %s - exiting." % (mysignal, frame))
    raise ExitDaemon


class ExitDaemon(Exception):
    """Exception used to exit daemon
    """
    pass


def get_config(config):
    """Reads config file. Returns config options as dictionary.
    """
    cfg = {}
    try:
        cfg = yaml.load(open(config, 'r'))
        if 'HOST' not in cfg:
            cfg['HOST'] = '0.0.0.0'
        if 'DATA_SIZE' not in cfg:
            cfg['DATA_SIZE'] = 512
        if 'SLEEP' not in cfg:
            cfg['SLEEP'] = 1
        if 'DEBUG' not in cfg:
            cfg['DEBUG'] = False
        if 'INFO' not in cfg:
            cfg['INFO'] = False

    except yaml.scanner.ScannerError as err:
        print('Invalid config file. Error: %s. Exiting...' % err)
        sys.exit(1)
    return cfg


class ConnThread(Thread):
    """Thread that handles one connection
    """
    def __init__(self, conn, config, secure):
        Thread.__init__(self)
        self.conn = conn
        self.config = config
        self.secure = secure
        if config['INFO']:
            print('New thread started')

    def send_response(self, code, resp):
        """Send http response
        """
        try:
            self.conn.send('HTTP/1.0 %s\n' % code)
            self.conn.send('Content-Type: text/plain\n\n')
            self.conn.send('%s\n' % resp)
        except socket.error, e:
            if config['DEBUG']:
                print(e)
            pass
        self.conn.close()

    def run(self):
        while True:
            data = self.conn.recv(config['DATA_SIZE'])
            break
        # GET or HEAD
        if data.startswith('GET /') or data.startswith('HEAD /'):
            try:
                if self.secure:
                    ld = ldap.initialize(self.config['URL_S'])
                    ld.simple_bind_s(self.config['USER'], self.config['PASS'])
                else:
                    ld = ldap.initialize(self.config['URL'])
                    ld.start_tls_s()
                    ld.simple_bind_s(self.config['USER'], self.config['PASS'])
                code = '200 OK'
                resp = 'OK'
            except ldap.LDAPError, e:
                code = '503 Service Unavailable'
                resp = e
                if config['DEBUG']:
                    print(e)
            self.send_response(code, resp)
        else:
            code = '400 Invalid Request'
            resp = 'Invalid Request'
            self.send_response(code, resp)


def socket_worker_process(config, secure=True):
    """Open a TCP socket and listen for incoming connections
    """
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            if secure:
                serversocket.bind((config['HOST'], config['PORT_S']))
            else:
                serversocket.bind((config['HOST'], config['PORT']))
        except Exception as exc:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            if config['DEBUG']:
                print('Exception: %s %s %s %s' % (exc, exc_type,
                                                  fname, exc_tb.tb_lineno))
        else:
            try:
                serversocket.listen(5)
            except Exception as exc:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                if config['DEBUG']:
                    print('Exception: %s %s %s %s' % (exc, exc_type,
                                                      fname, exc_tb.tb_lineno))
            while True:
                try:
                    conn, addr = serversocket.accept()
                    if config['INFO']:
                        print('Connection accepted: %s %s', conn, addr)
                    thread = ConnThread(conn, config, secure)
                    thread.start()
                except KeyboardInterrupt:
                    pass
                except Exception as exc:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    if config['DEBUG']:
                        print('Exception: %s %s %s %s' % (exc, exc_type,
                                                          fname, exc_tb.tb_lineno))
        try:
            sleep(1)
        except KeyboardInterrupt:
            pass
    return


if __name__ == '__main__':
    """main program
    """
    config = get_config(CONFIG_FILE)

    # a dictionary for saving processes info for debugging purposes
    process_list = {}

    # start ldap worker process
    ldap_worker = multiprocessing.Process(target=socket_worker_process, args=(config, False))
    ldap_worker.daemon = True
    ldap_worker.start()
    process_list['ldap_worker'] = ldap_worker
    print('Started process %s with pid %s' % ('ldap_worker', ldap_worker.pid))

    # start ldaps worker process
    ldaps_worker = multiprocessing.Process(target=socket_worker_process, args=(config,))
    ldaps_worker.daemon = True
    ldaps_worker.start()
    process_list['ldaps_worker'] = ldaps_worker
    print('Started process %s with pid %s' % ('ldaps_worker', ldaps_worker.pid))

    # define signals
    signal.signal(signal.SIGTERM, sig_term)
    signal.signal(signal.SIGINT, sig_term)
    signal.signal(signal.SIGHUP, sig_term)

    while True:
        try:
            signal.pause()
        except ExitDaemon:
            break
