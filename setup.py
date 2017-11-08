from setuptools import setup

setup(
    name='lingerclient',
    version='0.2.2',
    description="Blocking and non-blocking (asynchronous) clients for Linger",
    author='Jacob Svensson',
    author_email='jacob@nephics.com',
    license="http://www.apache.org/licenses/LICENSE-2.0",
    url='https://github.com/nephics/lingerclient',
    packages=['lingerclient'],
    requires=['tornado(>=4.5.2)'],
    install_requires=['tornado>=4.5.2'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Topic :: System :: Distributed Computing',
        'Topic :: System :: Networking'
    ]
)
