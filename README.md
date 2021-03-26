# Flatpak packaging for kolibri-installer-gnome

This package contains [Kolibri](https://learningequality.org/kolibri/) as well
as a GNOME front-end.

## Building

To build and install this package on your system, use flatpak-builder:

    flatpak-builder build-dir org.learningequality.Kolibri.yaml --install --user

Once it is installed, you can run Kolibri:

    flatpak run org.learningequality.Kolibri

Note that the Kolibri flatpak will use a different data directory than if it was
running on the host system. Instead of being located in ~/.kolibri, Kolibri's
database files will be stored in the Flatpak application's data directory, such
as `~/.var/app/org.learningequality.Kolibri/data/kolibri`. This can be changed
as usual by setting the `KOLIBRI_HOME` environment variable.

## Running Kolibri management commands

You can use the `kolibri` command inside the flatpak to run management commands. For example:

    flatpak run --command=kolibri org.learningequality.Kolibri manage listchannels

For information about Kolibri's management commands, please see <https://kolibri.readthedocs.io/en/latest/manage/command_line.html>.

## Adding desktop launchers for Kolibri channels

Kolibri generates desktop launchers as convenient shortcuts to specific channels you have installed. If you would like for these launchers to appear on your desktop, add `$HOME/.var/app/org.learningequality.Kolibri/data/kolibri/content/xdg/share` to your `XDG_DATA_DIRS`.

To achieve this for all users, create a file named `/usr/lib/systemd/user-environment-generators/61-kolibri-app-desktop-xdg-plugin` with the following contents, then log out and log in again:

    #!/bin/bash
    XDG_DATA_DIRS="$HOME/.var/app/org.learningequality.Kolibri/data/kolibri/content/xdg/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
    echo "XDG_DATA_DIRS=$XDG_DATA_DIRS"
