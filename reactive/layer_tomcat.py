# pylint: disable=c0111,c0325

import subprocess
import os
import psutil

from charms.reactive import when, when_not, when_any, set_state, remove_state
from charmhelpers.core import unitdata
from charmhelpers.core.templating import render
from charmhelpers.core.hookenv import status_set, open_port, close_port, config, charm_dir
from charmhelpers.fetch.archiveurl import ArchiveUrlFetchHandler
from jujubigdata import utils
from tomcat_xml_parser import TomcatXmlParser

# Key value store that can be used across hooks.
DB = unitdata.kv()
# Tomcat's installation directory.
TOMCAT_DIR = '/opt/apache-tomcat-9.0.1'

@when_not('layer-tomcat.downloaded')
def download_tomcat():
    '''Downloads Tomcat from Apache archive and extracts the tarball.'''
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
    '''Configures Tomcat by setting environment variable and adding a user.'''
    status_set('maintenance', 'Configuring Tomcat...')

    # Set environment variable CATALINA_HOME.
    with utils.environment_edit_in_place('/etc/environment') as env:
        env['CATALINA_HOME'] = TOMCAT_DIR

    # Create a file where the process id of Tomcat can be stored. This makes
    # it possible to check if Tomcat is running.
    with open(TOMCAT_DIR + "/bin/setenv.sh", "a+") as setenv:
        setenv.write('CATALINA_PID="$CATALINA_BASE/bin/catalina.pid"')


    # Creates an admin user that has access to the manager-gui.
    admin_username = config()["admin_username"]
    admin_password = config()["admin_password"]

    context = {'admin_username': admin_username,
               'admin_password': admin_password}
    render('tomcat-users.xml',
           TOMCAT_DIR + '/conf/tomcat-users.xml',
           context)

    set_state('layer-tomcat.configured')


@when('layer-tomcat.configured')
@when_not('layer-tomcat.started')
def start_tomcat():
    '''Starts a Tomcat instance.'''
    status_set('maintenance', 'Starting Tomcat...')
    http_port = config()["http_port"]

    print("First time starting Tomcat...")
    subprocess.check_call([TOMCAT_DIR + '/bin/startup.sh'])

    print("Opening HTTP port...")
    # Open the port from the config file (default 8080) so Tomcat can
    # be accessed after it is exposed.
    open_port(int(http_port))
    DB.set('http_port', http_port)

    set_state('layer-tomcat.started')
    status_set('active', 'Tomcat is running.')


# When a relation is made with another charm using the http interface
# f.e. haproxy then haproxy.available will trigger.
@when('layer-tomcat.started')
@when('haproxy.available')
@when_not('layer-tomcat.haproxy-configured')
def configure_haproxy(haproxy):
    '''Configure the http relation to point to the port of Tomcat.'''
    haproxy.configure(int(config()['http_port']))
    set_state('layer-tomcat.haproxy-configured')


@when('layer-tomcat.started')
@when('config.changed')
def change_config():
    '''When something changes in the config file then this method will trigger'''
    print("Changing config...")
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


@when('layer-tomcat.haproxy-configured')
@when('config.changed.http_port')
@when('haproxy.available')
def update_haproxy_relation(haproxy):
    '''When Tomcat it's port is changed then the port of the relation
    must also be updated to Tomcat's new port.'''
    new_http_port = config()['http_port']
    haproxy.configure(new_http_port)


@when('layer-tomcat.cluster-enabled')
@when_not('haproxy.available')
def missing_haproxy_notice():
    '''When the user enables cluster mode but there is no relation
    then the state will be put on blocked.'''
    set_state('layer-tomcat.blocked-no-haproxy')
    status_set('blocked', 'Relation with HAProxy is required for clustering.')


@when('layer-tomcat.blocked-no-haproxy')
@when_not('layer-tomcat.cluster-enabled')
def unblock_cluster_disabled():
    '''If the user disables cluster mode when the state was blocked due to
    a missing relation the state will become active again.'''
    remove_state('layer-tomcat.blocked-no-haproxy')
    status_set('active', 'Tomcat is running (not in cluster).')


@when('layer-tomcat.blocked-no-haproxy')
@when('layer-tomcat.cluster-enabled')
@when('haproxy.available')
def unblock_haproxy_available(haproxy):
    '''If the user adds an http relation (preferably one with haproxy) when the
    state was blocked then the state will become active again.'''
    remove_state('layer-tomcat.blocked-no-haproxy')
    status_set('active', 'Tomcat is running (in cluster).')


def change_http_config():
    '''Changes Tomcat's HTTP configuration.'''
    print("Changing HTTP config...")
    old_http_port = DB.get('http_port')
    new_http_port = config()['http_port']

    xml_parser = TomcatXmlParser(TOMCAT_DIR)
    xml_parser.set_port(new_http_port)

    # It is necessary to close the previous port for security reasons.
    close_port(int(old_http_port))
    open_port(int(new_http_port))
    DB.set('http_port', new_http_port)


def change_admin_config():
    '''Changes Tomcat's admin configuration.'''
    print("Changing admin config...")
    new_admin_name = config()['admin_username']
    new_admin_pass = config()['admin_password']

    # Here we use render instead of the TomcatXmlParser because tomcat-users.xml
    # is a small file compared to server.xml and that's easier to edit with
    # render. Feel free to use TomcatXmlParser instead of render.
    context = {'admin_username': new_admin_name,
               'admin_password': new_admin_pass}
    render('tomcat-users.xml',
           TOMCAT_DIR + '/conf/tomcat-users.xml',
           context)


def change_manager_config():
    '''Changes Tomcat's manager GUI configuration.'''
    print("Changing manager config...")
    new_manager_bool = config()['manager_enabled']
    xml_parser = TomcatXmlParser(TOMCAT_DIR)
    xml_parser.set_manager(new_manager_bool)


def change_cluster_config():
    '''Changes Tomcat's clustering configuration.'''
    print("Changing cluster config...")
    cluster_enabled = config()['cluster_enabled']
    xml_parser = TomcatXmlParser(TOMCAT_DIR)
    xml_parser.set_clustering_one_line(cluster_enabled)

    if cluster_enabled:
        set_state('layer-tomcat.cluster-enabled')
    else:
        remove_state('layer-tomcat.cluster-enabled')


def restart_tomcat():
    '''Restarts the Tomcat instance.'''
    # Only shutdown an instance if it is already running or else it will trip.
    # "How do you kill that which has no life?"
    if is_tomcat_running():
        print("Shutting down...")
        subprocess.check_call([TOMCAT_DIR + '/bin/shutdown.sh'])
    print("Starting up...")
    subprocess.check_call([TOMCAT_DIR + '/bin/startup.sh'])


def is_tomcat_running():
    '''If the process id from the file exists then Tomcat is running.'''
    catalina_pid_path = TOMCAT_DIR + "/bin/catalina.pid"
    if os.path.isfile(catalina_pid_path):
        # Get the process id of the tomcat instance.
        with open(catalina_pid_path, 'r') as pid_file:
            pid = pid_file.readline()
            return psutil.pid_exists(int(pid))
    else:
        return False
