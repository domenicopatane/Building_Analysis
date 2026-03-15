class Floor:
    def __init__(self, floor_id, label, z_base, x_offset, y_offset, width, height):
        """
        floor_id: int (es: -1, 0, 1)
        label: string ("Interrato", "Terra", ...)
        z_base: float, quota in metri rispetto all'inf-sin dell'interrato
        x_offset, y_offset: float, posizione di questo piano nell'edificio (origine sempre angolo inf-sin dell'interrato)
        width, height: float, dimensioni (in metri o normalizzate [0,1]) del piano
        """
        self.id = floor_id
        self.label = label
        self.z_base = z_base
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.width = width
        self.height = height

class Node3D:
    def __init__(self, node_id, x, y, z, floor_id, label=None):
        """
        x, y, z: posizione nel sistema globale riferito all'interrato!
        floor_id: riferimento all'id numerico del piano in cui si trova il nodo
        """
        self.id = node_id
        self.x = x
        self.y = y
        self.z = z
        self.floor_id = floor_id
        self.label = label or node_id