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

    with open(TOMCAT_DIR + "/bin/setenv.sh", "a+") as setenv:
        setenv.write('CATALINA_PID="$CATALINA_BASE/bin/catalina.pid"')


    # creates an admin user that has access to the manager-gui
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
    status_set('maintenance', 'Starting Tomcat...')
    http_port = config()["http_port"]
    print("First time starting Tomcat...")
    subprocess.check_call([TOMCAT_DIR + '/bin/startup.sh'])
    print("Opening HTTP port...")
    open_port(int(http_port))
    DB.set('http_port', http_port)

    set_state('layer-tomcat.started')
    status_set('active', 'Tomcat is running.')


# when a relation is made with another charm f.e. haproxy then haproxy.available will trigger
@when('layer-tomcat.started')
@when('haproxy.available')
@when_not('layer-tomcat.haproxy-configured')
def configure_haproxy(haproxy):
    haproxy.configure(int(config()['http_port']))
    set_state('layer-tomcat.haproxy-configured')


@when('layer-tomcat.started')
@when('config.changed')
def change_config():
    print("Changing config...")
    conf = config()
    #
    # if conf.changed('http_port'):
    #     change_http_config()
    #
    # if conf.changed('admin_username') or conf.changed('admin_password'):
    #     change_admin_config()
    #
    if conf.changed('manager_enabled'):
        change_manager_config()

    if conf.changed('cluster_enabled'):
        change_cluster_config()

    restart_tomcat()


@when('layer-tomcat.haproxy-configured')
@when('config.changed.http_port')
@when('haproxy.available')
def update_haproxy_relation(haproxy):
    new_http_port = config()['http_port']
    haproxy.configure(new_http_port)


@when('layer-tomcat.cluster-enabled')
@when_not('haproxy.available')
def missing_haproxy_notice():
    set_state('layer-tomcat.blocked-no-haproxy')
    status_set('blocked', 'Relation with HAProxy is required for clustering.')


@when('layer-tomcat.blocked-no-haproxy')
@when_not('layer-tomcat.cluster-enabled')
def unblock_cluster_disabled():
    remove_state('layer-tomcat.blocked-no-haproxy')
    status_set('active', 'Tomcat is running (not in cluster).')


@when('layer-tomcat.blocked-no-haproxy')
@when('layer-tomcat.cluster-enabled')
@when('haproxy.available')
def unblock_haproxy_available(haproxy):
    remove_state('layer-tomcat.blocked-no-haproxy')
    status_set('active', 'Tomcat is running (in cluster).')


def change_http_config():
    print("Changing HTTP config...")
    old_http_port = DB.get('http_port')
    new_http_port = config()['http_port']

    xml_parser = TomcatXmlParser(TOMCAT_DIR)
    xml_parser.set_port(new_http_port)

    close_port(int(old_http_port))
    open_port(int(new_http_port))
    DB.set('http_port', new_http_port)


def change_admin_config():
    print("Changing admin config...")
    new_admin_name = config()['admin_username']
    new_admin_pass = config()['admin_password']
    context = {'admin_username': new_admin_name,
               'admin_password': new_admin_pass}
    render('tomcat-users.xml',
           TOMCAT_DIR + '/conf/tomcat-users.xml',
           context)


def change_manager_config():
    print("Changing manager config...")
    new_manager_bool = config()['manager_enabled']
    xml_parser = TomcatXmlParser(TOMCAT_DIR)
    xml_parser.set_manager(new_manager_bool)


def change_cluster_config():
    print("Changing cluster config...")
    cluster_enabled = config()['cluster_enabled']
    xml_parser = TomcatXmlParser(TOMCAT_DIR)
    xml_parser.set_clustering_one_line(cluster_enabled)
    if cluster_enabled:
        set_state('layer-tomcat.cluster-enabled')
    else:
        remove_state('layer-tomcat.cluster-enabled')


def restart_tomcat():
    if is_tomcat_running():
        print("Shutting down...")
        subprocess.check_call([TOMCAT_DIR + '/bin/shutdown.sh'])
    print("Starting up...")
    subprocess.check_call([TOMCAT_DIR + '/bin/startup.sh'])

def is_tomcat_running():
    catalina_pid_path = TOMCAT_DIR + "/bin/catalina.pid"
    if os.path.isfile(catalina_pid_path):
        # Get the process id of the tomcat instance.
        with open(catalina_pid_path, 'r') as pid_file:
            pid = pid_file.readline()
            return psutil.pid_exists(int(pid))
    else:
        return False
