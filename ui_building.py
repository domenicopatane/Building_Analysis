from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont
from PyQt5.QtCore import Qt

class BuildingWidget(QWidget):
    def __init__(self, network, assets_dir="assets", parent=None):
        super().__init__(parent)
        self.network = network
        self.assets_dir = assets_dir
        self.node_clicked_callback = None
        self.setMouseTracking(True)
        self.last_tooltip_node = None
        self.current_floor = None   # Da gestire solo tramite main!
        self.floors = []
        self.nodes = self.network.nodes
        self.visual_mode = "rect"
        self.selected_node_id = None

        self.bg = self.get_bg_pixmap(0)
        self.setMinimumSize(self.bg.width(), self.bg.height())

    def set_current_floor(self, floor_id):
        self.current_floor = floor_id
        self.update()

    def set_floors(self, floors):
        self.floors = floors
        self.bg = self.get_bg_pixmap(self.current_floor)
        self.setMinimumSize(self.bg.width(), self.bg.height())
        self.update()

    def set_nodes(self, nodes):
        self.nodes = nodes
        if hasattr(self.network, 'nodes') and self.network.nodes is not nodes:
            self.network.nodes = nodes
        self.update()

    def set_rectangular_view(self, flag=True):
        self.visual_mode = "rect" if flag else "none"
        self.update()

    def set_png_view(self):
        self.visual_mode = "png"
        self.update()

    def get_bg_pixmap(self, floor):
        img_path = f"{self.assets_dir}/piano_{floor}.png"
        pix = QPixmap(img_path)
        if pix.isNull():
            pix = QPixmap(self.assets_dir + "/piano_placeholder.png")
        return pix

    def paintEvent(self, event):
        painter = QPainter(self)
        selected_floor = self.current_floor

        if self.visual_mode == "rect" and self.floors:
            margin = 35

            if selected_floor is None:
                N = len(self.floors)
                if N == 0:
                    painter.fillRect(self.rect(), Qt.white)
                    return

                max_w = max(f.width for f in self.floors)
                max_h = max(f.height for f in self.floors)
                if max_w <= 0 or max_h <= 0:
                    painter.fillRect(self.rect(), Qt.white)
                    return

                width_full = self.width() - 2 * margin
                height_maxrect = int((self.height() - margin * (N + 1)) / N)
                scale = min(width_full / max_w, height_maxrect / max_h)
                font = QFont("Arial", 11, QFont.Bold)
                for i, floor in enumerate(sorted(self.floors, key=lambda x: x.id, reverse=True)):
                    rect_w = int(floor.width * scale)
                    rect_h = int(floor.height * scale)
                    x_off = margin + int((width_full - rect_w) / 2)
                    y_off = margin + i * (height_maxrect + margin) + int((height_maxrect - rect_h) / 2)
                    painter.setFont(font)
                    floor_label_str = f"{floor.label} [ID {floor.id}]"  # <-- riferimento a z eliminato!
                    text_width = painter.fontMetrics().width(floor_label_str)
                    center_text = x_off + rect_w // 2 - text_width // 2
                    painter.drawText(center_text, y_off - 8, floor_label_str)
                    painter.setPen(Qt.black)
                    painter.setBrush(QColor(200, 230, 255, 100))
                    painter.drawRect(x_off, y_off, rect_w, rect_h)

                    # Assi e label
                    painter.drawLine(x_off, y_off + rect_h, x_off + rect_w, y_off + rect_h)  # asse x
                    painter.drawLine(x_off, y_off, x_off, y_off + rect_h)                   # asse y
                    painter.setFont(QFont("Arial", 10, QFont.Bold))
                    painter.drawText(x_off + rect_w - 10, y_off + rect_h + 16, "x")
                    painter.drawText(x_off - 18, y_off + 14, "y")
                    # painter.drawText(...) z eliminato

                    # Nodi
                    for n in self.nodes:
                        if getattr(n, "floor_id", getattr(n, "floor", None)) != floor.id:
                            continue
                        xn = x_off + int((n.x - floor.x_offset) / floor.width * rect_w)
                        yn = y_off + rect_h - int((n.y - floor.y_offset) / floor.height * rect_h)
                        if n.id == self.selected_node_id:
                            painter.setBrush(QColor(57, 92, 201, 230))
                        else:
                            painter.setBrush(QColor(40, 220, 40, 210))
                        painter.drawEllipse(xn - 8, yn - 8, 16, 16)
                        painter.setFont(QFont("Arial", 11, QFont.Bold))
                        painter.drawText(xn + 12, yn, getattr(n, "label", n.id))
                # Vista multipla: scritta eliminata!

            else:
                f = next((f for f in self.floors if f.id == selected_floor), None)
                if f is None:
                    painter.fillRect(self.rect(), Qt.white)
                    return
                max_w = f.width
                max_h = f.height
                width_full = self.width() - 2 * margin
                height_full = self.height() - 2 * margin
                scale = min(width_full / max_w, height_full / max_h)
                rect_w = int(f.width * scale)
                rect_h = int(f.height * scale)
                x_off = margin + int((width_full - rect_w) / 2)
                y_off = margin + int((height_full - rect_h) / 2)
                painter.setFont(QFont("Arial", 11, QFont.Bold))
                floor_label_str = f"{f.label} [ID {f.id}]"  # <-- riferimento a z eliminato!
                text_width = painter.fontMetrics().width(floor_label_str)
                center_text = x_off + rect_w // 2 - text_width // 2
                painter.drawText(center_text, y_off - 8, floor_label_str)
                painter.setPen(Qt.black)
                painter.setBrush(QColor(200, 230, 255, 100))
                painter.drawRect(x_off, y_off, rect_w, rect_h)

                # Assi e label
                painter.drawLine(x_off, y_off + rect_h, x_off + rect_w, y_off + rect_h)  # asse x
                painter.drawLine(x_off, y_off, x_off, y_off + rect_h)                   # asse y
                painter.setFont(QFont("Arial", 10, QFont.Bold))
                painter.drawText(x_off + rect_w - 10, y_off + rect_h + 16, "x")
                painter.drawText(x_off - 18, y_off + 14, "y")
                # painter.drawText(...) z eliminato

                # Nodi
                for n in self.nodes:
                    if getattr(n, "floor_id", getattr(n, "floor", None)) != f.id:
                        continue
                    xn = x_off + int((n.x - f.x_offset) / f.width * rect_w)
                    yn = y_off + rect_h - int((n.y - f.y_offset) / f.height * rect_h)
                    if n.id == self.selected_node_id:
                        painter.setBrush(QColor(57, 92, 201, 230))
                    else:
                        painter.setBrush(QColor(40, 220, 40, 210))
                    painter.drawEllipse(xn - 8, yn - 8, 16, 16)
                    painter.setFont(QFont("Arial", 11, QFont.Bold))
                    painter.drawText(xn + 12, yn, getattr(n, "label", n.id))
                painter.setFont(QFont("Arial", 9))
                painter.drawText(12, self.height() - 20, f"Vista Piano: {f.label}")

        elif self.visual_mode == "png" and selected_floor is not None:
            painter.drawPixmap(0, 0, self.bg)
            node_radius = 24
            for n in self.network.nodes:
                floor = getattr(n, "floor", getattr(n, "floor_id", None))
                if floor != selected_floor:
                    continue
                color = QColor("green") if getattr(n, "data_files", None) else QColor("red")
                if n.id == self.selected_node_id:
                    color = QColor(57, 92, 201, 230)
                x = int(n.x * self.bg.width())
                y = int(n.y * self.bg.height())
                painter.setBrush(color)
                painter.drawEllipse(x - node_radius // 2, y - node_radius // 2, node_radius, node_radius)
                painter.setFont(QFont("Arial", 11, QFont.Bold))
                painter.drawText(x - node_radius // 2 + 3, y + 6, n.id)
        else:
            painter.fillRect(self.rect(), Qt.white)

    def mousePressEvent(self, event):
        selected_floor = self.current_floor
        radius_sq = 16**2  # raggio selezione aumentato
        if self.visual_mode == "rect":
            margin = 35
            hit_node = None
            if selected_floor is None:
                N = len(self.floors)
                if N == 0:
                    return
                max_w = max(f.width for f in self.floors)
                max_h = max(f.height for f in self.floors)
                width_full = self.width() - 2 * margin
                height_maxrect = int((self.height() - margin * (N + 1)) / N)
                scale = min(width_full / max_w, height_maxrect / max_h)
                for i, floor in enumerate(sorted(self.floors, key=lambda x: x.id, reverse=True)):
                    rect_w = int(floor.width * scale)
                    rect_h = int(floor.height * scale)
                    x_off = margin + int((width_full - rect_w) / 2)
                    y_off = margin + i * (height_maxrect + margin) + int((height_maxrect - rect_h) / 2)
                    for n in self.nodes:
                        if getattr(n, "floor_id", getattr(n, "floor", None)) != floor.id:
                            continue
                        xn = x_off + int((n.x - floor.x_offset) / floor.width * rect_w)
                        yn = y_off + rect_h - int((n.y - floor.y_offset) / floor.height * rect_h)
                        if (event.x() - xn) ** 2 + (event.y() - yn) ** 2 < radius_sq:
                            hit_node = n
                            break
                    if hit_node: break
            else:
                f = next((f for f in self.floors if f.id == selected_floor), None)
                if f is None: return
                max_w = f.width
                max_h = f.height
                width_full = self.width() - 2 * margin
                height_full = self.height() - 2 * margin
                scale = min(width_full / max_w, height_full / max_h)
                rect_w = int(f.width * scale)
                rect_h = int(f.height * scale)
                x_off = margin + int((width_full - rect_w) / 2)
                y_off = margin + int((height_full - rect_h) / 2)
                for n in self.nodes:
                    if getattr(n, "floor_id", getattr(n, "floor", None)) != f.id:
                        continue
                    xn = x_off + int((n.x - f.x_offset) / f.width * rect_w)
                    yn = y_off + rect_h - int((n.y - f.y_offset) / f.height * rect_h)
                    if (event.x() - xn) ** 2 + (event.y() - yn) ** 2 < radius_sq:
                        hit_node = n
                        break
            if hit_node:
                self.selected_node_id = hit_node.id
                self.update()
                if self.node_clicked_callback:
                    self.node_clicked_callback(hit_node, None)
        elif self.visual_mode == "png":
            selected_floor = self.current_floor
            for n in self.network.nodes:
                floor = getattr(n, "floor", getattr(n, "floor_id", None))
                if floor != selected_floor:
                    continue
                x = int(n.x * self.bg.width())
                y = int(n.y * self.bg.height())
                if (event.x() - x) ** 2 + (event.y() - y) ** 2 < 24 ** 2:
                    self.selected_node_id = n.id
                    self.update()
                    if self.node_clicked_callback:
                        self.node_clicked_callback(n, None)
                    break

    def mouseMoveEvent(self, event):
        if self.visual_mode != "png":
            self.setToolTip("")
            return
        selected_floor = self.current_floor
        hovered = False
        for n in self.network.nodes:
            floor = getattr(n, "floor", getattr(n, "floor_id", None))
            if floor != selected_floor:
                continue
            x = int(n.x * self.bg.width())
            y = int(n.y * self.bg.height())
            if (event.x() - x) ** 2 + (event.y() - y) ** 2 < 24 ** 2:
                ultimo = max(n.data_files.keys()) if hasattr(n, "data_files") and n.data_files else 'nessuno'
                msg = f"{getattr(n, 'label', n.id)}\nUltimo file: {ultimo}"
                if msg != self.last_tooltip_node:
                    self.setToolTip(msg)
                    self.last_tooltip_node = msg
                hovered = True
                break
        if not hovered and self.last_tooltip_node is not None:
            self.setToolTip("")
            self.last_tooltip_node = None