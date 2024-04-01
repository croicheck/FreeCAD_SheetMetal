# -*- coding: utf-8 -*-
##############################################################################
#
#  SheetMetalBend.py
#
#  Copyright 2015 Shai Seger <shaise at gmail dot com>
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 2 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
##############################################################################

from FreeCAD import Gui
from PySide import QtCore, QtGui

import FreeCAD, FreeCADGui, Part, os
import SheetMetalBaseCmd
__dir__ = os.path.dirname(__file__)
iconPath = os.path.join( __dir__, 'Resources', 'icons' )
smEpsilon = 0.0000001

# add translations path
LanguagePath = os.path.join( __dir__, 'translations')
Gui.addLanguagePath(LanguagePath)
Gui.updateLocale()

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = 'sm1.'

def smWarnDialog(msg):
    diag = QtGui.QMessageBox(
        QtGui.QMessageBox.Warning,
        FreeCAD.Qt.translate("QMessageBox", "Error in macro MessageBox"),
        msg,
    )
    diag.setWindowModality(QtCore.Qt.ApplicationModal)
    diag.exec_()

def smBelongToBody(item, body):
    if (body is None):
        return False
    for obj in body.Group:
        if obj.Name == item.Name:
            return True
    return False

def smIsPartDesign(obj):
    return str(obj).find("<PartDesign::") == 0

def smIsOperationLegal(body, selobj):
    #FreeCAD.Console.PrintLog(str(selobj) + " " + str(body) + " " + str(smBelongToBody(selobj, body)) + "\n")
    if smIsPartDesign(selobj) and not smBelongToBody(selobj, body):
        smWarnDialog(
            FreeCAD.Qt.translate(
                "QMessageBox",
                "The selected geometry does not belong to the active Body.\n"
                "Please make the container of this item active by\n"
                "double clicking on it.",
            )
        )
        return False
    return True

def smGetClosestVert(vert, face):
  closestVert = None
  closestDist = 99999999
  for v in face.Vertexes:
    if vert.isSame(v):
      continue
    d = vert.distToShape(v)[0]
    if (d < closestDist):
      closestDist = d
      closestVert = v
  return closestVert


# we look for a matching inner edge to the selected outer one
# this function finds a single vertex of that edge
def smFindMatchingVert(shape, edge, vertid):
  facelist = shape.ancestorsOfType(edge, Part.Face)
  edgeVerts = edge.Vertexes
  v = edgeVerts[vertid]
  vfacelist = shape.ancestorsOfType(v, Part.Face)

  # find the face that is not in facelist
  for vface in vfacelist:
    if not vface.isSame(facelist[0]) and not vface.isSame(facelist[1]):
      break

  return smGetClosestVert(v, vface)
  
def smFindEdgeByVerts(shape, vert1, vert2):
  for edge in shape.Edges:
    if vert1.isSame(edge.Vertexes[0]) and vert2.isSame(edge.Vertexes[1]):
      break
    if vert1.isSame(edge.Vertexes[1]) and vert2.isSame(edge.Vertexes[0]):
      break
  else:
    edge = None
  return edge

def smSolidBend(radius = 1.0, selEdgeNames = '', MainObject = None):
  InnerEdgesToBend = []
  OuterEdgesToBend = []
  for selEdgeName in selEdgeNames:
    edge = MainObject.getElement(selEdgeName)


    facelist = MainObject.ancestorsOfType(edge, Part.Face)

    # find matching inner edge to selected outer one    
    v1 = smFindMatchingVert(MainObject, edge, 0)
    v2 = smFindMatchingVert(MainObject, edge, 1)
    matchingEdge = smFindEdgeByVerts(MainObject, v1, v2)
    if matchingEdge is not None:
      InnerEdgesToBend.append(matchingEdge)
      OuterEdgesToBend.append(edge)
  
  if len(InnerEdgesToBend) > 0:
    # find thickness of sheet by distance from v1 to one of the edges comming out of edge[0]
    # we assume all corners have same thickness
    for dedge in MainObject.ancestorsOfType(edge.Vertexes[0], Part.Edge):
      if not dedge.isSame(edge):
        break
    
    thickness = v1.distToShape(dedge)[0]

    resultSolid = MainObject.makeFillet(radius, InnerEdgesToBend)
    resultSolid = resultSolid.makeFillet(radius + thickness, OuterEdgesToBend)

  return resultSolid

class SMSolidBend:
  def __init__(self, obj):
    '''"Add Bend to Solid" '''
    selobj = Gui.Selection.getSelectionEx()[0]

    _tip_ = FreeCAD.Qt.translate("App::Property","Bend Radius")
    if FreeCAD.ActiveDocument.getObject("Sheet_metal_definition"):
        obj.addProperty(
            "App::PropertyLength", "radius", "Parameters", _tip_
        ).radius = FreeCAD.ActiveDocument.getObject("Sheet_metal_definition"
        ).Radius
    else:
        obj.addProperty(
            "App::PropertyLength", "radius", "Parameters", _tip_
        ).radius = 1.0
    _tip_ = FreeCAD.Qt.translate("App::Property","Thickness of sheetmetal")
    if FreeCAD.ActiveDocument.getObject("Sheet_metal_definition"):
        obj.addProperty(
            "App::PropertyLength", "thickness", "Parameters", _tip_
        ).thickness = FreeCAD.ActiveDocument.getObject("Sheet_metal_definition"
        ).Thickness
    else:
        obj.addProperty(
            "App::PropertyLength", "thickness", "Parameters", _tip_
        ).thickness = 1.0
    obj.addProperty("App::PropertyBool", "isSheetMetal", "Sheet metal", "is Sheet Metal Feature")
    obj.isSheetMetal = True
    _tip_ = FreeCAD.Qt.translate("App::Property","Base object")
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", _tip_).baseObject = (selobj.Object, selobj.SubElementNames)
    obj.Proxy = self

  def getElementMapVersion(self, _fp, ver, _prop, restored):
      if not restored:
          return smElementMapVersion + ver

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    # pass selected object shape

    Main_Object = fp.baseObject[0].Shape.copy()
    s = smSolidBend(radius = fp.radius.Value, selEdgeNames = fp.baseObject[1],
                MainObject = Main_Object)
    fp.Shape = s
    fp.baseObject[0].ViewObject.Visibility = False


class SMBendViewProviderTree:
  "A View provider that nests children objects under the created one (Part WB style)"

  def __init__(self, obj):
    obj.Proxy = self
    self.Object = obj.Object

  def attach(self, obj):
    self.Object = obj.Object
    return

  def setupContextMenu(self, viewObject, menu):
    action = menu.addAction(FreeCAD.Qt.translate("QObject", "Edit %1").replace("%1", viewObject.Object.Label))
    action.triggered.connect(lambda: self.startDefaultEditMode(viewObject))
    return False

  def startDefaultEditMode(self, viewObject):
    document = viewObject.Document.Document
    if not document.HasPendingTransaction:
      text = FreeCAD.Qt.translate("QObject", "Edit %1").replace("%1", viewObject.Object.Label)
      document.openTransaction(text)
    viewObject.Document.setEdit(viewObject.Object, 0)

  def updateData(self, fp, prop):
    return

  def getDisplayModes(self,obj):
    modes=[]
    return modes

  def setDisplayMode(self,mode):
    return mode

  def onChanged(self, vp, prop):
    return

  def __getstate__(self):
    #        return {'ObjectName' : self.Object.Name}
    return None

  def __setstate__(self, state):
    self.loads(state)

  # dumps and loads replace __getstate__ and __setstate__ post v. 0.21.2
  def dumps(self):
    return None

  def loads(self, state):
    if state is not None:
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  def claimChildren(self):
    objs = []
    if hasattr(self.Object,"baseObject"):
      objs.append(self.Object.baseObject[0])
    return objs

  def getIcon(self):
    return os.path.join( iconPath , 'SheetMetal_AddBend.svg')

  def setEdit(self,vobj,mode):
    taskd = SMBendTaskPanel()
    taskd.obj = vobj.Object
    taskd.update()
    self.Object.ViewObject.Visibility=False
    self.Object.baseObject[0].ViewObject.Visibility=True
    FreeCADGui.Control.showDialog(taskd)
    return True

  def unsetEdit(self,vobj,mode):
    FreeCADGui.Control.closeDialog()
    self.Object.baseObject[0].ViewObject.Visibility=False
    self.Object.ViewObject.Visibility=True
    return False

class SMBendViewProviderFlat:
  "A View provider that place new objects under the base object (Part design WB style)"

  def __init__(self, obj):
    obj.Proxy = self
    self.Object = obj.Object

  def attach(self, obj):
    self.Object = obj.Object
    return

  def updateData(self, fp, prop):
    return

  def getDisplayModes(self,obj):
    modes=[]
    return modes

  def setDisplayMode(self,mode):
    return mode

  def onChanged(self, vp, prop):
    return

  def __getstate__(self):
    #        return {'ObjectName' : self.Object.Name}
    return None

  def __setstate__(self, state):
    self.loads(state)

  # dumps and loads replace __getstate__ and __setstate__ post v. 0.21.2
  def dumps(self):
    return None

  def loads(self, state):
    if state is not None:
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  def claimChildren(self):

    return []

  def getIcon(self):
    return os.path.join( iconPath , 'SheetMetal_AddBend.svg')

  def setEdit(self,vobj,mode):
    taskd = SMBendTaskPanel()
    taskd.obj = vobj.Object
    taskd.update()
    self.Object.ViewObject.Visibility=False
    self.Object.baseObject[0].ViewObject.Visibility=True
    FreeCADGui.Control.showDialog(taskd)
    return True

  def unsetEdit(self,vobj,mode):
    FreeCADGui.Control.closeDialog()
    self.Object.baseObject[0].ViewObject.Visibility=False
    self.Object.ViewObject.Visibility=True
    return False

class SMBendTaskPanel:
    '''A TaskPanel for the Sheetmetal'''
    def __init__(self):

      self.obj = None
      self.form = QtGui.QWidget()
      self.form.setObjectName("SMBendTaskPanel")
      self.form.setWindowTitle("Binded faces/edges list")
      self.grid = QtGui.QGridLayout(self.form)
      self.grid.setObjectName("grid")
      self.title = QtGui.QLabel(self.form)
      self.grid.addWidget(self.title, 0, 0, 1, 2)
      self.title.setText("Select new face(s)/Edge(s) and press Update")

      # tree
      self.tree = QtGui.QTreeWidget(self.form)
      self.grid.addWidget(self.tree, 1, 0, 1, 2)
      self.tree.setColumnCount(2)
      self.tree.setHeaderLabels(["Name","Subelement"])

      # buttons
      self.addButton = QtGui.QPushButton(self.form)
      self.addButton.setObjectName("addButton")
      self.addButton.setIcon(QtGui.QIcon(os.path.join( iconPath , 'SheetMetal_Update.svg')))
      self.grid.addWidget(self.addButton, 3, 0, 1, 2)

      QtCore.QObject.connect(self.addButton, QtCore.SIGNAL("clicked()"), self.updateElement)
      self.update()

    def isAllowedAlterSelection(self):
        return True

    def isAllowedAlterView(self):
        return True

    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Ok)

    def update(self):
      'fills the treewidget'
      self.tree.clear()
      if self.obj:
        f = self.obj.baseObject
        if isinstance(f[1],list):
          for subf in f[1]:
            #FreeCAD.Console.PrintLog("item: " + subf + "\n")
            item = QtGui.QTreeWidgetItem(self.tree)
            item.setText(0,f[0].Name)
            item.setIcon(0,QtGui.QIcon(":/icons/Tree_Part.svg"))
            item.setText(1,subf)
        else:
          item = QtGui.QTreeWidgetItem(self.tree)
          item.setText(0,f[0].Name)
          item.setIcon(0,QtGui.QIcon(":/icons/Tree_Part.svg"))
          item.setText(1,f[1][0])
      self.retranslateUi(self.form)

    def updateElement(self):
      if self.obj:
        sel = FreeCADGui.Selection.getSelectionEx()[0]
        if sel.HasSubObjects:
          obj = sel.Object
          for elt in sel.SubElementNames:
            if "Face" in elt or "Edge" in elt:
              face = self.obj.baseObject
              found = False
              if (face[0] == obj.Name):
                if isinstance(face[1],tuple):
                  for subf in face[1]:
                    if subf == elt:
                      found = True
                else:
                  if (face[1][0] == elt):
                    found = True
              if not found:
                self.obj.baseObject = (sel.Object, sel.SubElementNames)
        self.update()

    def accept(self):
        FreeCAD.ActiveDocument.recompute()
        FreeCADGui.ActiveDocument.resetEdit()
        #self.obj.ViewObject.Visibility=True
        return True

    def retranslateUi(self, SMUnfoldTaskPanel):
        #SMUnfoldTaskPanel.setWindowTitle(QtGui.QApplication.translate("draft", "Faces", None))
        self.addButton.setText(QtGui.QApplication.translate("draft", "Update", None))


class AddBendCommandClass():
  """Add Solid Bend command"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'SheetMetal_AddBend.svg'), # the name of a svg file available in the resources
            'MenuText': FreeCAD.Qt.translate('SheetMetal','Make Bend'),
            'Accel': "S, B",
            'ToolTip' : FreeCAD.Qt.translate('SheetMetal','Create Bend where two walls come together on solids\n'
            '1. Select edge(s) to create bend on corner edge(s).\n'
            '2. Use Property editor to modify parameters')}

  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    selobj = Gui.Selection.getSelectionEx()[0].Object
    viewConf = SheetMetalBaseCmd.GetViewConfig(selobj)
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
    if not smIsOperationLegal(activeBody, selobj):
        return
    doc.openTransaction("Add Bend")
    if activeBody is None or not smIsPartDesign(selobj):
      a = doc.addObject("Part::FeaturePython","SolidBend")
      SMSolidBend(a)
      SMBendViewProviderTree(a.ViewObject)
    else:
      #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
      a = doc.addObject("PartDesign::FeaturePython","SolidBend")
      SMSolidBend(a)
      SMBendViewProviderFlat(a.ViewObject)
      activeBody.addObject(a)
    SheetMetalBaseCmd.SetViewConfig(a, viewConf)
    if SheetMetalBaseCmd.autolink_enabled():
      root = SheetMetalBaseCmd.getOriginalBendObject(a)
      if root:
        a.setExpression("radius", root.Label + ".radius")
    FreeCADGui.Selection.clearSelection()
    doc.recompute()
    doc.commitTransaction()
    return

  def IsActive(self):
    if len(Gui.Selection.getSelection()) < 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
      return False
#    selobj = Gui.Selection.getSelection()[0]
    for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
      if type(selFace) != Part.Edge :
        return False
    return True

Gui.addCommand("SheetMetal_AddBend", AddBendCommandClass())

