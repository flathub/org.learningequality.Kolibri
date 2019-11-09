#!/usr/bin/make -f

export KOLIBRI_VERSION:=$(shell grep -ohE "kolibri-[0-9\.]+.tar.gz" org.learningequality.Kolibri.json | grep -ohE "[0-9]+\.[0-9]+\.[0-9]+")

configure:
	./build_patches.sh

build: configure
	flatpak-builder --user --repo=repo --install --force-clean build-dir org.learningequality.Kolibri.json

bundle: build
	flatpak build-bundle repo kolibri.flatpak org.learningequality.Kolibri

run:
	flatpak-builder --run build-dir org.learningequality.Kolibri.json run_kolibri.sh

open:
	flatpak-builder --run build-dir org.learningequality.Kolibri.json open_kolibri.sh

start:
	flatpak run org.learningequality.Kolibri

stop:
	flatpak kill org.learningequality.Kolibri

clean:
	rm -r .flatpak-builder
	rm -r build-dir

shell:
	flatpak run --command=bash --devel org.learningequality.Kolibri
