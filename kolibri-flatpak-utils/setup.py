from setuptools import setup, find_packages

setup(
    name="kolibri-flatpak-utils",
    packages=["kolibri_flatpak"],
    package_dir={"kolibri_flatpak": ""},
    entry_points={
        "console_scripts": ["kolibri = kolibri_flatpak.kolibri_wrapper:main"]
    },
    python_requires=">=3.4",
    install_requires=["kolibri>=0.13.2"],
)
