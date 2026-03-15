import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QMessageBox
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from obspy import read

class TraceViewer(QDialog):
    def __init__(self, node, date, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Tracce nodo {node.label} - {date}")
        self.resize(800, 500)
        self.node = node
        self.date = date

        self.layout = QVBoxLayout(self)

        # Carica le tracce E/N/Z
        self.traces = self.load_traces_for_node_date()

        if not self.traces:
            QMessageBox.warning(
                self,
                "Dati assenti",
                "Nessun dato E/N/Z trovato per questo nodo e data."
            )
            lbl = QLabel("Non ci sono dati disponibili.\n\nVerifica la presenza dei file MiniSEED per tutte le componenti.")
            self.layout.addWidget(lbl)
            return

        # Label chiara
        comps = ', '.join(self.traces.keys())
        self.layout.addWidget(QLabel(f"Componenti trovate: {comps}"))

        # Figura matplotlib
        self.fig = Figure(figsize=(8, 4))
        self.canvas = FigureCanvas(self.fig)
        self.layout.addWidget(self.canvas)

        self.plot_traces()

    def load_traces_for_node_date(self):
        """
        Carica i dati E, N, Z (se disponibili) dal mapping node.data_files[date].
        Restituisce un dizionario: {"E": Stream, "N": Stream, "Z": Stream}
        """
        traces = {}
        if self.date not in self.node.data_files:
            return traces

        file_paths = self.node.data_files[self.date]   # {'E': path_E, 'N': path_N, 'Z': path_Z}
        for comp in ['E', 'N', 'Z']:
            fpath = file_paths.get(comp)
            if fpath and os.path.isfile(fpath):
                try:
                    traces[comp] = read(fpath)
                except Exception as e:
                    print(f"Errore caricando componente {comp} da {fpath}: {e}")
        return traces

    def plot_traces(self):
        colori = {"E": "r", "N": "g", "Z": "b"}
        ax = self.fig.add_subplot(111)
        plotted = 0
        for comp in ['E', 'N', 'Z']:
            if comp in self.traces and len(self.traces[comp]) > 0:
                stream = self.traces[comp][0]
                data = stream.data
                times = stream.times("matplotlib")
                ax.plot(times, data, label=comp, color=colori[comp])
                plotted += 1
        if plotted > 0:
            ax.set_xlabel("Tempo [s]")
            ax.set_ylabel("Accelerazione [counts o unità native]")
            ax.set_title(f"Tracce nodo {self.node.label} - {self.date}")
            ax.legend()
        else:
            ax.text(0.5, 0.5, "Nessuna traccia valida trovata",
                    ha="center", va="center", fontsize=14, color='gray')
        self.canvas.draw()