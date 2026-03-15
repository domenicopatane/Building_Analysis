"""
network.py -- Gestione rete multipiano e parsing file MiniSEED
Supporta nomi file tipo: S01_IT.NIS21..HNE.D.2026.069.mseed
"""

import os
from datetime import datetime

class Node:
    """
    Oggetto Nodo.
    Attributi:
        id (str): ID nodo (es. S01)
        x, y (float): posiz. normalizzata (0-1) sulla PNG del piano
        floor (int): piano del nodo (-1=interrato, 0=terra, 1=primo, ...)
        label (str): testo descrittivo
        data_files (dict): structure: { 'YYYYMMDD': { 'E': path, 'N': ..., 'Z': ... } }
    """
    def __init__(self, node_id, x, y, floor, label=None):
        self.id = node_id
        self.x = x
        self.y = y
        self.floor = floor
        self.label = label or node_id
        self.data_files = dict()

class Network:
    """
    Gestisce lista nodi e parsing file miniseed multipiano per dashboard.
    """
    def __init__(self):
        # Esempio: uno per piano. COORD normalizzate (0-1) rispetto alla PNG di piano.
        self.nodes = [
            Node("S01", 0.52, 0.76, -1, "Nodo S01 - Interrato"),
            Node("S02", 0.23, 0.29, 0, "Nodo S02 - Piano Terra"),
            Node("S03", 0.76, 0.30, 0, "Nodo S03 - Piano Terra"),
            Node("S04", 0.24, 0.29, 1, "Nodo S04 - Piano Primo"),
            Node("S05", 0.76, 0.29, 1, "Nodo S05 - Piano Primo"),
            # Puoi aggiungere altri nodi qui ...
        ]

    def find_node(self, node_id):
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def doy_to_ymd(self, year, doy):
        """Converte anno e giorno giuliano (001-366) in 'YYYYMMDD'."""
        dt = datetime.strptime(f"{year}{int(doy):03d}", "%Y%j")
        return dt.strftime("%Y%m%d")

    def update_data_files(self, data_folder_or_files):
        """
        Parsing file MiniSEED multipiano:
        atteso: S01_IT.NIS21..HNE.D.2026.069.mseed
        dove:
            S01 = ID nodo
            HNE/HNN/HNZ = componente (E/N/Z)
            2026 = anno
            069 = giorno giuliano (1-366)
        Può ricevere una CARTELLA o una LISTA di file.
        """
        import os
        ch_map = {'HNE': 'E', 'HNN': 'N', 'HNZ': 'Z'}
        node_ids = {n.id for n in self.nodes}
        for node in self.nodes:
            node.data_files.clear()

        # Se è una lista di file, processa quelli. Se è una cartella, lavora come prima.
        if isinstance(data_folder_or_files, (list, tuple)):
            files_iter = data_folder_or_files
            data_folder = os.path.dirname(files_iter[0]) if files_iter else ""
        else:
            data_folder = data_folder_or_files
            files_iter = [os.path.join(data_folder, fname)
                        for fname in os.listdir(data_folder)
                        if fname.endswith(".mseed")]

        for fpath in files_iter:
            fname = os.path.basename(fpath)
            if fname.endswith(".mseed"):
                parts = fname.split('.')
                # esempio parts: ['S01_IT', 'NIS21', '', 'HNE', 'D', '2026', '069', 'mseed']
                if len(parts) >= 7:
                    id_and_meta = parts[0]              # 'S01_IT'
                    node_id = id_and_meta.split('_')[0] # 'S01'
                    channel = parts[3]                  # 'HNE' (o HNN/HNZ)
                    if node_id in node_ids and channel in ch_map:
                        comp = ch_map[channel]
                        try:
                            year = int(parts[5])
                            doy = int(parts[6])
                            date = self.doy_to_ymd(year, doy)
                        except Exception:
                            continue
                        n = self.find_node(node_id)
                        if n:
                            if date not in n.data_files:
                                n.data_files[date] = {}
                            n.data_files[date][comp] = fpath