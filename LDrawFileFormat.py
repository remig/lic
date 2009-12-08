import shutil  # for file copy / rename
import os      # for path creation

import povray     # Build images from povray files
import l3p        # Build povray from DAT files
import config     # For user path info

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

def isValidCommentLine(line):
    return (len(line) > 2) and (line[1] == Comment)

def isValidBFCLine(line):
    return (len(line) > 3) and (line[1] == Comment) and (line[2] == BFCCommand)

def isValidTriangleLine(line):
    return (len(line) == 12) and (line[1] == TriangleCommand)

def lineToTriangle(line):
    d = {}
    d['color'] = float(line[2])
    d['points'] = [float(x) for x in line[3:]]
    return d

def isValidQuadLine(line):
    return (len(line) == 15) and (line[1] == QuadCommand)

def lineToQuad(line):
    d = {}
    d['color'] = float(line[2])
    d['points'] = [float(x) for x in line[3:]]
    return d

def isValidConditionalLine(line):
    return (len(line) == 15) and (line[1] == ConditionalLineCommand)

def lineToConditionalLine(line):
    d = {}
    d['color'] = float(line[2])
    d['points'] = [float(x) for x in line[3:9]]
    d['control points'] = [float(x) for x in line[9:]]
    return d

def isValidLineLine(line):
    return (len(line) == 9) and (line[1] == LineCommand)

def lineToLine(line):
    d = {}
    d['color'] = float(line[2])
    d['points'] = [float(x) for x in line[3:]]
    return d

def isValidFileLine(line):
    return (len(line) > 2) and (line[1] == Comment) and (line[2] == FileCommand)

def lineToFilename(line):
    return ' '.join(line[3:])

def isValidStepLine(line):
    return (len(line) > 2) and (line[1] == Comment) and (line[2] == StepCommand)

def isValidRotStepLine(line):
    return (len(line) > 3) and (line[1] == Comment) and (line[2] == RotStepCommand)

def lineToRotStep(line):
    d = {}
    if len(line) < 6:
        d['state'] = ENDCommand
    else:
        d['point'] = [float(line[3]), float(line[4]), float(line[5])]
        if len(line) == 7:
            d['state'] = line[6]
        else:
            d['state'] = 'REL'
    return d
    
def isValidPartLine(line):
    return (len(line) > 15) and (line[1] == PartCommand)

def lineToPart(line):
    return {'filename': line[15],
            'color': int(line[2]),
            'matrix': LDToOGLMatrix(line[3:15])}

def createPartLine(color, matrix, filename):
    l = [PartCommand, str(color)]
    m = OGLToLDMatrix(matrix)
    l += [str(x)[:-2] if str(x).endswith(".0") else str(x) for x in m]
    l.append(filename)
    line = ' '.join(l)
    return line

class LDrawFile(object):
    def __init__(self, filename):
        """
        Create a new LDrawFile based on a specific LDraw file.
        
        Parameters:
            filename: dat | ldr | mpd file to load into this LDrawFile.  Do not include any path
        """
        
        self.filename = filename      # filename, like 3057.dat
        self.name = ""                # coloquial name, like 2 x 2 brick
        self.isPrimitive = False      # Anything in the 'P' directory
        
        self.fileArray = []

    def loadFileArray(self):
        
        try:
            f = file(self.filename)
        except:
            try:
                f = file(os.path.join(config.LDrawPath, 'MODELS', self.filename))
            except IOError:
                try:
                    f = file(os.path.join(config.LDrawPath, 'PARTS', self.filename))
                    if (self.filename[:2] == 's\\'):
                        self.isPrimitive = True
                except IOError:
                    f = file(os.path.join(config.LDrawPath, 'P', self.filename))
                    self.isPrimitive = True
        
        # copy the file into an internal array, for easier access
        i = 1
        for l in f:
            self.fileArray.append([i] + l.split())
            i += 1
        f.close()
        
        self.name = ' '.join(self.fileArray[0][2:])

    def getSubmodels(self):
        
        # Loop through the file array searching for sub model FILE declarations
        submodels = []  # submodels[0] = (filename, start line number)
        for i, l in enumerate(self.fileArray[1:]):
            if isValidFileLine(l):
                submodels.append((l[3], i+1))  # + 1 because we start at line 1 not 0
        
        if len(submodels) < 1:
            return  # No submodels in file - we're done
        
        # Fixup submodel array by calculating the ending line number from the file
        for i in range(0, len(submodels)-1):
            submodels[i] = (submodels[i][0], [submodels[i][1], submodels[i+1][1]])
        
        # Last submodel is special case: its ending line is end of file array
        submodels[-1] = (submodels[-1][0], [submodels[-1][1], len(self.fileArray)])
        
        return dict(submodels)  # {filename: (start, stop)}
