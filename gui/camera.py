import math
from typing import Optional, Tuple

Vec3 = Tuple[float, float, float]

DEFAULT_ELEVATION: float = math.atan2(12, 8)   # góc nhìn mặc định, giữ như bản cũ
MIN_ELEVATION: float = math.radians(15)
MAX_ELEVATION: float = math.radians(85)        # dưới 90 độ để trục "lên" không bị suy biến
ORBIT_SENSITIVITY: float = 0.008               # radian trên mỗi điểm ảnh kéo
PAN_SENSITIVITY: float = 0.0016
ZOOM_STEP: float = 1.12
MIN_ZOOM_FACTOR: float = 0.35
MAX_ZOOM_FACTOR: float = 2.5
MIN_DISTANCE: float = 3.0
RESET_SECONDS: float = 0.35                    # thời gian đưa camera về vị trí mặc định


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class OrbitCamera:
    """Camera luôn nhìn vào một điểm trên mặt phẳng bản đồ, quay quanh điểm đó."""

    def __init__(
        self,
        center_x: float,
        center_z: float,
        distance: float,
        limits: Optional[Tuple[float, float, float, float]] = None,
    ) -> None:
        self.default_center: Tuple[float, float] = (center_x, center_z)
        self.default_distance: float = distance
        self.limits = limits          # (x nhỏ nhất, x lớn nhất, z nhỏ nhất, z lớn nhất) của điểm nhìn
        self.center_x: float = center_x
        self.center_z: float = center_z
        self.distance: float = distance
        self.yaw: float = 0.0
        self.elevation: float = DEFAULT_ELEVATION
        self._reset_from: Optional[Tuple[float, float, float, float, float]] = None
        self._reset_elapsed: float = 0.0
        self._reset_seconds: float = RESET_SECONDS

    def reset(self) -> None:
        """Về ngay vị trí mặc định."""
        self._reset_from = None
        self.center_x, self.center_z = self.default_center
        self.distance = self.default_distance
        self.yaw = 0.0
        self.elevation = DEFAULT_ELEVATION

    def start_reset(self, seconds: float = RESET_SECONDS) -> None:
        """Đưa camera về vị trí mặc định từ từ; bấm `seconds <= 0` thì về ngay."""
        if seconds <= 0:
            self.reset()
            return
        self._reset_from = (self.center_x, self.center_z, self.distance, self.yaw, self.elevation)
        self._reset_elapsed = 0.0
        self._reset_seconds = seconds

    @property
    def is_resetting(self) -> bool:
        return self._reset_from is not None

    def update(self, dt: float) -> None:
        """Tiến việc đặt lại camera (nếu đang chạy)."""
        if self._reset_from is None:
            return
        self._reset_elapsed += dt
        t = self._reset_elapsed / self._reset_seconds
        if t >= 1.0:
            self.reset()
            return
        k = _ease(t)
        x0, z0, d0, yaw0, el0 = self._reset_from
        yaw_delta = (0.0 - yaw0 + math.pi) % (2 * math.pi) - math.pi     # quay theo đường ngắn nhất
        self.center_x = x0 + (self.default_center[0] - x0) * k
        self.center_z = z0 + (self.default_center[1] - z0) * k
        self.distance = d0 + (self.default_distance - d0) * k
        self.yaw = yaw0 + yaw_delta * k
        self.elevation = el0 + (DEFAULT_ELEVATION - el0) * k

    @property
    def target(self) -> Vec3:
        return (self.center_x, 0.0, self.center_z)

    @property
    def eye(self) -> Vec3:
        horizontal = self.distance * math.cos(self.elevation)
        return (
            self.center_x + horizontal * math.sin(self.yaw),
            self.distance * math.sin(self.elevation),
            self.center_z + horizontal * math.cos(self.yaw),
        )

    def forward_ground(self) -> Tuple[float, float]:
        """Hướng nhìn chiếu xuống mặt phẳng bản đồ (x, z)."""
        return (-math.sin(self.yaw), -math.cos(self.yaw))

    def right_ground(self) -> Tuple[float, float]:
        return (math.cos(self.yaw), -math.sin(self.yaw))

    def orbit(self, dx: float, dy: float) -> None:
        """Kéo chuột (dx, dy điểm ảnh) để xoay quanh bản đồ."""
        self._reset_from = None
        self.yaw -= dx * ORBIT_SENSITIVITY
        self.yaw = (self.yaw + math.pi) % (2 * math.pi) - math.pi
        self.elevation = max(MIN_ELEVATION, min(MAX_ELEVATION, self.elevation + dy * ORBIT_SENSITIVITY))

    def zoom(self, steps: float) -> None:
        """steps dương là phóng to (lại gần), âm là thu nhỏ."""
        self._reset_from = None
        low = max(MIN_DISTANCE, self.default_distance * MIN_ZOOM_FACTOR)
        high = self.default_distance * MAX_ZOOM_FACTOR
        self.distance = max(low, min(high, self.distance * ZOOM_STEP ** (-steps)))

    def pan(self, dx: float, dy: float) -> None:
        """Kéo chuột để dịch điểm nhìn trên mặt phẳng bản đồ; cảnh đi theo con trỏ."""
        self._reset_from = None
        scale = self.distance * PAN_SENSITIVITY
        fx, fz = self.forward_ground()
        rx, rz = self.right_ground()
        self.center_x += (-rx * dx + fx * dy) * scale
        self.center_z += (-rz * dx + fz * dy) * scale
        if self.limits is not None:
            x0, x1, z0, z1 = self.limits
            self.center_x = max(x0, min(x1, self.center_x))
            self.center_z = max(z0, min(z1, self.center_z))