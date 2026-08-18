import tkinter as tk

num = 0

def jishuqi():
    global num          # 关键！声明用外面的全局 num
    num += 1
    label.config(text=str(num))

root = tk.Tk()                      # T 大写
root.title("计数器")
label = tk.Label(root, text="0", font=("Arial", 30))   # L 大写
label.pack(padx=30, pady=20)
btn = tk.Button(root, text="点一下", command=jishuqi)
btn.pack(pady=10)
root.mainloop()
#Continue  opencode -s ses_ff245c8eeffel9eg0gqNDs9Ga1