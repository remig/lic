"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LDrawColors.py) is part of Lic.

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

CurrentColor = 16
ComplimentColor = 24

# Dictionary that stores [R,G,B,name] values for each LDraw Color code
# TODO: Read this from LDCONFIG.LDR
colors = {
    0:  [0.13, 0.13, 0.13, 1.0, 'Black'],
    1:  [0.00, 0.20, 0.70, 1.0, 'Blue'],
    2:  [0.00, 0.55, 0.08, 1.0, 'Green'],
    3:  [0.00, 0.60, 0.62, 1.0, 'Teal'],
    4:  [0.77, 0.00, 0.15, 1.0, 'Red'],
    5:  [0.87, 0.40, 0.58, 1.0, 'Dark Pink'],
    6:  [0.36, 0.13, 0.00, 1.0, 'Brown'],
    7:  [0.76, 0.76, 0.76, 1.0, 'Grey'],
    8:  [0.39, 0.37, 0.32, 1.0, 'Dark Grey'],
    9:  [0.42, 0.67, 0.86, 1.0, 'Light Blue'],
    10: [0.42, 0.93, 0.56, 1.0, 'Bright Green'],
    11: [0.20, 0.65, 0.65, 1.0, 'Turquoise'],
    12: [1.00, 0.52, 0.48, 1.0, 'Salmon'],
    13: [0.98, 0.64, 0.78, 1.0, 'Pink'],
    14: [1.00, 0.86, 0.00, 1.0, 'Yellow'],
    15: [1.00, 1.00, 1.00, 1.0, 'White'],
    16: CurrentColor,
    17: [0.73, 1.00, 0.81, 1.0, 'Pastel Green'],
    18: [0.99, 0.91, 0.59, 1.0, 'Light Yellow'],
    19: [0.91, 0.81, 0.63, 1.0, 'Tan'],  
    20: [0.84, 0.77, 0.90, 1.0, 'Light Violet'],
    21: [0.88, 1.00, 0.69, 1.0, 'Glow in the Dark'],
    22: [0.51, 0.00, 0.48, 1.0, 'Violet'],
    23: [0.28, 0.20, 0.69, 1.0, 'Violet Blue'],
    24: ComplimentColor,
    25: [0.98, 0.38, 0.00, 1.0, 'Orange'],   
    26: [0.85, 0.11, 0.43, 1.0, 'Magenta'],
    27: [0.84, 0.94, 0.00, 1.0, 'Lime'],
    28: [0.77, 0.59, 0.31, 1.0, 'Dark Tan'],
    
    32: [0.39, 0.37, 0.32, 0.70, 'Trans Gray'],
    33: [0.00, 0.13, 0.63, 0.70, 'Trans Blue'],
    34: [0.02, 0.39, 0.20, 0.70, 'Trans Green'],
    35: [0.00, 0.66, 0.66, 0.60, 'Trans Dark Cyan'],    
    36: [0.77, 0.00, 0.15, 0.70, 'Trans Red'],
    37: [0.39, 0.00, 0.38, 0.60, 'Trans Violet'],
    38: [0.40, 0.20, 0.00, 0.60, 'Trans Brown'],
    39: [0.59, 0.59, 0.59, 0.60, 'Trans Light Gray'],
    40: [0.40, 0.40, 0.34, 0.60, 'Trans Dark Gray'],
    41: [0.68, 0.94, 0.93, 0.75, 'Trans Light Cyan'],       
    42: [0.75, 1.00, 0.00, 0.70, 'Trans Lime'],
    43: [0.33, 0.66, 1.00, 0.60, 'Trans Cyan'],
    44: [1.00, 0.33, 0.33, 0.60, 'Trans Light Red'],
    45: [0.87, 0.40, 0.58, 0.60, 'Trans Pink'],
    46: [0.79, 0.69, 0.00, 0.70, 'Trans Yellow'],
    47: [1.00, 1.00, 1.00, 0.70, 'Trans White'],
    
    57: [0.98, 0.38, 0.00, 0.60, 'Trans Orange'],
    
    70: [0.41, 0.25, 0.15, 1.0, 'Reddish Brown'],
    71: [0.64, 0.64, 0.64, 1.0, 'Stone Gray'],
    72: [0.39, 0.37, 0.38, 1.0, 'Dark Stone Gray'],
    
    134: [0.58, 0.53, 0.40, 1.0, 'Pearl Copper'],
    135: [0.67, 0.68, 0.67, 1.0, 'Pearl Gray'],
    
    137: [0.42, 0.48, 0.59, 1.0, 'Pearl Sand Blue'],
    
    142: [0.84, 0.66, 0.29, 1.0, 'Pearl Gold'],
    
    256: [0.13, 0.13, 0.13, 1.0, 'Rubber Black'],
    
    272: [0.00, 0.11, 0.41, 1.0, 'Dark Blue'],
    273: [0.00, 0.20, 0.70, 1.0, 'Rubber Blue'],
    
    288: [0.15, 0.27, 0.17, 1.0, 'Dark Green'],
    
    320: [0.47, 0.00, 0.11, 1.0, 'Dark Red'],
    
    324: [0.77, 0.00, 0.15, 1.0, 'Rubber Red'],
    
    334: [0.88, 0.43, 0.07, 1.0, 'Chrome Gold'],
    335: [0.75, 0.53, 0.51, 1.0, 'Sand Red'],
    
    366: [0.82, 0.51, 0.02, 1.0, 'Earth Orange'],
    
    373: [0.52, 0.37, 0.52, 1.0, 'Sand Violet'],
    
    375: [0.76, 0.76, 0.76, 1.0, 'Rubber Gray'],
    
    378: [0.63, 0.74, 0.67, 1.0, 'Sand Green'],
    379: [0.42, 0.48, 0.59, 1.0, 'Sand Blue'],
    
    382: [0.91, 0.81, 0.63, 1.0, 'Tan'], 

    431: [0.73, 1.00, 0.81, 1.0, 'Pastel Green'],

    462: [1.00, 0.62, 0.02, 1.0, 'Light Orange'],
    
    484: [0.70, 0.24, 0.00, 1.0, 'Dark Orange'],
    
    494: [0.82, 0.82, 0.82, 1.0, 'Electric Contact'],
    
    503: [0.90, 0.89, 0.85, 1.0, 'Light Gray'],
    
    511: [1.00, 1.00, 1.00, 1.0, 'Rubber White'],

    512: [0.0, 0.0, 0.0, 1.0, 'True Black'],
}

complimentColors = [8, 9, 10, 11, 12, 13, 0, 8, 0, 1, 2, 3, 4, 5, 8, 8]

def isRealColor(LDrawColorCode):
    if LDrawColorCode not in colors:
        return False
    color = colors[LDrawColorCode]
    if isinstance(color, list) and len(color) == 5:
        return True
    return False

def convertToRGBA(LDrawColorCode):
    if LDrawColorCode == CurrentColor:
        return CurrentColor
    if LDrawColorCode == ComplimentColor:
        return ComplimentColor
    if LDrawColorCode not in colors:
        print "Could not find LDraw Color: %d - Using Black." % LDrawColorCode
        return colors[0][0:-1]  # Return Black
    return colors[LDrawColorCode][0:-1]
    
def getColorName(LDrawColorCode):
    if LDrawColorCode == CurrentColor:
        return CurrentColor
    if LDrawColorCode == ComplimentColor:
        return ComplimentColor
    if LDrawColorCode not in colors:
        print "Could not find LDraw Color: %d - Using Black." % LDrawColorCode
        return colors[0][-1]  # Return Black
    return colors[LDrawColorCode][-1]

def complimentColor(LDrawColorCode):
    if LDrawColorCode > len(complimentColors):
        return convertToRGBA(complimentColors[-1])
    return convertToRGBA(complimentColors[LDrawColorCode])
