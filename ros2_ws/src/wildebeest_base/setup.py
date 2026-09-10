from glob import glob
from setuptools import find_packages, setup


package_name = 'wildebeest_base'


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools', 'pyserial'],
    zip_safe=True,
    maintainer='Wildebeest Pro maintainers',
    maintainer_email='maintainers@wildebeest-pro.org',
    description='Failsafe serial and mock base controller for Wildebeest Pro.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'serial_bridge = wildebeest_base.serial_bridge_node:main',
        ],
    },
)
