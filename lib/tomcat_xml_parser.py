# pylint: disable=c0111,c0325
from lxml import etree
from charmhelpers.core.hookenv import charm_dir

class TomcatXmlParser:
    """Class for editing the xml config files of Tomcat."""

    def __init__(self, dir):
        self.dir = dir
        self.server_config = dir + '/conf/server.xml'

    def set_port(self, port):
        doc = etree.parse(self.server_config)
        service = doc.find('Service')
        connector = service.find('Connector')

        for connector in doc.xpath('//Connector[@protocol="HTTP/1.1"]'):
            connector.set('port', port)

        with open(self.server_config, 'wb') as config_file:
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

    def add_clustering(self):
        doc = etree.parse(self.server_config)

        for engine in doc.xpath("/Server/Service[@name='Catalina']/Engine[@name='Catalina']"):
            default_cluster_path = '{}/files/default-cluster.xml'.format(charm_dir())
            with open(default_cluster_path, 'r') as cluster_config:
                cluster_xml = cluster_config.read()
                cluster = etree.fromstring(cluster_xml)
                engine.insert(0, cluster)

        with open(self.server_config, 'wb') as config_file:
            doc.write(config_file, pretty_print=True)

    def remove_clustering(self):
        doc = etree.parse(self.server_config)

        for engine in doc.xpath("/Server/Service[@name='Catalina']/Engine[@name='Catalina']"):
            for cluster in engine.findall('Cluster'):
                engine.remove(cluster)

        with open(self.server_config, 'wb') as config_file:
            doc.write(config_file, pretty_print=True)
