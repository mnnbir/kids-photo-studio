import sys
import math
import os
from PyQt6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, 
                             QGraphicsPixmapItem, QGraphicsItem, QStyle, QGraphicsRectItem)
from PyQt6.QtGui import QPixmap, QClipboard, QPainter, QPen, QColor, QBrush, QTransform, QIcon
from PyQt6.QtCore import Qt, QRectF, QPointF

# --- 1. The Custom Image Logic ---
class DraggableImage(QGraphicsPixmapItem):
    def __init__(self, pixmap):
        super().__init__(pixmap)
        
        self.setAcceptHoverEvents(True) 
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setTransformOriginPoint(self.boundingRect().center())
        
        # State variables
        self.resizing = False
        self.hover_corner = False
        self.cropping_mode = False
        self.crop_start = None
        self.crop_end = None
        
        # Cloning variables
        self.cloning_mode = False
        self.clone_item = None
        self.start_scene_pos = None
        self.original_item_pos = None

    def rotate_90(self):
        """Spins the image 90 degrees."""
        transform = QTransform().rotate(90)
        new_pixmap = self.pixmap().transformed(transform, Qt.TransformationMode.SmoothTransformation)
        center_scene = self.mapToScene(self.boundingRect().center())
        
        self.setPixmap(new_pixmap)
        self.setTransformOriginPoint(self.boundingRect().center())
        
        new_center_scene = self.mapToScene(self.boundingRect().center())
        offset = center_scene - new_center_scene
        self.setPos(self.pos() + offset)

    def hoverMoveEvent(self, event):
        """Handles cursor changes for resizing."""
        if not self.isSelected() or self.cropping_mode:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            super().hoverMoveEvent(event)
            return

        pos = event.pos()
        rect = self.boundingRect()
        m = 40.0 / self.scale() if self.scale() > 0 else 40.0

        if (pos.x() < rect.left() + m and pos.y() < rect.top() + m) or \
           (pos.x() > rect.right() - m and pos.y() > rect.bottom() - m):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            self.hover_corner = True
        elif (pos.x() > rect.right() - m and pos.y() < rect.top() + m) or \
             (pos.x() < rect.left() + m and pos.y() > rect.bottom() - m):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            self.hover_corner = True
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.hover_corner = False
            
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        """Detects Ctrl key for cloning or regular movement."""
        # Check for CTRL + Drag (Cloning)
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and not self.cropping_mode:
            try: self.scene().views()[0].main_window.save_state()
            except: pass

            self.cloning_mode = True
            self.start_scene_pos = event.scenePos()
            self.original_item_pos = self.pos()
            
            # Create the clone
            self.clone_item = DraggableImage(self.pixmap())
            self.clone_item.setScale(self.scale())
            self.clone_item.setRotation(self.rotation())
            self.scene().addItem(self.clone_item)
            self.clone_item.setPos(self.original_item_pos)
            
            # Lock the original in place while we drag the new one
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            return

        # Regular Click Logic
        try: self.scene().views()[0].main_window.save_state()
        except: pass

        if self.cropping_mode:
            self.crop_start = event.pos()
            self.crop_end = event.pos()
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            return

        if getattr(self, 'hover_corner', False) and self.isSelected():
            self.resizing = True
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            self.start_scale = self.scale()
            self.start_mouse_pos = event.scenePos()
        else:
            self.resizing = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handles straight-line cloning and resizing."""
        if self.cloning_mode and self.clone_item:
            current_mouse_pos = event.scenePos()
            diff = current_mouse_pos - self.start_scene_pos
            
            dx = diff.x()
            dy = diff.y()
            
            # Snap to straight line (Axis locking)
            if abs(dx) > abs(dy):
                # Horizontal Move
                self.clone_item.setPos(self.original_item_pos.x() + dx, self.original_item_pos.y())
            else:
                # Vertical Move
                self.clone_item.setPos(self.original_item_pos.x(), self.original_item_pos.y() + dy)
            return

        if self.cropping_mode and self.crop_start:
            self.crop_end = event.pos()
            self.update()
            return

        if self.resizing:
            center_scene_pos = self.mapToScene(self.transformOriginPoint())
            def calc_dist(p1, p2): return math.hypot(p1.x() - p2.x(), p1.y() - p2.y())
            current_dist = calc_dist(event.scenePos(), center_scene_pos)
            start_dist = calc_dist(self.start_mouse_pos, center_scene_pos)
            if start_dist > 0:
                scale_ratio = current_dist / start_dist
                new_scale = self.start_scale * scale_ratio
                if new_scale > 0.05: self.setScale(new_scale)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Finishes resizing, cropping, or cloning."""
        if self.cloning_mode:
            self.cloning_mode = False
            self.clone_item = None
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            return

        if self.cropping_mode and self.crop_start:
            self.crop_end = event.pos()
            rect = QRectF(self.crop_start, self.crop_end).normalized()
            if rect.width() > 10 and rect.height() > 10:
                top_left_scene = self.mapToScene(rect.topLeft())
                cropped_pixmap = self.pixmap().copy(rect.toRect())
                self.setPixmap(cropped_pixmap)
                self.setPos(top_left_scene)
                self.setTransformOriginPoint(self.boundingRect().center())
            self.crop_start = self.crop_end = None
            self.cropping_mode = False
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            for view in self.scene().views():
                if hasattr(view.main_window, 'reset_crop_button'): view.main_window.reset_crop_button()
            self.update()
            return

        if self.resizing:
            self.resizing = False
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget):
        option.state &= ~QStyle.StateFlag.State_Selected 
        super().paint(painter, option, widget)
        if self.isSelected() and not self.cropping_mode:
            pen = QPen(Qt.GlobalColor.blue, max(3.0 / self.scale(), 1.0), Qt.PenStyle.DashLine)
            painter.setPen(pen)
            rect = self.boundingRect()
            painter.drawRect(rect)
            hs = max(30.0 / self.scale(), 5.0) 
            painter.setBrush(Qt.GlobalColor.blue)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(rect.left(), rect.top(), hs, hs))
            painter.drawRect(QRectF(rect.right() - hs, rect.top(), hs, hs))
            painter.drawRect(QRectF(rect.left(), rect.bottom() - hs, hs, hs))
            painter.drawRect(QRectF(rect.right() - hs, rect.bottom() - hs, hs, hs))
        if self.cropping_mode and self.crop_start and self.crop_end:
            rect = QRectF(self.crop_start, self.crop_end).normalized()
            painter.setPen(QPen(Qt.GlobalColor.red, max(3.0 / self.scale(), 1.0), Qt.PenStyle.SolidLine))
            painter.setBrush(QColor(255, 0, 0, 80)) 
            painter.drawRect(rect)


# --- 2. The Custom Interactive View ---
class CanvasView(QGraphicsView):
    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main_window = main_window
        self.setAcceptDrops(True) 
        self.setStyleSheet("background-color: #2b2b2b; border: none;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.main_window.save_state()
            drop_point = self.mapToScene(event.position().toPoint())
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                valid_exts = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.avif', '.heic', '.heif')
                if file_path.lower().endswith(valid_exts):
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        if pixmap.width() > 500 or pixmap.height() > 500:
                            pixmap = pixmap.scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        item = DraggableImage(pixmap)
                        self.scene().addItem(item)
                        item.setPos(drop_point.x() - (pixmap.width() / 2), drop_point.y() - (pixmap.height() / 2))
                        drop_point.setX(drop_point.x() + 30)
                        drop_point.setY(drop_point.y() + 30)
            event.acceptProposedAction()

# --- 3. The Main Application Window ---
class A4PrintStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KIDS PHOTO PRINTING STUDIO")
        if os.path.exists("app_icon.ico"): self.setWindowIcon(QIcon("app_icon.ico"))

        self.undo_stack = []
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 794, 1123) 
        self.paper = QGraphicsRectItem(0, 0, 794, 1123)
        self.paper.setBrush(QBrush(Qt.GlobalColor.white))
        self.paper.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(self.paper)

        self.view = CanvasView(self.scene, self)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(10, 10, 10, 10)

        self.undo_btn = QPushButton("↩️ UNDO")
        self.undo_btn.setStyleSheet("font-size: 20px; font-weight: bold; padding: 15px; background-color: #607D8B; color: white; border-radius: 8px;")
        self.undo_btn.clicked.connect(self.undo)
        self.undo_btn.setVisible(False) 

        self.paste_btn = QPushButton("📋 PASTE")
        self.paste_btn.setStyleSheet("font-size: 20px; font-weight: bold; padding: 15px; background-color: #4CAF50; color: white; border-radius: 8px;")
        self.paste_btn.clicked.connect(self.paste_image)

        self.reset_btn = QPushButton("🧹 RESET")
        self.reset_btn.setStyleSheet("font-size: 20px; font-weight: bold; padding: 15px; background-color: #9E9E9E; color: white; border-radius: 8px;")
        self.reset_btn.clicked.connect(self.reset_canvas)

        self.print_btn = QPushButton("🖨️ PRINT")
        self.print_btn.setStyleSheet("font-size: 20px; font-weight: bold; padding: 15px; background-color: #2196F3; color: white; border-radius: 8px;")
        self.print_btn.clicked.connect(self.print_canvas)

        # Contextual Tools
        self.delete_btn = QPushButton("🗑️ DELETE")
        self.delete_btn.setStyleSheet("font-size: 20px; font-weight: bold; padding: 15px; background-color: #f44336; color: white; border-radius: 8px;")
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_btn.setVisible(False)

        self.rotate_btn = QPushButton("🔃 ROTATE")
        self.rotate_btn.setStyleSheet("font-size: 20px; font-weight: bold; padding: 15px; background-color: #FF9800; color: white; border-radius: 8px;")
        self.rotate_btn.clicked.connect(self.rotate_selected)
        self.rotate_btn.setVisible(False)

        self.crop_btn = QPushButton("✂️ CROP")
        self.crop_btn.setStyleSheet("font-size: 20px; font-weight: bold; padding: 15px; background-color: #9C27B0; color: white; border-radius: 8px;")
        self.crop_btn.clicked.connect(self.toggle_crop_mode)
        self.crop_btn.setVisible(False)

        button_layout.addWidget(self.undo_btn)
        button_layout.addWidget(self.paste_btn)
        button_layout.addWidget(self.reset_btn)
        button_layout.addWidget(self.print_btn)
        button_layout.addStretch() 
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.rotate_btn)
        button_layout.addWidget(self.crop_btn)

        layout = QVBoxLayout()
        layout.addLayout(button_layout)
        layout.addWidget(self.view)
        layout.setContentsMargins(0,0,0,0) 
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.showMaximized()

    def get_scene_state(self):
        state = []
        for item in self.scene.items():
            if isinstance(item, DraggableImage):
                state.append({'pixmap': item.pixmap(), 'pos': item.pos(), 'scale': item.scale(), 'rot': item.rotation()})
        return state

    def states_are_equal(self, s1, s2):
        if len(s1) != len(s2): return False
        for a, b in zip(s1, s2):
            if a['pixmap'].cacheKey() != b['pixmap'].cacheKey() or a['pos'] != b['pos'] or a['scale'] != b['scale'] or a['rot'] != b['rot']: return False
        return True

    def save_state(self):
        new_state = self.get_scene_state()
        if self.undo_stack and self.states_are_equal(self.undo_stack[-1], new_state): return
        self.undo_stack.append(new_state)
        self.undo_btn.setVisible(True)

    def undo(self):
        if not self.undo_stack: return
        curr = self.get_scene_state()
        rest = None
        while self.undo_stack:
            prev = self.undo_stack.pop()
            if not self.states_are_equal(curr, prev):
                rest = prev
                break
        if rest:
            for i in self.scene.items():
                if isinstance(i, DraggableImage): self.scene.removeItem(i)
            for d in reversed(rest):
                it = DraggableImage(d['pixmap'])
                it.setPos(d['pos'])
                it.setScale(d['scale'])
                it.setRotation(d['rot'])
                self.scene.addItem(it)
        if not self.undo_stack: self.undo_btn.setVisible(False)
        self.scene.clearSelection()

    def reset_canvas(self):
        """Clears everything off the paper."""
        if not any(isinstance(i, DraggableImage) for i in self.scene.items()):
            return
        self.save_state()
        for i in self.scene.items():
            if isinstance(i, DraggableImage):
                self.scene.removeItem(i)
        self.on_selection_changed()

    def on_selection_changed(self):
        has = len(self.scene.selectedItems()) > 0
        self.delete_btn.setVisible(has)
        self.rotate_btn.setVisible(has)
        self.crop_btn.setVisible(has)
        if not has:
            for i in self.scene.items():
                if isinstance(i, DraggableImage): i.cropping_mode = False
            self.reset_crop_button()

    def delete_selected(self):
        self.save_state()
        for i in self.scene.selectedItems(): self.scene.removeItem(i)

    def rotate_selected(self):
        self.save_state()
        for i in self.scene.selectedItems():
            if isinstance(i, DraggableImage): i.rotate_90()

    def toggle_crop_mode(self):
        for i in self.scene.selectedItems():
            if isinstance(i, DraggableImage):
                i.cropping_mode = not i.cropping_mode
                if i.cropping_mode:
                    self.crop_btn.setText("🟩 DRAW BOX ON PHOTO TO CROP")
                    self.crop_btn.setStyleSheet("font-size: 20px; font-weight: bold; padding: 15px; background-color: #E91E63; color: white; border-radius: 8px;")
                else: self.reset_crop_button()
                i.update()

    def reset_crop_button(self):
        self.crop_btn.setText("✂️ CROP")
        self.crop_btn.setStyleSheet("font-size: 20px; font-weight: bold; padding: 15px; background-color: #9C27B0; color: white; border-radius: 8px;")

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace): self.delete_selected()
        elif event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Z: self.undo()
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def paste_image(self):
        clip = QApplication.clipboard()
        mime = clip.mimeData()
        if mime.hasImage():
            self.save_state() 
            px = QPixmap.fromImage(clip.image())
            if px.width() > 500 or px.height() > 500:
                px = px.scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            it = DraggableImage(px)
            self.scene.addItem(it)
            it.setPos((794 / 2) - (px.width() / 2), (1123 / 2) - (px.height() / 2))

    def print_canvas(self):
        self.scene.clearSelection() 
        prn = QPrinter(QPrinter.PrinterMode.HighResolution)
        if QPrintDialog(prn, self).exec() == QPrintDialog.DialogCode.Accepted:
            pnt = QPainter(prn)
            tr = QRectF(0, 0, prn.pageLayout().paintRectPixels(prn.resolution()).width(), prn.pageLayout().paintRectPixels(prn.resolution()).height())
            self.scene.render(pnt, tr, QRectF(0, 0, 794, 1123))
            pnt.end()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = A4PrintStudio()
    window.show()
    sys.exit(app.exec())