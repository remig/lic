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

import os.path
from OpenGL import GL

LDrawPath = "C:/LDraw"  # TODO: Find better platform-agnostic default string

def importModel(filename, instructions):
    LDrawImporter(filename, instructions)

def importPart(filename, instructions, abstractPart):
    LDrawImporter(filename, instructions, abstractPart)

class LDrawImporter(object):
    
    def __init__(self, filename, instructions, parent = None):

        ldrawFile = LDrawFile(filename)
        self.lineList = ldrawFile.lineList
        self.submodels = ldrawFile.getSubmodels(filename)
        self.filename = filename
        self.instructions = instructions
        if parent:
            parent.name = ldrawFile.name

        self.loadAbstractPartFromStartStop(parent, *self.submodels[self.filename])

    def createNewPartFromLine(self, line, parent):

        filename, color, matrix = lineToPart(line)

        part = self.instructions.createPart(filename, color, matrix)

        if part.abstractPart is None:
            if filename in self.submodels:
                part.abstractPart = self.instructions.createAbstractSubmodel(filename, parent)
                self.loadAbstractPartFromStartStop(part.abstractPart, *self.submodels[filename])
            else:
                part.abstractPart = self.instructions.createAbstractPart(filename)
                self.loadAbstractPartFromFile(part.abstractPart, filename)
    
        return part
    
    def loadAbstractPartFromFile(self, part, filename):
        ldrawFile = LDrawFile(filename)
        part.isPrimitive = ldrawFile.isPrimitive
        part.name = ldrawFile.name
        self.loadAbstractPartFromLineList(part, ldrawFile.lineList)

    def loadAbstractPartFromStartStop(self, part, start, stop):
        lineList = self.lineList[start + 1 : stop]  # + 1 to skip over introductory FILE line
        self.loadAbstractPartFromLineList(part, lineList)
    
    def loadAbstractPartFromLineList(self, part, lineList):
    
        for line in lineList:
    
            if isFileLine(line): # A FILE line means we're finished loading this part
                return
    
            elif isStepLine(line):
                self.instructions.addBlankPage(part)

            elif isPartLine(line):
                newPart = self.createNewPartFromLine(line, part)
                if part:
                    newPart.setInversion(part.invertNext)
                    self.configureBlackPartColor(part.filename, newPart, part.invertNext)
                    part.invertNext = False
                self.instructions.addPart(newPart, part)
    
            elif isPrimitiveLine(line):
                shape, color, points = lineToPrimitive(line)
                self.instructions.addPrimitive(shape, color, points, part)
                
            elif part and isBFCLine(line):
                if line[3] == 'CERTIFY':
                    isCW = (len(line) == 5 and line[4] == 'CW')
                    part.winding = GL.GL_CW if isCW else GL.GL_CCW
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

StepCommand = 'STEP'
FileCommand = 'FILE'
BFCCommand = 'BFC'

def LDToGLMatrix(matrix):
    m = [float(x) for x in matrix]
    return [m[3], m[6], m[9], 0.0, m[4], m[7], m[10], 0.0, m[5], m[8], m[11], 0.0, m[0], m[1], m[2], 1.0]

def isPartLine(line):
    return (len(line) > 15) and (line[1] == PartCommand)

def lineToPart(line):
    filename = line[15]
    color = int(line[2])
    matrix = LDToGLMatrix(line[3:15])
    return (filename, color, matrix)

def isBFCLine(line):
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

def isConditionalLine(line):
    return (len(line) == 15) and (line[1] == ConditionalLineCommand)

def lineToConditionalLine(line):
    d = {}
    d['color'] = float(line[2])
    d['points'] = [float(x) for x in line[3:9]]
    d['control points'] = [float(x) for x in line[9:]]
    return d

def isFileLine(line):
    return (len(line) > 2) and (line[1] == Comment) and (line[2] == FileCommand)

def isStepLine(line):
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
        
        self.lineList = []
        self.loadFileList()

    def loadFileList(self):
        
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
            self.lineList.append([i] + l.split())
            i += 1
        f.close()
        
        self.name = ' '.join(self.lineList[0][2:])

    def getSubmodels(self, filename):
        
        # Loop through the file array searching for sub model FILE declarations
        submodels = [(filename, 0)]
        for i, l in enumerate(self.lineList[1:]):
            if isFileLine(l):
                submodels.append((l[3], i+1))  # + 1 because we start at line 1 not 0
        
        # Fixup submodel list by calculating the ending line number from the file
        for i in range(0, len(submodels)-1):
            submodels[i] = (submodels[i][0], [submodels[i][1], submodels[i+1][1]])
        
        # Last submodel is special case: its ending line is end of file array
        submodels[-1] = (submodels[-1][0], [submodels[-1][1], len(self.lineList)])
        
        return dict(submodels)  # {filename: (start index, stop index)}
