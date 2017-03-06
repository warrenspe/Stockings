"""
    This file is part of Stockings.

    Stockings is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Stockings is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Stockings.  If not, see <http://www.gnu.org/licenses/>.


    Author: Warren Spencer
    Email:  warrenspencer27@gmail.com
"""

import distutils.core

VERSION = "1.2.3"
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
    packages=['Stockings', 'Stockings.utils', 'Stockings.exceptions'],
    license="https://www.gnu.org/licenses/gpl-3.0.html",
    platforms=["Linux", "Windows"]
)
