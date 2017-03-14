'''
    LIC - Instruction Book Creation software
    Copyright (C) 2017 Jeremy Czajkowski

    This file (ObjImporter.py) is part of LIC.

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
'''


from copy import deepcopy
import logging

import trimesh

from LicImporters.LDrawImporter import LDrawImporter


LDrawPath = None  # This will be set by the object calling this importer

def importModel(filename, proxy):
    ObjImporter(filename, proxy)

def importPart(filename, proxy, abstractPart):
    ObjImporter.writeLogEntry("importPart method is not implement yet")

def importColorFile(proxy):
    LDrawImporter.loadLDConfig(proxy)

class ObjImporter(object):

    _PARTFILE = '300321.dat'  # Brick 2x2  Bright Red
    _MAXPARTS = 10
    _MAXSTEPS = 4

    def __init__(self, filename, proxy, parent=None):
        
        self.filename = filename
        self.mesh = None
        
        try:
            self.mesh = trimesh.load_mesh(self.filename)
        except Exception as error:
            logging.exception(error)
            return 
            
        try:
            LDrawImporter(self._PARTFILE ,proxy)
        except Exception as error:
            logging.exception(error)
        else:
            firstStep = proxy.getStepByNumber(1)
            if firstStep:
                firstPart = firstStep.csi.parts[0].parts[0] 
                xyzSize = firstPart.xyzSize()
                
                test = True
                while test:
                    lwh = self.mesh.extents     
                    test= lwh[0] < xyzSize[0] or lwh[1] < xyzSize[1] or lwh[2] < xyzSize[2]
                    if test:
                        self.mesh.apply_scale(1.5)

                zLength = int(lwh[2]/xyzSize[2])
                yLength = int(lwh[1]/xyzSize[1])
                xLength = int(lwh[0]/xyzSize[0])

                coords = []
                for x in range(xLength):
                    for y in range(yLength):
                        m1 = deepcopy(firstPart.matrix)
                        m1[12] = xyzSize[0] * x  
                        m1[13] = xyzSize[1] * y  
                        coords.append(m1)

                        for z in range(zLength):
                            m2 = deepcopy(m1)
                            m2[14] = xyzSize[2] * z
                            coords.append(m2)
                        
                step = firstStep
                page = firstStep.parentItem()
                model= page.instructions.mainModel
                    
                nPart = 1
                nStep = 1
                for matrix in coords:
                    nPart += 1
                    if nPart > self._MAXPARTS:
                        nPart = 0
                        nStep += 1
                        
                        step.csi.isDirty = True
                    
                        step = page.addBlankStep()
                        
                    if nStep > self._MAXSTEPS:
                        page.initLayout()   
                        
                        nPart = 0
                        nStep = 1
                        page = model.appendBlankPage()
                        step = page.steps[0]
                       
                    newPart = firstPart.duplicate()
                    newPart.matrix = matrix
        
                    step.addPart(newPart)
                    model.parts.append(newPart)
                        
                firstStep.removePart(firstPart)
                model.showHidePLIs(False, False)
                
    @staticmethod
    def writeLogEntry(message):
        logging.error('------------------------------------------------------\n ObjImporter => %s' % message)            
        
