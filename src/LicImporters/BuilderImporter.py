"""
    LIC - Instruction Book Creation software
    Copyright (C) 2015 Jeremy Czajkowski

    This file (Importers.BuilderImporter.py) is part of LIC.

    LIC is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    You should have received a copy of the Creative Commons License
    along with this program.  If not, see http://creativecommons.org/licenses/by-sa/3.0/
"""

import logging
import os.path

import LDrawImporter


LDrawPath = None  # This will be set by the object calling this importer

def importModel(filename, instructions):
    BuilderImporter(filename, instructions)

def importPart(filename, instructions, abstractPart):
    BuilderImporter(filename, instructions, abstractPart)

def importColorFile(instructions):
    BuilderImporter.loadLDConfig(instructions)

class BuilderImporter(LDrawImporter.LDrawImporter):
    
    def __init__(self, filename, instructions, parent=None):
        LDrawImporter.LDrawImporter.__init__(self, filename, instructions, parent)


    def writeLogEntry(self, message):
        logging.warning('------------------------------------------------------\n BuilderImporter => %s' % message)        

Comment = '0'
PartCommand = '1'
LineCommand = '2'
TriangleCommand = '3'
QuadCommand = '4'
ConditionalLineCommand = '5'

StepCommand = 'STEP'
FileCommand = 'FILE'
BFCCommand = 'BFC'
lineTerm = '\n'

def LDToGLMatrix(matrix):
    return LDrawImporter.LDToGLMatrix(matrix)

def GLToLDMatrix(matrix):
    return LDrawImporter.GLToLDMatrix(matrix)

def createPartLine(color, matrix, filename):
    return LDrawImporter.createPartLine(color, matrix, filename)

def isPartLine(line):
    return LDrawImporter.isPartLine(line)

def lineToPart(line):
    return LDrawImporter.lineToPart(line)

def createSubmodelLines(filename):
    return LDrawImporter.createSubmodelLines(filename)

def isBFCLine(line):
    return LDrawImporter.isBFCLine(line)

def isPrimitiveLine(line):
    return LDrawImporter.isPrimitiveLine(line)

def lineToPrimitive(line):
    return LDrawImporter.lineToPrimitive(line)

def lineTypeToGLShape(command):
    return LDrawImporter.lineTypeToGLShape(command)

def isConditionalLine(line):
    return LDrawImporter.isConditionalLine(line)

def lineToConditionalLine(line):
    return LDrawImporter.lineToConditionalLine(line)

def isFileLine(line):
    return LDrawImporter.isFileLine(line)

def isStepLine(line):
    return LDrawImporter.isStepLine(line)

def createStepLine():
    return LDrawImporter.createStepLine()

class BuilderFile(LDrawImporter.LDrawFile):

    def __init__(self, filename, filepath = ""):
        LDrawImporter.LDrawImporter.__init__(self, filename, filepath)
    
    