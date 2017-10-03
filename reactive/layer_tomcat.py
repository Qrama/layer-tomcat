# pylint: disable=c0111,c0325

import subprocess
import os
import charmhelpers.fetch.archiveurl as ch_archiveurl
from charmhelpers.core.templating import render
from charmhelpers.core import unitdata
from charms.reactive import when, when_not, set_state, remove_state
from charmhelpers.core.hookenv import status_set, open_port, close_port, config, charm_dir
from jujubigdata import utils
from lxml import etree

# key value store that can be used across hooks
DB = unitdata.kv()
TOMCAT_DIR = '/opt/apache-tomcat-9.0.1'

#@when('apt.installed.openjdk-8-jre-headless')
@when_not('layer-tomcat.downloaded')
def download_tomcat():
    status_set('maintenance', 'downloading...')

    if not os.path.isfile('/opt/apache-tomcat-9.0.1.tar.gz'):
        fetcher = ch_archiveurl.ArchiveUrlFetchHandler()
        fetcher.download('https://archive.apache.org/dist/tomcat/tomcat-9/v9.0.1/bin/apache-tomcat-9.0.1.tar.gz', '/opt/apache-tomcat-9.0.1.tar.gz')

    if not os.path.isdir(TOMCAT_DIR):
        subprocess.check_call(['tar', 'xvzf', '{}/apache-tomcat-9.0.1.tar.gz'.format('/opt'), '-C', '/opt'])

    set_state('layer-tomcat.downloaded')
    status_set('maintenance', 'downloaded')


@when('layer-tomcat.downloaded')
@when_not('layer-tomcat.configured')
def configure_tomcat():
    status_set('maintenance', 'configuring...')

    # set environment variable CATALINA_HOME
    with utils.environment_edit_in_place('/etc/environment') as env:
        env['CATALINA_HOME'] = TOMCAT_DIR

    # creates an admin user that has access to the manager-gui
    admin_username = config()["admin-username"]
    admin_password = config()["admin-password"]

    context = {'admin_username': admin_username,
               'admin_password': admin_password}
    render('tomcat-users.xml',
           TOMCAT_DIR + '/conf/tomcat-users.xml',
           context)

    # add values to key-value store so they can be used across hooks
    DB.set('admin_username', admin_username)
    DB.set('admin_password', admin_password)
    DB.set('manager_enabled', config()["manager-enabled"])
    DB.set('cluster_enabled', config()["cluster-enabled"])

    set_state('layer-tomcat.configured')
    status_set('maintenance', 'configured')


@when('layer-tomcat.configured')
@when_not('layer-tomcat.started')
def start_tomcat():
    status_set('maintenance', 'starting...')

    http_port = config()["http-port"]
    subprocess.check_call([TOMCAT_DIR + '/bin/startup.sh'])
    open_port(int(http_port))
    DB.set('http_port', http_port)

    set_state('layer-tomcat.started')
    status_set('active', 'running on port ' + http_port)


@when('layer-tomcat.started', 'layer-tomcat.restarting')
def stop_tomcat():
    status_set('maintenance', 'restarting...')
    subprocess.check_call([TOMCAT_DIR + '/bin/shutdown.sh'])
    remove_state('layer-tomcat.restarting')
    remove_state('layer-tomcat.started')


# when a relation is made with another charm f.e. haproxy then http.available will trigger
@when('layer-tomcat.started', 'http.available')
@when_not('layer-tomcat.http-configured')
def configure_http(http):
    print("Configuring http...")
    http.configure(int(config()['http-port']))
    set_state('layer-tomcat.http-configured')


# when tomcat is started and config has changed but no http-relation
@when('layer-tomcat.started', 'config.changed')
def change_config1():
    update_config()


# when tomcat is started and config has changed and has a http relation
@when('layer-tomcat.http-configured', 'http.available', 'config.changed')
def change_config2(http):
    update_config(http)


def update_config(http=None):
    print("Changing config...")
    # if a config changes change this to true
    config_changed = False

    cur_http_port = DB.get('http_port')
    new_http_port = config()['http-port']
    cur_manager_bool = DB.get('manager_enabled')
    new_manager_bool = config()['manager-enabled']
    cur_cluster_bool = DB.get('cluster_enabled')
    new_cluster_bool = config()['cluster-enabled']

    # check if the http-port config has been changed
    if not cur_http_port == new_http_port:
        print("Port has been changed, updating...")
        config_changed = True

        context = {'http_port': new_http_port}
        render('server.xml',
               TOMCAT_DIR + '/conf/server.xml',
               context)

        close_port(int(cur_http_port))
        open_port(int(new_http_port))
        # http-interface must also use new port
        if http is not None:
            http.configure(new_http_port)
        DB.set('http_port', new_http_port)
        status_set('active', 'Tomcat is running on port ' + new_http_port)

    # check if the manager-enabled config has been changed
    if not cur_manager_bool == new_manager_bool:
        print("Manager option has been changed, updating...")
        config_changed = True
        context = ""

        if new_manager_bool is True:
            context = {'manager_enabled': ".*"} # TODO: better regex for IP addresses
        else:
            context = {'manager_enabled': "127\.\d+\.\d+\.\d+|::1|0:0:0:0:0:0:0:1"}

        render('manager-context.xml',
               TOMCAT_DIR + '/webapps/manager/META-INF/context.xml',
               context)

        DB.set('manager_enabled', new_manager_bool)

    # check if the cluster-enabled config has been changed
    if not cur_cluster_bool == new_cluster_bool:
        print("Cluster option has been changed, updating...")
        config_changed = True
        edit_xml_clustering(new_cluster_bool)
        DB.set('cluster_enabled', new_cluster_bool)

    if config_changed is True:
        #restart_tomcat()
        set_state('layer-tomcat.restarting')
    else:
        print("Nothing has changed.")


def edit_xml_clustering(cluster_enabled):
    doc = etree.parse(TOMCAT_DIR + '/conf/server.xml')
    service = doc.find('Service')
    engine = service.find('Engine')

    # if user wants clustering add default-cluster-config to server.xml
    if cluster_enabled:
        default_cluster_path = '{}/files/default-cluster.xml'.format(charm_dir())
        with open(default_cluster_path, 'r') as cluster_config:

            cluster_string = cluster_config.read()
            cluster = etree.fromstring(cluster_string)
            engine.insert(0, cluster)

        with open(TOMCAT_DIR + '/conf/server.xml', 'wb') as config_file:
            doc.write(config_file, pretty_print=True)
    else:
        cluster = engine.find('Cluster')

        if cluster is not None:
            engine.remove(cluster)
            with open(TOMCAT_DIR + '/conf/server.xml', 'wb') as config_file:
                doc.write(config_file, pretty_print=True)
