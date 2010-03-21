"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (Importers.LDrawImporter.py) is part of Lic.

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

import os      # for path creation
from OpenGL import GL

LDrawPath = "C:/LDraw"

def importModel(filename, instructions):
    importer = LDrawImporter(filename, instructions)
    importer.importModel()

class LDrawImporter(object):
    
    def __init__(self, filename, instructions):

        ldrawFile = LDrawFile(filename)
        ldrawFile.loadFileArray()

        self.lineArray = ldrawFile.lineArray
        self.submodels = ldrawFile.getSubmodels()
        self.instructions = instructions

    def importModel(self):
        
        for line in self.lineArray[1:]:
            if isValidFileLine(line):
                return  # Done loading main model
    
            if isValidPartLine(line):
                part = self.createNewPartFromLine(line, None)
                self.instructions.addPart(part)
            #elif isValidStepLine(line):
            #    instructions.appendBlankPage()

    def createNewPartFromLine(self, line, parent):

        filename, color, matrix = lineToPart(line)

        part = self.instructions.createPart(filename, color, matrix)

        if part.abstractPart is None:
            if filename in self.submodels:
                start, stop = self.submodels[filename]
                lineArray = self.lineArray[start + 1 : stop]  # + 1 to skip over introductory FILE line
                part.abstractPart = self.instructions.createAbstractSubmodel(filename, parent)
                self.loadAbstractPartFromLineArray(part.abstractPart, lineArray)
            else:
                part.abstractPart = self.instructions.createAbstractPart(filename)
                self.loadAbstractPartFromFile(part.abstractPart, filename)
    
        return part
    
    def loadAbstractPartFromFile(self, part, filename):
    
        ldrawFile = LDrawFile(filename)
        ldrawFile.loadFileArray()
        
        part.isPrimitive = ldrawFile.isPrimitive
        part.name = ldrawFile.name
        self.loadAbstractPartFromLineArray(part, ldrawFile.lineArray)
    
    def loadAbstractPartFromLineArray(self, part, lineArray):
    
        for line in lineArray:
    
            if isValidFileLine(line): # A FILE line means we're finished loading this part
                return
    
            if isValidPartLine(line):
                newPart = self.createNewPartFromLine(line, part)
                newPart.setInversion(part.invertNext)
                self.configureBlackPartColor(part.filename, newPart, part.invertNext)
                part.invertNext = False
                self.instructions.addPart(newPart, part)
    
            elif isPrimitiveLine(line):
                shape, color, points = lineToPrimitive(line)
                part.addPrimitive(shape, color, points)
                
            #elif isValidConditionalLine(line):
            #    self.addPrimitive(lineToPrimitive(line), GL.GL_LINES)
            
            elif isValidBFCLine(line):
                if line[3] == 'CERTIFY':
                    part.winding = GL.GL_CW if line[4] == 'CW' else GL.GL_CCW
                elif line [3] == 'INVERTNEXT':
                    part.invertNext = True

    def configureBlackPartColor(self, filename, part, invertNext):
        fn = filename.lower()
        if fn == "stud.dat" and part.filename == "4-4cyli.dat":
            part.color = 512
        elif fn == "stud2.dat" and part.filename == "4-4cyli.dat":
            part.color = 512
        elif fn == "stud2a.dat" and part.filename == "4-4cyli.dat":
            part.color = 512
        elif fn == "stud4.dat" and part.filename == "4-4cyli.dat" and invertNext:
            part.color = 512

Comment = '0'
PartCommand = '1'
LineCommand = '2'
TriangleCommand = '3'
QuadCommand = '4'
ConditionalLineCommand = '5'

RotStepCommand = 'ROTSTEP'
StepCommand = 'STEP'
FileCommand = 'FILE'
BFCCommand = 'BFC'
ENDCommand = '0'

def IdentityMatrix():
    return [1.0, 0.0, 0.0, 0.0,  
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0]
    
def LDToOGLMatrix(matrix):
    m = [float(x) for x in matrix]
    return [m[3], m[6], m[9], 0.0, m[4], m[7], m[10], 0.0, m[5], m[8], m[11], 0.0, m[0], m[1], m[2], 1.0]

def OGLToLDMatrix(matrix):
    m = matrix
    return [m[12], m[13], m[14], m[0], m[4], m[8], m[1], m[5], m[9], m[2], m[6], m[10]]

def isValidPartLine(line):
    return (len(line) > 15) and (line[1] == PartCommand)

def lineToPart(line):
    filename = line[15]
    color = int(line[2])
    matrix = LDToOGLMatrix(line[3:15])
    return (filename, color, matrix)

def isValidCommentLine(line):
    return (len(line) > 2) and (line[1] == Comment)

def isValidBFCLine(line):
    return (len(line) > 3) and (line[1] == Comment) and (line[2] == BFCCommand)

def isPrimitiveLine(line):
    length = len(line)
    if length < 9:
        return False
    command = line[1]
    if command == LineCommand and length == 9:
        return True
    if command == TriangleCommand and length == 12:
        return True
    if command == QuadCommand and length == 15:
        return True
    return False

def lineToPrimitive(line):
    shape = lineTypeToGLShape(line[1])
    color = float(line[2])
    points = [float(x) for x in line[3:]]
    return (shape, color, points)

def lineTypeToGLShape(command):
    if command == LineCommand:
        return GL.GL_LINES
    if command == TriangleCommand:
        return GL.GL_TRIANGLES
    if command == QuadCommand:
        return GL.GL_QUADS
    return None

def isValidConditionalLine(line):
    return (len(line) == 15) and (line[1] == ConditionalLineCommand)

def lineToConditionalLine(line):
    d = {}
    d['color'] = float(line[2])
    d['points'] = [float(x) for x in line[3:9]]
    d['control points'] = [float(x) for x in line[9:]]
    return d

def isValidFileLine(line):
    return (len(line) > 2) and (line[1] == Comment) and (line[2] == FileCommand)

def isValidStepLine(line):
    return (len(line) > 2) and (line[1] == Comment) and (line[2] == StepCommand)

class LDrawFile(object):
    def __init__(self, filename):
        """
        Create a new LDrawFile instance based on the passed in LDraw file string.
        
        Parameters:
            filename: dat | ldr | mpd filename (string) to load into this LDrawFile.  Do not include any path
        """
        
        self.filename = filename      # filename, like 3057.dat
        self.name = ""                # coloquial name, like 2 x 2 brick
        self.isPrimitive = False      # Anything in the 'P' directory
        
        self.lineArray = []

    def loadFileArray(self):
        
        try:
            f = file(self.filename)
        except:
            try:
                f = file(os.path.join(LDrawPath, 'MODELS', self.filename))
            except IOError:
                try:
                    f = file(os.path.join(LDrawPath, 'PARTS', self.filename))
                    if (self.filename[:2] == 's\\'):
                        self.isPrimitive = True
                except IOError:
                    f = file(os.path.join(LDrawPath, 'P', self.filename))
                    self.isPrimitive = True
        
        # Copy the file into an internal array, for easier access
        i = 1
        for l in f:
            self.lineArray.append([i] + l.split())
            i += 1
        f.close()
        
        self.name = ' '.join(self.lineArray[0][2:])

    def getSubmodels(self):
        
        # Loop through the file array searching for sub model FILE declarations
        submodels = []  # submodels[0] = (filename, start line number)
        for i, l in enumerate(self.lineArray[1:]):
            if isValidFileLine(l):
                submodels.append((l[3], i+1))  # + 1 because we start at line 1 not 0
        
        if len(submodels) < 1:
            return {} # No submodels in file - we're done
        
        # Fixup submodel array by calculating the ending line number from the file
        for i in range(0, len(submodels)-1):
            submodels[i] = (submodels[i][0], [submodels[i][1], submodels[i+1][1]])
        
        # Last submodel is special case: its ending line is end of file array
        submodels[-1] = (submodels[-1][0], [submodels[-1][1], len(self.lineArray)])
        
        return dict(submodels)  # {filename: (start index, stop index)}
