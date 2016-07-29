import distutils.core

VERSION = "1.0"
NAME = "Stockings"

distutils.core.setup(
    name=NAME,
    version=VERSION,
    description="A socket wrapper which provides the ability to send and receive complete messages.",
    author="Warren Spencer",
    author_email="warrenspencer27@gmail.com",
    url="https://github.com/warrenspe/%s" % NAME,
    download_url="https://github.com/warrenspe/%s/tarball/%s" % (NAME, VERSION),
    keywords=['socket', 'message', 'complete', 'wrapper'],
    classifiers=[],
    packages=['Stockings']
)
