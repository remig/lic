from distutils.core import setup
import py2exe

setup(windows=[{'script':'Lic.py'}], 
      options={'py2exe':{'includes':['sip', 
                                     'OpenGL.platform.win32', 
                                     'OpenGL.arrays.lists',
                                     'OpenGL.arrays.ctypesarrays',
                                     ]}})