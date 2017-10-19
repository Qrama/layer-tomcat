# Overview

Apache Tomcat, often referred to as Tomcat Server, is an open-source Java Servlet Container developed by the Apache Software Foundation (ASF). Tomcat implements several Java EE specifications including Java Servlet, JavaServer Pages (JSP), Java EL, and WebSocket, and provides a "pure Java" HTTP web server environment in which Java code can run.

Apache Tomcat version 9.0 implements the Servlet 4.0 and JavaServer Pages 2.3 specifications from the Java Community Process, and includes many additional features that make it a useful platform for developing and deploying web applications and web services.

http://tomcat.apache.org

# Usage

Deploy the Tomcat charm:
```sh
juju deploy tomcat
```
Make Tomcat publicly available:
```sh
juju expose tomcat
```
Browse to the public IP with port to start using Tomcat. For example: "http://35.195.173.22:8080".

## Scale out Usage

Checklist for scaling Tomcat:
- Make sure you enable clustering in the configuration by clicking the **cluster_enabled** option.
- Add **<distributable/>** to **web.xml** of every webapp that needs session replication. The session state gets transferred for each web application that has distributable in its web.xml. The file can be found in the WEB-INF folder. For example: /opt/apache-tomcat-9.0.1/webapps/manager/WEB-INF/web.xml.
- A relation with [HAProxy] is required to make clustering work. If you decide to use a load balancer like HAProxy make sure you unexpose Tomcat and expose the load balancer for security reasons.

# Known Limitations and Issues

- At the moment clustering only works when your cloud provider enables multicasting.

# Contact Information

- [Tomcat Homepage]
- [Tomcat Clustering Documentation]

[service]: http://example.com
[icon guidelines]: https://jujucharms.com/docs/stable/authors-charm-icon
[haproxy]: <https://jujucharms.com/haproxy/41>
[tomcat homepage]: http://tomcat.apache.org/
[tomcat clustering documentation]: https://tomcat.apache.org/tomcat-9.0-doc/cluster-howto.html
