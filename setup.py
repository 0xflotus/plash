from setuptools import setup

setup(name='plash',
      version='0.1.0',
      description='Try new Linux distros',
      url='http://github.com/ihucos/plash',
      author='Irae Hueck Costa',
      author_email='irae.hueck.costa@gmail.com',
      license='MIT',
      packages=['plash', 'plash.actions', 'plash.distros'],
      scripts=['bin/plash'],
      install_requires=[
            'PyYAML==3.12'
      ],
      include_package_data=True,
      zip_safe=True)
