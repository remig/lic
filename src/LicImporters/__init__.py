"""
    LIC - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne
    Copyright (C) 2015 Jeremy Czajkowski

    This file (Importers.__init__.py) is part of LIC.

    LIC is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    You should have received a copy of the Creative Commons License
    along with this program.  If not, see http://creativecommons.org/licenses/by-sa/3.0/
"""

# Dictionary of all registered importers & the files they handle
# Each entry is the name of the importer module and a tuple of the file types it supports.
# First item in file type list should be a string representation of the importer itself.

Importers = {
"LDrawImporter": ("LDraw", "dat", "ldr", "mpd"),
"BuilderImporter": ("3D Builder", "l3b"),
# "LDDImporter":   ("LDD - NYI", "lxf"),
}

def getImporter(fileType):
    for importer, fileTypeList in Importers.items():
        fileTypeList = [f.lower() for f in fileTypeList]
        if fileType.lower() in fileTypeList:
            return importer
    return None

def getFileTypesString():
    return __fileTypes

def getFileTypesList():
    fileList = []
    for fileTypes in Importers.values():
        fileList += fileTypes[1:]
    return ['.' + f for f in fileList]

def __buildFileTypes():
    # (("LDraw", "mpd", "ldr", "dat"), ("LDD", "lxf"))
    # to
    # "LDD (*.lxf);;LDraw (*.mpd, *.ldr, *.dat)"

    formatString = ""
    for fileTypes in reversed(Importers.values()):
        formats = ['*.%s' % f.lower() for f in fileTypes[1:]]
        formatString += "%s (%s);;" % (fileTypes[0], " ".join(formats))
    return formatString[:-2]  # -2 to trim off trailing ;;

__fileTypes = __buildFileTypes()


