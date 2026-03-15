import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QLineEdit, QListWidget, QComboBox, QGroupBox, QSpinBox, QMessageBox, QFileDialog
)
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import Qt, pyqtSignal

from .building_cartesian_model import Floor, Node3D

class BuildingWidget(QWidget):
    # SEGNALI: trasmettono la lista aggiornata piani/nodi
    floors_updated = pyqtSignal(list)
    nodes_updated = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Planimetria e Nodi - Editor (Multi-piano)")
        self.floors = []
        self.nodes = []
        self.init_ui()

    def init_ui(self):
        mainbox = QHBoxLayout(self)

        # ----- AREA INPUT A SINISTRA -----
        inputbox = QVBoxLayout()

        # --- Sezione gestione piani ---
        floor_group = QGroupBox("Gestione Piani")
        floor_layout = QFormLayout()
        self.floor_id_in = QSpinBox(); self.floor_id_in.setRange(-10, 20)
        self.floor_label_in = QLineEdit()
        self.z_base_in = QLineEdit(); self.z_base_in.setPlaceholderText("quota z (metri)")
        self.xoff_in = QLineEdit(); self.xoff_in.setPlaceholderText("x offset (0-1, tip. 0)")
        self.yoff_in = QLineEdit(); self.yoff_in.setPlaceholderText("y offset (0-1, tip. 0)")
        self.width_in = QLineEdit(); self.width_in.setPlaceholderText("width (0-1)")
        self.height_in = QLineEdit(); self.height_in.setPlaceholderText("height (0-1)")
        floor_layout.addRow("ID Piano:", self.floor_id_in)
        floor_layout.addRow("Nome Piano:", self.floor_label_in)
        floor_layout.addRow("Quota z:", self.z_base_in)
        floor_layout.addRow("x_offset (0-1):", self.xoff_in)
        floor_layout.addRow("y_offset (0-1):", self.yoff_in)
        floor_layout.addRow("Width (0-1):", self.width_in)
        floor_layout.addRow("Height (0-1):", self.height_in)
        self.add_floor_btn = QPushButton("Aggiungi Piano")
        self.add_floor_btn.clicked.connect(self.add_floor)
        floor_layout.addRow(self.add_floor_btn)
        self.floors_list = QListWidget()
        floor_layout.addRow(QLabel("Piani inseriti:"), self.floors_list)
        floor_group.setLayout(floor_layout)
        inputbox.addWidget(floor_group)

        # --- Sezione gestione nodi ---
        node_group = QGroupBox("Gestione Nodi")
        node_layout = QFormLayout()
        self.node_id_in = QLineEdit()
        self.node_label_in = QLineEdit()
        self.node_floor_in = QComboBox()
        self.x_in = QLineEdit(); self.x_in.setPlaceholderText("x (0-1)")
        self.y_in = QLineEdit(); self.y_in.setPlaceholderText("y (0-1)")
        self.z_in = QLineEdit(); self.z_in.setPlaceholderText("z (metri)")
        node_layout.addRow("ID Nodo:", self.node_id_in)
        node_layout.addRow("Label Nodo:", self.node_label_in)
        node_layout.addRow("Piano:", self.node_floor_in)
        node_layout.addRow("x (0-1):", self.x_in)
        node_layout.addRow("y (0-1):", self.y_in)
        node_layout.addRow("z (metri):", self.z_in)
        self.add_node_btn = QPushButton("Aggiungi Nodo")
        self.add_node_btn.clicked.connect(self.add_node)
        node_layout.addRow(self.add_node_btn)
        self.nodes_list = QListWidget()
        node_layout.addRow(QLabel("Nodi inseriti:"), self.nodes_list)
        node_group.setLayout(node_layout)
        inputbox.addWidget(node_group)

        # ----- Pulsanti esporta/importa configurazione -----
        btn_save = QPushButton("Esporta Configurazione")
        btn_save.clicked.connect(self.export_config)
        btn_load = QPushButton("Importa Configurazione")
        btn_load.clicked.connect(self.import_config)
        inputbox.addWidget(btn_save)
        inputbox.addWidget(btn_load)

        inputbox.addStretch()
        mainbox.addLayout(inputbox, 1)

        # ----- AREA CANVAS A DESTRA -----
        self.canvas = MultiFloorCanvas(self)
        mainbox.addWidget(self.canvas, 3)
        self.setLayout(mainbox)

    def add_floor(self):
        try:
            floor_id = int(self.floor_id_in.value())
            label = self.floor_label_in.text() or f"Piano {floor_id}"
            z_base = float(self.z_base_in.text() or "0.0")
            x_offset = float(self.xoff_in.text() or "0.0")
            y_offset = float(self.yoff_in.text() or "0.0")
            width = float(self.width_in.text() or "1.0")
            height = float(self.height_in.text() or "1.0")
        except ValueError:
            QMessageBox.warning(self, "Errore", "Tutti i campi devono essere numerici.")
            return
        floor = Floor(floor_id, label, z_base, x_offset, y_offset, width, height)
        self.floors.append(floor)
        # aggiorna combobox nodi
        self.node_floor_in.clear()
        for f in sorted(self.floors, key=lambda x:x.id):
            self.node_floor_in.addItem(f.label, f.id)
        self.floors_list.addItem(f"{label} (ID {floor_id}, z={z_base})")
        self.canvas.floors = self.floors  # aggiorna anche il canvas
        self.canvas.update()
        self.floors_updated.emit(self.floors)

    def add_node(self):
        if not self.floors:
            QMessageBox.warning(self, "Errore", "Aggiungi almeno un piano prima di inserire nodi!")
            return
        node_id = self.node_id_in.text() or f"N{len(self.nodes)+1}"
        label = self.node_label_in.text() or node_id
        try:
            floor_idx = self.node_floor_in.currentIndex()
            floor_id = self.node_floor_in.itemData(floor_idx)
            x = float(self.x_in.text())
            y = float(self.y_in.text())
            z = float(self.z_in.text())
        except Exception:
            QMessageBox.warning(self, "Errore", "Dati nodo non validi.")
            return
        node = Node3D(node_id, x, y, z, floor_id, label)
        self.nodes.append(node)
        self.nodes_list.addItem(f"{label} (floor {floor_id}, x={x}, y={y}, z={z})")
        self.canvas.nodes = self.nodes
        self.canvas.update()
        self.nodes_updated.emit(self.nodes)

    def export_config(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Esporta configurazione", "config_edificio.json", "JSON (*.json)")
        if not fname:
            return
        data = {
            "floors": [
                {
                    "id": f.id,
                    "label": f.label,
                    "z_base": f.z_base,
                    "x_offset": f.x_offset,
                    "y_offset": f.y_offset,
                    "width": f.width,
                    "height": f.height
                } for f in self.floors
            ],
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "x": n.x,
                    "y": n.y,
                    "z": n.z,
                    "floor_id": n.floor_id
                } for n in self.nodes
            ]
        }
        with open(fname, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)

    def import_config(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Importa configurazione", "config_edificio.json", "JSON (*.json)")
        if not fname:
            return
        with open(fname, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        self.floors.clear()
        self.nodes.clear()
        self.floors_list.clear()
        self.nodes_list.clear()
        self.node_floor_in.clear()
        for f in data.get("floors", []):
            floor = Floor(f["id"], f["label"], f["z_base"], f["x_offset"], f["y_offset"], f["width"], f["height"])
            self.floors.append(floor)
            self.floors_list.addItem(f'{floor.label} (ID {floor.id}, z={floor.z_base})')
        for f in sorted(self.floors, key=lambda x: x.id):
            self.node_floor_in.addItem(f.label, f.id)
        for n in data.get("nodes", []):
            node = Node3D(n["id"], n["x"], n["y"], n["z"], n["floor_id"], n["label"])
            self.nodes.append(node)
            self.nodes_list.addItem(f'{node.label} (floor {node.floor_id}, x={node.x}, y={node.y}, z={node.z})')

        self.canvas.floors = self.floors
        self.canvas.nodes = self.nodes
        self.canvas.update()
        self.floors_updated.emit(self.floors)
        self.nodes_updated.emit(self.nodes)

class MultiFloorCanvas(QWidget):
    """Disegna tutti i piani ognuno in uno slot verticale distinto."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.floors = []
        self.nodes = []

    def paintEvent(self, event):
        if not self.floors:
            return
        qp = QPainter(self)
        N = len(self.floors)
        margin = 35
        height_per_floor = int((self.height() - margin * (N + 1)) / N) if N > 0 else self.height()
        width_full = self.width() - 2 * margin

        font = QFont("Arial", 11, QFont.Bold)
        for i, floor in enumerate(sorted(self.floors, key=lambda x: x.id, reverse=True)):  # dall'alto piano superiore
            y_top = margin + i * (height_per_floor + margin)
            x_left = margin
            rect_w = int(floor.width * width_full)
            rect_h = int(floor.height * height_per_floor)
            x_off = x_left + int((width_full - rect_w) / 2)
            y_off = y_top + int((height_per_floor - rect_h) / 2)

            # --- DISEGNA LA SCRITTA DEL PIANO SOPRA il rettangolo ---
            qp.setFont(font)
            floor_label_str = f"{floor.label} [ID {floor.id}]   z:{floor.z_base}"
            text_width = qp.fontMetrics().width(floor_label_str)
            center_text = x_off + rect_w // 2 - text_width // 2
            qp.drawText(center_text, y_off - 8, floor_label_str)

            # Rettangolo Piano
            qp.setPen(Qt.black)
            qp.setBrush(QColor(200, 230, 255, 100))
            qp.drawRect(x_off, y_off, rect_w, rect_h)

            # Disegna solo nodi di questo piano
            qp.setBrush(QColor(40, 220, 40, 210))
            for node in self.nodes:
                if getattr(node, "floor_id", None) != floor.id:
                    continue
                xn = x_off + int((node.x - floor.x_offset) / floor.width * rect_w)
                yn = y_off + rect_h - int((node.y - floor.y_offset) / floor.height * rect_h)
                qp.drawEllipse(xn - 8, yn - 8, 16, 16)
                qp.drawText(xn + 12, yn, node.label)

        qp.setFont(QFont("Arial", 9))
        qp.drawText(12, 18, "Vista Multipla: tutti i piani (dal più alto in alto)")
# --- ENTRYPOINT ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = BuildingWidget()
    gui.resize(950, 800)
    gui.show()
    sys.exit(app.exec_())