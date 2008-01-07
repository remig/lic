
CurrentColor = 16
ComplimentColor = 24

# Dictionary storing [R,G,B,name] values for each LDraw Color
colors = {
    0:  [0.13, 0.13, 0.13, 'Black'],
    1:  [0.00, 0.20, 0.70, 'Blue'],
    2:  [0.00, 0.55, 0.08, 'Green'],
    3:  [0.00, 0.60, 0.62, 'Teal'],
    4:  [0.77, 0.00, 0.15, 'Red'],
    5:  [0.87, 0.40, 0.58, 'Dark Pink'],
    6:  [0.36, 0.13, 0.00, 'Brown'],
    7:  [0.76, 0.76, 0.76, 'Grey'],
    8:  [0.39, 0.37, 0.32, 'Dark Grey'],
    9:  [0.42, 0.67, 0.86, 'Light Blue'],
    10: [0.42, 0.93, 0.56, 'Bright Green'],
    11: [0.20, 0.65, 0.65, 'Turquoise'],
    12: [1.00, 0.52, 0.48, 'Salmon'],
    13: [0.98, 0.64, 0.78, 'Pink'],
    14: [1.00, 0.86, 0.00, 'Yellow'],
    15: [1.00, 1.00, 1.00, 'White'],
    16: CurrentColor,
    17: [0.73, 1.00, 0.81, 'Pastel Green'],
    18: [0.99, 0.91, 0.59, 'Light Yellow'],
    19: [0.91, 0.81, 0.63, 'Tan'],  
    20: [0.84, 0.77, 0.90, 'Light Violet'],
    21: [0.88, 1.00, 0.69, 'Glow in the Dark'],
    22: [0.51, 0.00, 0.48, 'Violet'],
    23: [0.28, 0.20, 0.69, 'Violet Blue'],
    24: ComplimentColor,
    25: [0.98, 0.38, 0.00, 'Orange'],   
    26: [0.85, 0.11, 0.43, 'Magenta'],
    27: [0.84, 0.94, 0.00, 'Lime'],
    28: [0.77, 0.59, 0.31, 'Dark Tan'],
    
    32: [0.39, 0.37, 0.32, 0.90, 'Trans Gray'],
    33: [0.00, 0.13, 0.63, 0.90, 'Trans Blue'],
    34: [0.02, 0.39, 0.20, 0.90, 'Trans Green'],
    
    36: [0.77, 0.00, 0.15, 0.90, 'Trans Red'],
    37: [0.39, 0.00, 0.38, 'Trans Violet'], # missing alpha?
    
    40: [0.39, 0.37, 0.32, 0.90, 'Trans Gray'],
    41: [0.68, 0.94, 0.93, 0.95, 'Trans Light Cyan'],       
    42: [0.75, 1.00, 0.00, 0.90, 'Trans Flu Lime'],
    
    45: [0.87, 0.40, 0.58, 'Trans Pink'], # missing alpha?
    46: [0.79, 0.69, 0.00, 0.90, 'Trans Yellow'],
    47: [1.00, 1.00, 1.00, 0.90, 'Trans White'],
    
    57: [0.98, 0.38, 0.00, 0.80, 'Trans Flu Orange'],
    
    70: [0.41, 0.25, 0.15, 'Reddish Brown'],
    71: [0.64, 0.64, 0.64, 'Stone Gray'],
    72: [0.39, 0.37, 0.38, 'Dark Stone Gray'],
    
    134: [0.58, 0.53, 0.40, 'Pearl Copper'],
    135: [0.67, 0.68, 0.67, 'Pearl Gray'],
    
    137: [0.42, 0.48, 0.59, 'Pearl Sand Blue'],
    
    142: [0.84, 0.66, 0.29, 'Pearl Gold'],
    
    256: [0.13, 0.13, 0.13, 'Rubber Black'],
    
    272: [0.00, 0.11, 0.41, 'Dark Blue'],
    273: [0.00, 0.20, 0.70, 'Rubber Blue'],
    
    288: [0.15, 0.27, 0.17, 'Dark Green'],
    
    320: [0.47, 0.00, 0.11, 'Dark Red'],
    
    324: [0.77, 0.00, 0.15, 'Rubber Red'],
    
    334: [0.88, 0.43, 0.07, 'Chrome Gold'],
    335: [0.75, 0.53, 0.51, 'Sand Red'],
    
    366: [0.82, 0.51, 0.02, 'Earth Orange'],
    
    373: [0.52, 0.37, 0.52, 'Sand Violet'],
    
    375: [0.76, 0.76, 0.76, 'Rubber Gray'],
    
    378: [0.63, 0.74, 0.67, 'Sand Green'],
    379: [0.42, 0.48, 0.59, 'Sand Blue'],
    
    382: [0.91, 0.81, 0.63, 'Tan'], 

    431: [0.73, 1.00, 0.81, 'Pastel Green'],

    462: [1.00, 0.62, 0.02, 'Light Orange'],
    
    484: [0.70, 0.24, 0.00, 'Dark Orange'],
    
    494: [0.82, 0.82, 0.82, 'Electric Contact'],
    
    503: [0.90, 0.89, 0.85, 'Light Gray'],
    
    511: [1.00, 1.00, 1.00, 'Rubber White'],
}

complimentColors = [8, 9, 10, 11, 12, 13, 0, 8, 0, 1, 2, 3, 4, 5, 8, 8]

def convertToRGBA(LDrawColorCode):
    if LDrawColorCode == CurrentColor:
        return CurrentColor
    if LDrawColorCode == ComplimentColor:
        return ComplimentColor
    c  = colors[LDrawColorCode][0:-1]
    c.reverse()
    return c
    
def getColorName(LDrawColorCode):
    if LDrawColorCode == CurrentColor:
        return CurrentColor
    if LDrawColorCode == ComplimentColor:
        return ComplimentColor
    return colors[LDrawColorCode][-1]

def complimentColor(LDrawColorCode):
    if LDrawColorCode > len(complimentColors):
        return convertToRGBA(complimentColors[-1])
    return convertToRGBA(complimentColors[LDrawColorCode])
