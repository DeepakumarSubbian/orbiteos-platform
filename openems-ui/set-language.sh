#!/bin/sh
# Force English language in OpenEMS UI
sed -i 's|<app-root>|<script>localStorage.setItem("GLOBAL_language","en");</script><app-root>|' /var/www/html/openems/index.html
