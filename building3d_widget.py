import pyqtgraph.opengl as gl
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
import numpy as np

class Building3DWidget(QWidget):
    def __init__(self, get_floors, get_nodes, node_clicked_callback=None, parent=None):
        super().__init__(parent)
        self.get_floors = get_floors
        self.get_nodes = get_nodes
        self.node_clicked_callback = node_clicked_callback
        self.selected_node_id = None
        self._azimuth = 30
        self._elevation = 20
        self._z_amplify = 1.0

        main_layout = QVBoxLayout(self)
        self.view = gl.GLViewWidget()
        self.view.setCameraPosition(distance=2, elevation=self._elevation, azimuth=self._azimuth)
        main_layout.addWidget(self.view)
        self.meshes = []
        self.scatter = None

        self.render_scene()

        self.rotate_view = self._rotate_view
        self.tilt_view = self._tilt_view
        self.amplify_z_axis = self._amplify_z_axis

        self.view.mousePressEvent = self.mousePressEvent

    def _add_axes(self):
        axis_len = 1.1
        x_line = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [axis_len, 0, 0]]),
            color=QColor(0, 0, 0), width=2, antialias=True
        )
        self.view.addItem(x_line)
        y_line = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, axis_len, 0]]),
            color=QColor(0, 0, 0), width=2, antialias=True
        )
        self.view.addItem(y_line)
        z_line = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, 0, axis_len * self._z_amplify]]),
            color=QColor(0, 0, 0), width=2, antialias=True
        )
        self._z_line = z_line
        self.view.addItem(z_line)

    def _rotate_view(self):
        self._azimuth = (self._azimuth + 15) % 360
        self.view.setCameraPosition(azimuth=self._azimuth, elevation=self._elevation)

    def _tilt_view(self):
        self._elevation = (self._elevation + 10) % 90
        self.view.setCameraPosition(azimuth=self._azimuth, elevation=self._elevation)

    def _amplify_z_axis(self):
        self._z_amplify = 1.0 if self._z_amplify >= 3.0 else self._z_amplify + 1.0
        self.render_scene()

    def render_scene(self):
        while len(self.view.items) > 0:
            self.view.removeItem(self.view.items[0])
        self.meshes.clear()
        self._add_axes()
        floors = list(self.get_floors())
        for floor in floors:
            x, y, z = floor.x_offset, floor.y_offset, floor.z_base * self._z_amplify
            w, h = floor.width, floor.height
            verts = np.array([
                [x,      y,      z],
                [x + w,  y,      z],
                [x + w,  y + h,  z],
                [x,      y + h,  z],
            ])
            faces = np.array([[0, 1, 2], [0, 2, 3]])
            mesh = gl.GLMeshItem(
                vertexes=verts, faces=faces,
                color=(0, 0.8, 1, 0.25),
                drawEdges=True, edgeColor=(0, 0, 0, 1),
                shader='shaded', smooth=False
            )
            mesh.setGLOptions('translucent')
            self.view.addItem(mesh)
            self.meshes.append(mesh)
        if len(floors) > 1:
            w, h = floors[0].width, floors[0].height
            corners = [
                lambda f: (f.x_offset,          f.y_offset,          f.z_base * self._z_amplify),
                lambda f: (f.x_offset + w,      f.y_offset,          f.z_base * self._z_amplify),
                lambda f: (f.x_offset + w,      f.y_offset + h,      f.z_base * self._z_amplify),
                lambda f: (f.x_offset,          f.y_offset + h,      f.z_base * self._z_amplify),
            ]
            floors_sorted = sorted(floors, key=lambda f: f.z_base)
            for cfn in corners:
                line_pts = np.array([cfn(f) for f in floors_sorted])
                line = gl.GLLinePlotItem(
                    pos=line_pts,
                    color=(0, 0, 0, 1), width=1, antialias=True
                )
                self.view.addItem(line)
        nodes = self.get_nodes()
        if not nodes: return
        xs = np.array([float(n.x) for n in nodes])
        ys = np.array([float(n.y) for n in nodes])
        zs = np.array([float(getattr(n, 'z', 0.0)) * self._z_amplify for n in nodes])
        pos = np.c_[xs, ys, zs]

        # COLORAZIONE E DIMENSIONE identiche al 2D
        color = np.zeros((len(nodes), 4))
        size = np.array([16] * len(nodes))  # Diametro 16 px come il 2D (raggio 8)

        for i, n in enumerate(nodes):
            if hasattr(n, "id") and n.id == self.selected_node_id:
                # Blu selezionato (57,92,201) RGBA [0.223,0.361,0.788,0.9]
                color[i] = [57/255.0, 92/255.0, 201/255.0, 0.90]
            else:
                # Verde [40, 220, 40, 0.82]
                color[i] = [40/255.0, 220/255.0, 40/255.0, 0.82]

        self.scatter = gl.GLScatterPlotItem(pos=pos, color=color, size=size, pxMode=True)
        self.view.addItem(self.scatter)

    def select_node(self, node_id):
        self.selected_node_id = node_id
        self.render_scene()

    def mousePressEvent(self, ev):
        nodes = self.get_nodes()
        if not nodes or not self.scatter:
            return

        pts = np.array([[n.x, n.y, getattr(n, 'z', 0.0) * self._z_amplify] for n in nodes])
        mouse_x = ev.x()
        mouse_y = ev.y()
        w, h = self.view.width(), self.view.height()

        min_dist = float("inf")
        min_idx = None
        for idx, pos3d in enumerate(pts):
            x_range = np.ptp(pts[:, 0]) if np.ptp(pts[:, 0]) else 1
            y_range = np.ptp(pts[:, 1]) if np.ptp(pts[:, 1]) else 1

            norm_x = (pos3d[0] - np.min(pts[:, 0])) / x_range
            norm_y = (pos3d[1] - np.min(pts[:, 1])) / y_range

            scr_x = int(norm_x * w)
            scr_y = int((1 - norm_y) * h)  # invert Y per coordinata widget

            dist = (scr_x - mouse_x) ** 2 + (scr_y - mouse_y) ** 2
            if dist < min_dist:
                min_dist = dist
                min_idx = idx

        if min_idx is not None:
            n = nodes[min_idx]
            self.select_node(n.id)
            if self.node_clicked_callback:
                self.node_clicked_callback(n, None)

    def zoom_out(self):
        curr = self.view.opts.get('distance', 2.0)
        self.view.setCameraPosition(distance=curr * 1.2)

    def zoom_in(self):
        curr = self.view.opts.get('distance', 2.0)
        self.view.setCameraPosition(distance=max(curr * 0.8, 0.1))