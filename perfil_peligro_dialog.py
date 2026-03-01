import numpy as np
import random
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                 QPushButton, QCheckBox, QMessageBox, QFrame)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
# Se añade QgsColorButton para permitir la selección de colores nativa de QGIS
from qgis.gui import QgsVertexMarker, QgsMapLayerComboBox, QgsFieldComboBox, QgsColorButton
from qgis.core import QgsMapLayerProxyModel, QgsPointXY, QgsProject
from qgis.utils import iface

class ColorManagerDialog(QDialog):
    """Ventana emergente para asignar colores a las categorías encontradas en la capa"""
    def __init__(self, categorias, colores_actuales, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Colores de Peligro")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        self.color_widgets = {}

        # Crear una fila por cada categoría única detectada en el campo de la capa
        for cat in sorted(categorias):
            h_layout = QHBoxLayout()
            label = QLabel(str(cat))
            color_btn = QgsColorButton()
            color_btn.setAllowOpacity(True)
            
            # Recuperar color previo o asignar uno aleatorio si es una categoría nueva
            color = colores_actuales.get(cat, QColor(random.randint(0,255), random.randint(0,255), random.randint(0,255)))
            color_btn.setColor(color)
            
            h_layout.addWidget(label)
            h_layout.addStretch()
            h_layout.addWidget(color_btn)
            layout.addLayout(h_layout)
            self.color_widgets[cat] = color_btn

        self.btn_save = QPushButton("Guardar Cambios")
        self.btn_save.clicked.connect(self.accept)
        layout.addWidget(self.btn_save)

    def get_colors(self):
        """Retorna el diccionario de colores configurado por el usuario"""
        return {cat: btn.color() for cat, btn in self.color_widgets.items()}

class PerfilPeligroDialog(QDialog):
    session_settings = {'line_id': None, 'poly_id': None, 'dem_id': None, 'field': None, 'colors': {}, 'real_scale': False}

    def __init__(self, parent=iface.mainWindow()):
        super().__init__(parent)
        self.setWindowTitle("Perfil Topográfico con Niveles de Peligro")
        self.resize(1000, 850)
        
        self.setWindowFlags(Qt.Window) 
        self.setModal(False)

        self.marker = None
        self.puntos_geo = []
        # Diccionario que almacenará los colores personalizados
        self.peligroColors = PerfilPeligroDialog.session_settings['colors']

        self._setup_ui()
        self._restore_session()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        config_frame = QFrame()
        config_layout = QVBoxLayout(config_frame)
        
        config_layout.addWidget(QLabel("Capa de perfil (línea):"))
        self.cb_line = QgsMapLayerComboBox()
        self.cb_line.setFilters(QgsMapLayerProxyModel.LineLayer)
        config_layout.addWidget(self.cb_line)

        config_layout.addWidget(QLabel("Capa de peligro (polígonos):"))
        self.cb_poly = QgsMapLayerComboBox()
        self.cb_poly.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        config_layout.addWidget(self.cb_poly)

        h_field = QHBoxLayout()
        self.cb_field = QgsFieldComboBox()
        self.btn_colors = QPushButton("Gestionar Colores")
        h_field.addWidget(self.cb_field)
        h_field.addWidget(self.btn_colors)
        config_layout.addLayout(h_field)

        config_layout.addWidget(QLabel("DEM (Raster):"))
        self.cb_dem = QgsMapLayerComboBox()
        self.cb_dem.setFilters(QgsMapLayerProxyModel.RasterLayer)
        config_layout.addWidget(self.cb_dem)

        self.cb_real_scale = QCheckBox("Usar escala real (1:1)")
        config_layout.addWidget(self.cb_real_scale)
        
        main_layout.addWidget(config_frame)

        btn_container = QHBoxLayout()
        self.btn_run = QPushButton("GENERAR PERFIL")
        self.btn_run.setFixedWidth(280)
        self.btn_run.setStyleSheet("""
            QPushButton { font-weight: bold; height: 32px; background-color: #5d5fef; color: white; border-radius: 4px; }
            QPushButton:hover { background-color: #4a4cdb; }
        """)
        btn_container.addStretch(); btn_container.addWidget(self.btn_run); btn_container.addStretch()
        main_layout.addLayout(btn_container)

        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.canvas = FigureCanvasQTAgg(self.fig)
        main_layout.addWidget(self.canvas)

    def _restore_session(self):
        s = PerfilPeligroDialog.session_settings
        if s['line_id']: self.cb_line.setLayer(QgsProject.instance().mapLayer(s['line_id']))
        if s['poly_id']: 
            lyr = QgsProject.instance().mapLayer(s['poly_id'])
            self.cb_poly.setLayer(lyr)
            self.cb_field.setLayer(lyr) # Asegurar que el campo reconozca la capa restaurada
        if s['dem_id']: self.cb_dem.setLayer(QgsProject.instance().mapLayer(s['dem_id']))
        if s['field']: self.cb_field.setField(s['field'])
        self.cb_real_scale.setChecked(s['real_scale'])

    def _save_session(self):
        PerfilPeligroDialog.session_settings.update({
            'line_id': self.cb_line.currentLayer().id() if self.cb_line.currentLayer() else None,
            'poly_id': self.cb_poly.currentLayer().id() if self.cb_poly.currentLayer() else None,
            'dem_id': self.cb_dem.currentLayer().id() if self.cb_dem.currentLayer() else None,
            'field': self.cb_field.currentField(),
            'colors': self.peligroColors,
            'real_scale': self.cb_real_scale.isChecked()
        })

    def _connect_signals(self):
        self.cb_poly.layerChanged.connect(self.cb_field.setLayer)
        self.btn_run.clicked.connect(self._run)
        # Se activa la conexión para el botón de colores
        self.btn_colors.clicked.connect(self._gestionar_colores)
        self.canvas.mpl_connect("motion_notify_event", self._on_move)

    def _gestionar_colores(self):
        """Lógica para abrir el gestor de colores basado en los datos de la capa"""
        layer = self.cb_poly.currentLayer()
        field = self.cb_field.currentField()
        
        if not layer or not field:
            QMessageBox.warning(self, "Aviso", "Selecciona primero la capa de polígonos y el campo de peligro.")
            return

        # Obtener valores únicos del campo seleccionado para generar la lista de colores
        idx = layer.fields().indexOf(field)
        categorias = layer.uniqueValues(idx)
        
        dlg = ColorManagerDialog(categorias, self.peligroColors, self)
        if dlg.exec_():
            self.peligroColors = dlg.get_colors()
            self._save_session()

    def _run(self):
        self._save_session()
        line_layer = self.cb_line.currentLayer()
        dem_layer = self.cb_dem.currentLayer()
        poly_layer = self.cb_poly.currentLayer()
        field = self.cb_field.currentField()

        if not all([line_layer, dem_layer, poly_layer, field]):
            QMessageBox.warning(self, "Configuración", "Faltan datos de entrada.")
            return

        features = list(line_layer.selectedFeatures()) or list(line_layer.getFeatures())
        if not features: return

        line_geom = features[0].geometry()
        step = dem_layer.rasterUnitsPerPixelX() or 1.0
        dist_array = np.arange(0, line_geom.length() + step, step)
        
        z_vals, etiquetas, puntos_geo, dist_final = [], [], [], []
        provider = dem_layer.dataProvider()
        polys = [(f.geometry(), str(f[field])) for f in poly_layer.getFeatures() if not f.geometry().isNull()]

        for d in dist_array:
            g = line_geom.interpolate(d)
            if g.isNull(): continue
            pt = g.asPoint()
            val, ok = provider.sample(QgsPointXY(pt.x(), pt.y()), 1)
            
            if ok and val is not None and not np.isnan(val):
                z_vals.append(val)
                puntos_geo.append(pt)
                dist_final.append(d)
                
                nivel = "S/D"
                for p_geom, p_info in polys:
                    if p_geom.contains(g): nivel = p_info; break
                etiquetas.append(nivel)

        self.x_data, self.y_data, self.puntos_geo = np.array(dist_final), np.array(z_vals), puntos_geo
        self._plot(np.array(etiquetas))

    def _plot(self, etiquetas):
        self.ax.clear()
        self.ax.plot(self.x_data, self.y_data, color="#7f8c8d", lw=1.2, alpha=0.3, label="Terreno")

        unique_labels = sorted(set(etiquetas))
        for label in unique_labels:
            if label == "S/D": continue
            # Buscar el color definido por el usuario o usar negro por defecto
            color = self.peligroColors.get(label, QColor("black"))
            mask = (etiquetas == label)
            idx = np.where(mask)[0]
            if len(idx) == 0: continue
            
            grupos = np.split(idx, np.where(np.diff(idx) != 1)[0] + 1)
            for i, g in enumerate(grupos):
                p_idx = np.append(g, g[-1] + 1) if g[-1] + 1 < len(self.x_data) else g
                self.ax.plot(self.x_data[p_idx], self.y_data[p_idx], color=color.name(), 
                             lw=4, solid_capstyle='round', label=label if i == 0 else None)

        if self.cb_real_scale.isChecked(): self.ax.set_aspect('equal', adjustable='box')
        
        self.ax.legend(loc='best', frameon=True, framealpha=0.9, shadow=True, fontsize='small')
        self.ax.set_title("Perfil Topográfico con Peligro", fontsize=11, fontweight='bold')
        self.ax.set_xlabel("Distancia (m)"); self.ax.set_ylabel("Elevación (m)")
        self.ax.grid(True, ls=':', alpha=0.6)
        self.vline = self.ax.axvline(self.x_data[0], color="magenta", ls="--", visible=False)
        self.canvas.draw()

    def _on_move(self, event):
        if not event.inaxes or event.xdata is None or not hasattr(self, 'x_data') or len(self.x_data) == 0: return
        idx = np.abs(self.x_data - event.xdata).argmin()
        self.vline.set_xdata([self.x_data[idx]]); self.vline.set_visible(True)
        if self.marker: iface.mapCanvas().scene().removeItem(self.marker)
        self.marker = QgsVertexMarker(iface.mapCanvas())
        self.marker.setCenter(QgsPointXY(self.puntos_geo[idx].x(), self.puntos_geo[idx].y()))
        self.marker.setColor(Qt.magenta); self.marker.setIconType(QgsVertexMarker.ICON_X)
        self.canvas.draw_idle()