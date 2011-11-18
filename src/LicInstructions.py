"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicInstructions.py) is part of Lic.

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

from LicCommonImports import *

import Image

from LicHelpers import LicColor, LicColorDict
from LicCustomPages import Page, TitlePage
from LicModel import *
import LicImporters
from LicTemplateSettings import TemplateSettings

class Instructions(QObject):
    itemClassName = "Instructions"

    def __init__(self, parent, scene, glWidget):
        QObject.__init__(self, parent)

        self.templateSettings = TemplateSettings()
        
        self.scene = scene
        self.mainModel = None
        self.colorDict = LicColorDict()  # Dict of all valid LicColor instances for this particular model, indexed by LDraw color code
        self.partDictionary = {}      # x = AbstractPart("3005.dat"); partDictionary[x.filename] == x

        self.glContext = glWidget
        self.glContext.makeCurrent()

    def __getTemplate(self):
        return self.mainModel.template

    def __setTemplate(self, template):
        if (self.mainModel.template is None):
            self.mainModel.incrementRows(1)
        self.mainModel.template = template

    template = property(__getTemplate, __setTemplate)

    def clear(self):

        # Remove everything from the graphics scene
        if self.mainModel:
            self.mainModel.deleteAllPages(self.scene)

        self.mainModel = None
        self.partDictionary = {}
        Page.PageSize = Page.defaultPageSize
        Page.Resolution = Page.defaultResolution
        CSI.defaultScale = PLI.defaultScale = SubmodelPreview.defaultScale = 1.0
        CSI.defaultRotation = [20.0, 45.0, 0.0]
        PLI.defaultRotation = [20.0, -45.0, 0.0]
        CSI.highlightNewParts = False
        SubmodelPreview.defaultRotation = [20.0, 45.0, 0.0]
        LicGLHelpers.resetLightParameters()
        self.glContext.makeCurrent()

    def importModel(self, filename):

        self.mainModel = Mainmodel(self, self, filename)
        self.mainModel.appendBlankPage()
        self.mainModel.importModel()
        
        self.mainModel.syncPageNumbers()
        self.mainModel.addInitialPagesAndSteps()
        
        submodelCount = self.mainModel.submodelCount()
        pageList = self.mainModel.getPageList()
        pageList.sort(key = lambda x: x._number)
        totalCount = len(self.partDictionary) + len(self.mainModel.getCSIList()) + submodelCount  # Rough count only

        yield totalCount  # Special first value is maximum number of progression steps in load process

        yield "Initializing GL display lists"
        for label in self.initGLDisplayLists():  # generate all part GL display lists on the general glWidget
            yield label

        for label in self.initPartDimensions():  # Calculate width and height of each abstractPart in the part dictionary
            yield label

        yield "Initializing CSI Dimensions"
        for label in self.initCSIDimensions():   # Calculate width and height of each CSI in this instruction book
            yield label

        yield "Initializing Submodel Images"
        self.mainModel.addSubmodelImages()

        yield "Laying out Pages"
        for page in pageList:
            page.initLayout()

        yield "Reconfiguring Page Layouts"
        self.mainModel.mergeInitialPages()
        self.mainModel.reOrderSubmodelPages()
        self.mainModel.syncPageNumbers()

        for page in pageList:
            for label in page.adjustSubmodelImages():
                yield label
            page.resetPageNumberPosition()

    def getQuantitativeSizeMeasure(self):  # Get some arbitrary measure of how big / complex this file is (useful for progress bars)
        count = len(self.partDictionary)
        count += self.mainModel.pageCount()
        count += len(self.mainModel.getCSIList()) * 2
        return count

    def getModelName(self):
        return self.mainModel.filename

    def getPageList(self):
        return self.mainModel.getFullPageList()

    def getProxy(self):
        return InstructionsProxy(self)
    
    def spawnNewPage(self, submodel, number, row):
        return Page(submodel, self, number, row)
    
    def spawnNewTitlePage(self):
        return TitlePage(self)

    def initGLDisplayLists(self):

        self.glContext.makeCurrent()

        # First initialize all abstractPart display lists
        for part in self.partDictionary.values():
            if part.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
                yield "Initializing " + part.name
                part.createGLDisplayList()

        # Initialize the main model display list
        yield "Initializing Main Model GL display lists"
        self.mainModel.createGLDisplayList(True)
        self.mainModel.initSubmodelImageGLDisplayList()

        # Initialize all CSI display lists
        i = 0
        yield "Initializing CSI GL display lists"
        csiList = self.mainModel.getCSIList()
        for csi in csiList:
            yield "Initializing CSI " + str(i)
            csi.createGLDisplayList()
            i += 1

    def getAbstractPart(self, filename):
        pd = self.partDictionary
        part = None

        if filename in pd:
            part = pd[filename]
        elif filename.upper() in pd:
            part = pd[filename.upper()]
        else:
            # Set up dynamic module to be used for import 
            importerName = LicImporters.getImporter(os.path.splitext(filename)[1][1:])
            importModule = __import__("LicImporters.%s" % importerName, fromlist = ["LicImporters"])
            importModule.LDrawPath = LicConfig.LDrawPath

            part = AbstractPart(filename)
            importModule.importPart(filename, self.getProxy(), part)
            pd[filename] = part

        if part.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
            part.createGLDisplayList()
            part.resetPixmap(self.glContext)
            
        return part

    def getPartDimensionListAndCount(self, reset = False):
        if reset:
            partList = [part for part in self.partDictionary.values() if (not part.isPrimitive)]
        else:
            partList = [part for part in self.partDictionary.values() if (not part.isPrimitive) and (part.width == part.height == -1)]
        partList.append(self.mainModel)

        partDivCount = 25
        partStepCount = int(len(partList) / partDivCount)
        return (partList, partStepCount, partDivCount)
    
    def initPartDimensions(self, reset = False):
        """
        Calculates each uninitialized part's display width and height.
        Creates GL buffer to render a temp copy of each part, then uses those raw pixels to determine size.
        """

        partList, partStepCount, partDivCount = self.getPartDimensionListAndCount(reset)
        currentPartCount = currentCount = 0

        if not partList:
            return    # If there's no parts to initialize, we're done here

        partList2 = []
        sizes = [128, 256, 512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, LicGLHelpers.getGLFormat(), self.glContext)
            pBuffer.makeCurrent()

            # Render each image and calculate their sizes
            for abstractPart in partList:

                if abstractPart.initSize(size, pBuffer):  # Draw image and calculate its size:                    
                    currentPartCount += 1
                    if not currentPartCount % partDivCount:
                        currentPartCount = 0
                        currentCount +=1
                        yield "Initializing Part Dimensions (%d/%d)" % (currentCount, partStepCount)
                else:
                    partList2.append(abstractPart)

            if len(partList2) < 1:
                break  # All images initialized successfully
            else:
                partList = partList2  # Some images rendered out of frame - loop and try bigger frame
                partList2 = []

    def setAllCSIDirty(self):
        csiList = self.mainModel.getCSIList()
        for csi in csiList:
            csi.isDirty = True

    def updateMainModel(self, updatePartList = True):
        if self.mainModel.hasTitlePage():
            self.mainModel.titlePage.submodelItem.resetPixmap()
        if updatePartList:
            self.mainModel.updatePartList()

    def initCSIDimensions(self, repositionCSI = False):

        self.glContext.makeCurrent()

        csiList = self.mainModel.getCSIList()
        if not csiList:
            return  # All CSIs initialized - nothing to do here

        csiList2 = []
        sizes = [512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels or steps

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, LicGLHelpers.getGLFormat(), self.glContext)

            # Render each CSI and calculate its size
            for csi in csiList:
                pBuffer.makeCurrent()
                oldRect = csi.rect()
                result = csi.initSize(size, pBuffer)
                if result:
                    yield result
                    if repositionCSI:
                        newRect = csi.rect()
                        dx = oldRect.width() - newRect.width()
                        dy = oldRect.height() - newRect.height()
                        csi.moveBy(dx / 2.0, dy / 2.0)
                else:
                    csiList2.append(csi)

            if len(csiList2) < 1:
                break  # All images initialized successfully
            else:
                csiList = csiList2  # Some images rendered out of frame - loop and try bigger frame
                csiList2 = []

        self.glContext.makeCurrent()

    def exportToPOV(self):  # TODO: Fix POV Export so it works with the last year's worth of updates
        #global submodelDictionary
        #for model in submodelDictionary.values():
        #    if model.used:
        #        model.createPng()
        self.mainModel.createPng()
        self.mainModel.exportImagesToPov()
        
    def exportImages(self, scaleFactor = 1.0):
        
        pagesToDisplay = self.scene.pagesToDisplay
        self.scene.clearSelection()
        self.scene.showOnePage()
        self.scene.setBackgroundBrush(QBrush(Qt.NoBrush))

        # Build the list of pages that need to be exported
        pageList = self.mainModel.getFullPageList()
        pageList.sort(key = lambda x: x._number)
        yield len(pageList) # Special first value is number of steps in export process

        currentPageNumber = self.scene.currentPage._number  # Store this so we can restore selection later
        bufferManager = None

        if scaleFactor > 1.0:  # Make part lines a bit thicker for higher res output
            lineWidth = LicGLHelpers.getLightParameters()[2]
            GL.glLineWidth(lineWidth * scaleFactor)

        try:
            w, h = int(Page.PageSize.width() * scaleFactor), int(Page.PageSize.height() * scaleFactor)
            bufferManager = LicGLHelpers.FrameBufferManager(w, h)

            # Render & save each page as an image
            for page in pageList:

                page.lockIcon.hide()

                exportedFilename = os.path.join(LicConfig.glImageCachePath(), "Page_%d.png" % page.number)

                bufferManager.bindMSFB()
                LicGLHelpers.initFreshContext(True)

                page.drawGLItemsOffscreen(QRectF(0, 0, w, h), scaleFactor)
                bufferManager.blitMSFB()
                data = bufferManager.readFB()

                # Create an image from raw pixels and save to disk - would be nice to create QImage directly here
                image = Image.fromstring("RGBA", (w, h), data)
                image = image.transpose(Image.FLIP_TOP_BOTTOM)
                image.save(exportedFilename)

                # Create new blank image
                image = QImage(w, h, QImage.Format_ARGB32)
                painter = QPainter()
                painter.begin(image)

                self.scene.selectPage(page._number)
                self.scene.renderMode = 'background'
                self.scene.render(painter, QRectF(0, 0, w, h))

                glImage = QImage(exportedFilename)
                painter.drawImage(QPoint(0, 0), glImage)

                self.scene.selectPage(page._number)
                self.scene.renderMode = 'foreground'
                self.scene.render(painter, QRectF(0, 0, w, h))
    
                painter.end()

                newName = os.path.join(LicConfig.finalImageCachePath(), "Page_%d.png" % page.number)
                image.save(newName)

                # Need to re-open file to set DPI with PIL.  WTF Qt QImage?!
                # TODO: when we have proper page size & resolution export dialogs, enable this
                #image = Image.open(newName)
                #image.save(newName, "PNG", dpi=(300, 300))

                yield newName
                page.lockIcon.show()    

        finally:
            if bufferManager is not None:
                bufferManager.cleanup()
            self.scene.renderMode = 'full'
            self.scene.setPagesToDisplay(pagesToDisplay)
            self.scene.selectPage(currentPageNumber)
            self.scene.setBackgroundBrush(Qt.gray)

    def exportToPDF(self):

        # Create an image for each page
        # TODO: Connect PDF export to page resolution settings
        filename = os.path.join(LicConfig.pdfCachePath(), os.path.basename(self.mainModel.filename)[:-3] + "pdf")
        yield filename

        if sys.platform.startswith('darwin'):  # Temp workaround to PDF crash on OSX
            exporter = self.exportImages(2.0)
        else:
            exporter = self.exportImages(3.0)

        yield 2 * exporter.next()

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFileName(filename)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setFullPage(True)
        printer.setResolution(Page.Resolution)
        printer.setPaperSize(QSizeF(Page.PageSize), QPrinter.DevicePixel)

        pageFilenameList = []
        for pageFilename in exporter:
            fn = os.path.splitext(os.path.basename(pageFilename))[0].replace('_', ' ')
            yield "Rendering " + fn
            pageFilenameList.append(pageFilename)

        painter = QPainter()
        painter.begin(printer)
        for pageFilename in pageFilenameList:
            fn = os.path.splitext(os.path.basename(pageFilename))[0].replace('_', ' ')
            yield "Adding " + fn + " to PDF"
            image = QImage(pageFilename)
            painter.drawImage(QRectF(0.0, 0.0, Page.PageSize.width(), Page.PageSize.height()), image)
            if pageFilename != pageFilenameList[-1]:
                printer.newPage()
        painter.end()

    def updatePageNumbers(self, newNumber, increment = 1):
        if self.mainModel:
            self.mainModel.updatePageNumbers(newNumber, increment)

    def loadLDrawColors(self):
        self.colorDict = LicColorDict()
        LicImporters.LDrawImporter.importColorFile(self.getProxy())

class InstructionsProxy(object):

    def __init__(self, instructions):
        self.__instructions = instructions

    def createPart(self, fn, colorCode, matrix, invert = False):

        partDictionary = self.__instructions.partDictionary
        color = self.__instructions.colorDict[colorCode]
        part = Part(fn, color, matrix, invert)

        if fn in partDictionary:
            part.abstractPart = partDictionary[fn]
        elif fn.upper() in partDictionary:
            part.abstractPart = partDictionary[fn.upper()]
        elif fn.lower() in partDictionary:
            part.abstractPart = partDictionary[fn.lower()]
        return part

    def createAbstractPart(self, fn):
        partDictionary = self.__instructions.partDictionary
        partDictionary[fn] = AbstractPart(fn)
        return partDictionary[fn]

    def createAbstractSubmodel(self, fn, parent = None):

        partDictionary = self.__instructions.partDictionary
        if parent is None:
            parent = self.__instructions.mainModel

        part = partDictionary[fn] = Submodel(parent, self.__instructions, fn)
        part.appendBlankPage()
        return part

    def addColor(self, colorCode, r = 1.0, g = 1.0, b = 1.0, a = 1.0, name = 'Black'):
        cd = self.__instructions.colorDict
        cd[colorCode] = None if r is None else LicColor(r, g, b, a, name)

    def addPart(self, part, parent = None):
        if parent is None:
            parent = self.__instructions.mainModel

        parent.parts.append(part)

        if parent.isSubmodel:
            parent.pages[-1].steps[-1].addPart(part)

            if part.abstractPart.isSubmodel and not part.abstractPart.used:
                p = part.abstractPart
                p._parent = parent
                p._row = parent.pages[-1]._row
                p.used = True
                parent.pages[-1]._row += 1
                parent.submodels.append(p)

    def addPrimitive(self, shape, colorCode, points, parent = None):
        if parent is None:
            parent = self.__instructions.mainModel
        color = self.__instructions.colorDict[colorCode]
        primitive = Primitive(color, points, shape, parent.winding)
        parent.primitives.append(primitive)

    def addBlankPage(self, parent):
        if parent is None:
            parent = self.__instructions.mainModel
        if parent.isSubmodel:
            parent.appendBlankPage()
