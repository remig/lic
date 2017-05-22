"""
    LIC - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne
    Copyright (C) 2015 Jeremy Czajkowski

    This file (LicPovrayWrapper.py) is part of LIC.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
   
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
   
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os  # For process creation

import LicHelpers  # For access to writeLogEntry 
import config  # For pov-ray path


def boolToCommand(command, state):
    if state:
        return command
    return ''

def isExists():
    return os.path.exists(config.POVRayPath)
    
def __getDefaultCommand():
    return dict({
        'width': 512,
        'height': 512,
        'render': False,
        'no restore': True,
        'jitter' : False,
        'anti-alias' : True,
        'alpha' : True,
        'quality' : 3,
        'output type' : 'N',
        'exit' : True,
    })

povCommands = {
    'inFile' : ['+I', str],
    'outFile' : ['+O', str],
    
    'output type' : ['+F', str],  # Either N (png) or S (system - BMP on win32)
    'width' : ['+W', str],  # int - image width in pixels
    'height' : ['+H', str],  # int - image height in pixels
    
    'render' : ['', lambda b: boolToCommand('/RENDER', b)],  # Boolean - Render the specified scene (useless with inFile specified)
    'no restore' : ['', lambda b: boolToCommand('/NR', b)],  # Boolean - Do not open any previous files 
    'exit' : ['', lambda b: boolToCommand('/EXIT', b)],  # Boolean - Close this pov-ray instance after rendering
    
    'display' : ['Display=', str],  # Boolean - Turns graphic display preview on/off
    'verbose' : ['Verbose=', str],  # Boolean - Turns verbose messages on/off
    'alpha'   : ['Output_Alpha=', str],  # Boolean - Turns alpha channel on/off
    'anti-alias' : ['Antialias=', str],  # Boolean - Turns anti-aliasing on/off
    'jitter'  : ['Jitter=', str],  # Boolean - Turns aa-jitter on/off

    'quality' : ['+Q', str],  # Render quality - integer from (0 <= n <= 11)
    
    'include' : ['+HI', str],  # Include any extra files - specify full filename
}


def __runCommand(d):
    LogFile= open(os.path.join(config.appDataPath(),"activity.log"),"a")
    POVRayApp = config.POVRayPath
    if not os.path.isfile(POVRayApp):
        error_message = "Error: Could not find Pov-Ray in %s - aborting image generation" % os.path.dirname(POVRayApp)
        LicHelpers.writeLogEntry(error_message)
        print error_message
        return

    args = ['"' + POVRayApp + '"']
    for key, value in d.items():
        command = povCommands[key]
        if command:
            args.append(command[0] + command[1](value))
        else:
            if key == 'inFile':
                args.insert(1, value)  # Ensure input file is first command (after pvengine.exe itself)
            else:
                args.append(value)
                
    if config.writePOVRayActivity:                
        LogFile.write(" ".join(args)+"\n")
    LogFile.close()
                
    os.spawnv(os.P_WAIT, POVRayApp, args)
    
# camera = [('x', 20), ('y', 45), ('z', -90)]
def __fixPovFile(filename, imgWidth, imgHeight, offset, camera):

    tmpFilename = filename + '.tmp'
    licHeader = "// LIC: Processed lights, camera and rotation\n"
    # Check if file already exists in directory of cache, abort if not
    if not os.path.exists(filename):
        return
    originalFile = open(filename, 'r')
    
    # Bug in L3P: if we're rendering only one part, L3P declares it as an object, 
    # not union; PovRay then ignores the color, and we get a black part
    objectName = os.path.splitext(os.path.basename(filename))[0]
    objectName = objectName.replace('_', '__') + '_dot_dat'
    
    # Check if we've already processed this pov, abort if we have
    if originalFile.readline() == licHeader:
        originalFile.close()
        return

    lastObjectLine = ''
    inCamera = inLight = False
    copyFile = open(tmpFilename, 'w')
    copyFile.write(licHeader)

    for line in originalFile:
        
        if line.startswith('object { '):
            lastObjectLine = line
        
        elif line.startswith('#declare %s = object' % objectName):
            line = line.replace('object', 'union')
        
        elif line.startswith('light_source'):
            inLight = True
        
        elif line == '}\n' and inLight:
            inLight = False
            copyFile.write('\tshadowless\n')
        
        elif line.startswith('camera'):
            inCamera = True
            copyFile.write(line)
            copyFile.write('\torthographic\n')
            copyFile.write('\tlocation <-%f, %f, -1000>\n' % (offset.x(), -offset.y()))
            copyFile.write('\tsky      -y\n')
            copyFile.write('\tright    -%d * x\n' % (imgWidth))
            copyFile.write('\tup        %d * y\n' % (imgHeight))
            copyFile.write('\tlook_at   <-%f, %f, 0>\n' % (offset.x(), -offset.y()))
            copyFile.write('\trotate    <0, 1e-5, 0>\n')
        
        elif line == '}\n' and inCamera:
            inCamera = False
        
        if not inCamera:
            copyFile.write(line)
    
    originalFile.close()
    copyFile.close()
    
    # Determine last object in file on first pass, and try fix it.
    originalFile = open(tmpFilename, 'r')
    copyFile = open(filename, 'w')
    
    for line in originalFile:
        if line != lastObjectLine:
            copyFile.write(line)
        else:
            obj = filter(None , lastObjectLine.partition('#if'))
            for m in obj:
                startPosition = m.rfind('}') - 1
                if startPosition <= 0:
                    startPosition = m.__len__()
            # Insert the main object line...
                copyFile.write(m[:startPosition] + '\n')
                
            # ... with proper rotations inserted...
                for axis, amount in camera:
                    if axis == 'x':
                        copyFile.write('\trotate <%f, 0, 0>\n' % amount)
                    elif axis == 'y':
                        copyFile.write('\trotate <0, %f, 0>\n' % amount)
                    elif axis == 'z':               
                        copyFile.write('\trotate <0, 0, %f>\n' % amount)
                
            # ... then the rest of the original object line
                copyFile.write(''.join(m[startPosition:]))
    
    originalFile.close()
    copyFile.close()
    os.remove(tmpFilename)

def createPngFromPov(povFile, width, height, offset, scale, rotation):

    povFile = os.path.normcase(povFile)
    rawFilename = os.path.splitext(os.path.basename(povFile))[0]
    
    pngFile = os.path.join(config.pngCachePath(), rawFilename)
    pngFile = os.path.normcase("%s.png" % pngFile)
    
    if os.path.exists(povFile):
        if not os.path.isfile(pngFile):
            camera = [('x', rotation[0]), ('y', rotation[1]), ('z', rotation[2])]
            __fixPovFile(povFile, width, height, offset, camera)
            povCommand = __getDefaultCommand()
            povCommand['inFile'] = "\"%s\"" % povFile
            povCommand['outFile'] = "\"%s\"" % pngFile
            povCommand['width'] = width * scale
            povCommand['height'] = height * scale
            __runCommand(povCommand)
        
    return pngFile
    
