"""
Cấu hình thẻ neofetch trên profile — sửa file này là đủ, không cần đụng vào today.py.

Dòng nào để chuỗi rỗng "" thì sẽ tự ẩn khỏi ảnh.
Nội dung bám theo README hiện tại (không nêu nơi làm việc, xem docs/profile-design.md).
"""
import datetime

GITHUB_USERNAME = "minhlu-i"

# Mốc tính "Uptime". None = tính từ ngày tạo tài khoản GitHub.
# Muốn dùng ngày sinh thì ghi: datetime.datetime(1999, 1, 31)
UPTIME_SINCE = None

# Hình bên trái:
#   "image"     = ảnh minh hoạ ASCII màu trong scripts/art.json (2 người nhún nhảy + bong bóng)
#   "character" = nhân vật ASCII tự vẽ, gật gù + bong bóng thoại
#   "avatar"    = chuyển AVATAR_FILE thành ASCII (tĩnh)
#   "terminal"  = hình terminal minh@workstation (tĩnh)
ART = "image"
BUBBLE_TEXT = "I have done nothing productive all day."

# Ảnh chân dung để chuyển thành ASCII (đường dẫn tính từ gốc repo).
# Không có file thì dùng hình terminal "minh@workstation" có sẵn.
AVATAR_FILE = "assets/avatar.jpg"
ASCII_WIDTH = 38
ASCII_HEIGHT = 25
ASCII_INVERT = False   # True nếu ảnh nền sáng, chủ thể tối

HEADER = "minh@workstation"

SECTIONS = [
    [
        ("OS", "macOS, Ubuntu / WSL2"),
        ("Uptime", "{uptime}"),          # tự tính, đừng sửa
        ("Host", "Da Nang, Vietnam"),
        ("Kernel", "Backend Developer"),
        ("Shell", "Zsh / Bash + Starship, zoxide"),
    ],
    [
        ("Languages.Programming", "TypeScript, Python"),
        ("Languages.Computer", "SQL, Shell, YAML, JSON"),
        ("Languages.Real", "Vietnamese, English"),
    ],
    [
        ("Stack.Backend", "NestJS, PostgreSQL, Docker"),
        ("Tools.AI", "Codex, Claude Code"),
        ("Exploring", "System design, gamification"),
    ],
]

CONTACT = [
    ("LinkedIn", "minhlu"),
    ("Facebook", "minhlu99"),
    ("Email", ""),        # để trống = không hiện email công khai
]

LINE_WIDTH = 60
