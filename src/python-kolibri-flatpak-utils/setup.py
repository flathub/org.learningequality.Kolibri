from setuptools import setup, find_packages

setup(
    name="kolibri-flatpak-utils",
    packages=['kolibri_flatpak'],
    package_dir={'kolibri_flatpak': ''},
    entry_points={
        'console_scripts': [
            'run_kolibri = kolibri_flatpak.run_kolibri:main'
        ]
    },
    python_requires='>=3.4',
    install_requires=[
        'kolibri>=0.13.0'
    ]
)
