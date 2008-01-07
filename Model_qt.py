import math   # for sqrt
import os     # for output path creation

from OpenGL.GL import *
from OpenGL.GLU import *

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

import GLHelpers_qt

from LDrawFileFormat_qt import *
from LDrawColors import *
from Drawables import *

UNINIT_OGL_DISPID = -1
partDictionary = {}   # x = PartOGL("3005.dat"); partDictionary[x.filename] == x

def printRect(rect, text = ""):
    print text + ", l: %f, r: %f, t: %f, b: %f" % (rect.left(), rect.right(), rect.top(), rect.bottom())

class Instructions(object):

    def __init__(self, filename, scene, qGLWidget):
        
        # Part dimensions cache line format: filename width height center.x center.y leftInset bottomInset
        self.partDimensionsFilename = "PartDimensions.cache"
        self.scene = scene
        self.qGLWidget = qGLWidget
        
        self.pages = []
        self.currentStep = None
        self.importModel(filename)
        
        # First, generate all part GL display lists on the general glWidget.
        # Then, create a GLPixelBuffer tied to the glWidget, and use that for actual rendering (for its toImage() speed boost).
        self.qGLWidget.makeCurrent()
        self.initDraw()
        
        self.pages[-1].hide()
        self.pages[0].show()

    def addPage(self, page):
    
        self.pages.append(page)
        
        for page in self.pages:
            page.hide()
    
        self.pages[-1].show()

    def importModel(self, filename):
        """ Reads in an LDraw model file and popluates this instruction book with the info. """
        
        ldrawFile = LDrawFile(filename)
        
        # Loop over the specified LDraw file array, skipping the first line
        for line in ldrawFile.fileArray[1:]:
            
            # A FILE line means we're finished loading this model
            if isValidFileLine(line):
                return
            
            self._loadOneLDrawLineCommand(line)

    def _loadOneLDrawLineCommand(self, line):
        
        if isValidStepLine(line):
            self.addStep()
    
        elif isValidPartLine(line):
            self.addPart(lineToPart(line), line)
    
    def addStep(self):
        # For now, this implicitly adds a new page for each new step
        
        page = Page(self.scene)
        self.addPage(page)
        self.currentStep = Step(page)
        page.addStep(self.currentStep)

    def addPart(self, p, line):
        try:
            part = Part(p['filename'], self.qGLWidget, p['color'], p['matrix'])
        except IOError:
            # TODO: This should be printed - commented out for debugging
            #print "Could not find file: %s - Ignoring." % p['filename']
            return
        
        if not self.currentStep:
            self.addStep()
        
        self.currentStep.addPart(part)
    
    def drawBuffer(self):
    
        size = 300
        pBuffer = QGLPixelBuffer(size,  size, QGLFormat(), self.qGLWidget)
        pBuffer.makeCurrent()
        
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glShadeModel(GL_SMOOTH)
        
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        
        lightPos = [100.0, 500.0, -500.0]
        ambient = [0.2, 0.2, 0.2]
        diffuse = [0.8, 0.8, 0.8]
        specular = [0.5, 0.5, 0.5]
        
        glLightfv(GL_LIGHT0, GL_POSITION, lightPos)
        glLightfv(GL_LIGHT0, GL_AMBIENT, ambient)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse)
        glLightfv(GL_LIGHT0, GL_SPECULAR, specular)

        glEnable(GL_DEPTH_TEST)
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        GLHelpers_qt.adjustGLViewport(0, 0, size, size)
        GLHelpers_qt.rotateToPLIView()
        
        self.mainModel.draw()

        image = pBuffer.toImage()
        if image:
            print "have image"
            image.save("C:\\ldraw\\first_qt_render.png", None)
        
        self.qGLWidget.makeCurrent()
    
    def initDraw(self):
        
        # Initialize each part's gl display list, displayed dimensions, and pixmap
        self.initAllParts()
        
        # Layout each step on each page.  
        # TODO: This should only happen if we're importing a new model.  Otherwise, layout should be pulled from load / save binary blob
        for page in self.pages:
            for step in page.steps:
                step.initLayout()

    def initAllParts(self):
    
        # First initialize all GL display lists
        for part in partDictionary.values():
            part.createOGLDisplayList()
    
        # Calculate the width and height of each partOGL in the part dictionary
        self.initPartDimensionsManually()  # Init any parts we've already cached
    
    def initPartDimensionsManually(self):
        """
        Calculates each uninitialized part's display width and height.
        Creates GL buffer to render a temp copy of each part, then uses those raw pixels to determine size.
        Will append results to the part dimension cache file.
        """
        
        partList = [part for part in partDictionary.values() if (not part.isPrimitive) and (part.width == part.height == -1)]
        
        if not partList:
            return    # If there's no parts to look up, we're done here
    
        partList2 = []
        lines = []
        sizes = [128, 256, 512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels
        
        for size in sizes:
            
            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size,  size, QGLFormat(), self.qGLWidget)
            pBuffer.makeCurrent()
            
            # Render each image and calculate their sizes
            for partOGL in partList:
                
                if partOGL.initSize(size, pBuffer):  # Draw image and calculate its size:                    
                    lines.append(partOGL.dimensionsToString())
                    print partOGL.dimensionsToString()
                else:
                    partList2.append(partOGL)
            
            if len(partList2) < 1:
                break  # All images initialized successfully
            else:
                partList = partList2  # Some images rendered out of frame - loop and try bigger frame
                partList2 = []
        
        # Append any newly calculated part dimensions to cache file
        print ""
        if lines:
            f = open(self.partDimensionsFilename, 'a')
            f.writelines(lines)
            f.close()
    
    def save(self, filename = None):
        self.mainModel.partOGL.ldrawFile.saveFile(filename)
    
class Page(QGraphicsRectItem):
    """ A single page in an instruction book.  Contains one or more Steps. """
    
    NextNumber = 1
    inset = QPointF(15.5, 15.5)
    pageInset = 10
    
    def __init__(self, scene, number = -1):
        QGraphicsRectItem.__init__(self, None, scene)
        
        # Position this rectangle inset from the containing scene
        rect = scene.sceneRect().adjusted(Page.pageInset, Page.pageInset, -Page.pageInset, -Page.pageInset)
        self.setRect(rect)
        
        # Give this page a number
        if number == -1:
            self.number = Page.NextNumber
            Page.NextNumber += 1
        else:
            self.number = number
            Page.NextNumber = number + 1
        
        # Setup this page's page number
        self.numberItem = QGraphicsSimpleTextItem(str(self.number), self)
        self.numberItem.setFont(QFont("Arial", 15))

        # Position page number in bottom right page corner
        rect = self.numberItem.boundingRect()
        rect.moveBottomRight(self.rect().bottomRight() - Page.inset)
        self.numberItem.setPos(rect.topLeft())
        
        self.steps = []

    def addStep(self, step):
        
        self.steps.append(step)

    #def itemChange(self, change, value):
    #    if change == QGraphicsItem.ItemChildAddedChange:
    #        pass  # TODO: get a bloody QGraphicsItem out of that damn value
    #    return QGraphicsItem.itemChange(self, change, value)

    def paint(self, painter, option, widget = None):

        # Draw a slightly down-right translated black rectangle, for the page shadow effect
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))
        painter.drawRect(self.rect().translated(3, 3))

        # Draw the page itself - white with a thin black border
        painter.setPen(QPen(Qt.black))
        painter.setBrush(QBrush(Qt.white))
        painter.drawRect(self.rect())
        
        # Draw a (debug) rect around the page number label
        rect = self.numberItem.boundingRect()
        rect.translate(self.numberItem.pos())
        painter.drawRect(rect)

class Step(QGraphicsRectItem):
    """ A single step in an instruction book.  Contains one optional PLI and exactly one CSI. """

    NextNumber = 1
    inset = QPointF(15.5, 15.5)
    
    def __init__(self, parentPage, number = -1):
        QGraphicsRectItem.__init__(self, parentPage)
    
        self.setPos(parentPage.rect().topLeft())
        
        # Give this page a number
        if number == -1:
            self.number = Step.NextNumber
            Step.NextNumber += 1
        else:
            self.number = number
            Step.NextNumber = number + 1
        
        # Initialize Step's number label (position set in initLayout)
        self.numberItem = QGraphicsSimpleTextItem(str(self.number), self)
        self.numberItem.setFont(QFont("Arial", 15))
        
        self.parts = []
        self.pli = PLI(self.pos() + Step.inset, self)
        #self.csi = CSI(self, list(buffers))

    def addPart(self, part):
    
        self.parts.append(part)
        
        if self.pli:
            self.pli.addPart(part)

    def initLayout(self):
    
        print "initializing step: %d" % self.number
        self.pli.initLayout()
        
        # Position the Step number label beneath the PLI
        self.numberItem.setPos(self.pos() + Step.inset)
        self.numberItem.moveBy(0, self.pli.rect().height() + Step.inset.y() + 0.5)
        
        """
        # Ensure all sub model PLIs and steps are also initialized
        for part in self.parts:
            for page in part.partOGL.pages:
                for step in page.steps:
                    step.initLayout(context)
        
        # Tell this step's CSI about the PLI, so it can center itself vertically better
        if self.csi.fileLine is None:
            self.csi.offsetPLI = topGap
            self.csi.resize()
        """
    
    def paint(self, painter, option, widget = None):
        rect = self.numberItem.boundingRect()
        rect.translate(self.numberItem.pos())
        painter.drawRect(rect)
        QGraphicsRectItem.paint(self, painter, option, widget)
    
class PLIItem(QGraphicsRectItem):
    """ Represents one part inside a PLI along with its quantity label. """

    def __init__(self, parent, partOGL, color):
        QGraphicsRectItem.__init__(self, parent)
        self.partOGL = partOGL
        self.color = color
        self._count = 1
        
        self.pixmapItem = None
        
        # Initialize the quantity label (position set in initLayout)
        self.numberItem = QGraphicsSimpleTextItem(str(self._count), self)
        self.numberItem.setFont(QFont("Arial", 10))
        
        self.setPos(parent.inset)
        print "PLI x: %f, y: %f" % (parent.pos().x(), parent.pos().y())

    def initLayout(self):
    
        part = self.partOGL
        lblHeight = self.numberItem.boundingRect().height() / 2.0
        
        # Set this item to the same width & height as its part image
        self.setRect(0, 0, part.width, part.height)
        
        # Position quantity label based on part corner, empty corner triangle and label's size
        if part.leftInset == part.bottomInset == 0:
            dx = -3   # Bottom left triangle is full - shift just a little, for a touch more padding
        else:
            slope = part.leftInset / float(part.bottomInset)
            dx = ((part.leftInset - lblHeight) / slope) - 3  # 3 for a touch more padding

        self.numberItem.setPos(dx, self.rect().height() - lblHeight)

        if self.pixmapItem is None:
            pixmap = part.getPixmap(self.color)
            self.pixmapItem = QGraphicsPixmapItem(pixmap, self)
            self.numberItem.setZValue(self.pixmapItem.zValue() + 1)

    def _setCount(self, count):
        self._count = count
        self.numberItem.setText(str(self._count))

    def _getCount(self):
        return self._count
    
    count = property(fget = _getCount, fset = _setCount)
    
    def paint(self, painter, option, widget = None):
        pass
#        rect = self.numberItem.boundingRect()
#        rect.translate(self.numberItem.pos())
#        painter.drawRect(rect)
#        QGraphicsRectItem.paint(self, painter, option, widget)

class PLI(QGraphicsRectItem):
    """ Parts List Image.  Includes border and layout info for a list of parts in a step. """
    
    inset = QPointF(15, 15)
    
    def __init__(self, pos, parent):
        QGraphicsRectItem.__init__(self, parent)
        
        self.setPen(QPen(Qt.black))
        self.layout = {}  # {(part filename, color): PLIItem instance}
        self.setPos(pos)
        self.setRect(0, 0, 200, 100)

    def isEmpty(self):
        return True if len(self.layout) == 0 else False

    def addPart(self, part):
        
        item = (part.partOGL.filename, part.color)
    
        if item in self.layout:
            self.layout[item].count += 1
        else:
            self.layout[item] = PLIItem(self, part.partOGL, part.color)
            self.layout[item].setParentItem(self)
    
    def initLayout(self):
        """ 
        Allocate space for all parts in this PLI, and choose a decent layout.
        """

        # If this PLI is empty, nothing to do here
        if len(self.layout) < 1:
            return
        
        # Initialize each item in this PLI, so they have good rects and properly positioned quantity labels
        for item in self.layout.values():
            item.initLayout()
    
        # Return the height of the part in the specified layout item
        def itemHeight(layoutItem):
            return layoutItem.partOGL.height
        
        # Compare the width of layout Items 1 and 2
        def compareLayoutItemWidths(item1, item2):
            """ Returns 1 if part 2 is wider than part 1, 0 if equal, -1 if narrower. """
            if item1.partOGL.width < item2.partOGL.width:
                return 1
            if item1.partOGL.width == item2.partOGL.width:
                return 0
            return -1
        
        # Sort the list of parts in this PLI from widest to narrowest, with the tallest one first
        partList = self.layout.values()
        tallestPart = max(partList, key=itemHeight)
        partList.remove(tallestPart)
        partList.sort(compareLayoutItemWidths)
        partList.insert(0, tallestPart)
        
        b = self.rect()
        inset = PLI.inset.x()
        overallX = inset
        b.setSize(QSizeF(-1, -1))
        
        for i, item in enumerate(partList):
            
            # Move this PLIItem to its new position
            item.setPos(overallX, inset)
            
            # Check if the current PLI box is big enough to fit this part *below* the previous part,
            # without making the box any bigger.  If so, position part there instead.
            newWidth = item.rect().width()
            if i > 0:
                prevItem = partList[i-1]
                remainingHeight = b.height() - inset - inset - prevItem.rect().height()
                if item.rect().height() < remainingHeight:
                    overallX = prevItem.pos().x()
                    newWidth = prevItem.rect().width()
                    x = overallX + (newWidth - item.rect().width())
                    y = prevCorner.y + b.internalGap + item.rect().height()
                    item.setPos(x, y)
            
            # Increase overall x, box width and box height to make PLI box big enough for this part
            overallX += newWidth + inset
            b.setWidth(overallX)
            
            lblHeight = item.numberItem.boundingRect().height() / 2.0
            newHeight = item.rect().height() + lblHeight + (inset * 2)
            b.setHeight(max(b.height(), newHeight))
            self.setRect(b)

class PartOGL(object):
    """
    Represents one 'abstract' part.  Could be regular part, like 2x4 brick, could be a 
    simple primitive, like stud.dat.  
    Used inside 'concrete' Part below. One PartOGL instance will be shared across several 
    Part instances.  In other words, PartOGL represents everything that two 2x4 bricks have
    in common when present in a model, everything inside 3001.dat.
    """
    
    def __init__(self, filename, glContext):
        
        print "Creating: " + filename
        self.name = self.filename = filename
        self.ldrawFile = None
        
        self.glContext = glContext
        
        self.inverted = False  # TODO: Fix this! inverted = GL_CW
        self.invertNext = False
        self.parts = []
        self.primitives = []
        self.oglDispID = UNINIT_OGL_DISPID
        self.isPrimitive = False  # primitive here means any file in 'P'
        
        self.width = self.height = -1
        self.leftInset = self.bottomInset = -1
        self.center = Point(0, 0)
        
        self._loadFromFile()
    
    def _loadFromFile(self):
        
        self.ldrawFile = LDrawFile(self.filename)
        self.isPrimitive = self.ldrawFile.isPrimitive
        self.name = self.ldrawFile.name
        
        # Loop over the specified LDraw file array, skipping the first line
        for line in self.ldrawFile.fileArray[1:]:
            
            # A FILE line means we're finished loading this model
            if isValidFileLine(line):
                return
            
            self._loadOneLDrawLineCommand(line)

    def _loadOneLDrawLineCommand(self, line):
        
        if isValidPartLine(line):
            self.addPart(lineToPart(line), line)
        
        elif isValidTriangleLine(line):
            self.addPrimitive(lineToTriangle(line), GL_TRIANGLES)
        
        elif isValidQuadLine(line):
            self.addPrimitive(lineToQuad(line), GL_QUADS)
        
    def addPart(self, p, line):
        try:
            part = Part(p['filename'], self.glContext, p['color'], p['matrix'])
        except IOError:
            # TODO: This should be printed - commented out for debugging
            #print "Could not find file: %s - Ignoring." % p['filename']
            return
        
        self.parts.append(part)
    
    def addPrimitive(self, p, shape):
        primitive = Primitive(p['color'], p['points'], shape, self.inverted ^ self.invertNext)
        self.primitives.append(primitive)
    
    def createOGLDisplayList(self):
        """ Initialize this part's display list.  Expensive call, but called only once. """
        if self.oglDispID != UNINIT_OGL_DISPID:
            return
        
        # Ensure any parts in this part have been initialized
        for part in self.parts:
            if part.partOGL.oglDispID == UNINIT_OGL_DISPID:
                part.partOGL.createOGLDisplayList()
        
        self.oglDispID = glGenLists(1)
        glNewList(self.oglDispID, GL_COMPILE)
        
        for part in self.parts:
            part.callOGLDisplayList()
        
        for primitive in self.primitives:
            primitive.callOGLDisplayList()
        
        glEndList()

    def draw(self):
        glCallList(self.oglDispID)
    
    def dimensionsToString(self):
        if self.isPrimitive:
            return ""
        return "%s %d %d %d %d %d %d\n" % (self.filename, self.width, self.height, self.center.x, self.center.y, self.leftInset, self.bottomInset)

    def initSize(self, size, pBuffer):
        """
        Initialize this part's display width, height, empty corner insets and center point.
        To do this, draw this part to the already initialized GL buffer.
        These dimensions are required to properly lay out PLIs and CSIs.
        
        Parameters:
            size: Width & height of GL buffer to render to, in pixels.  Note that buffer is assumed square
        
        Returns:
            True if part rendered successfully.
            False if the part has been rendered partially or wholly out of frame.
        """
        
        # TODO: If a part is rendered at a size > 256, draw it smaller in the PLI - this sounds like a great way to know when to shrink a PLI image...
        # TODO: Check how many pieces would be rendered successfully at 128 - if significant, test adding that to size list, see if it speeds part generation up
        if self.isPrimitive:
            return True  # Primitive parts need not be sized
        
        params = GLHelpers_qt.initImgSize(size, size, self.oglDispID, False, self.filename, None, pBuffer)
        if params is None:
            return False
        
        # TODO: update some kind of load status bar here - this function is *slow*
        print self.filename + " - size: %d" % (size)
        
        self.width, self.height, self.center, self.leftInset, self.bottomInset = params
        return True

    def getPixmap(self, color = 0):

        if self.isPrimitive:
            return None  # Do not generate any pixmaps for primitives
        
        print "initializing pixmap %s, w: %f, h: %f" % (self.filename, self.width, self.height)
        pBuffer = QGLPixelBuffer(self.width, self.height, QGLFormat(), self.glContext)
        pBuffer.makeCurrent()
        
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glShadeModel(GL_SMOOTH)
        
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        
        lightPos = [100.0, 500.0, -500.0]
        ambient = [0.2, 0.2, 0.2]
        diffuse = [0.8, 0.8, 0.8]
        specular = [0.5, 0.5, 0.5]
        
        glLightfv(GL_LIGHT0, GL_POSITION, lightPos)
        glLightfv(GL_LIGHT0, GL_AMBIENT, ambient)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse)
        glLightfv(GL_LIGHT0, GL_SPECULAR, specular)

        glEnable(GL_DEPTH_TEST)
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        GLHelpers_qt.adjustGLViewport(0, 0, self.width, self.height)
        GLHelpers_qt.rotateToPLIView(self.center.x, self.center.y, 0.0)
        
        color = convertToRGBA(color)
        if len(color) == 3:
            glColor3fv(color)
        elif len(color) == 4:
            glColor4fv(color)
        
        self.draw()

        image = pBuffer.toImage()
        if image:
            image.save("C:\\ldraw\\tmp\\buffer_%s.png" % self.filename, None)
    
        pixmap = QPixmap.fromImage(image)
        self.glContext.makeCurrent()
        return pixmap
    
class Part:
    """
    Represents one 'concrete' part, ie, an 'abstract' part (partOGL), plus enough
    info to draw that abstract part in context of a model, ie color, positional 
    info, containing buffer state, etc.  In other words, Part represents everything
    that could be different between two 2x4 bricks in a model, everything contained
    in one LDraw FILE (5) command.
    """
    
    def __init__(self, filename, glContext, color = 16, matrix = None, invert = False):
        
        self.color = color
        self.matrix = matrix
        self.inverted = invert
        
        if filename in partDictionary:
            self.partOGL = partDictionary[filename]
        else:
            self.partOGL = partDictionary[filename] = PartOGL(filename, glContext)
        
        self.name = self.partOGL.name

    def callOGLDisplayList(self):
        
        # must be called inside a glNewList/EndList pair
        color = convertToRGBA(self.color)
        
        if color != CurrentColor:
            glPushAttrib(GL_CURRENT_BIT)
            if len(color) == 3:
                glColor3fv(color)
            elif len(color) == 4:
                glColor4fv(color)
        
        if self.inverted:
            glPushAttrib(GL_POLYGON_BIT)
            glFrontFace(GL_CW)
        
        if self.matrix:
            glPushMatrix()
            glMultMatrixf(self.matrix)
            
        glCallList(self.partOGL.oglDispID)
        
        if self.matrix:
            glPopMatrix()
        
        if self.inverted:
            glPopAttrib()
        
        if color != CurrentColor:
            glPopAttrib()

    def draw(self):
        self.partOGL.draw()

class Primitive:
    """
    Not a primitive in the LDraw sense, just a single line/triangle/quad.
    Used mainly to construct an OGL display list for a set of points.
    """
    
    def __init__(self, color, points, type, invert = True):
        self.color = color
        self.type = type
        self.points = points
        self.inverted = invert

    # TODO: using numpy for all this would probably work a lot better
    def addNormal(self, p1, p2, p3):
        Bx = p2[0] - p1[0]
        By = p2[1] - p1[1]
        Bz = p2[2] - p1[2]
        
        Cx = p3[0] - p1[0]
        Cy = p3[1] - p1[1]
        Cz = p3[2] - p1[2]
        
        Ax = (By * Cz) - (Bz * Cy)
        Ay = (Bz * Cx) - (Bx * Cz)
        Az = (Bx * Cy) - (By * Cx)
        l = math.sqrt((Ax*Ax)+(Ay*Ay)+(Az*Az))
        if l != 0:
            Ax /= l
            Ay /= l
            Az /= l
        return [Ax, Ay, Az]
    
    def callOGLDisplayList(self):
        
        # must be called inside a glNewList/EndList pair
        color = convertToRGBA(self.color)
        
        if color != CurrentColor:
            glPushAttrib(GL_CURRENT_BIT)
            if len(color) == 3:
                glColor3fv(color)
            elif len(color) == 4:
                glColor4fv(color)
        
        p = self.points
        
        if self.inverted:
            normal = self.addNormal(p[6:9], p[3:6], p[0:3])
            #glBegin( GL_LINES )
            #glVertex3f(p[3], p[4], p[5])
            #glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #glEnd()
            
            glBegin( self.type )
            glNormal3fv(normal)
            if self.type == GL_QUADS:
                glVertex3f( p[9], p[10], p[11] )
            glVertex3f( p[6], p[7], p[8] )
            glVertex3f( p[3], p[4], p[5] )
            glVertex3f( p[0], p[1], p[2] )
            glEnd()
        else:
            normal = self.addNormal(p[0:3], p[3:6], p[6:9])
            #glBegin( GL_LINES )
            #glVertex3f(p[3], p[4], p[5])
            #glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #glEnd()
            
            glBegin( self.type )
            glNormal3fv(normal)
            glVertex3f( p[0], p[1], p[2] )
            glVertex3f( p[3], p[4], p[5] )
            glVertex3f( p[6], p[7], p[8] )
            if self.type == GL_QUADS:
                glVertex3f( p[9], p[10], p[11] )
            glEnd()
        
        if color != CurrentColor:
            glPopAttrib()
