"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicL3PWrapper.py) is part of Lic.

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

import os      # For setting LDraw environment and process creation
import config  # For path to l3p

def listToCSVStr(l):
    s = ''
    for i in l:
        s += str(i) + ','
    return s[:-1]
    
def boolToCommand(command, bool):
    if bool:
        return command
    return ''

def __getDefaultCommand():
    return dict({
        'camera position' : [20, -45, 0],
        'background' : [1.0, 1.0, 1.0],
        
        'seam width' : 0.5,
        'quality' : 3,
        'color' : 0,
        
        'overwrite' : True,
        'bumps' : True,
        'LGEO' : False,
    })

l3pCommands = {
    'inFile' : None,
    'outFile' : None,
    
    'camera position' : ['-cg', listToCSVStr],  # [20, -45, 0] = (lat, long, r)
    'background' : ['-b', listToCSVStr],   # [r, g, b] 0 <= r <= 1
    'light' : ['-lg', listToCSVStr],  # [45, -45, 0] = (lat, long, r)
    
    'seam width' : ['-sw', str],  # int
    'quality' : ['-q', str],  # int
    'color' : ['-c', str],  # LDraw Color code
    
    'overwrite' : ['', lambda b: boolToCommand('-o', b)], # Boolean
    'bumps' : ['', lambda b: boolToCommand('-bu', b)],    # Boolean
    'LGEO' : ['', lambda b: boolToCommand('-lgeo', b)],   # Boolean
}

os.environ['LDRAWDIR'] = config.LDrawPath
    
# d: {'camera position' : [20,-45,0], 'inputFile' : 'hello.dat'}
def __runCommand(d):
    
    l3pApp = config.L3PPath
    if not os.path.isfile(l3pApp):
        print "Error: Could not find L3p - aborting image generation"
        return
    
    args = [l3pApp]
    for key, value in d.items():
        command = l3pCommands[key]
        if command:
            args.append(command[0] + command[1](value))
        else:
            if key == 'inFile':
                args.insert(1, value)  # Ensure input file is first command (after l3p.exe itself)
            else:
                args.append(value)
    os.spawnv(os.P_WAIT, l3pApp, args)

def createPovFromDat(datFile, color = None):
    
    rawFilename = os.path.splitext(os.path.basename(datFile))[0]
    povFile = os.path.join(config.povCachePath(), rawFilename)
    
    if color is None:
        povFile = "%s.pov" % povFile
    else:
        povFile = "%s_%d.pov" % (povFile, color)
    
    if not os.path.isfile(povFile):
        l3pCommand = __getDefaultCommand()
        l3pCommand['inFile'] = datFile
        l3pCommand['outFile'] = povFile
        if color:
            l3pCommand['color'] = color
        __runCommand(l3pCommand)
        
    return povFile

        
