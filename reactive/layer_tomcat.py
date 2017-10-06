# pylint: disable=c0111,c0325

import subprocess
import os

from charms.reactive import when, when_not, when_any, set_state, remove_state
from charmhelpers.core import unitdata
from charmhelpers.core.templating import render
from charmhelpers.core.hookenv import status_set, open_port, close_port, config, charm_dir
from charmhelpers.fetch.archiveurl import ArchiveUrlFetchHandler
from jujubigdata import utils
from tomcat_xml_parser import TomcatXmlParser

# key value store that can be used across hooks
DB = unitdata.kv()
TOMCAT_DIR = '/opt/apache-tomcat-9.0.1'

@when_not('layer-tomcat.downloaded')
def download_tomcat():
    status_set('maintenance', 'Downloading Tomcat...')
    if not os.path.isfile('/opt/apache-tomcat-9.0.1.tar.gz'):
        fetcher = ArchiveUrlFetchHandler()
        fetcher.download('https://archive.apache.org/dist/tomcat/tomcat-9/v9.0.1/bin/apache-tomcat-9.0.1.tar.gz', '/opt/apache-tomcat-9.0.1.tar.gz')

    if not os.path.isdir(TOMCAT_DIR):
        subprocess.check_call(['tar', 'xvzf', '/opt/apache-tomcat-9.0.1.tar.gz', '-C', '/opt'])

    set_state('layer-tomcat.downloaded')


@when('layer-tomcat.downloaded')
@when_not('layer-tomcat.configured')
def configure_tomcat():
    status_set('maintenance', 'Configuring Tomcat...')

    # set environment variable CATALINA_HOME
    with utils.environment_edit_in_place('/etc/environment') as env:
        env['CATALINA_HOME'] = TOMCAT_DIR

    # creates an admin user that has access to the manager-gui
    admin_username = config()["admin_username"]
    admin_password = config()["admin_password"]

    context = {'admin_username': admin_username,
               'admin_password': admin_password}
    render('tomcat-users.xml',
           TOMCAT_DIR + '/conf/tomcat-users.xml',
           context)

    # add values to key-value store so they can be used across hooks
    DB.set('admin_username', admin_username)
    DB.set('admin_password', admin_password)
    DB.set('manager_enabled', config()["manager_enabled"])
    DB.set('cluster_enabled', config()["cluster_enabled"])

    set_state('layer-tomcat.configured')


@when('layer-tomcat.configured')
@when_not('layer-tomcat.started')
def start_tomcat():
    status_set('maintenance', 'Starting Tomcat...')
    http_port = config()["http_port"]
    subprocess.check_call([TOMCAT_DIR + '/bin/startup.sh'])
    open_port(int(http_port))
    DB.set('http_port', http_port)

    set_state('layer-tomcat.started')
    status_set('active', 'Tomcat is running.')


# when a relation is made with another charm f.e. haproxy then http.available will trigger
@when('layer-tomcat.started', 'http.available')
@when_not('layer-tomcat.http-configured')
def configure_http(http):
    status_set('maintenance', 'Configuring http...')
    http.configure(int(config()['http_port']))
    set_state('layer-tomcat.http-configured')


@when('layer-tomcat.started', 'config.changed')
def change_config():
    conf = config()

    if conf.changed('http_port'):
        change_http_config()

    if conf.changed('admin_username') or conf.changed('admin_password'):
        change_admin_config()

    if conf.changed('manager_enabled'):
        change_manager_config()

    if conf.changed('cluster_enabled'):
        change_cluster_config()

    restart_tomcat()


def change_http_config():
    print("Changing port...")
    old_http_port = DB.get('http_port')
    new_http_port = config()['http_port']

    xml_parser = TomcatXmlParser(TOMCAT_DIR)
    xml_parser.set_port(new_http_port)

    close_port(int(old_http_port))
    open_port(int(new_http_port))

    DB.set('http_port', new_http_port)
    print("Changed port.")


def change_admin_config():
    print("Changing admin...")
    new_admin_name = config()['admin_username']
    new_admin_pass = config()['admin_password']

    context = {'admin_username': new_admin_name,
               'admin_password': new_admin_pass}
    render('tomcat-users.xml',
           TOMCAT_DIR + '/conf/tomcat-users.xml',
           context)

    DB.set('admin_username', new_admin_name)
    DB.set('admin_password', new_admin_pass)
    print("Changed admin.")


def change_manager_config():
    print("Changing manager...")
    new_manager_bool = config()['manager_enabled']

    xml_parser = TomcatXmlParser(TOMCAT_DIR)
    xml_parser.set_manager(new_manager_bool)

    DB.set('manager_enabled', new_manager_bool)
    print("Changed manager.")


def change_cluster_config():
    print("Changing cluster...")
    new_cluster_bool = config()['cluster_enabled']

    xml_parser = TomcatXmlParser(TOMCAT_DIR)
    xml_parser.set_manager(new_cluster_bool)

    DB.set('cluster_enabled', new_cluster_bool)
    print("Changed cluster.")


def restart_tomcat():
    print("Restarting Tomcat...")
    print("Shutting down...")
    subprocess.check_call([TOMCAT_DIR + '/bin/shutdown.sh'])
    print("Starting tomcat...")
    subprocess.check_call([TOMCAT_DIR + '/bin/startup.sh'])
    print("Tomcat has been restarted.")
