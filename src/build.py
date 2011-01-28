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

import os
import sys
import zipfile

from Lic import __version__ as lic_version

def createOSXDist():

    import shutil
    import subprocess

    if not sys.platform.startswith('darwin'):
        print "Must use OSX to create OSX distribution"
        return
  
    root = "/Users/remig/Code/pywork"
    src_root = os.path.join(root, 'lic/src/Lic.py')
    app_root = os.path.join(root, 'LicApp')
    pyinstaller_path = os.path.join(root, 'pyinstaller')
    spec_file = os.path.join(app_root, 'Lic.spec')

    if not os.path.isdir(pyinstaller_path):
        print "Could not find pyinstaller in %s" % pyinstaller_path
        return

    if os.path.isdir(app_root):
        print "Delete %s before proceeding" % app_root
        return

    print "Creating OSX Distribution"
    subprocess.call(['%s/Makespec.py' % pyinstaller_path, '--onefile', '--out=%s' % app_root, src_root])

    if not os.path.isfile(spec_file):
        print "Failed to create Spec file - something went horribly awry.  Good luck!"
        return

    f = open(spec_file, 'a')
    f.write("\n")
    f.write("import sys\n")
    f.write("if sys.platform.startswith('darwin'):\n")
    f.write("    app = BUNDLE(exe, appname='Lic', version='%s')\n" % lic_version)
    f.write("\n")
    f.close()

    subprocess.call(['%s/Build.py' % pyinstaller_path, spec_file])

    resources = app_root + '/MacLic.app/Contents/Resources'
    os.rmdir(resources)
    shutil.copytree('/Library/Frameworks/QtGui.framework/Resources', resources)

    inf_file = app_root + '/MacLic.app/Contents/Info.plist'
    fin = open(inf_file, 'r')
    fou = open(inf_file + '_new', 'w')

    nextLine = False
    for line in fin:
        line = line.replace('MacLic', 'Lic')
        if nextLine and line.count('1') > 0:
            line = line.replace('1', '0')
        nextLine = line.count('LSBackgroundOnly') > 0
        fou.write(line)
    fin.close()
    fou.close()

    os.rename(inf_file + '_new', inf_file)
    os.rename(app_root + '/MacLic.app', app_root + '/Lic.app')

    zipDir(root + '/lic_%s_osx.zip' % lic_version, app_root + '/Lic.app', len(app_root) + 1)

    print "Complete!"

def createSourceDist():

    import pysvn
        
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
    zipDir(new_src + '.zip', new_src, len(root) + 1)
    
    print "Complete!"

def zipDir(zip_file, zip_dir, root_len):
    z = zipfile.ZipFile(zip_file, 'w')
    for base, unused, files in os.walk(zip_dir):
        for f in files:
            fn = os.path.join(base, f)
            z.write(fn, fn[root_len:])
    z.close()

if __name__ == '__main__':
    if sys.platform.startswith('darwin'):
        createOSXDist()
    else:
        createSourceDist()
    

