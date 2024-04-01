
import FreeCAD, os, csv, Part
from PySide import QtGui, QtCore
from FreeCAD import Gui

__dir__ = os.path.dirname(__file__)
iconPath = os.path.join(__dir__, "Resources", "icons")

class SheetMetalDefinition:
    def __init__(self, obj, radius, thickness, toolset, kfactor):
        '''Add properties to sheet metal definition'''
        obj.addProperty("App::PropertyLength", "Thickness", "Sheet metal parameter", "Thickness of the sheet metal").Thickness = thickness #float(thickness.replace(',', '.'))
        obj.addProperty("App::PropertyLength", "Radius", "Sheet metal parameter", "Inner bending radius").Radius = radius #float(radius.replace(',', '.'))
        obj.addProperty("App::PropertyFloatConstraint", "K_factor", "Sheet metal parameter", "K-factor for unfolding").K_factor = kfactor #float(kfactor.replace(',', '.'))
        obj.addProperty("App::PropertyString", "Toolset", "Sheet metal parameter", "Geometry of bending tools (punch & die)").Toolset = toolset
        # obj.addProperty("App::PropertyBool", "isManuallyChanged", "Sheet metal parameter", 
        #                 "Feedback if parameter was manually changed. This wouldn't match the bending table any more and results in wrong unfold!"
        #                 ).isManuallyChanged = False
        obj.Proxy = self

    def onChanged(self, fp, prop):
        '''Do something when a property has changed'''
        FreeCAD.Console.PrintMessage("Change property: " + str(prop) + "\n")
        #smd = FreeCAD.ActiveDocument.getObject("Sheet_metal_definition")
        #smd.isManuallyChanged = True

    def execute(self, fp):
        '''Do something when doing a recomputation, this method is mandatory'''
        FreeCAD.Console.PrintMessage("Recompute Python sheet metal definition feature\n")
        smd = FreeCAD.ActiveDocument.getObject("Sheet_metal_definition")
        for obj in FreeCAD.ActiveDocument.Objects: # change params to those of the sheet metal definition object
            if 'isSheetMetal' in obj.PropertiesList:
                if obj.isSheetMetal == True:
                    obj.radius = smd.Radius
                    if 'thickness' in obj.PropertiesList:
                        obj.thickness = smd.Thickness # only in BaseBend
                    if 'kfactor' in obj.PropertiesList:
                        obj.kfactor = smd.K_factor # only in FoldWall
                    FreeCAD.activeDocument().recompute()
        # FreeCAD.Console.PrintError("Sheet metal definition overwritten manually!\r\n")


class ViewProviderSMDef:
    def __init__(self, obj):
        '''Set this object to the proxy object of the actual view provider'''
        obj.Proxy = self
        self.Object = obj.Object

    def attach(self, obj):
        '''Setup the scene sub-graph of the view provider, this method is mandatory'''
        self.Object = obj.Object
        return

    def updateData(self, fp, prop):
        return

    def dumps(self):
        '''When saving the document this object gets stored using Python's json module.\
                Since we have some un-serializable parts here -- the Coin stuff -- we must define this method\
                to return a tuple of all serializable objects or None.'''
        return None

    def loads(self,state):
        '''When restoring the serialized object from document we have the chance to set some internals here.\
                Since no data were serialized nothing needs to be done here.'''
        return None
    
    def getIcon(self):
        return os.path.join(iconPath, "SheetMetal_Definition.svg")

def showBendTableChooserWindow():
    smd_window.show()

class AddSheetMetalDefinitionCmd:
    """Add Sheet Metal Definition command"""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(iconPath, "SheetMetal_Definition.svg"),
            "MenuText": "Create a sheet metal definition",
            "ToolTip": "Holds values for radius, thickness and k-factor from csv table"
            #"MenuText": FreeCAD.Qt.translate("SheetMetal", "Make Base Wall"),
            #"Accel": "C, B",
            # "ToolTip": FreeCAD.Qt.translate(
            #     "SheetMetal",
            #     "Create a sheetmetal wall from a sketch\n"
            #     "1. Select a Skech to create bends with walls.\n"
            #     "2. Use Property editor to modify other parameters",
            # ),
        }

    def Activated(self):
        showBendTableChooserWindow()

    def IsActive(self):
        if FreeCAD.ActiveDocument:
            return True
        else:
            return False


class UiSmdWindow(object):
     def __init__(self, smd_window):
        self.window = smd_window
        smd_window.setObjectName("smd_window")
        smd_window.resize(500, 150)
        smd_window.setWindowTitle("Sheet Metal Definition from csv table")

        self.btnSelect = QtGui.QPushButton(smd_window)
        self.btnSelect.setGeometry(QtCore.QRect(330, 20, 150, 40))
        self.btnSelect.clicked.connect(self.on_btnSelect_clicked)
        self.btnSelect.setText("select")

        self.btnLoad = QtGui.QPushButton(smd_window)
        self.btnLoad.setGeometry(QtCore.QRect(20, 20, 150, 40))
        self.btnLoad.clicked.connect(self.on_btnLoad_clicked)
        self.btnLoad.setText("load bend table")
   
        # Label for delimiter
        self.labelDelimiter = QtGui.QLabel(smd_window)
        self.labelDelimiter.setGeometry(QtCore.QRect(180, 30, 80, 20))
        self.labelDelimiter.setText("csv delimiter:")
     
        # Delimiter
        self.txtFieldDelimiter = QtGui.QLineEdit(smd_window)
        self.txtFieldDelimiter.setGeometry(QtCore.QRect(260, 30, 20, 20))
        self.txtFieldDelimiter.setObjectName("txtDelimiter")
        self.txtFieldDelimiter.setText(",")
        self.txtFieldDelimiter.setAlignment(QtCore.Qt.AlignCenter)
        self.txtFieldDelimiter.setToolTip("set your delimiter here e.g. , ; : \\t |")

        self.comboBox = QtGui.QComboBox(smd_window)
        self.comboBox.setGeometry(QtCore.QRect(25, 80, 450, 25))
        self.csvList=[]
        # todo: window in foreground !!!

        # Label for pre selected csv bend table
        self.labelBendTable = QtGui.QLabel(smd_window)
        self.labelBendTable.setGeometry(QtCore.QRect(20, 120, 450, 20))

        if os.path.isfile(os.path.join(__dir__, "bendTablePath.txt")):
            try:
                with open(os.path.join(__dir__, "bendTablePath.txt"), 'r') as pathFile:
                    pathFileContent = pathFile.readlines() 
                    pathDelim = pathFileContent[0].replace('\n', '')
                    pathVar = pathFileContent[1]
                    try:
                        with open(pathVar, 'r') as path: # important: csv file encoding utf8 without BOM !!!
                            reader = csv.reader(path, delimiter = pathDelim)
                            self.csvList = list(reader)
                            for row in self.csvList:
                                self.comboBox.addItem(row[6])
                            self.txtFieldDelimiter.setText(pathDelim)
                            self.labelBendTable.setText(pathVar)
                            self.labelBendTable.setToolTip(pathVar)
                    except Exception:
                        FreeCAD.Console.PrintMessage("Couldn't read path from path file\n")
            except Exception:
                FreeCAD.Console.PrintMessage("Couldn't read path file\n")


     def on_btnLoad_clicked(self):
        openedFile = ""
        if self.labelBendTable.text() == "":
            path = __dir__
        else:
            path = self.labelBendTable.text()

        try:
            openedFile = QFileDialog.getOpenFileName(None, QString.fromLocal8Bit("Load .csv file"), path, "*.csv") # PyQt4
        except Exception:
            openedFile, Filter = QtGui.QFileDialog.getOpenFileName(None, "Load .csv file", path, "*.csv") #PySide
        if openedFile == "":
            FreeCAD.Console.PrintMessage("Process aborted, no file loaded"+"\n")
        else:
            try:
                file = open(openedFile, "r")
                try:
                    delim = self.txtFieldDelimiter.text()
                    reader = csv.reader(file, delimiter = delim)
                    self.csvList = list(reader)
                    for row in self.csvList:
                        self.comboBox.addItem(row[6])
                    self.labelBendTable.setText(openedFile)
                    self.labelBendTable.setToolTip(openedFile)

                    # write selected path to file
                    with open(os.path.join(__dir__, "bendTablePath.txt"), 'w') as pathFile:
                        pathFile.write(delim + "\n" + openedFile)
                except Exception:
                    FreeCAD.Console.PrintError("Error read file "+"\n") 
                finally:
                    file.close()
            except Exception:
                FreeCAD.Console.PrintError("Error in Open the file "+openedFile+"\n")


     def on_btnSelect_clicked(self):
        rowIndex = self.comboBox.currentIndex()

        radius = float((self.csvList[rowIndex][3]).replace(',', '.'))
        thickness = float((self.csvList[rowIndex][0]).replace(',', '.'))
        toolset = str(self.csvList[rowIndex][2] + self.csvList[rowIndex][5])
        kfactor = float((self.csvList[rowIndex][4]).replace(',', '.'))

        self.window.hide()
        createSheetMetalDefinition(radius, thickness, toolset, kfactor)

def createSheetMetalDefinition(radius, thickness, toolset, kfactor):
    if FreeCAD.ActiveDocument.getObject("Sheet_metal_definition"): # if sheet metal definition already exists
         FreeCAD.Console.PrintMessage("Sheet metal definition overwritten!\r\n")
         smd = FreeCAD.ActiveDocument.getObject("Sheet_metal_definition")
         smd.Radius = radius
         smd.Thickness = thickness
         smd.Toolset = toolset
    else:
        smd=FreeCAD.ActiveDocument.addObject("PartDesign::FeaturePython", "Sheet metal definition")
        SheetMetalDefinition(smd, radius, thickness, toolset, kfactor)
        ViewProviderSMDef(smd.ViewObject)
    
    # change all existing sheet metals to radius and thickness from bend table
    for obj in FreeCAD.ActiveDocument.Objects:
        if 'isSheetMetal' in obj.PropertiesList:
            if obj.isSheetMetal == True:
                obj.radius = radius
                if 'thickness' in obj.PropertiesList:
                    obj.thickness = thickness # only in BaseBend
                FreeCAD.activeDocument().recompute()

# Add button to WorkBench
Gui.addCommand("SMDefinition", AddSheetMetalDefinitionCmd())

smd_window = QtGui.QMainWindow()
ui = UiSmdWindow(smd_window)
smd_window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)