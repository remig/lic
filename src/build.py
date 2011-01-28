"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (Lic.py) is part of Lic.

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


def createSourceDist():

    import os
    import sys
    import pysvn
    import zipfile
        
    from Lic import __version__ as lic_version

    if sys.platform != 'win32':
        print "Must use win32 to create source distribution"
        return

    root = "C:/lic_dist"
    src = os.path.join(root, "src")
    svn_url = "http://lic.googlecode.com/svn/trunk"

    if os.path.isdir(root):
        print "Delete %s before proceeding" % root
        return

    print "Creating root"
    os.mkdir(root)
    
    print "Exporting source from SVN"
    client = pysvn.Client()
    client.export(svn_url, src)
    
    print "Renaming source folder"
    new_src = os.path.join(root, "lic_%s_src" % lic_version)
    os.rename(src, new_src)
    
    print "Zipping source folder"
    root_len = len(root) + 1
    z = zipfile.ZipFile(new_src + '.zip', 'w')
    for base, unused, files in os.walk(new_src):
        for f in files:
            fn = os.path.join(base, f)
            z.write(fn, fn[root_len:])
    z.close()
    
    print "Complete!"

if __name__ == '__main__':
    createSourceDist()
    

