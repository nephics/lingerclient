from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()


setup(
    name='lingerclient',
    version='1.0.0',
    description="Blocking and non-blocking (asynchronous) clients for Linger",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Jacob Svensson',
    author_email='jacob@nephics.com',
    license="http://www.apache.org/licenses/LICENSE-2.0",
    url='https://github.com/nephics/lingerclient',
    packages=['lingerclient'],
    requires=['tornado(>=4.5.2)'],
    install_requires=['tornado>=4.5.2'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Topic :: System :: Distributed Computing',
        'Topic :: System :: Networking',
        'Topic :: Utilities'
    ]
)
