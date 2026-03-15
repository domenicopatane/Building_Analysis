import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QAction, QFileDialog, QMessageBox, QTabWidget,
    QPushButton, QHBoxLayout, QActionGroup, QSplitter
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from network import Network
from ui_building import BuildingWidget
from modules.trace_viewer import TraceViewer
from modules.health import HealthDialog
from modules.dataset_manager import DatasetManager
from modules.planimetria_nodi_gui import BuildingWidget as PlanimetriaNodiWidget

from building3d_widget import Building3DWidget

ASSETS_DIR = "assets"

class MainWindow(QMainWindow):
    def __init__(self, network):
        super().__init__()
        self.setWindowTitle("BSAFE Dashboard Reale - Multi Piano")
        self.setGeometry(100, 100, 1300, 780)
        self.network = network
        self.data_dir = None

        # --- BOOLEANS PER ATTIVAZIONE TAB ---
        self.config_caricata = False
        self.dati_sismici_caricati = False

        # --- MENU ---
        menubar = self.menuBar()
        data_menu = menubar.addMenu('&Data')
        building_menu = menubar.addMenu('&Building')
        tools_menu = menubar.addMenu('&Strumenti')

        import_config_action = QAction('Carica configurazione edificio...', self)
        import_config_action.triggered.connect(self.import_building_config)
        data_menu.addAction(import_config_action)

        plani_nodi_action = QAction('Gestione Planimetrie e Nodi', self)
        plani_nodi_action.triggered.connect(self.show_plani_nodi)
        data_menu.addAction(plani_nodi_action)

        change_dir_action = QAction('Carica Dati Sismici...', self)
        change_dir_action.triggered.connect(self.choose_data_dir)
        data_menu.addAction(change_dir_action)

        health_action = QAction('Stato di Salute Rete', self)
        health_action.triggered.connect(self.show_health)
        building_menu.addAction(health_action)

        oma_action = QAction('&Modulo Analisi Modale (soon)', self)
        oma_action.setDisabled(True)
        tools_menu.addAction(oma_action)

        # --- AREA GRAFICA ---
        self.tabs = QTabWidget()
        self.tab_map = QWidget()
        self.map_layout = QVBoxLayout(self.tab_map)

        # SPLITTER ORIZZONTALE (non si aggiunge ancora a tabs!)
        self.splitter = QSplitter()
        self.splitter.setOrientation(1)  # 1=Qt.Horizontal

        # ---- WIDGET 2D SINISTRA ----
        self.building = BuildingWidget(self.network, assets_dir=ASSETS_DIR)
        self.building.node_clicked_callback = self.show_traces_node
        self.building.setMinimumWidth(500)
        self.building.set_rectangular_view(True)
        self.building.current_floor = None

        # ---- AREA 3D (CONTAINER CON BOTTONI) ----
        self.area3d_container = QWidget()
        self.area3d_layout = QVBoxLayout(self.area3d_container)
        self.area3d_layout.setContentsMargins(0, 0, 0, 0)
        self.area3d_layout.setSpacing(4)

        self.building3d = Building3DWidget(
            get_floors=lambda: self.building.floors,
            get_nodes=lambda: self.building.nodes,
            node_clicked_callback=self.show_traces_node
        )
        self.building3d.setMinimumWidth(400)
        self.area3d_layout.addWidget(self.building3d)

        # ---- SOLO BARRA COMANDI SOTTO 3D! ----
        bar_bottom = QHBoxLayout()
        self.btn_rot = QPushButton("↻ Ruota")
        self.btn_incl = QPushButton("↕ Inclina")
        self.btn_z = QPushButton("⤒ Amplifica Z")
        self.btn_zoom_out_3d = QPushButton("Riduci 3D")
        self.btn_zoom_in_3d = QPushButton("Ingrandisci 3D")
        self.btn_rot.clicked.connect(self.building3d.rotate_view)
        self.btn_incl.clicked.connect(self.building3d.tilt_view)
        self.btn_z.clicked.connect(self.building3d.amplify_z_axis)
        self.btn_zoom_out_3d.clicked.connect(self.zoom_out_3d)
        self.btn_zoom_in_3d.clicked.connect(self.zoom_in_3d)
        bar_bottom.addWidget(self.btn_rot)
        bar_bottom.addWidget(self.btn_incl)
        bar_bottom.addWidget(self.btn_z)
        bar_bottom.addWidget(self.btn_zoom_out_3d)
        bar_bottom.addWidget(self.btn_zoom_in_3d)
        bar_bottom.addStretch()
        self.area3d_layout.addLayout(bar_bottom)

        # ---- AGGIUNTA ALLO SPLITTER ----
        self.splitter.addWidget(self.building)
        self.splitter.addWidget(self.area3d_container)

        self.map_layout.addWidget(self.splitter)

        self.tab_map.setLayout(self.map_layout)
        # --- NON aggiungere all'avvio ---
        # self.tabs.addTab(self.tab_map, "Planimetria e Nodi")
        self.setCentralWidget(self.tabs)

        self.statusBar().showMessage("Pronto. Carica configurazione e dati dai menu.")
        self.plani_nodi_widget = None

    def try_enable_piani_tab(self):
        if self.config_caricata and self.dati_sismici_caricati:
            if self.tabs.indexOf(self.tab_map) == -1:
                self.tabs.addTab(self.tab_map, "Planimetria e Nodi")
                w = self.width()
                self.splitter.setSizes([w//2, w//2])

    def zoom_out_3d(self):
        if hasattr(self.building3d, "zoom_out"):
            self.building3d.zoom_out()

    def zoom_in_3d(self):
        if hasattr(self.building3d, "zoom_in"):
            self.building3d.zoom_in()

    def choose_data_dir(self, initial=False):
        caption = "Seleziona la cartella Dati (contenente i file miniseed)"
        directory = QFileDialog.getExistingDirectory(self, caption)
        if directory:
            import glob
            # Mostra anche i file nelle SOTTOCARTELLE
            mseed_files = glob.glob(os.path.join(directory, "**", "*.mseed"), recursive=True)

            if not mseed_files:
                QMessageBox.warning(self, "Nessun file", "Nessun file .mseed trovato nella cartella.")
                return

            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QListWidgetItem
            dlg = QDialog(self)
            dlg.setWindowTitle("Seleziona i file .mseed da caricare")
            layout = QVBoxLayout(dlg)
            filelist = QListWidget()
            filelist.setSelectionMode(QListWidget.MultiSelection)
            for mf in mseed_files:
                item = QListWidgetItem(os.path.relpath(mf, directory))
                item.setData(Qt.UserRole, mf)
                filelist.addItem(item)
            filelist.selectAll()  # tutti selezionati di default
            layout.addWidget(filelist)
            btn_ok = QPushButton("Carica i file selezionati")
            layout.addWidget(btn_ok)
            btn_ok.clicked.connect(dlg.accept)
            dlg.setLayout(layout)
            if dlg.exec_():
                selected_files = [item.data(Qt.UserRole) for item in filelist.selectedItems()]
                if not selected_files:
                    QMessageBox.warning(self, "Nessuna selezione!", "Non hai selezionato nessun file.")
                    return
                self.data_dir = directory  # opzionale
                self.network.update_data_files(selected_files)
                self.dati_sismici_caricati = True
                self.statusBar().showMessage(f"File selezionati: {len(selected_files)}")
                self.building.repaint()
                self.building3d.render_scene()
                self.try_enable_piani_tab()
        elif initial:
            QMessageBox.warning(
                self,
                "Attenzione",
                "È necessario scegliere la cartella Dati per proseguire."
            )
            self.choose_data_dir(initial=True)

    def show_traces_node(self, node, date=None):
        data_files = getattr(node, "data_files", None)
        self.building.selected_node_id = node.id
        self.building.update()
        self.building3d.select_node(node.id)

        if not data_files:
            QMessageBox.warning(
                self, "Dati assenti",
                f"Nessun file trovato per {getattr(node,'label',getattr(node,'id',''))} (id: {getattr(node, 'id', '')})"
            )
            self.statusBar().showMessage(
                f"Nessun file trovato per {getattr(node,'label',getattr(node,'id',''))} (id: {getattr(node, 'id', '')})"
            )
            return
        if not date:
            date = sorted(data_files.keys())[-1]
        viewer = TraceViewer(node, date, self)
        viewer.exec_()
        self.statusBar().showMessage(f"Mostrate tracce di {getattr(node,'label',getattr(node,'id',''))} ({date})")

    def show_health(self):
        dlg = HealthDialog(self.network, self)
        dlg.exec_()
        self.statusBar().showMessage("Stato salute rete visualizzato.")

    def show_dataset_manager(self):
        dm = DatasetManager(self.network, self)
        if dm.exec_():
            node, date = dm.get_selection()
            self.show_traces_node(node, date)

    def show_plani_nodi(self):
        if self.plani_nodi_widget is None:
            self.plani_nodi_widget = PlanimetriaNodiWidget()
            self.plani_nodi_widget.floors_updated.connect(self.on_floors_updated)
            self.plani_nodi_widget.nodes_updated.connect(self.on_nodes_updated)
        self.plani_nodi_widget.show()
        self.plani_nodi_widget.raise_()

    def on_floors_updated(self, floor_list):
        if hasattr(self.building, "set_floors"):
            self.building.set_floors(floor_list)
        self.building3d.render_scene()
        self.statusBar().showMessage(f"Piani aggiornati da editor: {len(floor_list)} piani.")

    def on_nodes_updated(self, node_list):
        if hasattr(self.building, "set_nodes"):
            self.building.set_nodes(node_list)
        if hasattr(self.network, "nodes") and self.network.nodes is not node_list:
            self.network.nodes = node_list
        self.building3d.render_scene()
        self.statusBar().showMessage(f"Nodi aggiornati da editor: {len(node_list)} nodi.")

    def import_building_config(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Carica Configurazione Edificio", "config_edificio.json", "JSON (*.json)")
        if not fname:
            return
        with open(fname, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        from modules.building_cartesian_model import Floor, Node3D
        floors = []
        for f in data.get("floors", []):
            floor = Floor(f["id"], f["label"], f["z_base"], f["x_offset"], f["y_offset"], f["width"], f["height"])
            floors.append(floor)
        nodes = []
        for n in data.get("nodes", []):
            node_id_orig = n["id"]
            label = n["label"] if "label" in n else n["id"]
            node = Node3D(node_id_orig, n["x"], n["y"], n["z"], n["floor_id"], label)
            nodes.append(node)
        old_nodes_by_id = {getattr(nd, 'id', None): nd for nd in getattr(self.network, "nodes", [])}
        for n in nodes:
            if hasattr(n, 'id') and n.id in old_nodes_by_id:
                old = old_nodes_by_id[n.id]
                if hasattr(old, "data_files"):
                    n.data_files = old.data_files
        if hasattr(self.building, "set_floors"):
            self.building.set_floors(floors)
        if hasattr(self.building, "set_nodes"):
            self.building.set_nodes(nodes)
        if hasattr(self.network, "nodes") and self.network.nodes is not nodes:
            self.network.nodes = nodes
        self.config_caricata = True
        self.building3d.render_scene()
        self.statusBar().showMessage(f"Configurazione caricata: {len(floors)} piani, {len(nodes)} nodi")
        self.try_enable_piani_tab()

    def set_building_view(self, mode):
        if mode == "rect":
            if hasattr(self.building, "set_rectangular_view"):
                self.building.set_rectangular_view(True)
            self.action_view_rect.setChecked(True)
            self.action_view_png.setChecked(False)
            msg = "Vista schematica rettangolare multipiano"
        elif mode == "png":
            if hasattr(self.building, "set_png_view"):
                self.building.set_png_view()
            self.action_view_png.setChecked(True)
            self.action_view_rect.setChecked(False)
            msg = "Vista planimetria PNG"
        else:
            if hasattr(self.building, "visual_mode"):
                self.building.visual_mode = "none"
                self.building.update()
            msg = "Nessuna vista selezionata"
        self.statusBar().showMessage(msg)

if __name__ == "__main__":
    import pyqtgraph as pg
    pg.setConfigOptions(background='w', foreground='k')
    app = QApplication(sys.argv)
    net = Network()
    win = MainWindow(net)
    win.show()
    sys.exit(app.exec_())