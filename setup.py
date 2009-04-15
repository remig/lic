from distutils.core import setup
import py2exe

# To build: python setup.py py2exe

py2exeOptions = dict(
                     compressed = True,
                     #skip_archive = True,  
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
      options = {'py2exe': py2exeOptions},
      )