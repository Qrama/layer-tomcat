import subprocess
import os
import charmhelpers.fetch.archiveurl as ch_archiveurl
from charmhelpers.core.templating import render
from charmhelpers.core import unitdata
from charms.reactive import when, when_not, set_state
from charmhelpers.core.hookenv import status_set, open_port, close_port, config
from jujubigdata import utils

# key value store that can be used across hooks
db = unitdata.kv()

@when('java.installed')
@when_not('layer-tomcat.installed')
def install_layer_tomcat():
    tomcat_dir = '/opt/tomcat'
    if not os.path.isdir(tomcat_dir):
        os.mkdir(tomcat_dir)

    if not os.path.isfile(tomcat_dir + '/apache-tomcat-9.0.0.M26'):
        fetcher = ch_archiveurl.ArchiveUrlFetchHandler()
        fetcher.download('http://www-eu.apache.org/dist/tomcat/tomcat-9/v9.0.0.M26/bin/apache-tomcat-9.0.0.M26.tar.gz',
        '/opt/tomcat/apache-tomcat-9.0.0.M26.tar.gz')

    if not os.path.isdir(tomcat_dir + '/apache-tomcat-9.0.0.M26'):
        subprocess.check_call(['tar', 'xvzf', '{}/apache-tomcat-9.0.0.M26.tar.gz'.format(tomcat_dir), '-C', tomcat_dir])

    with utils.environment_edit_in_place('/etc/environment') as env:
        env['CATALINA_HOME'] = '/opt/tomcat/apache-tomcat-9.0.0.M26'

    set_state('layer-tomcat.installed')

@when('layer-tomcat.installed')
@when_not('layer-tomcat.started')
def start_tomcat():
    http_port = config()["http-port"]
    subprocess.check_call(['/opt/tomcat/apache-tomcat-9.0.0.M26/bin/startup.sh'])
    open_port(int(http_port))
    db.set('http_port', http_port)
    set_state('layer-tomcat.started')
    status_set('active', 'Tomcat is running on port ' + config()["http-port"])

@when('http.available', 'layer-tomcat.started')
@when_not('layer-tomcat.http-configured')
def configure_http(http):
    http.configure(int(config()['http-port']))
    set_state('layer-tomcat.http-configured')

@when('layer-tomcat.started', 'config.changed')
def change_config():
    cur_http_port = db.get('http_port')
    new_http_port = config()['http-port']

    if not cur_http_port == new_http_port:
        context = {'http_port': new_http_port}
        render('server.xml', '/opt/tomcat/apache-tomcat-9.0.0.M26/conf/server.xml', context)
        close_port(int(cur_http_port))
        open_port(int(new_http_port))

    restart_tomcat()
    status_set('active', 'Tomcat is running on port ' + new_http_port)

def restart_tomcat():
    subprocess.check_call(['/opt/tomcat/apache-tomcat-9.0.0.M26/bin/shutdown.sh'])
    subprocess.check_call(['/opt/tomcat/apache-tomcat-9.0.0.M26/bin/startup.sh'])
