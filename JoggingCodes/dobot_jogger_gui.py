# pip install PySide6 pydobotplus
import sys
import time
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QTextEdit,
    QMessageBox,
    QDoubleSpinBox,
)

from pydobotplus import Dobot


# ==============================================================================
# CONFIG
# ==============================================================================

DOBOT_PORT = "COM8"

DEFAULT_X = 230.0
DEFAULT_Y = 0.0
DEFAULT_Z = 90.0
DEFAULT_R = 0.0

DEFAULT_STEP = 2.0


# ==============================================================================
# SAFETY LIMITS
# ==============================================================================

X_MIN = 180.0
X_MAX = 310.0

Y_MIN = -120.0
Y_MAX = 120.0

Z_MIN = 40.0
Z_MAX = 120.0

R_MIN = -90.0
R_MAX = 90.0


# ==============================================================================
# SAFETY HELPERS
# ==============================================================================

def clamp_value(value, minimum, maximum):
    return max(minimum, min(maximum, float(value)))


def clamp_pose(x, y, z, r):
    safe_x = clamp_value(x, X_MIN, X_MAX)
    safe_y = clamp_value(y, Y_MIN, Y_MAX)
    safe_z = clamp_value(z, Z_MIN, Z_MAX)
    safe_r = clamp_value(r, R_MIN, R_MAX)

    was_clamped = (
        safe_x != float(x)
        or safe_y != float(y)
        or safe_z != float(z)
        or safe_r != float(r)
    )

    return safe_x, safe_y, safe_z, safe_r, was_clamped


# ==============================================================================
# DOBOT CONTROLLER
# ==============================================================================

class DobotController:
    def __init__(self, port):
        self.port = port
        self.device = None
        self.connected = False

    def connect(self):
        self.device = Dobot(port=self.port)
        time.sleep(1)

        self.device.clear_alarms()
        self.connected = True

    def close(self):
        if self.device is not None:
            self.device.close()

        self.connected = False

    def home(self):
        self._check()
        self.device.home()

    def move_to(self, x, y, z, r):
        self._check()

        safe_x, safe_y, safe_z, safe_r, was_clamped = clamp_pose(x, y, z, r)

        result = self.device.move_to(
            x=float(safe_x),
            y=float(safe_y),
            z=float(safe_z),
            r=float(safe_r)
        )

        return safe_x, safe_y, safe_z, safe_r, was_clamped, result

    def get_pose(self):
        self._check()

        if hasattr(self.device, "pose"):
            return self.device.pose()

        if hasattr(self.device, "get_pose"):
            return self.device.get_pose()

        raise AttributeError("No pose method found. Tried pose() and get_pose().")

    def _check(self):
        if self.device is None or not self.connected:
            raise RuntimeError("Dobot is not connected.")


# ==============================================================================
# MAIN GUI
# ==============================================================================

class DobotJoggerGUI(QMainWindow):
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Dobot Manual Jogger")
        self.resize(1050, 720)

        self.dobot = DobotController(DOBOT_PORT)
        self.dobot_connected = False
        self.move_busy = False

        self.x = DEFAULT_X
        self.y = DEFAULT_Y
        self.z = DEFAULT_Z
        self.r = DEFAULT_R
        self.step = DEFAULT_STEP

        self.log_signal.connect(self.log)

        self.build_ui()
        self.update_status()

    # --------------------------------------------------------------------------
    # UI
    # --------------------------------------------------------------------------

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)

        left = QVBoxLayout()
        right = QVBoxLayout()

        left.addWidget(self.create_connection_group())
        left.addWidget(self.create_position_group())
        left.addWidget(self.create_jog_group())
        left.addWidget(self.create_log_group())

        right.addWidget(self.create_manual_group())
        right.addWidget(self.create_instruction_group())

        root.addLayout(left, stretch=2)
        root.addLayout(right, stretch=2)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #202124;
            }

            QLabel {
                color: #f1f1f1;
                font-size: 14px;
            }

            QGroupBox {
                color: white;
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px 0 4px;
            }

            QPushButton {
                background-color: #3c4043;
                color: white;
                padding: 10px;
                border-radius: 6px;
                font-size: 14px;
            }

            QPushButton:hover {
                background-color: #5f6368;
            }

            QPushButton:pressed {
                background-color: #2b2c2f;
            }

            QDoubleSpinBox {
                background-color: #111;
                color: white;
                border: 1px solid #555;
                padding: 6px;
                font-size: 14px;
            }

            QTextEdit {
                background-color: #111;
                color: #00ff99;
                border: 1px solid #555;
                font-size: 13px;
            }
        """)

    def create_connection_group(self):
        box = QGroupBox("Connection")
        layout = QGridLayout(box)

        self.btn_connect = QPushButton("Connect Dobot")
        self.btn_disconnect = QPushButton("Disconnect Dobot")
        self.btn_home = QPushButton("Home Dobot")
        self.btn_get_pose = QPushButton("Get Current Coordinates")
        self.btn_emergency = QPushButton("EMERGENCY DISCONNECT")

        self.btn_connect.clicked.connect(self.connect_dobot)
        self.btn_disconnect.clicked.connect(self.disconnect_dobot)
        self.btn_home.clicked.connect(self.home_dobot)
        self.btn_get_pose.clicked.connect(self.get_current_pose)
        self.btn_emergency.clicked.connect(self.emergency_disconnect)

        self.btn_emergency.setStyleSheet(
            "background-color: #b00020; color: white; font-weight: bold;"
        )

        layout.addWidget(self.btn_connect, 0, 0)
        layout.addWidget(self.btn_disconnect, 0, 1)
        layout.addWidget(self.btn_home, 1, 0, 1, 2)
        layout.addWidget(self.btn_get_pose, 2, 0, 1, 2)
        layout.addWidget(self.btn_emergency, 3, 0, 1, 2)

        return box

    def create_position_group(self):
        box = QGroupBox("Current Jog Target")
        layout = QVBoxLayout(box)

        self.lbl_status = QLabel()
        self.lbl_status.setWordWrap(True)

        layout.addWidget(self.lbl_status)

        return box

    def create_jog_group(self):
        box = QGroupBox("Jog Buttons")
        layout = QGridLayout(box)

        btn_x_minus = QPushButton("X-")
        btn_x_plus = QPushButton("X+")

        btn_y_minus = QPushButton("Y-")
        btn_y_plus = QPushButton("Y+")

        btn_z_minus = QPushButton("Z-")
        btn_z_plus = QPushButton("Z+")

        btn_r_minus = QPushButton("R-")
        btn_r_plus = QPushButton("R+")

        btn_x_minus.clicked.connect(lambda: self.jog("x", -1))
        btn_x_plus.clicked.connect(lambda: self.jog("x", +1))

        btn_y_minus.clicked.connect(lambda: self.jog("y", -1))
        btn_y_plus.clicked.connect(lambda: self.jog("y", +1))

        btn_z_minus.clicked.connect(lambda: self.jog("z", -1))
        btn_z_plus.clicked.connect(lambda: self.jog("z", +1))

        btn_r_minus.clicked.connect(lambda: self.jog("r", -1))
        btn_r_plus.clicked.connect(lambda: self.jog("r", +1))

        layout.addWidget(QLabel("X Axis"), 0, 0)
        layout.addWidget(btn_x_minus, 0, 1)
        layout.addWidget(btn_x_plus, 0, 2)

        layout.addWidget(QLabel("Y Axis"), 1, 0)
        layout.addWidget(btn_y_minus, 1, 1)
        layout.addWidget(btn_y_plus, 1, 2)

        layout.addWidget(QLabel("Z Axis"), 2, 0)
        layout.addWidget(btn_z_minus, 2, 1)
        layout.addWidget(btn_z_plus, 2, 2)

        layout.addWidget(QLabel("R Axis"), 3, 0)
        layout.addWidget(btn_r_minus, 3, 1)
        layout.addWidget(btn_r_plus, 3, 2)

        return box

    def create_manual_group(self):
        box = QGroupBox("Manual Coordinate Input")
        layout = QGridLayout(box)

        self.spin_x = QDoubleSpinBox()
        self.spin_y = QDoubleSpinBox()
        self.spin_z = QDoubleSpinBox()
        self.spin_r = QDoubleSpinBox()
        self.spin_step = QDoubleSpinBox()

        for spin in [self.spin_x, self.spin_y, self.spin_z, self.spin_r]:
            spin.setRange(-500.0, 500.0)
            spin.setDecimals(2)

        self.spin_x.setValue(self.x)
        self.spin_y.setValue(self.y)
        self.spin_z.setValue(self.z)
        self.spin_r.setValue(self.r)

        self.spin_step.setRange(0.5, 50.0)
        self.spin_step.setDecimals(1)
        self.spin_step.setValue(self.step)

        self.spin_x.valueChanged.connect(self.spin_changed)
        self.spin_y.valueChanged.connect(self.spin_changed)
        self.spin_z.valueChanged.connect(self.spin_changed)
        self.spin_r.valueChanged.connect(self.spin_changed)
        self.spin_step.valueChanged.connect(self.step_changed)

        btn_move = QPushButton("Move to Entered Coordinates")
        btn_safe_start = QPushButton("Move to Safe Start")
        btn_apply_clamp = QPushButton("Clamp Values to Safe Range")

        btn_move.clicked.connect(self.move_to_spin_values)
        btn_safe_start.clicked.connect(self.move_to_safe_start)
        btn_apply_clamp.clicked.connect(self.apply_clamp_to_spins)

        layout.addWidget(QLabel("X"), 0, 0)
        layout.addWidget(self.spin_x, 0, 1)

        layout.addWidget(QLabel("Y"), 1, 0)
        layout.addWidget(self.spin_y, 1, 1)

        layout.addWidget(QLabel("Z"), 2, 0)
        layout.addWidget(self.spin_z, 2, 1)

        layout.addWidget(QLabel("R"), 3, 0)
        layout.addWidget(self.spin_r, 3, 1)

        layout.addWidget(QLabel("Jog Step"), 4, 0)
        layout.addWidget(self.spin_step, 4, 1)

        layout.addWidget(btn_move, 5, 0, 1, 2)
        layout.addWidget(btn_safe_start, 6, 0, 1, 2)
        layout.addWidget(btn_apply_clamp, 7, 0, 1, 2)

        return box

    def create_instruction_group(self):
        box = QGroupBox("Instruction Manual")
        layout = QVBoxLayout(box)

        manual = QTextEdit()
        manual.setReadOnly(True)

        manual.setPlainText(
            "DOBOT JOGGING MANUAL\n"
            "====================\n\n"

            "1. Before Running\n"
            "-----------------\n"
            "- Connect Dobot USB.\n"
            "- Close DobotStudio / DobotLab.\n"
            "- Check COM port in Device Manager.\n"
            "- Update DOBOT_PORT in code if needed.\n\n"

            "2. Starting\n"
            "-----------\n"
            "- Click Connect Dobot.\n"
            "- Click Home Dobot if required.\n"
            "- Use Move to Safe Start before testing.\n\n"

            "3. Jogging\n"
            "----------\n"
            "X+ / X- : move robot forward/backward in X\n"
            "Y+ / Y- : move robot left/right in Y\n"
            "Z+ / Z- : move robot up/down\n"
            "R+ / R- : rotate end effector\n\n"

            "4. Keyboard Shortcuts\n"
            "---------------------\n"
            "I : X+\n"
            "K : X-\n"
            "L : Y+\n"
            "J : Y-\n"
            "E : Z+\n"
            "Z : Z-\n"
            "O : R+\n"
            "U : R-\n"
            "H : Home\n"
            "P : Get current pose\n"
            "Q : Quit\n\n"

            "5. Safety Limits\n"
            "----------------\n"
            f"X range: {X_MIN} to {X_MAX}\n"
            f"Y range: {Y_MIN} to {Y_MAX}\n"
            f"Z range: {Z_MIN} to {Z_MAX}\n"
            f"R range: {R_MIN} to {R_MAX}\n\n"

            "If you enter values outside this range, the program clamps them.\n\n"

            "6. Recommended Testing\n"
            "----------------------\n"
            "- Start with Z high, around 90.\n"
            "- Use small step size: 1 or 2 mm.\n"
            "- Test X and Y movement slowly.\n"
            "- Do not lower Z until you are sure XY movement is correct.\n\n"

            "7. Emergency\n"
            "------------\n"
            "- Click EMERGENCY DISCONNECT.\n"
            "- If the robot still moves, turn off Dobot power physically.\n"
        )

        layout.addWidget(manual)

        return box

    def create_log_group(self):
        box = QGroupBox("Log")
        layout = QVBoxLayout(box)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(170)

        layout.addWidget(self.log_box)

        return box

    # --------------------------------------------------------------------------
    # STATUS / LOG
    # --------------------------------------------------------------------------

    def log(self, message):
        self.log_box.append(message)
        print(message)

    def update_status(self):
        self.lbl_status.setText(
            f"Dobot: {'Connected' if self.dobot_connected else 'Disconnected'}\n\n"
            f"Target Position:\n"
            f"X = {self.x:.2f}\n"
            f"Y = {self.y:.2f}\n"
            f"Z = {self.z:.2f}\n"
            f"R = {self.r:.2f}\n\n"
            f"Jog Step = {self.step:.2f}\n\n"
            f"Safe Limits:\n"
            f"X: {X_MIN} to {X_MAX}\n"
            f"Y: {Y_MIN} to {Y_MAX}\n"
            f"Z: {Z_MIN} to {Z_MAX}\n"
            f"R: {R_MIN} to {R_MAX}"
        )

    def set_spin_values(self):
        self.spin_x.blockSignals(True)
        self.spin_y.blockSignals(True)
        self.spin_z.blockSignals(True)
        self.spin_r.blockSignals(True)

        self.spin_x.setValue(self.x)
        self.spin_y.setValue(self.y)
        self.spin_z.setValue(self.z)
        self.spin_r.setValue(self.r)

        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(False)
        self.spin_z.blockSignals(False)
        self.spin_r.blockSignals(False)

    # --------------------------------------------------------------------------
    # DOBOT CONNECTION
    # --------------------------------------------------------------------------

    def connect_dobot(self):
        if self.dobot_connected:
            self.log("[DOBOT] Already connected.")
            return

        def worker():
            try:
                self.log_signal.emit(f"[DOBOT] Connecting on {DOBOT_PORT}...")
                self.dobot.connect()
                self.dobot_connected = True
                self.log_signal.emit("[DOBOT] Connected successfully.")
                self.update_status()
            except Exception as e:
                self.dobot_connected = False
                self.log_signal.emit(f"[DOBOT ERROR] Connection failed: {e}")
                self.update_status()

        threading.Thread(target=worker, daemon=True).start()

    def disconnect_dobot(self):
        try:
            self.dobot.close()
            self.dobot_connected = False
            self.log("[DOBOT] Disconnected.")
        except Exception as e:
            self.log(f"[DOBOT ERROR] Disconnect failed: {e}")

        self.update_status()

    def emergency_disconnect(self):
        try:
            self.dobot.close()
        except Exception:
            pass

        self.dobot_connected = False
        self.move_busy = False

        self.log("[EMERGENCY] Dobot connection closed.")

        QMessageBox.warning(
            self,
            "Emergency Disconnect",
            "Dobot connection was closed.\n\n"
            "If the arm is still moving, use the physical emergency stop or power switch."
        )

        self.update_status()

    def check_dobot_ready(self):
        if not self.dobot_connected:
            QMessageBox.warning(self, "Dobot Not Connected", "Connect Dobot first.")
            return False

        if self.move_busy:
            QMessageBox.warning(self, "Dobot Busy", "Wait for the current movement to finish.")
            return False

        return True

    # --------------------------------------------------------------------------
    # MOVEMENT
    # --------------------------------------------------------------------------

    def move_async(self, x, y, z, r, label="Move"):
        if not self.check_dobot_ready():
            return

        def worker():
            try:
                self.move_busy = True

                safe_x, safe_y, safe_z, safe_r, was_clamped, result = self.dobot.move_to(
                    x, y, z, r
                )

                self.x = safe_x
                self.y = safe_y
                self.z = safe_z
                self.r = safe_r

                self.log_signal.emit(
                    f"[DOBOT] {label}: X={safe_x:.2f}, Y={safe_y:.2f}, "
                    f"Z={safe_z:.2f}, R={safe_r:.2f}"
                )

                if result is not None:
                    self.log_signal.emit(f"[DOBOT RESULT] {result}")

                if was_clamped:
                    self.log_signal.emit("[SAFETY] Requested pose was outside limits and was clamped.")

                self.set_spin_values()
                self.update_status()

            except Exception as e:
                self.log_signal.emit(f"[DOBOT ERROR] {label} failed: {e}")

            finally:
                self.move_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def jog(self, axis, direction):
        if axis == "x":
            self.x += direction * self.step
        elif axis == "y":
            self.y += direction * self.step
        elif axis == "z":
            self.z += direction * self.step
        elif axis == "r":
            self.r += direction * self.step

        self.set_spin_values()
        self.update_status()

        self.move_async(self.x, self.y, self.z, self.r, label=f"Jog {axis.upper()}")

    def move_to_spin_values(self):
        self.x = self.spin_x.value()
        self.y = self.spin_y.value()
        self.z = self.spin_z.value()
        self.r = self.spin_r.value()

        confirm = QMessageBox.question(
            self,
            "Move Dobot",
            f"Move Dobot to:\n\n"
            f"X={self.x:.2f}\n"
            f"Y={self.y:.2f}\n"
            f"Z={self.z:.2f}\n"
            f"R={self.r:.2f}\n\n"
            f"The arm will move.",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        self.move_async(self.x, self.y, self.z, self.r, label="Manual Move")

    def move_to_safe_start(self):
        confirm = QMessageBox.question(
            self,
            "Move to Safe Start",
            f"Move Dobot to safe start?\n\n"
            f"X={DEFAULT_X}\n"
            f"Y={DEFAULT_Y}\n"
            f"Z={DEFAULT_Z}\n"
            f"R={DEFAULT_R}",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        self.x = DEFAULT_X
        self.y = DEFAULT_Y
        self.z = DEFAULT_Z
        self.r = DEFAULT_R

        self.set_spin_values()
        self.update_status()

        self.move_async(self.x, self.y, self.z, self.r, label="Safe Start")

    def home_dobot(self):
        if not self.check_dobot_ready():
            return

        confirm = QMessageBox.question(
            self,
            "Home Dobot",
            "Home Dobot now?\n\nThe arm will move.",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        def worker():
            try:
                self.move_busy = True
                self.log_signal.emit("[DOBOT] Homing started...")
                self.dobot.home()

                self.x = DEFAULT_X
                self.y = DEFAULT_Y
                self.z = DEFAULT_Z
                self.r = DEFAULT_R

                self.set_spin_values()
                self.update_status()

                self.log_signal.emit("[DOBOT] Homing completed.")

            except Exception as e:
                self.log_signal.emit(f"[DOBOT ERROR] Homing failed: {e}")

            finally:
                self.move_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def get_current_pose(self):
        if not self.check_dobot_ready():
            return

        try:
            pose = self.dobot.get_pose()
            self.log(f"[POSE] {pose}")

            if hasattr(pose, "x"):
                self.x = float(pose.x)
                self.y = float(pose.y)
                self.z = float(pose.z)
                self.r = float(pose.r)

                self.set_spin_values()
                self.update_status()

                self.log(
                    f"[COORDINATES] X={self.x:.2f}, Y={self.y:.2f}, "
                    f"Z={self.z:.2f}, R={self.r:.2f}"
                )

        except Exception as e:
            self.log(f"[DOBOT ERROR] Could not get pose: {e}")

    # --------------------------------------------------------------------------
    # SPIN BOX EVENTS
    # --------------------------------------------------------------------------

    def spin_changed(self):
        self.x = self.spin_x.value()
        self.y = self.spin_y.value()
        self.z = self.spin_z.value()
        self.r = self.spin_r.value()

        self.update_status()

    def step_changed(self):
        self.step = self.spin_step.value()
        self.update_status()

    def apply_clamp_to_spins(self):
        safe_x, safe_y, safe_z, safe_r, was_clamped = clamp_pose(
            self.spin_x.value(),
            self.spin_y.value(),
            self.spin_z.value(),
            self.spin_r.value()
        )

        self.x = safe_x
        self.y = safe_y
        self.z = safe_z
        self.r = safe_r

        self.set_spin_values()
        self.update_status()

        if was_clamped:
            self.log("[SAFETY] Values clamped to safe range.")
        else:
            self.log("[SAFETY] Values already inside safe range.")

    # --------------------------------------------------------------------------
    # KEYBOARD SHORTCUTS
    # --------------------------------------------------------------------------

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_I:
            self.jog("x", +1)
        elif key == Qt.Key_K:
            self.jog("x", -1)
        elif key == Qt.Key_L:
            self.jog("y", +1)
        elif key == Qt.Key_J:
            self.jog("y", -1)
        elif key == Qt.Key_E:
            self.jog("z", +1)
        elif key == Qt.Key_Z:
            self.jog("z", -1)
        elif key == Qt.Key_O:
            self.jog("r", +1)
        elif key == Qt.Key_U:
            self.jog("r", -1)
        elif key == Qt.Key_H:
            self.home_dobot()
        elif key == Qt.Key_P:
            self.get_current_pose()
        elif key == Qt.Key_Q:
            self.close()
        else:
            super().keyPressEvent(event)

    # --------------------------------------------------------------------------
    # CLOSE EVENT
    # --------------------------------------------------------------------------

    def closeEvent(self, event):
        try:
            self.dobot.close()
        except Exception:
            pass

        event.accept()


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    app = QApplication(sys.argv)

    window = DobotJoggerGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()