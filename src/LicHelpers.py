"""
    LIC - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne
    Copyright (C) 2015 Jeremy Czajkowski

    This file (LicHelpers.py) is part of LIC.

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

import collections
import logging
import os.path
import re
import unicodedata

from PyQt4.Qt import qGray, qRgb
from PyQt4.QtCore import Qt, QPointF, QString, QSettings
from PyQt4.QtGui import QPainterPath

import LDrawColors
from config import partsCachePath


SUBWINDOW_BACKGROUND = "#FFFACD"
SUBWINDOW_WATING_TEXT = "Operation in progress..."
SUBWINDOW_LOCKAPP_TEXT= SUBWINDOW_WATING_TEXT
SUBWINDOW_CALCULATING_TEXT = "Calculations in the course..."

BASEPLATES_FILE = [
'u8011.dat','u572p01.dat','93607.dat','915p04.dat','915p02.dat','915p01.dat','915.dat','912.dat','911.dat',
'896p01.dat','896.dat','879h.dat','811.dat','809.dat','80547.dat','785.dat','782h.dat','6851.dat',
'648.dat','6475.dat','6261.dat','613p01.dat','613.dat','612p01.dat','612.dat','611p01.dat','611.dat',
'610p01.dat','6100p05.dat','6100p04.dat','6100p03.dat','6100p02.dat','6100p01.dat','6100.dat','610.dat','609p01.dat',
'6099p06.dat','6099p05.dat','6099p04.dat','6099p03.dat','6099p02.dat','6099p01.dat','6099.dat','6092.dat','609.dat',
'608p33.dat','608p04.dat','608p03.dat','608p02.dat','608p01.dat','608.dat','607p01.dat','607.dat','606p33.dat','606p02.dat',
'606p01.dat','606.dat','6024.dat','53588.dat','51595p02.dat','51595p01.dat','51595.dat','51542.dat','50384.dat',
'49059.dat','455p02.dat','455p01.dat','455.dat','4478p04.dat','4478p03.dat','4478p02.dat','4478p01.dat','4478.dat',
'44343p02.dat','44343p01.dat','44343hp01.dat','44343h.dat','44342p01.dat','44342h.dat','44341p01.dat','44341h.dat','44336p03.dat','44336p02.dat',
'44336p01.dat','44336.dat','4268.dat','425p02.dat','425p01.dat','425h.dat','4187h.dat','4186p01.dat','4186h.dat',
'400.dat','397.dat','3947.dat','3867p02.dat','3867p01.dat','3867h.dat','3865h.dat','3857h.dat','3857.dat',
'385.dat','3811p05.dat','3811p04.dat','3811p03.dat','3811p02.dat','3811p01.dat','3811h.dat','3811.dat',
'374p04.dat','374p03.dat','374p02.dat','374p01.dat','374.dat','367.dat','3645p04.dat','3645p03.dat','3645p02.dat',
'3645h.dat','3497h.dat','3334h.dat','31074.dat','31043.dat','309p04.dat','309p03.dat','309p02.dat','309p01.dat',
'309.dat','30473.dat','30271.dat','30225bp1.dat','30225b.dat','30030p01.dat','30030.dat','2552p06.dat','2552p05.dat',
'2552.dat','2361p03.dat','2361p02.dat','2361p01.dat','2361.dat','2360p02.dat','2360p01.dat','2360.dat','2359p03.dat','2359p02.dat',
'2359p01.dat','2359.dat','2358p04.dat','2358p03.dat','2358p02.dat','2358.dat','2296.dat','210h.dat','184h.dat',
'10p0b.dat','10p0a.dat','10p09.dat','10p08.dat','10p07.dat','10p06.dat','10p05.dat','10p04.dat','10p03.dat',
'10p02.dat','10p01.dat','10h.dat','10.dat','0904.dat','0903.dat','0902.dat','0901.dat']

class LicColor(object):

    def __init__(self, r=0.13, g=0.13, b=0.13, a=1.0, name='Black', ldrawCode=16):
        self.rgba = [r, g, b, a]
        self.name = name
        self.ldrawCode = ldrawCode

    def __eq__(self, other):
        if other:
            return self.rgba == other.rgba and self.name == other.name
        return False

    def duplicate(self):
        r, g, b, a = self.rgba
        return LicColor(r, g, b, a, self.name)
    
    def sortKey(self):
        return sum(self.rgba)
    
    @staticmethod
    def black():
        return LicColor(0.0, 0.0, 0.0, 1.0, 'Black')

    @staticmethod
    def red():
        return LicColor(0.77, 0.00, 0.15, 1.0, 'Red')
    
    def code(self):
        hextr = self.ldrawCode
        if self.ldrawCode == LDrawColors.CurrentColor:
            for color in LDrawColors.colors:
                rgba = LDrawColors.colors[color]
                if isinstance(rgba, collections.Iterable):
                    r = "%.2f" % rgba[0] == "%.2f" % self.rgba[0]
                    b = "%.2f" % rgba[1] == "%.2f" % self.rgba[1]
                    g = "%.2f" % rgba[2] == "%.2f" % self.rgba[2]
                    if r and b and g:
                        hextr = color 
                        break 
            if hextr == LDrawColors.CurrentColor:
                r , g , b = self.rgba[0] * 256 , self.rgba[1] * 256 , self.rgba[2] * 256   
                alpha = 2 if self.rgba[3] > 0.5 else 3
                if self.rgba[3] < 0.2:
                    alpha = 7
                hextr = "0x0%d%0.2X%0.2X%0.2X" % (alpha, r, g, b)   
        return hextr

    @staticmethod                
    def RGBAfromCustom(hexColorCode):
        """
        0x02RRGGBB = opaque RGB
        0x03RRGGBB = transparent RGB
        0x04RGBRGB = opaque dither
        0x05RGBxxx = transparent dither (xxx is ignored)
        0x06xxxRGB = transparent dither (xxx is ignored)
        0x07xxxxxx = invisible
        """
        hexColor = hexColorCode[2:]
        colorCls = "01"
        if hexColorCode[2:4] in ["02", "03", "04", "05", "06", "07"]:
            colorCls = hexColorCode[2:4]
            hexColor = hexColorCode[4:]
        try:
            r , g , b = int(hexColor[0:2], 16), int(hexColor[2:4], 16), int(hexColor[4:6], 16)
        except ValueError:
            r , g , b = 256, 256, 256 
        if "07" == colorCls:
            a = 0.1
        else:
            a = 1.0 if colorCls in ["01", "02", "04"] else 0.5
            
        r , g , b = float(r) / 256 , float(g) / 256 , float(b) / 256
        return (r, g, b, a)
    
class LicColorDict(dict):
    def __missing__(self, k):
        color_error = "Could not find LDraw Color: %d - Using Black" % k
        writeLogEntry(color_error , "LicColorDict")
        black = LicColor.black()
        self[k] = black  # Store for future lookups - chances are, if one call failed, many more will
        print color_error
        return black

def writeLogEntry(message , sender="UnknownDeliverer"):
    logging.error('------------------------------------------------------\n {0} => {1}'.format(sender , message))


# lambda is bound dynamically to the last variable used, so we can't 
# use it in a loop for creating menu actions.  Use this instead.
# usage: menu.addAction("menu text", makeFunc(self.moveToCallout, callout))
def makeFunc(func, arg):
    def f(): func(arg)
    return f

def VariantToFloatList(v):
    return [i.toFloat()[0] for i in v.toList()]

def determinant3x3(m):
    # m must be in the form [[00, 01, 02], [10, 11, 12], [20, 21, 22]]
    d1 = m[0][0] * ((m[1][1] * m[2][2]) - (m[1][2] * m[2][1]))
    d2 = m[0][1] * ((m[1][0] * m[2][2]) - (m[1][2] * m[2][0]))
    d3 = m[0][2] * ((m[1][0] * m[2][1]) - (m[1][1] * m[2][0]))
    return d1 - d2 + d3

def multiplyMatrices(matrix1, matrix2):
    # m1 & m2 must be in the form [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    # ie, matrix list straigth from a Part
    m1 = listToMatrix(matrix1)
    m2 = listToMatrix(matrix2)
    m = [[0] * 4, [0] * 4, [0] * 4, [0] * 4]
    
    for i in range(4):
        for j in range(4):
            for k in range(4):
                m[i][j] += m1[i][k] * m2[k][j]
        
    return matrixToList(m)

def listToMatrix(l):
    return [l[0:4], l[4:8], l[8:12], l[12:16]]

def matrixToList(m):
    return m[0] + m[1] + m[2] + m[3]

def GLMatrixToXYZ(matrix):
    return [matrix[12], matrix[13], matrix[14]]

def getCodesFile():
    iniFile = os.path.join(partsCachePath(), 'codes.ini')
    return QSettings(QString(iniFile), QSettings.IniFormat)

def getWeightsFile():
    iniFile = os.path.join(partsCachePath(), 'weights.ini')
    return QSettings(QString(iniFile), QSettings.IniFormat)

def determinePartCode(strdata):
    """
    search LEGO equivalent for LDraw code - like 6268b.dat <=> 6268
    """
    # get access to database
    suplement = getCodesFile()
    
    # avoid case sensitivity
    strdata = strdata.upper()
    # prepare input value to search cross database
    name = "{0}/{1}.dat".format('Design', strdata)   
    # initiate output value
    result = 0
    
    # first check the database ,when value is not exists 
    # return what had been
    if strdata.__len__() > 3:
        txt = suplement.value(name, strdata).toString()
        res = re.split(r'\D', txt.toUpper())
        if res and res[0].__len__() > 3:
            result = res[0]
            
    # write name if not found in database with 0 value
    # 0 - mean: LDraw part code like 6268b.dat do not have assignment
    if result <= 0:
        suplement.setValue(name, 0)
    return result

def compareParts(p1, p2):
    if p1 and p2:
        b1 = p1.getPartBoundingBox()
        b2 = p2.getPartBoundingBox()
        
        if abs(b1.y1 - b2.y1) < 6.0:  # tops equal enough - 6 to handle technic pins in holes
            
            if abs(b1.y2 - b2.y2) < 4.0:  # bottoms equal enough too
                return cmp((-b1.z1, b1.x1), (-b2.z1, b2.x1))  # back to front, left to right
            
            if b1.y2 < b2.y2:  # compare bottoms
                return 1
            return -1
            
        if b1.y1 < b2.y1:  # compare tops
            return 1
    return -1

def getOffsetFromBox(direction, box):

    if direction == Qt.Key_Up or direction == Qt.Key_Down:
        return box.xSize()
    elif direction == Qt.Key_PageUp or direction == Qt.Key_PageDown:
        return box.ySize()
    elif direction == Qt.Key_Left or direction == Qt.Key_Right:
        return box.zSize()

def displacementToDistance(displacement, direction):

    if direction == Qt.Key_Up:
        return -displacement[0]
    elif direction == Qt.Key_Down:
        return displacement[0]
        
    elif direction == Qt.Key_PageUp:
        return -displacement[1]
    elif direction == Qt.Key_PageDown:
        return displacement[1]
        
    elif direction == Qt.Key_Left:
        return -displacement[2]
    elif direction == Qt.Key_Right:
        return displacement[2]
    return None

def distanceToDisplacement(distance, direction):

    displacement = [0.0, 0.0, 0.0]

    if direction == Qt.Key_Up:
        displacement[0] = -distance
    elif direction == Qt.Key_Down:
        displacement[0] = distance
        
    elif direction == Qt.Key_PageUp:
        displacement[1] = -distance
    elif direction == Qt.Key_PageDown:
        displacement[1] = distance
        
    elif direction == Qt.Key_Left:
        displacement[2] = -distance
    elif direction == Qt.Key_Right:
        displacement[2] = distance
    else:
        return None

    return displacement

def getDisplacementOffset(direction, initialOffset, box):

    offset = 60.0 if initialOffset else 0
    displacement = [0.0, 0.0, 0.0]

    if direction == Qt.Key_Up:
        displacement[0] -= offset + box.xSize()
    elif direction == Qt.Key_Down:
        displacement[0] += offset + box.xSize()
        
    elif direction == Qt.Key_PageUp:
        displacement[1] -= offset + box.ySize()
    elif direction == Qt.Key_PageDown:
        displacement[1] += offset + box.ySize()
        
    elif direction == Qt.Key_Left:
        displacement[2] -= offset + box.zSize()
    elif direction == Qt.Key_Right:
        displacement[2] += offset + box.zSize()
    else:
        return None

    return displacement
        
def getOppositeDirection(direction):
    if direction == Qt.Key_Up:
        return Qt.Key_Down
    if direction == Qt.Key_Down:
        return Qt.Key_Up
    if direction == Qt.Key_PageUp:
        return Qt.Key_PageDown
    if direction == Qt.Key_PageDown:
        return Qt.Key_PageUp
    if direction == Qt.Key_Left:
        return Qt.Key_Right
    if direction == Qt.Key_Right:
        return Qt.Key_Left

def snapToGrid(item):
    gridSpacing = 50
    x = gridSpacing * int(item.pos().x() / gridSpacing)
    y = gridSpacing * int(item.pos().y() / gridSpacing)
    item.setPos(x, y)

def polygonToCurvedPath(polygon, radius):
    
    path = QPainterPath()
    for i, pt in enumerate(polygon):
        
        #TODO: if two points are too close to draw the desired radius, either remove those points or draw at smaller radius
        px, py = polygon[i - 1] if i > 0 else polygon[-1]
        nx, ny = polygon[i + 1] if i < len(polygon) - 1 else polygon[0]
        x, y = pt
        
        if px == x:
            dy = y - py
            r = radius if dy < 0 else -radius
            p1 = QPointF(x, y + r)
        else:
            dx = x - px
            r = radius if dx < 0 else -radius
            p1 = QPointF(x + r, y)
        
        if x == nx:
            dy = y - ny
            r = radius if dy < 0 else -radius
            p2 = QPointF(x, y + r)
        else:
            dx = x - nx
            r = radius if dx < 0 else -radius
            p2 = QPointF(x + r, y)
        
        if i == 0:
            path.moveTo(p1)
        else:
            path.lineTo(p1)
        path.cubicTo(pt, pt, p2)

    path.closeSubpath()
    return path
    
def partlist_sortify(list_data):
    """
    Sort parts by y axis
    
    Reverse to sort in descending order,
    when all values is smaller than 0 (zero)
    to avoid  start "build in the air"
    """
    revTest = all( v.matrix[13] < 0 for v in list_data )
    
    list_data.sort(key=lambda i: i.y() ,reverse=revTest)      

def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.

    Based on code in: Django
    """
    value = unicodedata.normalize('NFKD', unicode(value))
    value = value.encode('ascii', 'ignore')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    value = re.sub('[-\s]+', '-', value)
    return value

def rangeify(regexp, value):
    """
    Split string, converts to integer, parsing only matched a pattern,
    and remove duplicates.
    
    """
    vals = []
    for r in value.split(","):
        if regexp.match(r) is not None:
            if str(r).find("-") > 0:
                rc = str(r).split("-")
                for i in range(int(rc[0]), int(rc[1]) + 1):
                    if i > 0:
                        vals.append(i)
            else:
                if int(r) > 0:
                    vals.append(int(r)) 
    vals = list(set(vals))   
    return vals
