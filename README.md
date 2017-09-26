# Overview

Apache Tomcat, often referred to as Tomcat Server, is an open-source Java Servlet Container developed by the Apache Software Foundation (ASF). Tomcat implements several Java EE specifications including Java Servlet, JavaServer Pages (JSP), Java EL, and WebSocket, and provides a "pure Java" HTTP web server environment in which Java code can run.

Apache Tomcat version 9.0 implements the Servlet 4.0 and JavaServer Pages 2.3 specifications from the Java Community Process, and includes many additional features that make it a useful platform for developing and deploying web applications and web services.

http://tomcat.apache.org

# Usage

To deploy this Tomcat charm use:
  juju deploy tomcat

To make Tomcat publicly available use:
  juju expose tomcat

## Scale out Usage

If the charm has any recommendations for running at scale, outline them in
examples here. For example if you have a memcached relation that improves
performance, mention it here.

## Known Limitations and Issues

This not only helps users but gives people a place to start if they want to help
you add features to your charm.

# Configuration

The configuration options will be listed on the charm store, however If you're
making assumptions or opinionated decisions in the charm (like setting a default
administrator password), you should detail that here so the user knows how to
change it immediately, etc.

# Contact Information

Though this will be listed in the charm store itself don't assume a user will
know that, so include that information here:

## Upstream Project Name

  - Upstream website
  - Upstream bug tracker
  - Upstream mailing list or contact information
  - Feel free to add things if it's useful for users


[service]: http://example.com
[icon guidelines]: https://jujucharms.com/docs/stable/authors-charm-icon
