"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (build.py) is part of Lic.

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

# A fundamental difference in packaging on win32 vs. osx: this win32 script will
# export the code to build from SVN.  osx script will only build the code in
# the currently checked out project.  This is because pysvn doesn't yet work
# correctly on osx.  Boo.
  
import os
import sys
import zipfile
import subprocess

def perr(s):
    print s

def zipDir(zip_file, zip_dir, root_len):
    z = zipfile.ZipFile(zip_file, 'w')
    for base, unused, files in os.walk(zip_dir):
        for f in files:
            fn = os.path.join(base, f)
            z.write(fn, fn[root_len:])
    z.close()

def createOSXDist():

    import shutil
    from Lic import __version__ as lic_version
    from Lic import _debug as lic_debug

    if lic_debug and raw_input('Trying to build from DEBUG!!  Proceed? y/n: ').lower() != 'y':
        return
    
    if not sys.platform.startswith('darwin'):
        return perr("Must use OSX to create OSX distribution")
  
    root = "/Users/remig/Code/pywork"
    pyinstaller_path = os.path.join(root, 'pyinstaller')
    src_root = os.path.join(root, 'lic', 'src', 'Lic.py')
    app_root = os.path.join(root, 'LicApp')
    lic_root = os.path.join(app_root, 'Lic.app')
    mac_root = os.path.join(app_root, 'MacLic.app')
    spec_file = os.path.join(app_root, 'Lic.spec')

    if not os.path.isdir(pyinstaller_path):
        return perr("Could not find pyinstaller in %s" % pyinstaller_path)

    if os.path.isdir(app_root):
        return perr("Delete %s before proceeding" % app_root)

    print "Creating OSX Distribution"
    subprocess.call(['%s/Makespec.py' % pyinstaller_path, '--onefile', '--out=%s' % app_root, src_root])

    if not os.path.isfile(spec_file):
        return perr("Failed to create Spec file - something went horribly awry.  Good luck!")

    f = open(spec_file, 'a')
    f.write("\n")
    f.write("import sys\n")
    f.write("if sys.platform.startswith('darwin'):\n")
    f.write("    app = BUNDLE(exe, appname='Lic', version='%s')\n" % lic_version)
    f.write("\n")
    f.close()

    subprocess.call(['%s/Build.py' % pyinstaller_path, spec_file])

    resources = os.path.join(mac_root, 'Contents', 'Resources')
    os.rmdir(resources)
    shutil.copytree('/Library/Frameworks/QtGui.framework/Resources', resources)

    inf_file = os.path.join(mac_root, 'Contents', 'Info.plist')
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
    os.rename(mac_root, lic_root)

    zipName = root + '/lic_%s_osx.zip' % lic_version
    zipDir(zipName, lic_root, len(app_root) + 1)

    print "OSX Distribution created: %s" % zipName

def createSvnExport(root):

    if sys.platform != 'win32':
        return perr("Must use win32 to create source distribution")

    if os.path.isdir(root):
        return perr("Delete %s root folder before proceeding" % root)

    import pysvn

    src_root = os.path.join(root, "lic_src")
    svn_url = "http://lic.googlecode.com/svn/trunk"

    print "Creating %s root" % root
    os.mkdir(root)
    
    print "Exporting source from SVN"
    client = pysvn.Client()
    client.export(svn_url, src_root)
    
    print "Renaming source folder"
    sys.path[0] = os.path.join(src_root, 'src')
    from Lic import __version__ as lic_version, _debug as lic_debug

    new_src_root = os.path.join(root, "lic_%s_src" % lic_version)
    os.rename(src_root, new_src_root)

    return new_src_root, lic_version, lic_debug
    
def createSourceDist(root, src_root):

    if sys.platform != 'win32':
        return perr("Must use win32 to create source distribution")

    if not os.path.isdir(src_root):
        return perr("Source root %s does not exist!! Failed to create Source Distribution." % src_root)

    print "Zipping source folder"
    zipName = src_root + '.zip'
    zipDir(zipName, src_root, len(root) + 1)
    
    print "Source Distribution created: %s" % zipName
    
def createWin32Dist(root, src_root, lic_version):

    if sys.platform != 'win32':
        return perr("Must use win32 to create win32 distribution")

    if not os.path.isdir(src_root):
        return perr("Source root %s does not exist!! Failed to create Win32 Distribution." % src_root)

    pyinstaller_path = r"C:\Python26\Lib\site-packages\pyinstaller"
    if not os.path.isdir(pyinstaller_path):
        return perr("Could not find pyinstaller in %s" % pyinstaller_path)

    build_root = os.path.join(root, 'lic_%s_pyinst' % lic_version)
    spec_file = os.path.join(build_root, 'Lic.spec')

    #Makespec.py --windowed --icon="C:\lic\images\lic_logo.ico" --out="C:\lic\tmp" C:\lic_dist\lic_0.50_src\src\Lic.py
    print "Creating Win32 Spec file"
    args = ['python',
            os.path.join(pyinstaller_path, 'Makespec.py'),
            '--windowed',
            '--icon=%s' % os.path.join(src_root,'images', 'lic_logo.ico'),
            '--onefile',
            '--out=%s' % build_root,
            '%s' % os.path.join(src_root, 'src', 'Lic.py')]
    subprocess.call(' '.join(args))

    if not os.path.isfile(spec_file):
        return perr("Failed to create Spec file - something went horribly awry.  Good luck!")

    # This is no longer necessary - default_template is compiled into the resource bundle 
#    print "Updating Spec file so it includes extra necessary data files"
#    fin = open(spec_file, 'r')
#    fou = open(spec_file + '_new', 'w')
#
#    for line in fin:
#        fou.write(line)
#        if line.count('a.binaries') > 0:
#            fou.write('               [("default_template.lit", r"%s", "DATA")],\n' % os.path.join(src_root, 'src', 'default_template.lit'))
#    fin.close()
#    fou.close()
#    os.remove(spec_file)
#    os.rename(spec_file + '_new', spec_file)

    print "Creating Win32 Binary Distribution"
    subprocess.call('python %s %s' % (os.path.join(pyinstaller_path, 'Build.py'), spec_file))

    print "Renaming dist/Lic folder"
    dist_root = os.path.join(build_root, "dist")
    new_root = os.path.join(build_root, "lic_%s_win32" % lic_version)
    os.rename(dist_root, new_root)
    os.rename(os.path.join(new_root, 'Lic.exe'), os.path.join(new_root, 'Lic_%s.exe') % lic_version)

    print "Creating final win32 zip"
    zipName = os.path.join(root, 'lic_%s_win32.zip' % lic_version)
    zipDir(zipName, new_root, len(build_root) + 1)

    print "Win32 Distribution created: %s" % zipName

def main():

    if sys.platform.startswith('darwin'):
        createOSXDist()

    elif sys.platform.startswith('win32'):
        
        root = "C:\\lic_dist"
        res = createSvnExport(root)
        if res is None:
            return

        src_root, lic_version, lic_debug = res

        if lic_debug and raw_input('Trying to build from DEBUG!!  Proceed? y/n: ').lower() != 'y':
            return
    
        createSourceDist(root, src_root)
        createWin32Dist(root, src_root, lic_version)

    else:
        return perr("Cannot run build script on %s" % sys.platform)

if __name__ == '__main__':
    main()
