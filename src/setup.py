"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (setup.py) is part of Lic.

    Lic is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Lic is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/
"""

from distutils.core import setup
import py2exe

"""
Create a win32 binary re-distributable package.  This creates a handful of
folders (build, dist, etc) in the src folder.  Everything in dist can then be 
zipped & distributed.  In there will be Lic.exe, a tiny executable that 
simply invokes the (bundled) python interpreter with Lic.py.
"""

# To build: cd c:\lic\src  c:\python25\python.exe setup.py py2exe

py2exeOptions = dict(
                     compressed = True,
                     #skip_archive = True,
                     packages = ['LicImporters'],
                     excludes = ['doctest', 'difflib', 'pdb', 'unittest', 'inspect', '_ssl'],
                     includes = ['sip', 'OpenGL.platform.win32', 'OpenGL.arrays.lists', 'OpenGL.arrays.ctypesarrays'],
                     )

setup(name = 'Lic',
      version = '0.5',
      description = 'Lego Instruction Creator',
      url = 'http://bugeyedmonkeys.com/lic',
      license = 'GNU General Public License (GPL)',
      author = 'Remi Gagne',
      windows = [{'script':'Lic.py'}], 
      data_files = [('', ['c:\lic\dynamic_template.lit'])],
      options = {'py2exe': py2exeOptions},
      )
