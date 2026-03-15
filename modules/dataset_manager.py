"""
Modulo dataset_manager.py
-------------------------
Gestisce la navigazione e selezione dei dataset giorno-nodo disponibili.
Permette di selezionare data e nodo e richiama i relativi file per la visualizzazione.
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton

class DatasetManager(QDialog):
    """
    Finestra/modulo per selezione rapida file multi-giorno.
    Offre combobox per data e nodo e ritorna selezione.
    """
    def __init__(self, network, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestione dataset multi-giorno")
        self.selected_node = None
        self.selected_date = None
        layout = QVBoxLayout(self)

        self.lbl = QLabel("Seleziona nodo e data")
        self.cb_node = QComboBox()
        self.cb_date = QComboBox()
        self.btn_ok = QPushButton("OK")

        self.network = network
        self.cb_node.addItems([n.label for n in network.nodes])
        self.cb_node.currentIndexChanged.connect(self.update_dates)
        self.btn_ok.clicked.connect(self.accept)

        layout.addWidget(self.lbl)
        layout.addWidget(self.cb_node)
        layout.addWidget(self.cb_date)
        layout.addWidget(self.btn_ok)
        self.setLayout(layout)
        self.update_dates()

    def update_dates(self):
        node = self.network.nodes[self.cb_node.currentIndex()]
        self.cb_date.clear()
        self.cb_date.addItems(list(sorted(node.data_files.keys())))

    def get_selection(self):
        node = self.network.nodes[self.cb_node.currentIndex()]
        date = self.cb_date.currentText()
        return node, date