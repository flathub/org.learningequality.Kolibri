
# build the patch to insert the search provider service
diff -u /dev/null patches/sources/gnome_search_provider_service.py > patches/gnome_search_provider_service.py.patch
sed -i -e "s/src/kolibri-${KOLIBRI_VERSION}\/kolibri\/core\/content\/management\/commands/" patches/gnome_search_provider_service.py.patch

# build the patch to insert the dbus activation service
diff -u /dev/null patches/sources/dbus_activation_service.py > patches/dbus_activation_service.py.patch
sed -i -e "s/src/kolibri-${KOLIBRI_VERSION}\/kolibri\/core\/content\/management\/commands/" patches/dbus_activation_service.py.patch