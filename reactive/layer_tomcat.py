import subprocess
import os
import charmhelpers.fetch.archiveurl as ch_archiveurl
from charms.reactive import when, when_not, set_state
from charmhelpers.core.hookenv import status_set, open_port
from jujubigdata import utils

@when('java.installed')
@when_not('layer-tomcat.installed')
def install_layer_tomcat():
    tomcat_dir = '/opt/tomcat'
    if not os.path.isdir(tomcat_dir):
        os.mkdir(tomcat_dir)

    fetcher = ch_archiveurl.ArchiveUrlFetchHandler()
    fetcher.download('http://www-eu.apache.org/dist/tomcat/tomcat-9/v9.0.0.M26/bin/apache-tomcat-9.0.0.M26.tar.gz',
    '/opt/tomcat/apache-tomcat-9.0.0.M26.tar.gz')

    subprocess.check_call(['tar', 'xvzf', '{}/apache-tomcat-9.0.0.M26.tar.gz'.format(tomcat_dir), '-C', tomcat_dir])

    with utils.environment_edit_in_place('/etc/environment') as env:
        env['CATALINA_HOME'] = '/opt/tomcat/apache-tomcat-9.0.0.M26'
    set_state('layer-tomcat.installed')

@when('layer-tomcat.installed')
@when_not('layer-tomcat.started')
def start_tomcat():
    open_port(8080)
    subprocess.call('/opt/tomcat/apache-tomcat-9.0.0.M26/bin/startup.sh', shell=True)
    set_state('layer-tomcat.started')
    status_set('active', 'Ready')