import random                      # 随机数模块，用于布雷时随机选取地雷位置
import re                          # 正则表达式，用于解析 AI 返回的坐标
import threading                   # 线程模块，让 AI 请求不卡住界面
import tkinter as tk              # tkinter 图形界面库，负责创建窗口和控件
from tkinter import messagebox    # 消息弹窗模块，用于提示游戏胜利/失败

from llm_api.call_zhipu import chat  # 智谱 GLM API 调用函数


class Minesweeper:
    """扫雷游戏主类，封装了整个游戏的状态和交互逻辑。

    属性说明：
        rows / cols：棋盘行数、列数
        mines：地雷总数
        board：二维棋盘，值为 -1 表示地雷，0~8 表示周围地雷数量
        revealed：二维布尔表，标记哪些格子已被翻开
        flagged：二维布尔表，标记哪些格子被玩家插了旗
        remaining：剩余需要翻开的"安全格"数量（翻开一个减一，归零即胜利）
    """

    def __init__(self, master, rows=9, cols=9, mines=10):
        """初始化游戏：保存参数、初始化状态并构建界面。"""
        self.master = master        # 主窗口对象
        self.rows = rows            # 棋盘行数
        self.cols = cols            # 棋盘列数
        self.mines = mines          # 地雷数量
        self.cell_size = 30         # 单元格尺寸（备用）
        self.first_click = True     # 是否第一次点击（第一次点击后才能布雷，保证首格安全）
        self.buttons = {}           # 字典，键为 (r, c) 坐标，值为对应的按钮控件
        self.board = [[0] * cols for _ in range(rows)]        # 棋盘数据（初始全为 0）
        self.revealed = [[False] * cols for _ in range(rows)] # 翻开状态，初始全部未翻开
        self.flagged = [[False] * cols for _ in range(rows)]  # 插旗状态，初始全部无旗
        self.remaining = rows * cols - mines                  # 需翻开的非地雷格总数
        self.master.title("扫雷")     # 设置窗口标题

        # 创建主框架（容纳控制栏、游戏板）
        self.main_frame = tk.Frame(self.master)
        self.main_frame.pack(fill="both", expand=True)

        # 创建顶部控制栏（难度按钮、重置按钮、计时器、地雷计数）
        self.create_control_bar()

        # 创建游戏板（生成 rows*cols 个格子按钮）
        self.create_game_board()

        # 创建底部状态栏（当前难度、操作提示）
        self.create_status_bar()

    def create_control_bar(self):
        """创建顶部的控制栏：难度选择、重置按钮、计时器、地雷剩余数显示。"""
        # 整个控制栏的外框容器
        control_frame = tk.Frame(self.main_frame, relief="raised", borderwidth=1, bg="light gray")
        control_frame.pack(fill="x", padx=5, pady=5)

        # 左侧：难度选择区域
        difficulty_frame = tk.Frame(control_frame, bg="light gray")
        difficulty_frame.pack(side="left", padx=10, pady=5)

        tk.Label(difficulty_frame, text="难度:", font=("Arial", 10, "bold"), bg="light gray").pack(side="left", padx=5)

        self.difficulty_var = tk.StringVar(value="初级")  # 当前难度名称（默认初级）
        difficulties = [                                   # 预设三种难度：名称 / 行 / 列 / 地雷数
            ("初级", 9, 9, 10),
            ("中级", 16, 16, 40),
            ("高级", 30, 16, 99)
        ]

        for name, rows, cols, mines in difficulties:
            # 每种难度按钮使用不同颜色区分
            bg_color = "#4CAF50" if name == "初级" else ("#FF9800" if name == "中级" else "#F44336")

            btn = tk.Button(
                difficulty_frame,
                text=name,
                width=8,
                font=("Arial", 10, "bold"),
                bg=bg_color,
                fg="white",
                # lambda 默认参数绑定，避免循环结束后变量被覆盖
                command=lambda r=rows, c=cols, m=mines, n=name: self.change_difficulty(r, c, m, n)
            )
            btn.pack(side="left", padx=2)

        # 中间区域：重置按钮和计时器，expand=True 让其水平居中
        middle_frame = tk.Frame(control_frame, bg="light gray")
        middle_frame.pack(side="left", expand=True)

        # 重置按钮（用表情符号表示状态）
        self.reset_btn = tk.Button(
            middle_frame,
            text="😊",
            width=3,
            height=1,
            font=("Arial", 16),
            command=self.reset,
            relief="raised",
            borderwidth=2
        )
        self.reset_btn.pack(side="left", padx=20)

        # AI 提示按钮：点击后让大模型分析棋盘并建议下一步
        self.ai_btn = tk.Button(
            middle_frame,
            text="🤖 AI 提示",
            font=("Arial", 10, "bold"),
            command=self.ai_hint,
            relief="raised",
            borderwidth=2
        )
        self.ai_btn.pack(side="left", padx=20)

        # 计时器标签，显示已经过去多少秒
        self.timer_label = tk.Label(middle_frame, text="000", font=("Arial", 14, "bold"), bg="light gray")
        self.timer_label.pack(side="left", padx=10)

        # 计时器相关状态：开始时间和是否正在计时
        self.start_time = None
        self.timer_running = False

        # 右侧：显示剩余地雷数量
        right_frame = tk.Frame(control_frame, bg="light gray")
        right_frame.pack(side="right", padx=10, pady=5)

        tk.Label(right_frame, text="地雷:", font=("Arial", 10, "bold"), bg="light gray").pack(side="left", padx=5)
        self.mines_display = tk.Label(right_frame, text=str(self.mines), font=("Arial", 14, "bold"), bg="light gray", fg="red")
        self.mines_display.pack(side="left")

    def start_timer(self):
        """启动计时器（仅在游戏开始后的第一次点击时启动）。"""
        if not self.timer_running:
            self.timer_running = True
            self.start_time = 0
            self.update_timer()

    def update_timer(self):
        """每秒刷新一次计时显示，通过 after 实现周期性调用。"""
        if self.timer_running:
            self.start_time += 1                    # 秒数 +1
            self.timer_label.config(text=f"{self.start_time:03d}")  # 三位数显示（如 001）
            self.master.after(1000, self.update_timer)  # 1 秒后再调用自己，形成循环

    def stop_timer(self):
        """停止计时器。"""
        self.timer_running = False

    def change_difficulty(self, rows, cols, mines, difficulty_name):
        """切换游戏难度：重置数据、停止计时、重建棋盘并更新标题。"""
        # 更新游戏参数
        self.rows = rows
        self.cols = cols
        self.mines = mines
        self.first_click = True
        self.board = [[0] * cols for _ in range(rows)]
        self.revealed = [[False] * cols for _ in range(rows)]
        self.flagged = [[False] * cols for _ in range(rows)]
        self.remaining = rows * cols - mines

        # 停止当前计时器并把显示归零
        self.stop_timer()
        self.timer_label.config(text="000")

        # 更新窗口标题和难度显示
        self.master.title(f"扫雷 - {difficulty_name}")
        self.difficulty_var.set(difficulty_name)

        # 重置按钮恢复默认表情
        self.reset_btn.config(text="😊")

        # 清除旧的游戏板（销毁旧棋盘中的所有按钮）
        if hasattr(self, 'game_frame'):
            self.game_frame.destroy()

        # 按新参数重新生成游戏板
        self.create_game_board()

    def create_status_bar(self):
        """创建底部状态栏：显示当前难度和操作提示。"""
        self.status_frame = tk.Frame(self.master, relief="sunken", borderwidth=1)
        self.status_frame.pack(side="bottom", fill="x")

        # 左侧显示当前难度名称
        difficulty_name = self.difficulty_var.get()
        self.difficulty_label = tk.Label(self.status_frame, text=f"当前难度: {difficulty_name}", font=("Arial", 10))
        self.difficulty_label.pack(side="left", padx=10)

        # 右侧显示操作提示信息
        self.info_label = tk.Label(self.status_frame, text="左键点击，右键标记", font=("Arial", 9))
        self.info_label.pack(side="right", padx=10)

    def update_control_display(self):
        """把控制栏中的地雷数显示刷新为当前地雷总数。"""
        self.mines_display.config(text=str(self.mines))

    def create_game_board(self):
        """生成棋盘：为每个格子创建一个按钮并绑定左键/右键事件。"""
        self.game_frame = tk.Frame(self.main_frame)
        self.game_frame.pack(expand=True, fill="both", padx=10, pady=10)

        # 根据棋盘大小调整单元格尺寸，保证不同难度都能放下
        if self.rows <= 9 and self.cols <= 9:
            cell_size = 35
        elif self.rows <= 16 and self.cols <= 16:
            cell_size = 25
        else:
            cell_size = 20

        for r in range(self.rows):
            for c in range(self.cols):
                btn = tk.Button(
                    self.game_frame,
                    width=2,
                    height=1,
                    font=("Consolas", 10, "bold"),
                    command=lambda r=r, c=c: self.click(r, c),  # 左键点击翻开
                )
                btn.grid(row=r, column=c, padx=0, pady=0)
                btn.bind("<Button-3>", lambda e, r=r, c=c: self.right_click(r, c))  # 右键插旗/拔旗
                self.buttons[(r, c)] = btn  # 保存坐标到按钮的映射

    def restart(self, rows=None, cols=None, mines=None, difficulty_name="当前难度"):
        """按指定参数重新开始一局游戏（默认沿用当前参数）。"""
        # 若未指定参数，则沿用当前游戏的参数
        rows = rows if rows is not None else self.rows
        cols = cols if cols is not None else self.cols
        mines = mines if mines is not None else self.mines

        # 重置所有游戏状态
        self.rows = rows
        self.cols = cols
        self.mines = mines
        self.first_click = True
        self.board = [[0] * cols for _ in range(rows)]
        self.revealed = [[False] * cols for _ in range(rows)]
        self.flagged = [[False] * cols for _ in range(rows)]
        self.remaining = rows * cols - mines

        # 若提供了新难度名称，则更新窗口标题
        if difficulty_name != "当前难度":
            self.master.title(f"扫雷 - {difficulty_name}")
            self.difficulty_var.set(difficulty_name)

        # 清除旧棋盘并重建
        if hasattr(self, 'game_frame'):
            self.game_frame.destroy()
        self.create_game_board()

        # 刷新控制栏中的地雷数显示
        self.update_control_display()

    def reset(self):
        """重置按钮的回调：停止计时、清零计时、恢复表情、然后重新开局。"""
        # 停止计时器
        self.stop_timer()
        # 重置计时器显示
        self.timer_label.config(text="000")
        self.reset_btn.config(text="😊")
        # 更新地雷数显示
        self.update_control_display()
        # 重新开始
        self.restart()

    def place_mines(self, safe_r, safe_c):
        """随机布雷，并计算每个非地雷格周围的地雷数量。

        参数：
            safe_r / safe_c：第一次点击的坐标，保证该格及其附近不会布雷。
        """
        # 生成所有格子坐标的列表
        positions = [(r, c) for r in range(self.rows) for c in range(self.cols)]
        positions.remove((safe_r, safe_c))  # 确保首格不是地雷

        # 随机挑选 self.mines 个位置放地雷（值为 -1）
        for _ in range(self.mines):
            r, c = positions.pop(random.randrange(len(positions)))
            self.board[r][c] = -1

        # 遍历每个非地雷格，统计其 8 邻域内的地雷数量
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == -1:
                    continue  # 地雷格跳过
                self.board[r][c] = sum(
                    1
                    for dr in (-1, 0, 1)   # 行方向偏移
                    for dc in (-1, 0, 1)   # 列方向偏移
                    if (dr or dc)          # 排除自身 (0,0)
                    and 0 <= r + dr < self.rows   # 行不越界
                    and 0 <= c + dc < self.cols   # 列不越界
                    and self.board[r + dr][c + dc] == -1  # 邻居是地雷
                )

    def click(self, r, c):
        """左键点击格子：首次点击先布雷，踩雷则结束，否则翻开并判断胜负。"""
        if self.revealed[r][c] or self.flagged[r][c]:
            return  # 已翻开或已插旗的格子不响应

        if self.first_click:
            # 第一次点击：布雷（避开当前格）并启动计时器
            self.first_click = False
            self.place_mines(r, c)
            self.start_timer()

        if self.board[r][c] == -1:
            # 踩到地雷：停止计时并游戏失败
            self.stop_timer()
            self.game_over()
            return

        self.flood_fill(r, c)  # 展开空白区域
        if self.remaining == 0:
            # 所有安全格都已翻开，胜利
            self.stop_timer()
            self.win()

    def right_click(self, r, c):
        """右键点击格子：在插旗和拔旗之间切换。"""
        if self.revealed[r][c]:
            return  # 已翻开的格子不能再插旗

        if self.flagged[r][c]:
            # 已插旗：拔旗并恢复数字
            self.flagged[r][c] = False
            self.buttons[(r, c)].config(text="", bg="SystemButtonFace")
            self.mines_increment()
        else:
            # 未插旗：插旗并减少显示的地雷数
            self.flagged[r][c] = True
            self.buttons[(r, c)].config(text="🚩", fg="red", bg="SystemButtonFace")
            self.mines_decrement()

    def mines_increment(self):
        """取消标记时调用：显示的地雷剩余数 +1，并按数值改变颜色。"""
        # 增加显示的地雷数（取消标记时）
        current_text = self.mines_display.cget("text")
        if current_text.isdigit():  # 只处理纯数字显示
            new_count = int(current_text) + 1
            self.mines_display.config(text=str(new_count))
            # 根据数量改变颜色
            if new_count == 0:
                self.mines_display.config(fg="green")
            elif new_count < 0:
                self.mines_display.config(fg="red")
            else:
                self.mines_display.config(fg="black")

    def mines_decrement(self):
        """标记地雷时调用：显示的地雷剩余数 -1，并按数值改变颜色。"""
        # 减少显示的地雷数（标记时）
        current_text = self.mines_display.cget("text")
        if current_text.isdigit():
            new_count = int(current_text) - 1
            self.mines_display.config(text=str(new_count))
            # 根据数量改变颜色
            if new_count == 0:
                self.mines_display.config(fg="green")
            elif new_count < 0:
                self.mines_display.config(fg="red")
            else:
                self.mines_display.config(fg="black")

    def flood_fill(self, r, c):
        """翻开点击的格子；若该格数字为 0，则递归展开周围所有空白区域。

        使用栈实现广度优先式的展开（经典扫雷逻辑）：
        当前格为 0 时，把 8 邻域未翻开的格子压入栈继续处理。
        """
        stack = [(r, c)]  # 待处理格子栈
        while stack:
            r, c = stack.pop()
            if self.revealed[r][c] or self.flagged[r][c]:
                continue  # 已翻开或已插旗的格子跳过
            self.revealed[r][c] = True   # 标记为已翻开
            self.remaining -= 1          # 剩余安全格数量减一
            self.show_number(r, c)       # 显示数字或留白
            if self.board[r][c] == 0:
                # 空白格：把 8 邻域加入栈继续展开
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols:
                            stack.append((nr, nc))

    def show_number(self, r, c):
        """在格子上显示对应的数字，并把按钮置为不可点击（已翻开样式）。"""
        btn = self.buttons[(r, c)]
        val = self.board[r][c]
        if val == 0:
            # 数字为 0 时留白显示
            btn.config(text="", relief="sunken", bg="light gray", state="disabled")
        else:
            # 不同数字使用不同颜色（经典扫雷配色）
            colors = ["", "blue", "green", "red", "dark blue", "brown", "cyan", "black", "gray"]
            btn.config(
                text=str(val),
                fg=colors[val],
                relief="sunken",
                bg="light gray",
                state="disabled",
            )

    def ai_hint(self):
        """AI 提示按钮的回调：把棋盘发给大模型，让它在后台思考建议的格子。"""
        # 用一个标志防止上一次请求还没回来时又点一次
        if getattr(self, "ai_busy", False):
            return
        self.ai_busy = True
        self.ai_btn.config(text="🤖 思考中...", state="disabled")

        # 网络请求会卡住界面，所以放到后台线程去跑
        t = threading.Thread(target=self._ai_worker, daemon=True)
        t.start()

    def _find_safe_cell(self):
        """确定性推理：找必定安全的格子（不靠猜）。

        规则（经典扫雷推理）：
        对一个已翻开的数字格 n，统计它 8 邻域里：
        - 已插旗数 f，未翻开的未知格列表 unknown
        - 若 n - f == 0：周围雷已全被旗标记，剩下的 unknown 全是安全格
        - 若 len(unknown) == n - f：unknown 全是雷（可插旗，但不返回）

        返回第一个安全格坐标 (r, c)；找不到（需要猜测）返回 None。
        """
        for r in range(self.rows):
            for c in range(self.cols):
                if not self.revealed[r][c] or self.board[r][c] <= 0:
                    continue  # 只看已翻开的数字格
                n = self.board[r][c]
                # 8 邻域坐标
                neighbors = [
                    (r + dr, c + dc)
                    for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                    if (dr or dc)
                    and 0 <= r + dr < self.rows
                    and 0 <= c + dc < self.cols
                ]
                unknown = [p for p in neighbors
                           if not self.revealed[p[0]][p[1]] and not self.flagged[p[0]][p[1]]]
                flags = sum(1 for p in neighbors if self.flagged[p[0]][p[1]])
                remaining = n - flags           # 这个数字周围还需要几颗雷
                if remaining == 0 and unknown:
                    return unknown[0]           # 周围雷已排完，未知格全安全
                # len(unknown) == remaining：未知格全是雷，不返回（自动插旗）
        return None

    def _ai_worker(self):
        """后台线程里执行的逻辑：确定性算法找安全格，找不到才请求模型。"""
        try:
            # 第一步：用确定性推理找必安全格（不踩雷）
            safe = self._find_safe_cell()
            if safe:
                r, c = safe
            else:
                # 第二步：没有必安全格，只能靠猜，这时才轮到 LLM
                r, c = self._ask_llm_for_hint()
        except Exception as e:
            # 出错时回到主线程弹窗（tkinter 不能在子线程直接操作界面）
            self.master.after(0, lambda err=e: self._ai_error(err))
            return
        # 成功后回到主线程执行点击
        self.master.after(0, lambda rr=r, cc=c: self._ai_apply(rr, cc))

    def _ask_llm_for_hint(self):
        """没有必安全格时，请求 LLM 建议一个格子（最多重试 3 次）。"""
        for attempt in range(3):
            board_text = self._board_to_text()
            prompt = (
                "你是一个扫雷高手。下面是一个扫雷棋盘，用一行行文本表示：\n"
                "- 数字表示该格子周围的地雷数量（已翻开）\n"
                "- 0 表示已翻开的空格\n"
                "- ? 表示未翻开的格子\n"
                "- 旗 表示玩家标记为地雷的格子\n"
                "棋盘如下（r 代表行，从 0 开始）：\n"
                f"{board_text}\n\n"
                "现在没有确定的必安全格，只能靠猜测。请选一个你认为踩雷概率最低的格子。"
                "只能选择 ? 标记的未翻开格子，不要选择已翻开或插旗的格子。"
                "只回答一个坐标，格式严格为 (行,列)，例如 (3,5)。不要输出其他任何内容。"
            )
            answer = chat(prompt)
            # 用正则从回答里提取坐标，比如 "我认为 (3,5) 是安全的"
            m = re.search(r"\((\d+)\s*,\s*(\d+)\)", answer)
            if not m:
                raise ValueError(f"AI 没有给出有效坐标，回答是：{answer[:60]}...")
            r, c = int(m.group(1)), int(m.group(2))
            # 坐标必须落在棋盘范围内，且必须是未翻开的格子，否则重试
            if (0 <= r < self.rows and 0 <= c < self.cols
                    and not self.revealed[r][c] and not self.flagged[r][c]):
                return r, c
        # 重试 3 次仍未得到有效格子，抛错让上层提示
        raise ValueError("AI 多次给出无效格子")

    def _board_to_text(self):
        """把当前棋盘编码成适合发给大模型的文本。"""
        lines = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                if self.revealed[r][c]:
                    row.append(str(self.board[r][c]))   # 已翻开：显示数字（0 也显示）
                elif self.flagged[r][c]:
                    row.append("旗")                    # 插旗
                else:
                    row.append("?")                     # 未翻开
            lines.append(" ".join(row))
        return "\n".join(lines)

    def _ai_apply(self, r, c):
        """主线程中执行 AI 建议的点击。"""
        self.ai_busy = False
        self.ai_btn.config(text="🤖 AI 提示", state="normal")
        # 若格子已被翻开或插旗，说明 AI 建议无效，直接忽略
        if self.revealed[r][c] or self.flagged[r][c]:
            self.info_label.config(text="AI 建议的格子已不可点击，请重试")
            return
        self.info_label.config(text=f"AI 建议点击 ({r},{c})")
        self.click(r, c)

    def _ai_error(self, err):
        """AI 请求出错时恢复按钮状态并提示。"""
        self.ai_busy = False
        self.ai_btn.config(text="🤖 AI 提示", state="normal")
        messagebox.showinfo("AI 提示", f"AI 思考失败：{err}")

    def game_over(self):
        """踩雷后执行：显示所有地雷与错误旗子，弹窗提示并重置游戏。"""
        # 显示所有地雷
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == -1:
                    # 地雷显示为炸弹图标
                    self.buttons[(r, c)].config(text="💣", fg="black", relief="sunken", bg="light gray")
                elif self.flagged[r][c] and self.board[r][c] != -1:
                    # 插旗位置没有地雷，标为错误 ❌
                    self.buttons[(r, c)].config(text="❌", fg="red", relief="sunken", bg="light gray")

        # 更新重置按钮表情为"失败"表情
        self.reset_btn.config(text="😵")

        messagebox.showinfo("扫雷", "踩到地雷了，游戏结束！")

        # 弹窗关闭后自动重置游戏
        self.reset()

    def win(self):
        """全部安全格翻开后执行：给所有地雷插旗、弹窗提示并重置游戏。"""
        # 标记所有地雷（自动插上红旗）
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == -1:
                    self.buttons[(r, c)].config(text="🚩", fg="red")

        # 更新重置按钮表情为"胜利"表情
        self.reset_btn.config(text="😎")

        messagebox.showinfo("扫雷", "恭喜你赢了！")

        # 弹窗关闭后自动重置游戏
        self.reset()


if __name__ == "__main__":
    # 程序入口：创建主窗口、初始化游戏并进入事件循环
    root = tk.Tk()
    app = Minesweeper(root)
    root.mainloop()
