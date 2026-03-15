"""
Modulo health.py
----------------
Valuta lo stato di salute dei nodi accelerometrici: presenza dati, 'uptime', quantità file, mancanze per data/nodo.
Restituisce warning o segnali grafici (es. colore nodo).
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel

class HealthDialog(QDialog):
    """
    Finestra che visualizza lo stato di salute della rete: nodi attivi, mancanze file, overview del sistema.
    """
    def __init__(self, network, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stato di salute della rete")
        layout = QVBoxLayout(self)
        summary = ""
        for n in network.nodes:
            nfiles = len(n.data_files)
            summary += f"Nodo {n.label}: {nfiles} file trovati\n"
        info = QLabel(summary)
        layout.addWidget(info)
        self.setLayout(layout)