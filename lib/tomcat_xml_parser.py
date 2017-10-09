# pylint: disable=c0111,c0325
from lxml import etree
from charmhelpers.core.hookenv import charm_dir

class TomcatXmlParser:
    """Class for editing the xml config files of Tomcat."""

    def __init__(self, dir):
        self.dir = dir

    def set_port(self, port):
        doc = etree.parse(self.dir + '/conf/server.xml')
        service = doc.find('Service')
        connector = service.find('Connector')
        # edit the port of the first connector
        connector.set('port', port)

        with open(self.dir  + '/conf/server.xml', 'wb') as config_file:
            doc.write(config_file, pretty_print=True)

    def set_manager(self, manager_enabled):
        doc = etree.parse(self.dir + '/webapps/manager/META-INF/context.xml')
        valve = doc.find('Valve')

        if manager_enabled:
            valve.set('allow', '.*')
        else:
            valve.set('allow', '127\.\d+\.\d+\.\d+|::1|0:0:0:0:0:0:0:1')

        with open(self.dir + '/webapps/manager/META-INF/context.xml', 'wb') as new:
            doc.write(new, pretty_print=True)

    def set_clustering(self, cluster_enabled):
        doc = etree.parse(self.dir + '/conf/server.xml')
        service = doc.find('Service')
        engine = service.find('Engine')

        # if user wants clustering add default-cluster-config to server.xml
        if cluster_enabled:
            default_cluster_path = '{}/files/default-cluster.xml'.format(charm_dir())
            with open(default_cluster_path, 'r') as cluster_config:
                cluster_string = cluster_config.read()
                cluster = etree.fromstring(cluster_string)
                engine.insert(0, cluster)

            with open(self.dir + '/conf/server.xml', 'wb') as config_file:
                doc.write(config_file, pretty_print=True)
        else:
            cluster = engine.find('Cluster')

            if cluster is not None:
                engine.remove(cluster)
                with open(self.dir + '/conf/server.xml', 'wb') as config_file:
                    doc.write(config_file, pretty_print=True)
